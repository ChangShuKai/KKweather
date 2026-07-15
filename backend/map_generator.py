import os
import time
import requests
import json
import argparse

BACKEND_DIR = os.path.dirname(__file__)
# Save directly to backend/static so FastAPI can serve it live!
MAP_LIVE_DIR = os.path.join(BACKEND_DIR, 'static', 'hd_map')
STATE_FILE = os.path.join(BACKEND_DIR, 'static', 'map_state.json')

TARGET_ZOOM = 8
# Limit to 9 minutes (540 seconds) for cron, but bypassed if --unlimited
TIME_LIMIT = 540 

def download_tile(z, x, y):
    url = f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"
    tile_dir = os.path.join(MAP_LIVE_DIR, str(z), str(x))
    os.makedirs(tile_dir, exist_ok=True)
    
    tile_path = os.path.join(tile_dir, f"{y}.jpg")
    if os.path.exists(tile_path):
        return True # Already downloaded
        
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            with open(tile_path, 'wb') as f:
                f.write(resp.content)
            return True
    except Exception as e:
        pass
    return False

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"z": 0, "x": 0, "y": 0}

def save_state(z, x, y):
    with open(STATE_FILE, 'w') as f:
        json.dump({"z": z, "x": x, "y": y}, f)

def generate_global_map_incremental(unlimited=False):
    print(f"Starting Incremental Global HD Map Render (Target Zoom: {TARGET_ZOOM})...")
    if unlimited:
        print(">>> UNLIMITED MODE ACTIVATED: Will run until completely finished! <<<")
        
    os.makedirs(MAP_LIVE_DIR, exist_ok=True)
    
    state = load_state()
    start_z, start_x, start_y = state['z'], state['x'], state['y']
    start_time = time.time()
    downloaded_this_session = 0

    print(f"Resuming puzzle from piece Z:{start_z} X:{start_x} Y:{start_y}")

    for z in range(start_z, TARGET_ZOOM + 1):
        max_coord = 2**z
        x_range_start = start_x if z == start_z else 0
        
        for x in range(x_range_start, max_coord):
            y_range_start = start_y if (z == start_z and x == start_x) else 0
            
            for y in range(y_range_start, max_coord):
                if download_tile(z, x, y):
                    downloaded_this_session += 1
                
                # Check time limit every tile (unless unlimited)
                if not unlimited and (time.time() - start_time >= TIME_LIMIT):
                    save_state(z, x, y + 1)
                    print(f"Time limit reached ({TIME_LIMIT}s). Cached {downloaded_this_session} tiles. Pausing until next cron.")
                    return

    # If loops finish, the entire map is complete!
    print(f"BINGO! Global HD Map up to Zoom {TARGET_ZOOM} completely rendered! ({downloaded_this_session} tiles downloaded)")
    
    # Remove state file so next time it starts fresh
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print("Live Puzzle Map is fully complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--unlimited', action='store_true', help='Run without time limits')
    args = parser.parse_args()
    
    generate_global_map_incremental(unlimited=args.unlimited)
