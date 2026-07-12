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

def process_view(files, region_name, bbox, mode):
    import dask
    import dask.array as da
    import gc

    # Squeeze out maximum performance! Use all logical host cores (often 4, 8, or 16).
    dask.config.set(scheduler='threads', num_workers=os.cpu_count() or 4)
    dask.config.set({"array.chunk-size": "16MiB"})

    if not files:
        print("No files to process.")
        return None

    reader = 'ahi_nc' if files[0].endswith('.nc') else 'ahi_hsd'
    
    first_file = os.path.basename(files[0])
    parts = first_file.split('_')
    if len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
        timestamp_str = f"{parts[2]}_{parts[3]}"
    else:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        
    try:
        from pyresample.geometry import AreaDefinition
        from satpy.enhancements.enhancer import get_enhanced_image
        
        # We handle shapefiles drawing inline
        shapefile_dir = os.path.join(os.path.dirname(__file__), 'shapefiles')
        has_shapefiles = os.path.exists(os.path.join(shapefile_dir, 'gshhs_c.b'))
        
        if region_name == "global":
            stride = 4
        elif region_name == "asia":
            stride = 2
        else:
            stride = 1
            
        res_code = 'i' if region_name == 'taiwan' else ('l' if region_name == 'asia' else 'c')
        
        if mode == "true_color":
            # ==========================================
            # 1. True Color Image
            # ==========================================
            print(f"[{region_name}] Loading True Color bands with reader {reader}...")
            tc_files = [f for f in files if any(b in f for b in ['_B01_', '_B02_', '_B03_', '_B04_'])]
            scn_tc = Scene(filenames=tc_files, reader=reader)
            scn_tc.load(['true_color'])
            
            if bbox:
                print(f"[{region_name}] Cropping True Color to bounding box...")
                local_scn_tc = scn_tc.crop(ll_bbox=bbox)
            else:
                local_scn_tc = scn_tc
                
            print(f"[{region_name}] Enhancing True Color...")
            img = get_enhanced_image(local_scn_tc['true_color'])
            
            old_area = local_scn_tc['true_color'].attrs['area']
            
            if stride > 1:
                img.data = img.data[:, ::stride, ::stride]
                
            print(f"[{region_name}] Computing True Color image...")
            pil_img = img.pil_image()
            
            new_area = AreaDefinition(
                old_area.area_id, old_area.description, old_area.proj_id, old_area.crs,
                pil_img.width, pil_img.height, old_area.area_extent
            )
            
            if has_shapefiles:
                from pycoast import ContourWriterPIL
                print(f"[{region_name}] Drawing coastlines and gridlines...")
                cw = ContourWriterPIL(shapefile_dir)
                cw.add_coastlines(pil_img, new_area, resolution=res_code, outline='yellow', width=1)
                cw.add_grid(pil_img, new_area, (10, 10), (5, 5), outline='yellow', width=1)
            
            filename_tc = f"himawari_true_color_{region_name}_{timestamp_str}.webp"
            path_tc = os.path.join(STATIC_DIR, filename_tc)
            print(f"[{region_name}] Saving {filename_tc}...")
            pil_img.save(path_tc, format="WEBP", quality=85)
            
            result = f"/static/images/{filename_tc}"
            
            del img, local_scn_tc, scn_tc

        elif mode == "ir":
            # ==========================================
            # 2. Infrared Image
            # ==========================================
            print(f"[{region_name}] Loading Infrared band with reader {reader}...")
            ir_files = [f for f in files if '_B14_' in f]
            scn_ir = Scene(filenames=ir_files, reader=reader)
            scn_ir.load(['B14'])
            
            if bbox:
                print(f"[{region_name}] Cropping Infrared to bounding box...")
                local_scn_ir = scn_ir.crop(ll_bbox=bbox)
            else:
                print(f"[{region_name}] Using native B14 area for Global Infrared...")
                local_scn_ir = scn_ir
                
            ir = local_scn_ir['B14'].data
            
            old_area = local_scn_ir['B14'].attrs['area']
            
            # Since IR is already lower resolution (2km), we divide stride by 2 for global
            ir_stride = 2 if region_name == "global" else 1
                
            ir = ir[::ir_stride, ::ir_stride]
            
            def process_ir_block(arr):
                import numpy as np
                arr = np.nan_to_num(arr, nan=273.15)
                arr = np.clip(arr, 180, 310)
                norm = (310.0 - arr) / 130.0
                indices = np.clip(norm * 255, 0, 255).astype(np.int32)
                return IR_LUT[indices]
                
            ir_rgb_da = ir.map_blocks(process_ir_block, dtype=np.uint8, new_axis=[2], chunks=tuple(ir.chunks) + ((3,),))
            
            print(f"[{region_name}] Computing Infrared array...")
            ir_rgb_np = ir_rgb_da.compute()
            
            pil_img_ir = Image.fromarray(ir_rgb_np)
            
            new_area_ir = AreaDefinition(
                old_area.area_id, old_area.description, old_area.proj_id, old_area.crs,
                pil_img_ir.width, pil_img_ir.height, old_area.area_extent
            )
            
            if has_shapefiles:
                from pycoast import ContourWriterPIL
                print(f"[{region_name}] Drawing coastlines and gridlines for IR...")
                cw = ContourWriterPIL(shapefile_dir)
                cw.add_coastlines(pil_img_ir, new_area_ir, resolution=res_code, outline='yellow', width=1)
                cw.add_grid(pil_img_ir, new_area_ir, (10, 10), (5, 5), outline='yellow', width=1)
            
            filename_ir = f"himawari_ir_{region_name}_{timestamp_str}.webp"
            path_ir = os.path.join(STATIC_DIR, filename_ir)
            print(f"[{region_name}] Saving {filename_ir}...")
            pil_img_ir.save(path_ir, format="WEBP", quality=85)
            
            result = f"/static/images/{filename_ir}"
            
            del ir_rgb_np, ir_rgb_da, ir
            del local_scn_ir, scn_ir

        print(f"[{region_name} - {mode}] Finished processing. Flushing memory.")
        dask.config.set(scheduler='threads')
        gc.collect()
        
        return {"path": result, "timestamp": timestamp_str}

    except Exception as e:
        print(f"[{region_name} - {mode}] Error processing images: {e}")
        return None

def process_taiwan_view(files, mode):
    return process_view(files, "taiwan", (118, 21, 124, 26), mode)

def process_asia_view(files, mode):
    return process_view(files, "asia", (110, 10, 150, 50), mode)

def process_global_view(files, mode):
    return process_view(files, "global", None, mode)
