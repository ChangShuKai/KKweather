import os
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

def update_latest_json(region_name, result):
    if not result:
        return
    data = {
        "true_color": {},
        "ir": {},
        "timestamp": result["timestamp"]
    }
    if os.path.exists(LATEST_DATA_FILE):
        try:
            with open(LATEST_DATA_FILE, 'r') as f:
                old_data = json.load(f)
                data["true_color"] = old_data.get("true_color", {})
                data["ir"] = old_data.get("ir", {})
        except Exception:
            pass
            
    data["true_color"][region_name] = result["true_color"]
    data["ir"][region_name] = result["ir"]
    data["timestamp"] = result["timestamp"]
    
    with open(LATEST_DATA_FILE, 'w') as f:
        json.dump(data, f)

def job_fetch_and_process_taiwan():
    print("Starting scheduled job: Taiwan View")
    downloaded_files = get_latest_files()
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Processing Taiwan View...")
        download_dir = os.path.dirname(downloaded_files[0])
        result = process_taiwan_view(download_dir)
        if result:
            update_latest_json("taiwan", result)
            print("Taiwan View Job completed successfully.")
        else:
            print("Taiwan View Job failed during processing.")
    else:
        print("No new files downloaded.")

def job_fetch_and_process_asia():
    print("Starting scheduled job: Asia View")
    downloaded_files = get_latest_files()
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Processing Asia View...")
        download_dir = os.path.dirname(downloaded_files[0])
        result = process_asia_view(download_dir)
        if result:
            update_latest_json("asia", result)
            print("Asia View Job completed successfully.")
        else:
            print("Asia View Job failed during processing.")
    else:
        print("No new files downloaded.")

def job_fetch_and_process_global():
    print("Starting scheduled job: Global View")
    downloaded_files = get_latest_files()
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} files. Processing Global View...")
        download_dir = os.path.dirname(downloaded_files[0])
        result = process_global_view(download_dir)
        if result:
            update_latest_json("global", result)
            print("Global View Job completed successfully.")
        else:
            print("Global View Job failed during processing.")
    else:
        print("No new files downloaded.")

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
    if os.path.exists(LATEST_DATA_FILE):
        with open(LATEST_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"status": "processing"}

os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
