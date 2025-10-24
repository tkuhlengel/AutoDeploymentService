#!/bin/bash
set -e

echo "============================================"
echo "Generate Systemd Service File"
echo "============================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Error: .env file not found at $SCRIPT_DIR/.env"
    echo "Please create the .env file before running this script."
    exit 1
fi

# Source the .env file
set -a
source "$SCRIPT_DIR/.env"
set +a

# Get current username
CURRENT_USER=$(whoami)

# Get the user's primary group
USER_GROUP=$(id -gn "$CURRENT_USER")

# Validate required variables
if [ -z "$REPO_PATH" ]; then
    echo "Error: REPO_PATH not set in .env file"
    exit 1
fi

if [ -z "$PORT" ]; then
    echo "Warning: PORT not set in .env file, using default 9000"
    PORT=9000
fi

if [ -z "$LOG_DIR" ]; then
    LOG_DIR="$HOME/.local/log/autoupdater"
    echo "Warning: LOG_DIR not set in .env file, using default $LOG_DIR"
fi

echo "Configuration:"
echo "  User: $CURRENT_USER"
echo "  Group: $USER_GROUP"
echo "  Working Directory: $SCRIPT_DIR"
echo "  Repository Path: $REPO_PATH"
echo "  Log Directory: $LOG_DIR"
echo "  Port: $PORT"
echo ""

# Determine UV path
UV_PATH=$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")
if [ ! -f "$UV_PATH" ] && [ ! -L "$UV_PATH" ]; then
    # Check if it's an alias by looking in common locations
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_PATH="$HOME/.local/bin/uv"
    else
        echo "Warning: Could not find uv binary, using default path"
        UV_PATH="$HOME/.local/bin/uv"
    fi
fi

echo "UV Path: $UV_PATH"
echo ""

# Generate the service file content
SERVICE_FILE="$SCRIPT_DIR/autoupdater.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Gitea Webhook Auto-updater Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$USER_GROUP
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$SCRIPT_DIR/.env
ExecStart=$UV_PATH run webhook_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=autoupdater

# Security hardening
NoNewPrivileges=false
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$LOG_DIR $REPO_PATH

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file generated at: $SERVICE_FILE"
echo ""
echo "Service file contents:"
echo "----------------------------------------"
cat "$SERVICE_FILE"
echo "----------------------------------------"
echo ""
echo "To install this service:"
echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable autoupdater"
echo "  sudo systemctl start autoupdater"
echo ""
echo "To check status:"
echo "  sudo systemctl status autoupdater"
