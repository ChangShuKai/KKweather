import os
import sys
import psutil
from collections import deque
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import json
from datetime import datetime
from contextlib import asynccontextmanager
from .processor import process_taiwan_view, process_asia_view, process_global_view

LATEST_DATA_FILE = os.path.join(os.path.dirname(__file__), 'latest.json')

log_buffer = deque(maxlen=100)

class LogInterceptor:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        if isinstance(data, str) and data.strip():
            lines = data.strip().split('\n')
            for line in lines:
                if line:
                    log_buffer.append(line)

    def flush(self):
        self.stream.flush()

sys.stdout = LogInterceptor(sys.stdout)
sys.stderr = LogInterceptor(sys.stderr)

def update_latest_json(region_name, mode, result):
    if not result:
        return
        
    data = {
        "status": "partial",
        "true_color": {"global": None, "asia": None, "taiwan": None},
        "ir": {"global": None, "asia": None, "taiwan": None},
        "timestamp": result["timestamp"]
    }
    
    if os.path.exists(LATEST_DATA_FILE):
        try:
            with open(LATEST_DATA_FILE, 'r') as f:
                old_data = json.load(f)
                if old_data.get("timestamp") == result["timestamp"]:
                    data["true_color"] = old_data.get("true_color", data["true_color"])
                    data["ir"] = old_data.get("ir", data["ir"])
        except Exception:
            pass
            
    data[mode][region_name] = result["path"]
    data["timestamp"] = result["timestamp"]
    
    all_done = all(
        data["true_color"].get(r) is not None and data["ir"].get(r) is not None
        for r in ["global", "asia", "taiwan"]
    )
    if all_done:
        data["status"] = "completed"
    
    with open(LATEST_DATA_FILE, 'w') as f:
        json.dump(data, f)



def job_fetch_and_process_all():
    print("[Progress] 0% - Starting satellite data pipeline")
    try:
        from backend.fetcher import find_latest_prefix, fetch_segments, DOWNLOAD_DIR
        import glob
        
        print("[Progress] 2% - Cleaning up old data files...")
        old_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.DAT*"))
        for f in old_files:
            try: os.remove(f)
            except: pass
            
        print("[Progress] 5% - Checking for latest files on AWS S3...")
        prefix = find_latest_prefix()
        
        if not prefix:
            print("[Progress] 100% - No new files to process.")
            return

        print(f"[Progress] 10% - Latest data found: {prefix}")
        from backend.processor import process_taiwan_view, process_asia_view, process_global_view
        
        # ---------------------------------------------------------
        # PIECE 1: TAIWAN (Segment 4)
        # ---------------------------------------------------------
        print("[Progress] 15% - Downloading Segment 3 for Taiwan...")
        tw_files = fetch_segments(prefix, ['_S0310.'])
        
        print(f"[Progress] 20% - Processing Taiwan True Color ({len(tw_files)} files)...")
        tw_tc = process_taiwan_view(tw_files, "true_color")
        update_latest_json("taiwan", "true_color", tw_tc)
        
        print("[Progress] 35% - Processing Taiwan Infrared...")
        tw_ir = process_taiwan_view(tw_files, "ir")
        update_latest_json("taiwan", "ir", tw_ir)
        
        # ---------------------------------------------------------
        # PIECE 2: ASIA (Segments 3, 4, 5)
        # ---------------------------------------------------------
        print("[Progress] 45% - Downloading Segments 1, 2, 4 for Asia...")
        # S03 is already downloaded, it will just be verified
        asia_files = fetch_segments(prefix, ['_S0110.', '_S0210.', '_S0310.', '_S0410.'])
        
        print(f"[Progress] 50% - Processing Asia True Color ({len(asia_files)} files)...")
        asia_tc = process_asia_view(asia_files, "true_color")
        update_latest_json("asia", "true_color", asia_tc)
        
        print("[Progress] 65% - Processing Asia Infrared...")
        asia_ir = process_asia_view(asia_files, "ir")
        update_latest_json("asia", "ir", asia_ir)
        
        # ---------------------------------------------------------
        # PIECE 3: GLOBAL (All Segments)
        # ---------------------------------------------------------
        print("[Progress] 75% - Downloading remaining segments for Global...")
        global_files = fetch_segments(prefix, None)
        
        print(f"[Progress] 80% - Processing Global True Color ({len(global_files)} files)...")
        global_tc = process_global_view(global_files, "true_color")
        update_latest_json("global", "true_color", global_tc)
        
        print("[Progress] 90% - Processing Global Infrared...")
        global_ir = process_global_view(global_files, "ir")
        update_latest_json("global", "ir", global_ir)
        
        print("[Progress] 100% - All views completed successfully!")
    except Exception as e:
        print(f"[Progress] 100% - Job failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce': True,
            'max_instances': 1
        }
    )
    # Run the combined pipeline every 20 minutes
    scheduler.add_job(job_fetch_and_process_all, 'cron', minute='0,20,40')
    
    scheduler.start()
    
    # Run once at startup asynchronously to avoid blocking the port binding
    scheduler.add_job(job_fetch_and_process_all, 'date', run_date=datetime.now())
    
    yield
    # Shutdown
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# Allow CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (images and frontend)
static_dir = os.path.join(os.path.dirname(__file__), 'static')
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')

