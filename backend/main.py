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

        # ---------------------------------------------------------
        # PIECE 1: TAIWAN (動態匹配包含 _S03 的所有最新段落)
        # ---------------------------------------------------------
        print("[Progress] 15% - Downloading Segment 3 for Taiwan (Dynamic)...")
        tw_files = fetch_segments(prefix, ['_S03'])
        if not tw_files: raise Exception("無法下載到台灣區域最新的衛星 DAT 檔案！")

        print(f"[Progress] 20% - Processing Taiwan True Color ({len(tw_files)} files)...")
        tw_tc = process_taiwan_view(tw_files, "true_color")
        update_latest_json("taiwan", "true_color", tw_tc)

        print("[Progress] 35% - Processing Taiwan Infrared...")
        tw_ir = process_taiwan_view(tw_files, "ir")
        update_latest_json("taiwan", "ir", tw_ir)

        # ---------------------------------------------------------
        # PIECE 2: ASIA (動態匹配 1, 2, 3, 4 段落)
        # ---------------------------------------------------------
        print("[Progress] 45% - Downloading Segments 1, 2, 4 for Asia (Dynamic)...")
        asia_files = fetch_segments(prefix, ['_S01', '_S02', '_S03', '_S04'])

        print(f"[Progress] 50% - Processing Asia True Color ({len(asia_files)} files)...")
        asia_tc = process_asia_view(asia_files, "true_color")
        update_latest_json("asia", "true_color", asia_tc)

        print("[Progress] 65% - Processing Asia Infrared...")
        asia_ir = process_asia_view(asia_files, "ir")
        update_latest_json("asia", "ir", asia_ir)

        # ---------------------------------------------------------
        # PIECE 3: GLOBAL (All Segments)
        # ---------------------------------------------------------
        print("[Progress] 75% - Downloading remaining segments for Global...")
        global_files = fetch_segments(prefix, None)

        print(f"[Progress] 80% - Processing Global True Color ({len(global_files)} files)...")
        global_tc = process_global_view(global_files, "true_color")
        update_latest_json("global", "true_color", global_tc)

        print("[Progress] 90% - Processing Global Infrared...")
        global_ir = process_global_view(global_files, "ir")
        update_latest_json("global", "ir", global_ir)

        print("[Progress] 100% - All views completed successfully!")
    except Exception as e:
        print(f"[Progress] 100% - Job failed: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    # GitHub Actions 直接作為指令稿執行此主程式
    job_fetch_and_process_all()
