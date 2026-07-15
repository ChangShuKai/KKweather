import os
import glob
from satpy import Scene
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageChops, ImageFont
import shutil
from pyresample.geometry import AreaDefinition
from pycoast import ContourWriterPIL

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images')
os.makedirs(STATIC_DIR, exist_ok=True)

# 為了同時發布到 GitHub Pages 前端，自動建立並對應前端的靜態目錄
FRONTEND_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'static', 'images')
os.makedirs(FRONTEND_STATIC_DIR, exist_ok=True)

try:
    # pyrefly: ignore [missing-import]
    import matplotlib.colormaps as cm
    _magma = cm.get_cmap('magma')
except ImportError:
    # pyrefly: ignore [name-defined]
    import matplotlib.pyplot as plt
    _magma = plt.get_cmap('magma')

IR_LUT = (_magma(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)

def enhance_rgb(band):
    b_min, b_max = np.percentile(band, (2, 98))
    if b_max - b_min < 1e-5:
        b_max = b_min + 1e-5
    band_norm = np.clip((band - b_min) / (b_max - b_min), 0, 1)
    return (np.power(band_norm, 0.55) * 255).astype(np.uint8)

def process_view(files, region_name, bbox, mode):
    import dask
    import gc

    # GitHub Actions 算力全開：使用全核心多執行緒
    dask.config.set(scheduler='threads', num_workers=os.cpu_count() or 4)
    dask.config.set({"array.chunk-size": "32MiB"})

    if not files:
        print(f"[{region_name} - {mode}] 沒有可處理的檔案清單。")
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
        shapefile_dir = os.path.join(os.path.dirname(__file__), 'shapefiles')
        has_shapefiles = os.path.exists(os.path.join(shapefile_dir, 'GSHHS_c_L1.shp'))
        res_code = 'i' if region_name == 'taiwan' else ('l' if region_name == 'asia' else 'c')

        if mode == "true_color":
            print(f"[{region_name}] 正在載入真彩波段...")
            tc_files = [f for f in files if any(b in f for b in ['_B01_', '_B02_', '_B03_', '_B04_', '_B14_'])]
            scn_tc = Scene(filenames=tc_files, reader=reader)
            scn_tc.load(['true_color', 'B14'])

            local_scn_tc = scn_tc.crop(ll_bbox=bbox) if bbox else scn_tc
            local_scn_tc = local_scn_tc.resample(resampler='native')
            stride = 4 if region_name == "global" else (2 if region_name == "asia" else 1)
            
            tc_data = local_scn_tc['true_color'][:, ::stride, ::stride].compute()
            ir_data = local_scn_tc['B14'][::stride, ::stride].compute()

            from satpy.writers import get_enhanced_image
            img_day = get_enhanced_image(tc_data)
            pil_img_day = img_day.pil_image()
            
            img_ir = get_enhanced_image(ir_data)
            pil_img_ir = img_ir.pil_image().convert("RGB")

            old_area = tc_data.attrs['area']
            new_area = AreaDefinition(old_area.area_id, old_area.description, old_area.proj_id, old_area.crs, pil_img_day.width, pil_img_day.height, old_area.area_extent)

            pil_img = pil_img_day # 預設為全白天
            ir_final = pil_img_ir

            if has_shapefiles:
                cw = ContourWriterPIL(shapefile_dir)
                
                # 1. 製作陸地遮罩
                land_mask = Image.new('L', pil_img_day.size, 0)
                shapefile_path = os.path.join(shapefile_dir, f'GSHHS_{res_code}_L1.shp')
                try:
                    cw.add_shapefile_shapes(land_mask, new_area, shapefile_path, fill=255)
                    # 2. 將夜晚紅外線影像的「陸地區域」染成暗紅色 (雲的數值極亮不受影響)
                    red_tint = Image.new("RGB", pil_img_ir.size, (100, 30, 30))
                    ir_tinted = ImageChops.lighter(pil_img_ir, red_tint)
                    ir_final = Image.composite(ir_tinted, pil_img_ir, land_mask)
                except Exception:
                    pass

            # 3. 日夜無縫融合 (取白天與夜晚兩張圖的最亮值)
            pil_img = ImageChops.lighter(pil_img_day, ir_final)

            if has_shapefiles:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12 if region_name == 'taiwan' else 14)
                except Exception:
                    font = None

                if region_name == 'taiwan':
                    grid_space = (2, 2)
                elif region_name == 'asia':
                    grid_space = (10, 10)
                else:
                    grid_space = (30, 30)

                cw.add_coastlines(pil_img, new_area, resolution=res_code, outline='yellow')
                cw.add_borders(pil_img, new_area, resolution=res_code, outline='cyan', level=1)
                cw.add_grid(pil_img, new_area, grid_space, grid_space, outline='yellow', width=1, write_text=True, font=font, text_color='yellow')

            # 儲存帶時間戳記的檔案
            timestamp_dir = os.path.join(STATIC_DIR, timestamp_str)
            front_timestamp_dir = os.path.join(FRONTEND_STATIC_DIR, timestamp_str)
            os.makedirs(timestamp_dir, exist_ok=True)
            os.makedirs(front_timestamp_dir, exist_ok=True)

            filename_tc = f"himawari_true_color_{region_name}.webp"
            path_tc = os.path.join(timestamp_dir, filename_tc)
            pil_img.save(path_tc, format="WEBP", quality=85)

            # 🔥 核心防護：另外複製一份並覆蓋成「固定檔名最新圖」
            latest_filename_tc = f"latest_{region_name}_color.webp"
            shutil.copy(path_tc, os.path.join(STATIC_DIR, latest_filename_tc))
            
            # 同步複製到前端靜態目錄
            shutil.copy(path_tc, os.path.join(front_timestamp_dir, filename_tc))
            shutil.copy(path_tc, os.path.join(FRONTEND_STATIC_DIR, latest_filename_tc))

            result = f"/static/images/{timestamp_str}/{filename_tc}"
            del local_scn_tc, scn_tc

        elif mode == "ir":
            print(f"[{region_name}] 正在載入紅外線波段...")
            ir_files = [f for f in files if '_B14_' in f]
            scn_ir = Scene(filenames=ir_files, reader=reader)
            scn_ir.load(['B14'])

            local_scn_ir = scn_ir.crop(ll_bbox=bbox) if bbox else scn_ir
            ir = local_scn_ir['B14'].data
            old_area = local_scn_ir['B14'].attrs['area']
            ir_stride = 2 if region_name == "global" else 1
            ir = ir[::ir_stride, ::ir_stride]

            def process_ir_block(arr):
                arr = arr.astype(np.float32, copy=False)
                np.nan_to_num(arr, copy=False, nan=273.15)
                np.clip(arr, 180.0, 310.0, out=arr)
                arr -= 310.0
                arr /= -130.0
                arr *= 255.0
                np.clip(arr, 0, 255, out=arr)
                return IR_LUT[arr.astype(np.int32)]

            ir_rgb_da = ir.map_blocks(process_ir_block, dtype=np.uint8, new_axis=[2], chunks=tuple(ir.chunks) + ((3,),))
            ir_rgb_np = ir_rgb_da.compute()
            pil_img_ir = Image.fromarray(ir_rgb_np)

            new_area_ir = AreaDefinition(old_area.area_id, old_area.description, old_area.proj_id, old_area.crs, pil_img_ir.width, pil_img_ir.height, old_area.area_extent)

            if has_shapefiles:
                cw = ContourWriterPIL(shapefile_dir)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12 if region_name == 'taiwan' else 14)
                except Exception:
                    font = None

                if region_name == 'taiwan':
                    grid_space = (2, 2)
                elif region_name == 'asia':
                    grid_space = (10, 10)
                else:
                    grid_space = (30, 30)

                cw.add_coastlines(pil_img_ir, new_area_ir, resolution=res_code, outline='yellow')
                cw.add_borders(pil_img_ir, new_area_ir, resolution=res_code, outline='cyan', level=1)
                cw.add_grid(pil_img_ir, new_area_ir, grid_space, grid_space, outline='yellow', width=1, write_text=True, font=font, text_color='yellow')

            # 儲存帶時間戳記的檔案
            timestamp_dir = os.path.join(STATIC_DIR, timestamp_str)
            front_timestamp_dir = os.path.join(FRONTEND_STATIC_DIR, timestamp_str)
            os.makedirs(timestamp_dir, exist_ok=True)
            os.makedirs(front_timestamp_dir, exist_ok=True)

            filename_ir = f"himawari_ir_{region_name}.webp"
            path_ir = os.path.join(timestamp_dir, filename_ir)
            pil_img_ir.save(path_ir, format="WEBP", quality=85)

            # 🔥 核心防護：另外複製一份並覆蓋成「固定檔名最新圖」
            latest_filename_ir = f"latest_{region_name}_ir.webp"
            shutil.copy(path_ir, os.path.join(STATIC_DIR, latest_filename_ir))
            
            # 同步複製到前端靜態目錄
            shutil.copy(path_ir, os.path.join(front_timestamp_dir, filename_ir))
            shutil.copy(path_ir, os.path.join(FRONTEND_STATIC_DIR, latest_filename_ir))

            result = f"/static/images/{timestamp_str}/{filename_ir}"
            del ir_rgb_np, ir_rgb_da, ir, local_scn_ir, scn_ir

        gc.collect()
        return {"path": result, "timestamp": timestamp_str}

    except Exception as e:
        print(f"[{region_name} - {mode}] 解析錯誤: {e}")
        return None

def process_taiwan_view(files, mode):
    # CWB Taiwan bounds are approximately: 117E to 125E, 20N to 27N
    return process_view(files, "taiwan", (117, 20, 125, 27), mode)

def process_asia_view(files, mode):
    # CWB Asia bounds are approximately: 100E to 145E, 0N to 45N
    return process_view(files, "asia", (100, 0, 145, 45), mode)

def process_global_view(files, mode):
    return process_view(files, "global", None, mode)
