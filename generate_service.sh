#!/bin/bash
set -e

USER_MODE=false
if [ "$1" = "--user" ]; then
    USER_MODE=true
fi

if [ "$USER_MODE" = true ]; then
    echo "============================================"
    echo "Generate Systemd User Service File"
    echo "============================================"
else
    echo "============================================"
    echo "Generate Systemd Service File"
    echo "============================================"
fi
echo ""

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
echo "  Mode: $([ "$USER_MODE" = true ] && echo "user" || echo "system")"
echo "  User: $CURRENT_USER"
echo "  Group: $USER_GROUP"
echo "  Working Directory: $SCRIPT_DIR"
echo "  Repository Path: $REPO_PATH"
echo "  Log Directory: $LOG_DIR"
echo "  Port: $PORT"
echo ""

PYTHON_PATH="$INSTALL_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_PATH" ] && [ ! -L "$PYTHON_PATH" ]; then
    echo "Warning: Python interpreter not found at $PYTHON_PATH"
    echo "Make sure 'uv sync' has been run in $INSTALL_DIR to create the virtualenv"
fi

echo "Python Path: $PYTHON_PATH"
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

SERVICE_FILE="$SCRIPT_DIR/autodeployment.service"

HARDEN=false
if [ "$USER_MODE" = false ]; then
    echo "Security hardening restricts the service's filesystem and kernel access."
    echo "Recommended for production. Requires ReadWritePaths for $LOG_DIR, $REPO_PATH, $INSTALL_DIR."
    echo ""
    read -p "Enable security hardening? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        HARDEN=true
    fi
    echo ""
fi

HARDENING_BLOCK=""
if [ "$HARDEN" = true ]; then
    HARDENING_BLOCK="
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
ReadWritePaths=$LOG_DIR $REPO_PATH $INSTALL_DIR"
fi

if [ "$USER_MODE" = true ]; then
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Gitea Webhook Auto-Deployment Service
After=network.target network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=300

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$PYTHON_PATH $INSTALL_DIR/webhook_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=autodeployment

MemoryMax=512M
TasksMax=50

[Install]
WantedBy=default.target
EOF
else
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
ExecStart=$PYTHON_PATH $INSTALL_DIR/webhook_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=autodeployment
${HARDENING_BLOCK}

MemoryMax=512M
TasksMax=50

[Install]
WantedBy=multi-user.target
EOF
fi

echo "✓ Service file generated at: $SERVICE_FILE"
echo ""
echo "Service file contents:"
echo "----------------------------------------"
cat "$SERVICE_FILE"
echo "----------------------------------------"
echo ""

if [ "$USER_MODE" = true ]; then
    echo "To install this user service:"
    echo "  mkdir -p ~/.config/systemd/user"
    echo "  cp $SERVICE_FILE ~/.config/systemd/user/"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable autodeployment"
    echo "  systemctl --user start autodeployment"
    echo ""
    echo "To check status:"
    echo "  systemctl --user status autodeployment"
    echo ""
    echo "To view logs:"
    echo "  journalctl --user -u autodeployment -f"
else
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
fi
