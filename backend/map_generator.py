import os
import time
import requests
import json
import argparse
import concurrent.futures

BACKEND_DIR = os.path.dirname(__file__)
MAP_LIVE_DIR = os.path.join(BACKEND_DIR, 'static', 'hd_map')
STATE_FILE = os.path.join(BACKEND_DIR, 'static', 'map_state.json')

TARGET_ZOOM = 14
TIME_LIMIT = 540 
MAX_WORKERS = 20
BATCH_SIZE = 100

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
            try:
                from PIL import Image, ImageDraw, ImageFont
                import io
                
                # Load image from bytes
                img = Image.open(io.BytesIO(resp.content))
                draw = ImageDraw.Draw(img)
                
                text = "KKWeather"
                
                # Try to load a nice font, fallback to default if not available
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except IOError:
                    font = ImageFont.load_default()
                    
                # Calculate text size and position (bottom right)
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                width, height = img.size
                x_pos = width - text_width - 5
                y_pos = height - text_height - 5
                
                # Draw semi-transparent background for text visibility
                draw.rectangle([x_pos - 2, y_pos - 2, x_pos + text_width + 2, y_pos + text_height + 2], fill=(0, 0, 0, 128))
                # Draw text
                draw.text((x_pos, y_pos), text, font=font, fill=(255, 255, 255, 200))
                
                # Save the watermarked image
                img.save(tile_path, "JPEG", quality=85)
                return True
            except Exception as e:
                # Fallback to saving raw bytes if image processing fails
                print(f"Watermark failed: {e}")
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

import math

def get_tile_coord(lat, lon, zoom):
    x = int((lon + 180.0) / 360.0 * (2.0 ** zoom))
    sec = 1.0 / math.cos(math.radians(lat))
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + sec) / math.pi) / 2.0 * (2.0 ** zoom))
    return x, y

def coord_generator():
    # Taiwan Bounding Box (Lat: 21.5 to 25.5, Lon: 119.5 to 122.5)
    tw_lat_min, tw_lat_max = 21.5, 25.5
    tw_lon_min, tw_lon_max = 119.5, 122.5

    # PRIORITY 1: Taiwan Zoom 7 to 14
    for z in range(7, TARGET_ZOOM + 1):
        min_x, max_y = get_tile_coord(tw_lat_min, tw_lon_min, z) # Bottom Left
        max_x, min_y = get_tile_coord(tw_lat_max, tw_lon_max, z) # Top Right
        
        min_x = max(0, min_x - 1)
        max_x = min(2**z - 1, max_x + 1)
        min_y = max(0, min_y - 1)
        max_y = min(2**z - 1, max_y + 1)

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                path = os.path.join(MAP_LIVE_DIR, str(z), str(x), f"{y}.jpg")
                if not os.path.exists(path):
                    yield (z, x, y)

    # PRIORITY 2: World Zoom 0 to 6
    for z in range(0, 7):
        min_x, max_x = 0, 2**z - 1
        min_y, max_y = 0, 2**z - 1
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                path = os.path.join(MAP_LIVE_DIR, str(z), str(x), f"{y}.jpg")
                if not os.path.exists(path):
                    yield (z, x, y)

def generate_global_map_incremental(unlimited=False):
    print(f"Starting Incremental Global HD Map Render (Target Zoom: {TARGET_ZOOM})...")
    if unlimited:
        print(f">>> UNLIMITED MODE ACTIVATED: {MAX_WORKERS} Threads <<<")
    else:
        print(f">>> CRON MODE: {MAX_WORKERS} Threads <<<")
        
    os.makedirs(MAP_LIVE_DIR, exist_ok=True)
    
    state = load_state()
    start_z, start_x, start_y = state['z'], state['x'], state['y']
    start_time = time.time()
    downloaded_this_session = 0

    print(f"Resuming puzzle from piece Z:{start_z} X:{start_x} Y:{start_y}")

    coord_gen = coord_generator()
    
    is_finished = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while True:
            batch = []
            for _ in range(BATCH_SIZE):
                try:
                    batch.append(next(coord_gen))
                except StopIteration:
                    is_finished = True
                    break
                    
            if not batch:
                break
                
            # Submit batch concurrently
            futures = {executor.submit(download_tile, z, x, y): (z, x, y) for (z, x, y) in batch}
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    downloaded_this_session += 1
                    
            # Safe checkpoint at end of batch
            last_z, last_x, last_y = batch[-1]
            save_state(last_z, last_x, last_y + 1)
            
            if not unlimited and (time.time() - start_time >= TIME_LIMIT):
                print(f"Time limit reached ({TIME_LIMIT}s). Cached {downloaded_this_session} tiles. Pausing until next cron.")
                return

    if is_finished:
        print(f"BINGO! Global HD Map up to Zoom {TARGET_ZOOM} completely rendered! ({downloaded_this_session} tiles downloaded)")
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        print("Live Puzzle Map is fully complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--unlimited', action='store_true', help='Run without time limits')
    args = parser.parse_args()
    
    generate_global_map_incremental(unlimited=args.unlimited)
