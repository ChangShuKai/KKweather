from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import psutil
import os
import threading
import json

app = FastAPI()

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
    mem = psutil.virtual_memory()
    return {
        "server_name": "gcp-kkweather",
        "cpu": {
            "usage_percent": psutil.cpu_percent(interval=0.1),
            "logical_cores": psutil.cpu_count(logical=True)
        },
        "memory": {
            "usage_percent": mem.percent,
            "used_mb": mem.used / (1024 * 1024),
            "total_mb": mem.total / (1024 * 1024),
            "free_mb": mem.available / (1024 * 1024)
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
