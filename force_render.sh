#!/bin/bash
set -e

# This script pauses normal operations and runs the unlimited map generator
echo "=================================================="
echo "🚀 INITIATING LIVE PUZZLE HD MAP RENDERING 🚀"
echo "=================================================="

echo "1. Pausing Himawari cron schedules..."
crontab -l 2>/dev/null | grep -v "run_satellite.sh" | crontab -

echo "2. Stopping any currently running satellite activities..."
pkill -f "main.py" || echo "No satellite tasks were running."

echo "3. Starting Unlimited Map Generator in the background..."
export PYTHONPATH="$HOME/KKweather"
source "$HOME/KKweather/venv/bin/activate"

# Run it in nohup so it doesn't stop when SSH disconnects
nohup python "$HOME/KKweather/backend/map_generator.py" --unlimited > "/home/kai1010210/satellite.log" 2>&1 &

echo ""
echo "✅ Render triggered successfully!"
echo "The generator is now running non-stop. It will download the map puzzle piece by piece directly into the live folder."
echo ""
echo "To watch the live progress log, run:"
echo "  tail -f ~/KKweather/hd_map_render.log"
echo ""
echo "Once the rendering is completely finished (it might take a long time!),"
echo "simply run 'bash ~/KKweather/setup_repo.sh' to restore the standard Himawari cronjobs."
