#!/bin/bash
set -e

echo "Starting deployment..."

# Navigate to project directory
cd /opt/voip-api

# Pull latest code (this happens via git hook, but just in case)
git fetch origin
git reset --hard origin/main

# Activate virtual environment
source venv/bin/activate

# Install/update Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Copy FreeSWITCH configs if they exist
if [ -d "freeswitch-config" ]; then
    echo "Updating FreeSWITCH configuration..."
    cp -r freeswitch-config/autoload_configs/* /etc/freeswitch/autoload_configs/
    
    # Reload FreeSWITCH config
    fs_cli -x "reloadxml" || echo "Could not reload FreeSWITCH (may not be running)"
fi

# Restart API service
echo "Restarting API service..."
systemctl restart voip-api

echo "Deployment complete!"