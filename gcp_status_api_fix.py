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
}

def update_metrics_loop():
    # Initialize psutil CPU polling
    psutil.cpu_percent(interval=None)
    while True:
        try:
            # interval=1 blocks for 1 second, perfect for background thread
            cpu = psutil.cpu_percent(interval=1.0)
            mem = psutil.virtual_memory()
            system_metrics["cpu_percent"] = cpu
            system_metrics["mem_percent"] = mem.percent
            system_metrics["mem_used"] = mem.used / (1024 * 1024)
            system_metrics["mem_total"] = mem.total / (1024 * 1024)
            system_metrics["mem_free"] = mem.available / (1024 * 1024)
        except Exception:
            pass
        time.sleep(0.1)

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


import google.generativeai as genai
import subprocess
from pydantic import BaseModel

# Initialize Gemini
genai.configure(api_key="AIzaSyDyKOHTza6492Gr3MwYl5apg0EZKhh8DJQ")

def run_shell_command(command: str) -> str:
    """Executes a shell command on the Linux server and returns the output. Use this to inspect the system, manage processes, or manipulate files."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        out = result.stdout
        if result.stderr:
            out += f"\n[stderr]: {result.stderr}"
        return out if out else "(Command executed successfully with no output)"
    except Exception as e:
        return f"Error executing command: {str(e)}"

sys_instruct = "You are a highly capable AI Server Administrator. You have full root access to this GCP Linux server. When the user asks you to do something, use the run_shell_command tool to execute commands, gather info, and make changes. Once you have the info, explain the result clearly and concisely to the user in Traditional Chinese."
model = genai.GenerativeModel('gemini-1.5-pro', tools=[run_shell_command], system_instruction=sys_instruct)
chat_session = None

class AgentRequest(BaseModel):
    message: str
    username: str
    password: str

@app.post("/api/agent")
def run_agent_command(req: AgentRequest):
    global chat_session
    if req.username != "kai1010210@gmail.com" or req.password != "a12221316":
        return {"status": "error", "output": "Unauthorized"}
    
    if chat_session is None:
        chat_session = model.start_chat(enable_automatic_function_calling=True)

    try:
        response = chat_session.send_message(req.message)
        return {"status": "success", "output": response.text}
    except Exception as e:
        return {"status": "error", "output": f"AI Error: {str(e)}"}

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
