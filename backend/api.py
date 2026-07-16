from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))
GCP_URL = "http://34.80.61.138:8080"

# 1. Proxy static images from GCP
@app.get("/static/{filepath:path}")
def proxy_static(filepath: str):
    url = f"{GCP_URL}/static/{filepath}"
    try:
        resp = requests.get(url, stream=True, timeout=10)
        return StreamingResponse(resp.iter_content(chunk_size=8192), media_type=resp.headers.get('content-type', 'image/webp'))
    except Exception as e:
        return JSONResponse(status_code=502, content={"message": "Failed to proxy image from GCP"})

# 2. Proxy API endpoints
@app.get("/api/{endpoint:path}")
def proxy_api_get(endpoint: str):
    url = f"{GCP_URL}/api/{endpoint}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    except Exception as e:
        return JSONResponse(status_code=502, content={"status": "processing", "message": "等待連線至伺服器..."})

@app.post("/api/{endpoint:path}")
async def proxy_api_post(endpoint: str, request: Request):
    url = f"{GCP_URL}/api/{endpoint}"
    try:
        data = await request.json()
        resp = requests.post(url, json=data, timeout=35)
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    except Exception as e:
        return JSONResponse(status_code=502, content={"status": "error", "message": f"Proxy Error: {str(e)}"})

# 3. Proxy /logs and /status
@app.get("/logs")
def proxy_logs():
    return proxy_api_get("logs")

@app.get("/status")
def proxy_status():
    return proxy_api_get("status")

# 4. Serve Frontend
@app.get("/")
def read_root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

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
