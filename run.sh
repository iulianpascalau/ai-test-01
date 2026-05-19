#!/bin/bash
# run.sh
# Pulls latest code, builds frontend, sets up backend, and configures systemd daemons.

set -e

echo "1. Pulling latest release tag..."
git fetch --tags origin || echo "Warning: git fetch failed or not a git repository."
LATEST_TAG=$(git describe --tags $(git rev-list --tags --max-count=1) 2>/dev/null || true)
if [ -n "$LATEST_TAG" ]; then
    echo "Checking out latest tag: $LATEST_TAG"
    git checkout "$LATEST_TAG" || echo "Warning: git checkout failed."
else
    echo "Warning: No tags found. Continuing deployment with current state..."
fi

echo "2. Setting up backend..."
cd backend
# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
pip install -r ../requirements.txt
cd ..

echo "3. Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "4. Installing 'serve' to host the React frontend..."
sudo npm install -g serve

echo "5. Configuring SystemD Daemons..."
PROJECT_DIR=$(pwd)
USER_NAME=$USER

# Backend Service
cat <<EOF | sudo tee /etc/systemd/system/agent-backend.service
[Unit]
Description=Agentic Workspace FastAPI Backend
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
EOF

# Frontend Service
cat <<EOF | sudo tee /etc/systemd/system/agent-frontend.service
[Unit]
Description=Agentic Workspace React Frontend
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR/frontend
ExecStart=/usr/bin/npx serve -s dist -l 5173

[Install]
WantedBy=multi-user.target
EOF

echo "6. Reloading systemd and restarting daemons..."
sudo systemctl daemon-reload

sudo systemctl stop agent-backend || true
sudo systemctl stop agent-frontend || true

sudo systemctl enable agent-backend
sudo systemctl enable agent-frontend

sudo systemctl start agent-backend
sudo systemctl start agent-frontend

echo "=========================================================="
echo "Deployment complete!"
echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"
echo "Check statuses with: sudo systemctl status agent-backend"
echo "=========================================================="
