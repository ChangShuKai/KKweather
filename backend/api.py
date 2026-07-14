from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
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
LATEST_JSON = os.path.join(BASE_DIR, "latest.json")

# Serve frontend files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
frontend_dir = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))
app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/api/latest")
def get_latest():
    if os.path.exists(LATEST_JSON):
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    return {"status": "processing", "message": "等待 GitHub Actions 即時運算中..."}

@app.get("/api/logs")
def get_logs():
    return {"logs": ["[Progress] 100% - 影像正由 GitHub Actions 每 10 分鐘自動同步更新"]}

# Serve any other frontend HTML files (like status.html)
@app.get("/{filename}.html")
def serve_html(filename: str):
    file_path = os.path.join(frontend_dir, f"{filename}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"message": "File not found"})

@app.get("/{filename}.css")
def serve_css(filename: str):
    file_path = os.path.join(frontend_dir, f"{filename}.css")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"message": "File not found"})

@app.get("/{filename}.js")
def serve_js(filename: str):
    file_path = os.path.join(frontend_dir, f"{filename}.js")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"message": "File not found"})
