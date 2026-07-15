#!/bin/bash
set -e

# This script pauses normal operations and runs the unlimited map generator
echo "=================================================="
echo "🚀 INITIATING LIVE PUZZLE HD MAP RENDERING 🚀"
echo "=================================================="

echo "Starting Unlimited Map Generator in the background..."
export PYTHONPATH="$HOME/KKweather"
source "$HOME/KKweather/venv/bin/activate"

# Run it in nohup so it doesn't stop when SSH disconnects
nohup python "$HOME/KKweather/backend/map_generator.py" --unlimited > "/home/kai1010210/satellite.log" 2>&1 &

echo ""
echo "✅ Render triggered successfully!"
echo "The generator is now running non-stop. It will download the map puzzle piece by piece directly into the live folder."
echo ""
echo "To watch the live progress log, run:"
echo "  tail -f /home/kai1010210/satellite.log"
echo ""
echo "Note: The Himawari satellite tracking is still running in the background simultaneously."