@app.get("/api/latest")
def get_latest():
    images_dir = os.path.join(static_dir, "images")
    if not os.path.exists(images_dir) or not os.path.exists(LATEST_DATA_FILE):
        return {"status": "processing", "message": log_buffer[-1] if log_buffer else "Initial satellite rendering in progress..."}
        
    try:
        with open(LATEST_DATA_FILE, 'r') as f:
            data = json.load(f)
            latest_ts = data.get("timestamp")
    except Exception:
        return {"status": "processing", "message": log_buffer[-1] if log_buffer else "Initial satellite rendering in progress..."}

    if not latest_ts:
        return {"status": "processing", "message": log_buffer[-1] if log_buffer else "Initial satellite rendering in progress..."}

    response = {
        "status": "partial",
        "true_color": {},
        "ir": {},
        "timestamp": latest_ts
    }
    
    all_done = True
    for view in ["true_color", "ir"]:
        for region in ["global", "asia", "taiwan"]:
            filename = f"himawari_{view}_{region}_{latest_ts}.webp"
            filepath = os.path.join(images_dir, filename)
            if os.path.exists(filepath):
                response[view][region] = f"/static/images/{filename}"
            else:
                response[view][region] = None
                all_done = False
                
    if all_done:
        response["status"] = "completed"
        
    return response

@app.get("/api/logs")
def get_logs():
    return {"logs": list(log_buffer)}

def get_container_memory_usage():
    try:
        # Cgroups v2
        if os.path.exists('/sys/fs/cgroup/memory.current'):
            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                return int(f.read().strip())
        # Cgroups v1
        elif os.path.exists('/sys/fs/cgroup/memory/memory.usage_in_bytes'):
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                return int(f.read().strip())
    except Exception:
        pass
    # Fallback: process memory (can under-report if there are subprocesses)
    return psutil.Process().memory_info().rss

@app.get("/api/status")
def remote_android_metrics():
    # Use interval=0.1 to get accurate instantaneous CPU usage (runs in threadpool since this is a sync def)
    cpu_usage = psutil.cpu_percent(interval=0.1)
    
    used_bytes = get_container_memory_usage()
    used_mb = round(used_bytes / (1024 * 1024), 2)
    
    # Render container has a hard ceiling of 512MB RAM
    total_mb = 512.0
    free_mb = round(total_mb - used_mb, 2)
    usage_percent = round((used_mb / total_mb) * 100, 2)
    
    return {
        "server_name": "KKweather-Render-Cluster",
        "status": "online",
        "cpu": {
            "usage_percent": cpu_usage,
            "logical_cores": psutil.cpu_count() or 1
        },
        "memory": {
            "total_mb": total_mb,
            "used_mb": used_mb,
            "free_mb": free_mb,
            "usage_percent": min(usage_percent, 100.0)
        },
        "runtime": {
            "pid": os.getpid(),
            "active_threads": psutil.Process().num_threads()
        }
    }

os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
