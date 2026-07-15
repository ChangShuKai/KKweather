#!/bin/bash
set -e

WORK_DIR="$HOME/KKweather"

# Install fastapi and uvicorn
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

source "$WORK_DIR/venv/bin/activate"
pip install fastapi uvicorn

# Create systemd service
SERVICE_FILE="/etc/systemd/system/kkweather-status.service"
sudo bash -c "cat << 'EOF' > $SERVICE_FILE
[Unit]
Description=KKWeather Status API
After=network.target

[Service]
User=kai1010210
Group=kai1010210
WorkingDirectory=/home/kai1010210/KKweather
Environment=\"PATH=/home/kai1010210/KKweather/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
ExecStart=/home/kai1010210/KKweather/venv/bin/python gcp_status_api.py

[Install]
WantedBy=multi-user.target
EOF"

# Start and enable the service
sudo systemctl daemon-reload
sudo systemctl enable kkweather-status.service
sudo systemctl restart kkweather-status.service

# Allow port 8080 in ufw
sudo ufw allow 8080/tcp
