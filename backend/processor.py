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
    import dask
    import dask.array as da
    import gc

    # Force Dask to compute immediately without memory hoarding and use small chunks
    dask.config.set(scheduler='synchronous')
    dask.config.set({"array.chunk-size": "8MiB"})

    files = glob.glob(os.path.join(download_dir, '*'))
    if not files:
        print("No files to process.")
        return None

    reader = 'ahi_nc' if files[0].endswith('.nc') else 'ahi_hsd'
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    
    regions = {
        'global': None,
        'asia': (110, 10, 150, 50),
        'taiwan': (118, 21, 124, 26)
    }
    
    results = {
        "true_color": {},
        "ir": {},
        "timestamp": timestamp_str
    }
    
    try:
        # ==========================================
        # 1. True Color Image (Sequential Processing)
        # ==========================================
        print(f"Loading True Color bands with reader {reader}...")
        scn_tc = Scene(filenames=files, reader=reader)
        scn_tc.load(['B01', 'B02', 'B03'])
        
        print("Resampling True Color to finest native area...")
        global_scn_tc = scn_tc.resample(scn_tc.finest_area())
        
        for region_name, bbox in regions.items():
            print(f"Processing True Color - {region_name}...")
            if bbox:
                local_scn_tc = global_scn_tc.crop(ll_bbox=bbox)
            else:
                local_scn_tc = global_scn_tc
                
            r = local_scn_tc['B03'].data
            g = local_scn_tc['B02'].data
            b = local_scn_tc['B01'].data
            
            # Memory-efficient dask operations (inplace-like behavior via dask graph)
            g_enhanced = da.clip(g * 1.2 - r * 0.1, 0, 100)
            
            def normalize_block(arr):
                import numpy as np
                arr = np.nan_to_num(arr)
                arr = np.clip(arr, 0, 100)
                return (arr / 100.0 * 255).astype(np.uint8)
                
            r_norm = r.map_blocks(normalize_block, dtype=np.uint8)
            g_norm = g_enhanced.map_blocks(normalize_block, dtype=np.uint8)
            b_norm = b.map_blocks(normalize_block, dtype=np.uint8)
            
            rgb_da = da.stack([r_norm, g_norm, b_norm], axis=-1)
            
            print(f"Computing True Color array ({region_name})...")
            # Computes chunks iteratively. Only the final uint8 array stays in memory (~360MB max for global)
            rgb_np = rgb_da.compute()
            
            filename = f"himawari_true_color_{region_name}_{timestamp_str}.png"
            path = os.path.join(STATIC_DIR, filename)
            print(f"Saving {filename} at Native Resolution...")
            Image.fromarray(rgb_np).save(path)
            
            results["true_color"][region_name] = f"/static/images/{filename}"
            
            print(f"Flushing memory for {region_name}...")
            del rgb_np, rgb_da, r_norm, g_norm, b_norm, r, g, b, g_enhanced
            if bbox:
                del local_scn_tc
            gc.collect()

        del global_scn_tc, scn_tc
        gc.collect()

        # ==========================================
        # 2. Infrared Image (Sequential Processing)
        # ==========================================
        print(f"Loading Infrared band with reader {reader}...")
        scn_ir = Scene(filenames=files, reader=reader)
        scn_ir.load(['B14'])
        
        print("Resampling Infrared to finest native area...")
        global_scn_ir = scn_ir.resample(scn_ir.finest_area())
        
        for region_name, bbox in regions.items():
            print(f"Processing Infrared - {region_name}...")
            if bbox:
                local_scn_ir = global_scn_ir.crop(ll_bbox=bbox)
            else:
                local_scn_ir = global_scn_ir
                
            ir = local_scn_ir['B14'].data
            
            def process_ir_block(arr):
                import numpy as np
                import matplotlib.pyplot as plt
                arr = np.nan_to_num(arr, nan=273.15)
                arr = np.clip(arr, 180, 310)
                norm = (310 - arr) / (310 - 180)
                cmap = plt.get_cmap('magma')
                rgba = cmap(norm)
                return (rgba[..., :3] * 255).astype(np.uint8)
                
            ir_rgb_da = ir.map_blocks(process_ir_block, dtype=np.uint8, new_axis=[2], chunks=tuple(ir.chunks) + ((3,),))
            
            print(f"Computing Infrared array ({region_name})...")
            ir_rgb_np = ir_rgb_da.compute()
            
            filename = f"himawari_ir_{region_name}_{timestamp_str}.png"
            path = os.path.join(STATIC_DIR, filename)
            print(f"Saving {filename} at Native Resolution...")
            Image.fromarray(ir_rgb_np).save(path)
            
            results["ir"][region_name] = f"/static/images/{filename}"
            
            print(f"Flushing memory for {region_name}...")
            del ir_rgb_np, ir_rgb_da, ir
            if bbox:
                del local_scn_ir
            gc.collect()
            
        del global_scn_ir, scn_ir
        gc.collect()
        
        print("Finished generating all regions.")
        return results

    except Exception as e:
        print(f"Error processing images: {e}")
        return None
