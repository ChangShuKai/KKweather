#!/bin/bash
set -e

REPO_URL="https://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@github.com/ChangShuKai/KKweather.git"
WORK_DIR="$HOME/KKweather"

# 1. Clone or Update the repository
if [ ! -d "$WORK_DIR/.git" ]; then
    git clone "$REPO_URL" "$WORK_DIR"
else
    cd "$WORK_DIR"
    git remote set-url origin "$REPO_URL"
    git pull origin main
fi

cd "$WORK_DIR"

# Configure Git
git config user.email "action@github.com"
git config user.name "GCP Worker Bot"

# 2. Setup Python Virtual Environment using pyenv's Python 3.11.9
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

if [ ! -d "$WORK_DIR/venv" ]; then
    ~/.pyenv/versions/3.11.9/bin/python -m venv "$WORK_DIR/venv"
fi

# Activate and install dependencies
source "$WORK_DIR/venv/bin/activate"
python -m pip install --upgrade pip
pip install numpy pillow webp requests psutil satpy pyresample pycoast dask pykdtree xarray h5netcdf netCDF4 matplotlib scipy boto3 pyspectral pyorbital

# 3. Create run_satellite.sh
cat << 'EOF' > "$HOME/run_satellite.sh"
#!/bin/bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

cd "$HOME/KKweather"
source venv/bin/activate
export PYTHONPATH="$HOME/KKweather"

# 1. Pull latest code
git pull --rebase --autostash origin main

# 2. Setup shapefiles if missing
mkdir -p backend/shapefiles
cd backend/shapefiles
if [ ! -f "GSHHS_c_L1.shp" ]; then
  curl -sL http://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.3.7.zip -o gshhg.zip
  unzip -qo gshhg.zip
  find . -name "*.shp" -o -name "*.shx" -o -name "*.dbf" -o -name "*.prj" -exec mv {} . \;
  rm -rf GSHHS_shp WDBII_shp gshhg.zip
fi
cd ../..

# 3. Check if we should pause Himawari for HD map generation
CURRENT_HOUR=$(date +"%H")
CURRENT_DOW=$(date +"%u") # 1=Mon, 7=Sun
IS_MAP_WINDOW=0

# Everyday 00:00 - 06:00
if [ "$CURRENT_HOUR" -ge 0 ] && [ "$CURRENT_HOUR" -lt 6 ]; then
  IS_MAP_WINDOW=1
# Mon-Fri 09:00 - 15:00
elif [ "$CURRENT_DOW" -le 5 ] && [ "$CURRENT_HOUR" -ge 9 ] && [ "$CURRENT_HOUR" -lt 15 ]; then
  IS_MAP_WINDOW=1
fi

if [ "$IS_MAP_WINDOW" -eq 1 ]; then
  echo "HD Map rendering window active. Skipping Himawari fetch to render Global HD Map."
  python backend/map_generator.py || true
  exit 0
fi

# 4. Run the generator
python backend/main.py

# 5. Commit and push
mkdir -p backend/static/images
mkdir -p frontend/static/images
git add --all backend/static/images/ || true
git add --all frontend/static/images/ || true
git add backend/latest.json || true

git diff --cached --quiet || git commit -m "🤖 自動更新【台灣/亞洲/全景】衛星圖 (from GCP)"
git push origin main || true
EOF

chmod +x "$HOME/run_satellite.sh"

# 4. Setup Crontab
(crontab -l 2>/dev/null | grep -v "run_satellite.sh"; echo "*/10 * * * * /bin/bash $HOME/run_satellite.sh >> $HOME/satellite.log 2>&1") | crontab -

echo "Setup completed successfully!"
