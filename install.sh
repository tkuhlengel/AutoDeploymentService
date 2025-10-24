#!/bin/bash
set -e

echo "============================================"
echo "Gitea Webhook Auto-updater Installation"
echo "============================================"
echo ""

# Check if running as trevor user
if [ "$(whoami)" == "root" ]; then
    echo "Error: This script must not be run as root user"
    exit 1
fi

# Check if the .env file exists in the current directory
if [ ! -f .env ]; then
    echo "Error: .env file not found in the current directory"
    echo "Please create the .env file before running this script."
    echo "Hint: You can copy from .env.example and modify as needed."
    exit 1
fi

# Define paths
source .env
SOURCE_DIR="$(pwd)"
#INSTALL_DIR="/home/trevor/autoupdater"
#SERVICE_FILE="autoupdater.service"
#SYSTEMD_DIR="/etc/systemd/system"
#LOG_DIR="/home/trevor/.local/log/autoupdater"

# Check if UV is installed, if not, install it
echo "Step 0: Checking for UV..."
if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the profile to make uv available in current session
    export PATH="$HOME/.local/bin:$PATH"
    echo "UV installed successfully"
else
    echo "UV is already installed"
fi

echo "Step 1: Creating installation directory..."
mkdir -p "$INSTALL_DIR"

echo "Step 2: Copying files to $INSTALL_DIR..."
cp webhook_server.py "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"
cp generate_service.sh "$INSTALL_DIR/"
cp configure_sudo.sh "$INSTALL_DIR/"

# Make scripts executable
chmod +x "$INSTALL_DIR/webhook_server.py"
chmod +x "$INSTALL_DIR/generate_service.sh"
chmod +x "$INSTALL_DIR/configure_sudo.sh"

echo "Step 3: Setting up configuration..."
if [ -f "$INSTALL_DIR/.env" ]; then
    echo "Warning: .env file already exists at $INSTALL_DIR/.env"
    echo "Skipping .env creation. Please verify your configuration."
else
    # Since this is already required to run the install, we can copy it
    cp .env "$INSTALL_DIR/.env"
    echo "Created .env file at $INSTALL_DIR/.env"
    echo "IMPORTANT: Edit $INSTALL_DIR/.env and set your WEBHOOK_SECRET and other variables, then run this script again!"
fi

echo "Step 4: Creating log directory..."
mkdir -p "$LOG_DIR"

echo "Step 5: Installing Python dependencies with UV..."
cd "$INSTALL_DIR"
uv sync
echo "Dependencies installed successfully"

echo "Step 6: Generating systemd service file..."
cd "$(dirname "$0")"
./generate_service.sh

echo "Step 7: Installing systemd service..."
sudo systemctl stop autodeployment.service || true
echo "This step requires sudo privileges."
sudo cp "$SOURCE_DIR/autodeployment.service" "$SYSTEMD_DIR/"
sudo systemctl daemon-reload
sudo systemctl restart autodeployment.service || true

echo ""
echo "============================================"
echo "Installation Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Edit $INSTALL_DIR/.env and configure your WEBHOOK_SECRET"
echo "2. Verify all paths in $INSTALL_DIR/.env are correct"
echo "3. Configure passwordless sudo:"
echo "   cd $INSTALL_DIR && ./configure_sudo.sh"
echo "4. Enable and start the service:"
echo "   sudo systemctl enable autodeployment"
echo "   sudo systemctl start autodeployment"
echo "5. Check service status:"
echo "   sudo systemctl status autodeployment"
echo "6. View logs:"
echo "   journalctl -u autodeployment -f"
echo "   tail -f $LOG_DIR/autodeploymentservice.log"
echo ""
