import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import json
from contextlib import asynccontextmanager
from .fetcher import get_latest_files
from .processor import process_images

LATEST_DATA_FILE = os.path.join(os.path.dirname(__file__), 'latest.json')

def job_fetch_and_process():
    print("Starting scheduled job: Fetch and Process")
    downloaded_files = get_latest_files()
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Processing...")
        download_dir = os.path.dirname(downloaded_files[0])
        result = process_images(download_dir)
        if result:
            with open(LATEST_DATA_FILE, 'w') as f:
                json.dump(result, f)
            print("Job completed successfully.")
        else:
            print("Job failed during processing.")
    else:
        print("No new files downloaded.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = BackgroundScheduler()
    scheduler.add_job(job_fetch_and_process, 'interval', minutes=10)
    scheduler.start()
    
    # Run once at startup
    job_fetch_and_process()
    
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

os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

@app.get("/api/latest")
def get_latest():
    if os.path.exists(LATEST_DATA_FILE):
        with open(LATEST_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"status": "processing"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
