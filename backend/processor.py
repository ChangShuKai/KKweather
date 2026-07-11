import os
import glob
from satpy import Scene
from pyresample import create_area_def
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images')
os.makedirs(STATIC_DIR, exist_ok=True)

def process_images(download_dir):
    files = glob.glob(os.path.join(download_dir, '*'))
    if not files:
        print("No files to process.")
        return None

    reader = 'ahi_nc' if files[0].endswith('.nc') else 'ahi_hsd'
    print(f"Loading scene with reader {reader}...")
    
    try:
        scn = Scene(filenames=files, reader=reader)
        # Load required bands
        scn.load(['B01', 'B02', 'B03', 'B14'])
        
        # Define target area (Equirectangular / Plate Carree)
        # Extent: [lon_min, lat_min, lon_max, lat_max]
        # Himawari-9 is centered at 140.7E. Let's create an area covering Asia/Australia
        area_id = 'asia_eqc'
        proj_dict = {'proj': 'eqc', 'lat_ts': 0, 'lat_0': 0, 'lon_0': 140.7, 'ellps': 'WGS84'}
        extent = [60, -60, 220, 60] # Approximate extent
        
        # Let's just use the native projection for full disk or resample to a standard area
        # A 2000x2000 grid
        target_area = create_area_def(area_id, proj_dict, area_extent=[-8000000, -8000000, 8000000, 8000000], resolution=8000)
        
        print("Resampling scene...")
        local_scn = scn.resample(target_area)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        
        # 1. Custom True Color with Green Enhancement
        print("Generating True Color...")
        r = local_scn['B03'].values
        g = local_scn['B02'].values
        b = local_scn['B01'].values
        
        # Green anomaly correction (simple approximation since we don't have B04)
        # Enhancing green slightly and reducing red contribution to green
        g_enhanced = np.clip(g * 1.2 - r * 0.1, 0, 100)
        
        # Normalize to 0-255
        def normalize(arr):
            arr = np.nan_to_num(arr)
            arr = np.clip(arr, 0, 100) # Reflectance usually 0-100
            return (arr / 100.0 * 255).astype(np.uint8)
            
        rgb = np.dstack((normalize(r), normalize(g_enhanced), normalize(b)))
        
        true_color_filename = f"himawari_true_color_{timestamp_str}.jpg"
        true_color_path = os.path.join(STATIC_DIR, true_color_filename)
        Image.fromarray(rgb).save(true_color_path, quality=90)
        
        # 2. Custom Infrared (Band 14)
        print("Generating Custom Infrared...")
        ir = local_scn['B14'].values
        # Band 14 is brightness temperature in Kelvin. 
        # Colder temps (high clouds) -> brighter colors
        
        ir = np.nan_to_num(ir, nan=273.15)
        # Typical range: 180K (cold cloud) to 310K (warm surface)
        ir_clipped = np.clip(ir, 180, 310)
        # Normalize so that cold is 1, warm is 0 for colormap
        ir_norm = (310 - ir_clipped) / (310 - 180)
        
        # Apply magma colormap
        cmap = plt.get_cmap('magma')
        ir_rgba = cmap(ir_norm)
        ir_rgb = (ir_rgba[:, :, :3] * 255).astype(np.uint8)
        
        ir_filename = f"himawari_ir_{timestamp_str}.jpg"
        ir_path = os.path.join(STATIC_DIR, ir_filename)
        Image.fromarray(ir_rgb).save(ir_path, quality=90)
        
        print(f"Generated {true_color_filename} and {ir_filename}")
        
        return {
            "true_color": f"/static/images/{true_color_filename}",
            "ir": f"/static/images/{ir_filename}",
            "timestamp": timestamp_str
        }

    except Exception as e:
        print(f"Error processing images: {e}")
        return None
