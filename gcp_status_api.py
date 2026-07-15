from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import psutil
import os
import threading
import json
import time

app = FastAPI()

# Global metrics cache
system_metrics = {
    "cpu_percent": 0.0,
    "mem_percent": 0.0,
    "mem_used": 0.0,
    "mem_total": 0.0,
    "mem_free": 0.0,
    "net_recv_kbps": 0.0,
    "net_sent_kbps": 0.0,
}

def update_metrics_loop():
    # Initialize psutil CPU polling
    psutil.cpu_percent(interval=None)
    last_net = psutil.net_io_counters()
    
    while True:
        try:
            # interval=1 blocks for 1 second, perfect for background thread
            cpu = psutil.cpu_percent(interval=1.0)
            mem = psutil.virtual_memory()
            
            # Network speed calculation
            current_net = psutil.net_io_counters()
            bytes_recv = current_net.bytes_recv - last_net.bytes_recv
            bytes_sent = current_net.bytes_sent - last_net.bytes_sent
            last_net = current_net
            
            system_metrics["cpu_percent"] = cpu
            system_metrics["mem_percent"] = mem.percent
            system_metrics["mem_used"] = mem.used / (1024 * 1024)
            system_metrics["mem_total"] = mem.total / (1024 * 1024)
            system_metrics["mem_free"] = mem.available / (1024 * 1024)
            system_metrics["net_recv_kbps"] = (bytes_recv / 1024) # KB/s
            system_metrics["net_sent_kbps"] = (bytes_sent / 1024) # KB/s
        except Exception:
            pass

# Start background polling thread
metrics_thread = threading.Thread(target=update_metrics_loop, daemon=True)
metrics_thread.start()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LATEST_JSON = os.path.join(BASE_DIR, "backend", "latest.json")
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Serve backend static files (images)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/api/latest")
def get_latest():
    if os.path.exists(LATEST_JSON):
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Rewrite paths to point to this server
            for mode in ["true_color", "ir"]:
                if mode in data:
                    for region in ["global", "asia", "taiwan"]:
                        path = data[mode].get(region)
                        if path and path.startswith("/static/"):
                            # Use relative path since it's same origin now
                            data[mode][region] = path
            return data
    return {"status": "processing", "message": "等待首次排程產圖中..."}

@app.get("/api/history")
def get_history():
    history_list = []
    if os.path.exists(STATIC_DIR):
        folders = [f for f in os.listdir(STATIC_DIR) if os.path.isdir(os.path.join(STATIC_DIR, f)) and len(f) == 13 and '_' in f]
        history_list = sorted(folders, reverse=True)
    return {"history": history_list}

@app.get("/api/logs")
@app.get("/logs")
def get_logs():
    log_file = "/home/kai1010210/satellite.log"
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-50:] if line.strip()]
        except Exception as e:
            logs = [f"Error reading logs: {str(e)}"]
    else:
        logs = ["等待排程初次執行中... (日誌檔案尚未建立)"]
        
    return {"logs": logs}

@app.get("/status")
@app.get("/api/status")
def get_status():
    return {
        "server_name": "gcp-kkweather",
        "cpu": {
            "usage_percent": system_metrics["cpu_percent"],
            "logical_cores": psutil.cpu_count(logical=True)
        },
        "memory": {
            "usage_percent": system_metrics["mem_percent"],
            "used_mb": system_metrics["mem_used"],
            "total_mb": system_metrics["mem_total"],
            "free_mb": system_metrics["mem_free"]
        },
        "network": {
            "recv_kbps": system_metrics["net_recv_kbps"],
            "sent_kbps": system_metrics["net_sent_kbps"]
        },
        "runtime": {
            "pid": os.getpid(),
            "active_threads": threading.active_count()
        }
    }

# Serve frontend HTML/JS/CSS files
@app.get("/")
def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{filename}")
def serve_file(filename: str):
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"message": "File not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
