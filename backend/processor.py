import os
import glob
from satpy import Scene
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images')
os.makedirs(STATIC_DIR, exist_ok=True)

# Pre-compute IR Look-Up Table (LUT) to avoid matplotlib overhead inside Dask blocks
try:
    import matplotlib.colormaps as cm
    _magma = cm.get_cmap('magma')
except ImportError:
    import matplotlib.pyplot as plt
    _magma = plt.get_cmap('magma')

IR_LUT = (_magma(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)

def _process_single_view(files, region_name, bbox):
    import dask
    import dask.array as da
    import gc

    # Force Dask to compute immediately without memory hoarding and use small chunks
    dask.config.set(scheduler='synchronous')
    dask.config.set({"array.chunk-size": "8MiB"})

    if not files:
        print("No files to process.")
        return None

    reader = 'ahi_nc' if files[0].endswith('.nc') else 'ahi_hsd'
    
    # Extract timestamp from filename (e.g. HS_H09_20260712_0840_...)
    first_file = os.path.basename(files[0])
    parts = first_file.split('_')
    if len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
        timestamp_str = f"{parts[2]}_{parts[3]}"
    else:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    
    results = {
        "true_color": None,
        "ir": None,
        "timestamp": timestamp_str
    }
    
    try:
        # ==========================================
        # 1. True Color Image
        # ==========================================
        print(f"[{region_name}] Loading True Color bands with reader {reader}...")
        scn_tc = Scene(filenames=files, reader=reader)
        scn_tc.load(['B01', 'B02', 'B03'])
        
        if bbox:
            print(f"[{region_name}] Cropping True Color to bounding box...")
            cropped_scn_tc = scn_tc.crop(ll_bbox=bbox)
            print(f"[{region_name}] Resampling cropped True Color to 1km using native resampler...")
            target_area = cropped_scn_tc.coarsest_area()
            local_scn_tc = cropped_scn_tc.resample(target_area, resampler='native')
            del cropped_scn_tc
        else:
            print(f"[{region_name}] Resampling Global True Color to 1km using native resampler...")
            target_area = scn_tc.coarsest_area()
            local_scn_tc = scn_tc.resample(target_area, resampler='native')
            
        r = local_scn_tc['B03'].data
        g = local_scn_tc['B02'].data
        b = local_scn_tc['B01'].data
        
        # Apply stride to drastically reduce memory usage before computing
        if region_name == "global":
            stride = 4  # 1km -> 4km (approx 2750x2750)
        elif region_name == "asia":
            stride = 2  # 1km -> 2km (approx 2000x2000)
        else:
            stride = 1  # 1km (approx 600x500)
            
        r = r[::stride, ::stride]
        g = g[::stride, ::stride]
        b = b[::stride, ::stride]
        
        g_enhanced = da.clip(g * 1.2 - r * 0.1, 0, 100)
        
        def normalize_block(arr):
            import numpy as np
            arr = np.nan_to_num(arr)
            arr = np.clip(arr, 0, 100)
            return (arr * 2.55).astype(np.uint8)
            
        r_norm = r.map_blocks(normalize_block, dtype=np.uint8)
        g_norm = g_enhanced.map_blocks(normalize_block, dtype=np.uint8)
        b_norm = b.map_blocks(normalize_block, dtype=np.uint8)
        
        rgb_da = da.stack([r_norm, g_norm, b_norm], axis=-1)
        
        print(f"[{region_name}] Computing True Color array...")
        rgb_np = rgb_da.compute()
        
        filename_tc = f"himawari_true_color_{region_name}_{timestamp_str}.webp"
        path_tc = os.path.join(STATIC_DIR, filename_tc)
        print(f"[{region_name}] Saving {filename_tc}...")
        Image.fromarray(rgb_np).save(path_tc, format="WEBP", quality=85)
        
        results["true_color"] = f"/static/images/{filename_tc}"
        
        del rgb_np, rgb_da, r_norm, g_norm, b_norm, r, g, b, g_enhanced
        del local_scn_tc, scn_tc
        gc.collect()

        # ==========================================
        # 2. Infrared Image
        # ==========================================
        print(f"[{region_name}] Loading Infrared band with reader {reader}...")
        scn_ir = Scene(filenames=files, reader=reader)
        scn_ir.load(['B14'])
        
        if bbox:
            print(f"[{region_name}] Cropping Infrared to bounding box...")
            local_scn_ir = scn_ir.crop(ll_bbox=bbox)
        else:
            print(f"[{region_name}] Using native B14 area for Global Infrared...")
            local_scn_ir = scn_ir
            
        ir = local_scn_ir['B14'].data
        
        # B14 is natively 2km
        if region_name == "global":
            stride = 2  # 2km -> 4km (approx 2750x2750)
        elif region_name == "asia":
            stride = 1  # 2km (approx 2000x2000)
        else:
            stride = 1  # 2km (approx 300x250)
            
        ir = ir[::stride, ::stride]
        
        def process_ir_block(arr):
            import numpy as np
            arr = np.nan_to_num(arr, nan=273.15)
            arr = np.clip(arr, 180, 310)
            # Map 310 -> 0, 180 -> 255
            norm = (310.0 - arr) / 130.0
            indices = np.clip(norm * 255, 0, 255).astype(np.int32)
            # IR_LUT is accessible from the module scope
            return IR_LUT[indices]
            
        ir_rgb_da = ir.map_blocks(process_ir_block, dtype=np.uint8, new_axis=[2], chunks=tuple(ir.chunks) + ((3,),))
        
        print(f"[{region_name}] Computing Infrared array...")
        ir_rgb_np = ir_rgb_da.compute()
        
        filename_ir = f"himawari_ir_{region_name}_{timestamp_str}.webp"
        path_ir = os.path.join(STATIC_DIR, filename_ir)
        print(f"[{region_name}] Saving {filename_ir}...")
        Image.fromarray(ir_rgb_np).save(path_ir, format="WEBP", quality=85)
        
        results["ir"] = f"/static/images/{filename_ir}"
        
        del ir_rgb_np, ir_rgb_da, ir
        del local_scn_ir, scn_ir

        print(f"[{region_name}] Finished processing. Flushing memory.")
        # Ensure dask caches are cleared per requirements
        dask.config.set(scheduler='synchronous')
        gc.collect()
        
        return results

    except Exception as e:
        print(f"[{region_name}] Error processing images: {e}")
        return None

def process_taiwan_view(files):
    return _process_single_view(files, "taiwan", (118, 21, 124, 26))

def process_asia_view(files):
    return _process_single_view(files, "asia", (110, 10, 150, 50))

def process_global_view(files):
    return _process_single_view(files, "global", None)
