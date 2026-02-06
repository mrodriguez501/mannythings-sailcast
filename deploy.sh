#!/bin/bash
# ============================================
# SailCast Deployment Script
# Deploys to AWS Lightsail instance
# ============================================

set -e

echo "=== SailCast Deployment ==="

# Configuration
REMOTE_USER="ubuntu"
REMOTE_HOST="your-lightsail-ip"
REMOTE_DIR="/home/ubuntu/mannythings-sailcast"

# Build the React frontend
echo "[1/4] Building frontend..."
cd client
npm run build
cd ..

# Sync files to Lightsail
echo "[2/4] Syncing files to Lightsail..."
rsync -avz --exclude='node_modules' \
            --exclude='venv' \
            --exclude='.env' \
            --exclude='__pycache__' \
            --exclude='.git' \
            . ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/

# Install dependencies and restart on remote
echo "[3/4] Installing dependencies on remote..."
ssh ${REMOTE_USER}@${REMOTE_HOST} << 'EOF'
    cd /home/ubuntu/mannythings-sailcast/server
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
EOF

echo "[4/4] Restarting services..."
ssh ${REMOTE_USER}@${REMOTE_HOST} << 'EOF'
    sudo systemctl restart sailcast
    echo "SailCast service restarted"
EOF

echo "=== Deployment complete ==="
