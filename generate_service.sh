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

# Validate webhook_server.py exists
if [ ! -f "$SCRIPT_DIR/webhook_server.py" ]; then
    echo "Error: webhook_server.py not found at $SCRIPT_DIR/webhook_server.py"
    exit 1
fi

# Validate log directory can be created
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    echo "Warning: Cannot create log directory at $LOG_DIR"
    echo "Make sure you have write permissions or the service will fail to start"
fi

# Validate repo path exists
if [ ! -d "$REPO_PATH" ]; then
    echo "Warning: Repository path $REPO_PATH does not exist"
    echo "The service may fail to operate correctly"
fi

# Generate the service file content
SERVICE_FILE="$SCRIPT_DIR/autodeployment.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Gitea Webhook Auto-Deployment Service
After=network.target network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=300

[Service]
Type=simple
User=$CURRENT_USER
Group=$USER_GROUP
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=uv run $INSTALL_DIR/webhook_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=autodeployment

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictSUIDSGID=true
RestrictNamespaces=true
LockPersonality=true
ReadWritePaths=$LOG_DIR $REPO_PATH $HOME/.cache/uv $INSTALL_DIR

# Resource limits
MemoryMax=512M
TasksMax=50

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
echo "  sudo systemctl enable autodeployment"
echo "  sudo systemctl start autodeployment"
echo ""
echo "To check status:"
echo "  sudo systemctl status autodeployment"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u autodeployment -f"
