import os
import sys
import psutil
import shutil
from collections import deque
import json
import glob
from datetime import datetime

LATEST_DATA_FILE = os.path.join(os.path.dirname(__file__), 'latest.json')
log_buffer = deque(maxlen=100)

class LogInterceptor:
    def __init__(self, stream): self.stream = stream
    def write(self, data):
        self.stream.write(data)
        if isinstance(data, str) and data.strip():
            lines = data.strip().split('\n')
            for line in lines:
                if line: log_buffer.append(line)
    def flush(self): self.stream.flush()

sys.stdout = LogInterceptor(sys.stdout)
sys.stderr = LogInterceptor(sys.stderr)

def update_latest_json(region_name, mode, result):
    if not result: return
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
        except Exception: pass

    data[mode][region_name] = result["path"]
    data["timestamp"] = result["timestamp"]

    all_done = all(data["true_color"].get(r) is not None and data["ir"].get(r) is not None for r in ["global", "asia", "taiwan"])
    if all_done: data["status"] = "completed"
    with open(LATEST_DATA_FILE, 'w') as f: json.dump(data, f)

def job_fetch_and_process_all():
    print("[Progress] 0% - Starting satellite data pipeline")
    try:
        from backend.fetcher import find_latest_prefix, fetch_segments, DOWNLOAD_DIR
        from backend.processor import process_taiwan_view, process_asia_view, process_global_view

        print("[Progress] 2% - Cleaning up old data files...")
        old_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.DAT*"))
        for f in old_files:
            try: os.remove(f)
            except: pass

        print("[Progress] 5% - Checking for latest files on AWS S3...")
        prefix = find_latest_prefix()

        if not prefix:
            print("[Progress] 100% - No new files to process.")
            return

        print(f"[Progress] 10% - Latest data found on AWS: {prefix}")

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # ---------------------------------------------------------
            # PIECE 1: TAIWAN 
            # ---------------------------------------------------------
            print("[Progress] 15% - Downloading Segment 3 for Taiwan (Dynamic)...")
            tw_files = fetch_segments(prefix, ['_S03'])
            if not tw_files: raise Exception("無法下載到台灣區域最新的衛星 DAT 檔案！")

            # 🔥 優化：在處理台灣影像的同時，背景開始下載亞洲區域檔案
            print("[Progress] 20% - [Background] Start downloading Segments 1-4 for Asia...")
            future_asia_files = executor.submit(fetch_segments, prefix, ['_S01', '_S02', '_S03', '_S04'])

            print(f"[Progress] 25% - Processing Taiwan True Color ({len(tw_files)} files)...")
            tw_tc = process_taiwan_view(tw_files, "true_color")
            update_latest_json("taiwan", "true_color", tw_tc)

            print("[Progress] 35% - Processing Taiwan Infrared...")
            tw_ir = process_taiwan_view(tw_files, "ir")
            update_latest_json("taiwan", "ir", tw_ir)

            # ---------------------------------------------------------
            # PIECE 2: ASIA 
            # ---------------------------------------------------------
            print("[Progress] 45% - Waiting for Asia downloads to complete...")
            asia_files = future_asia_files.result()

            # 🔥 優化：在處理亞洲影像的同時，背景開始下載全球區域檔案
            print("[Progress] 50% - [Background] Start downloading remaining segments for Global...")
            future_global_files = executor.submit(fetch_segments, prefix, None)

            print(f"[Progress] 55% - Processing Asia True Color ({len(asia_files)} files)...")
            asia_tc = process_asia_view(asia_files, "true_color")
            update_latest_json("asia", "true_color", asia_tc)

            print("[Progress] 65% - Processing Asia Infrared...")
            asia_ir = process_asia_view(asia_files, "ir")
            update_latest_json("asia", "ir", asia_ir)

            # ---------------------------------------------------------
            # PIECE 3: GLOBAL 
            # ---------------------------------------------------------
            print("[Progress] 75% - Waiting for Global downloads to complete...")
            global_files = future_global_files.result()

            print(f"[Progress] 80% - Processing Global True Color ({len(global_files)} files)...")
            global_tc = process_global_view(global_files, "true_color")
            update_latest_json("global", "true_color", global_tc)

            print("[Progress] 90% - Processing Global Infrared...")
            global_ir = process_global_view(global_files, "ir")
            update_latest_json("global", "ir", global_ir)

        print("[Progress] 95% - Cleaning up old image folders (keeping latest 12 hours)...")
        cleanup_old_images()

        print("[Progress] 100% - All views completed successfully!")
    except Exception as e:
        print(f"[Progress] 100% - Job failed: {e}")
        import sys
        sys.exit(1)

def cleanup_old_images():
    from backend.processor import STATIC_DIR, FRONTEND_STATIC_DIR
    import shutil
    import os
    
    for base_dir in [STATIC_DIR, FRONTEND_STATIC_DIR]:
        if not os.path.exists(base_dir): continue
        folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f)) and len(f) == 13 and '_' in f]
        folders.sort()
        
        # Keep latest 72 folders (12 hours * 6 per hour)
        if len(folders) > 72:
            folders_to_delete = folders[:-72]
            for folder in folders_to_delete:
                dir_path = os.path.join(base_dir, folder)
                try:
                    shutil.rmtree(dir_path)
                    print(f"Deleted old folder: {dir_path}")
                except Exception as e:
                    print(f"Failed to delete {dir_path}: {e}")

if __name__ == "__main__":
    # GitHub Actions 直接作為指令稿執行此主程式
    job_fetch_and_process_all()
