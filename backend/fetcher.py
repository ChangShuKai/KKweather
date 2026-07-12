import os
import boto3
from datetime import datetime, timedelta, timezone
import concurrent.futures

AWS_BUCKET = 'noaa-himawari9'
DATA_PREFIX = 'AHI-L1b-FLDK'  # Often L1b FLDK
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_latest_files():
    s3 = boto3.client('s3', config=boto3.session.Config(signature_version=boto3.session.botocore.UNSIGNED))
    
    # Check current time in UTC
    now = datetime.now(timezone.utc)
    
    # Try current hour and previous hour to find latest data
    times_to_check = [now, now - timedelta(hours=1)]
    
    latest_prefix = None
    
    for t in times_to_check:
        # AHI-L1b-FLDK/YYYY/MM/DD/HHMM/
        # Let's list by date
        date_prefix = f"{DATA_PREFIX}/{t.strftime('%Y/%m/%d')}/"
        resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=date_prefix, Delimiter='/')
        
        prefixes = resp.get('CommonPrefixes', [])
        if prefixes:
            # Sort prefixes (which contain the times) and get the latest
            sorted_prefixes = sorted([p['Prefix'] for p in prefixes], reverse=True)
            for p in sorted_prefixes:
                # Check if there are files in this prefix
                f_resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=p)
                if 'Contents' in f_resp and len(f_resp['Contents']) > 0:
                    latest_prefix = p
                    break
        if latest_prefix:
            break
            
    if not latest_prefix:
        print("No recent data found.")
        return []
        
    print(f"Latest prefix found: {latest_prefix}")
    
    # We want bands 1, 2, 3, 14
    # File format is typically: HS_H09_YYYYMMDD_HHMM_Bxx_FLDK_Rxx_Sxxxx.DAT
    # Or for NetCDF: maybe it's `.nc`
    
    resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=latest_prefix)
    all_files = [item['Key'] for item in resp.get('Contents', [])]
    
    # Filter for the bands we need (01, 02, 03, 14)
    target_bands = ['B01', 'B02', 'B03', 'B14']
    files_to_download = []
    
    for band in target_bands:
        for f in all_files:
            if band in f:
                files_to_download.append(f)
                
    downloaded_paths = []
    
    def download_single_file(f):
        filename = os.path.basename(f)
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        if not os.path.exists(local_path):
            print(f"Downloading {filename}...")
            s3.download_file(AWS_BUCKET, f, local_path)
        else:
            print(f"File {filename} already exists, skipping.")
        return local_path

    # Download concurrently using up to 10 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_single_file, f): f for f in files_to_download}
        for future in concurrent.futures.as_completed(futures):
            try:
                local_path = future.result()
                downloaded_paths.append(local_path)
            except Exception as exc:
                print(f"File download generated an exception: {exc}")
                
    # Sort paths to keep the original logical ordering
    downloaded_paths.sort()
        
    return downloaded_paths

if __name__ == '__main__':
    get_latest_files()
