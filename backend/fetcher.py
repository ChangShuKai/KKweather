import os
import boto3
from datetime import datetime, timedelta, timezone
import concurrent.futures
import bz2

AWS_BUCKET = 'noaa-himawari9'
DATA_PREFIX = 'AHI-L1b-FLDK'  # Often L1b FLDK
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def find_latest_prefix():
    s3 = boto3.client('s3', config=boto3.session.Config(signature_version=boto3.session.botocore.UNSIGNED))
    now = datetime.now(timezone.utc)
    times_to_check = [now, now - timedelta(hours=1)]
    latest_prefix = None
    
    for t in times_to_check:
        date_prefix = f"{DATA_PREFIX}/{t.strftime('%Y/%m/%d')}/"
        resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=date_prefix, Delimiter='/')
        prefixes = resp.get('CommonPrefixes', [])
        if prefixes:
            sorted_prefixes = sorted([p['Prefix'] for p in prefixes], reverse=True)
            for p in sorted_prefixes:
                f_resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=p)
                if 'Contents' in f_resp and len(f_resp['Contents']) > 0:
                    latest_prefix = p
                    break
        if latest_prefix:
            break
            
    return latest_prefix

def fetch_segments(prefix, segments=None):
    if not prefix:
        return []
        
    s3 = boto3.client('s3', config=boto3.session.Config(signature_version=boto3.session.botocore.UNSIGNED))
    resp = s3.list_objects_v2(Bucket=AWS_BUCKET, Prefix=prefix)
    all_files = [item['Key'] for item in resp.get('Contents', [])]
    
    # Filter for the bands we need (01, 02, 03, 04, 14)
    target_bands = ['B01', 'B02', 'B03', 'B04', 'B14']
    files_to_download = []
    
    for band in target_bands:
        for f in all_files:
            if band in f:
                if segments is None or any(seg in f for seg in segments):
                    files_to_download.append(f)
                
    downloaded_paths = []
    
    def download_single_file(f):
        filename = os.path.basename(f)
        local_bz2_path = os.path.join(DOWNLOAD_DIR, filename)
        uncompressed_path = local_bz2_path.replace('.bz2', '')
        
        if not os.path.exists(uncompressed_path):
            if not os.path.exists(local_bz2_path):
                print(f"Downloading {filename}...")
                from boto3.s3.transfer import TransferConfig
                config = TransferConfig(max_concurrency=1)
                s3.download_file(AWS_BUCKET, f, local_bz2_path, Config=config)
            
            print(f"Decompressing {filename}...")
            with bz2.BZ2File(local_bz2_path, 'rb') as source, open(uncompressed_path, 'wb') as dest:
                # Read in chunks to avoid memory spikes
                for data in iter(lambda: source.read(100 * 1024), b''):
                    dest.write(data)
            
            if os.path.exists(local_bz2_path):
                os.remove(local_bz2_path)
        else:
            print(f"File {filename} already decompressed, skipping.")
            
        return uncompressed_path

    # Use 4 threads to fetch and decompress in parallel to avoid OOM on 512MB limit
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
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
    prefix = find_latest_prefix()
    print("最新 Prefix 基地位置:", prefix)
    
    # 💡 終極修正：不要寫死 _S0310.，只要包含 _S03（第三分段）就全抓！
    # 這樣不管後面是 09 還是 10，都能保證 100% 抓到當下最新的即時影像！
    files = fetch_segments(prefix, ['_S03'])
    print("成功抓取最新衛星檔案清單:", files)