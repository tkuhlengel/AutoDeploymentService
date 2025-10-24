#!/bin/bash
set -e

echo "============================================"
echo "Configure Passwordless Sudo"
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

# Validate required variables
if [ -z "$UPDATE_SCRIPT" ]; then
    echo "Error: UPDATE_SCRIPT not set in .env file"
    exit 1
fi

# Get current username
CURRENT_USER=$(whoami)

echo "Current user: $CURRENT_USER"
echo "Script to allow: $UPDATE_SCRIPT"
echo ""

# Check if the update script exists
if [ ! -f "$UPDATE_SCRIPT" ]; then
    echo "Warning: Update script not found at $UPDATE_SCRIPT"
    echo "The sudo configuration will still be created, but the script doesn't exist yet."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create sudoers configuration
SUDOERS_FILE="/etc/sudoers.d/autoupdater"
SUDOERS_CONTENT="# Allow $CURRENT_USER to run the autoupdater deployment script without password
$CURRENT_USER ALL=(ALL) NOPASSWD: $UPDATE_SCRIPT"

echo "Creating sudoers configuration..."
echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null

# Set correct permissions (sudoers files must be 0440)
sudo chmod 0440 "$SUDOERS_FILE"

# Validate the sudoers file
if sudo visudo -c -f "$SUDOERS_FILE"; then
    echo ""
    echo "✓ Sudoers configuration created successfully at $SUDOERS_FILE"
    echo ""
    echo "Verifying configuration..."
    sudo -l | grep -A 1 "may run the following" || true
    echo ""
    echo "You can now run the following command without a password:"
    echo "  sudo $UPDATE_SCRIPT"
else
    echo ""
    echo "Error: Sudoers configuration is invalid!"
    echo "Removing the configuration file..."
    sudo rm "$SUDOERS_FILE"
    exit 1
fi
