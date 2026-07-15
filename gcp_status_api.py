from fastapi import FastAPI
import psutil
import os
import threading

app = FastAPI()

@app.get("/status")
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

@app.get("/logs")
def get_logs():
    log_file = "/home/kai1010210/satellite.log"
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Get the last 30 lines to avoid sending too much text
                logs = [line.strip() for line in lines[-30:] if line.strip()]
        except Exception as e:
            logs = [f"Error reading logs: {str(e)}"]
    else:
        logs = ["等待排程初次執行中... (日誌檔案尚未建立)"]
        
    return {"logs": logs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
