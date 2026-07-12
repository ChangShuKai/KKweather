from backend.fetcher import get_latest_files
from backend.processor import process_taiwan_view

files = get_latest_files()
print("Files downloaded and decompressed:", len(files))
res = process_taiwan_view(files)
print("Result:", res)
