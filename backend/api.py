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
    import requests
    github_url = "https://raw.githubusercontent.com/ChangShuKai/KKweather/main/backend/latest.json"
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
        resp = requests.get(github_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # 將本地靜態路徑轉換為 GitHub Raw 直接讀取連結
            for mode in ["true_color", "ir"]:
                if mode in data:
                    for region in ["global", "asia", "taiwan"]:
                        path = data[mode].get(region)
                        if path and path.startswith("/static/"):
                            filename = path.split("/")[-1]
                            data[mode][region] = f"https://raw.githubusercontent.com/ChangShuKai/KKweather/main/backend/static/images/{filename}"
            return data
    except Exception:
        pass

    if os.path.exists(LATEST_JSON):
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
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
