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
from .fetcher import get_latest_files
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

def update_latest_json(region_name, result):
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
            
    data["true_color"][region_name] = result["true_color"]
    data["ir"][region_name] = result["ir"]
    data["timestamp"] = result["timestamp"]
    
    all_done = all(
        data["true_color"].get(r) is not None and data["ir"].get(r) is not None
        for r in ["global", "asia", "taiwan"]
    )
    if all_done:
        data["status"] = "completed"
    
    with open(LATEST_DATA_FILE, 'w') as f:
        json.dump(data, f)

CURRENT_CYCLE_FILE = os.path.join(os.path.dirname(__file__), 'current_cycle.json')

def job_fetch_and_process_taiwan():
    print("Starting scheduled job: Taiwan View")
    downloaded_files = get_latest_files()
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Processing Taiwan View...")
        with open(CURRENT_CYCLE_FILE, 'w') as f:
            json.dump({"files": downloaded_files}, f)
        result = process_taiwan_view(downloaded_files)
        if result:
            update_latest_json("taiwan", result)
            print("Taiwan View Job completed successfully.")
        else:
            print("Taiwan View Job failed during processing.")
    else:
        print("No new files downloaded.")

def job_fetch_and_process_asia():
    print("Starting scheduled job: Asia View")
    if os.path.exists(CURRENT_CYCLE_FILE):
        with open(CURRENT_CYCLE_FILE, 'r') as f:
            downloaded_files = json.load(f).get("files", [])
        if downloaded_files:
            print(f"Using {len(downloaded_files)} files from current cycle. Processing Asia View...")
            result = process_asia_view(downloaded_files)
            if result:
                update_latest_json("asia", result)
                print("Asia View Job completed successfully.")
            else:
                print("Asia View Job failed during processing.")
            return
    print("No active cycle files found for Asia View.")

def job_fetch_and_process_global():
    print("Starting scheduled job: Global View")
    if os.path.exists(CURRENT_CYCLE_FILE):
        with open(CURRENT_CYCLE_FILE, 'r') as f:
            downloaded_files = json.load(f).get("files", [])
        if downloaded_files:
            print(f"Using {len(downloaded_files)} files from current cycle. Processing Global View...")
            result = process_global_view(downloaded_files)
            if result:
                update_latest_json("global", result)
                print("Global View Job completed successfully.")
            else:
                print("Global View Job failed during processing.")
            return
    print("No active cycle files found for Global View.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce': True,
            'max_instances': 1
        }
    )
    # Job 1 (Taiwan): Runs every 20 minutes, starting at minute 0 (e.g., at minute 0, 20, 40)
    scheduler.add_job(job_fetch_and_process_taiwan, 'cron', minute='0,20,40')
    # Job 2 (Asia): Runs every 20 minutes, staggered by 5 minutes (e.g., at minute 5, 25, 45)
    scheduler.add_job(job_fetch_and_process_asia, 'cron', minute='5,25,45')
    # Job 3 (Global): Runs every 20 minutes, staggered by 10 minutes (e.g., at minute 10, 30, 50)
    scheduler.add_job(job_fetch_and_process_global, 'cron', minute='10,30,50')
    
    scheduler.start()
    
    # Run once at startup asynchronously to avoid blocking the port binding
    scheduler.add_job(job_fetch_and_process_taiwan, 'date', run_date=datetime.now())
    
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
