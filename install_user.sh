#!/bin/bash
set -e

echo "============================================"
echo "Gitea Webhook Auto-updater Installation"
echo "         (User Mode - systemctl --user)"
echo "============================================"
echo ""

# Refuse to run as root — user-mode services run under a regular account
if [ "$(whoami)" == "root" ]; then
    echo "Error: This script must not be run as root."
    echo "User-mode services run under your regular account."
    exit 1
fi

# Require .env
if [ ! -f .env ]; then
    echo "Error: .env file not found in the current directory"
    echo "Please create the .env file before running this script."
    echo "Hint: You can copy from .env.example and modify as needed."
    exit 1
fi

# Source configuration
source .env
SOURCE_DIR="$(pwd)"

# Override SYSTEMD_DIR to user-mode path regardless of .env value
SYSTEMD_DIR="$HOME/.config/systemd/user"

# ── Step 0: Ensure UV is installed ──────────────────────────────
echo "Step 0: Checking for UV..."
if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "UV installed successfully"
else
    echo "UV is already installed"
fi

# ── Step 1: Create install directory ────────────────────────────
echo "Step 1: Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# ── Step 2: Copy application files ─────────────────────────────
echo "Step 2: Copying files to $INSTALL_DIR..."
cp webhook_server.py "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"
cp generate_service.sh "$INSTALL_DIR/"
cp configure_sudo.sh "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/webhook_server.py"
chmod +x "$INSTALL_DIR/generate_service.sh"
chmod +x "$INSTALL_DIR/configure_sudo.sh"

# ── Step 3: Write expanded .env into install dir ────────────────
echo "Step 3: Setting up configuration..."
sed "s|\${HOME}|$HOME|g; s|\$HOME|$HOME|g" .env > "$INSTALL_DIR/.env"
echo "Created .env file at $INSTALL_DIR/.env"

# ── Step 4: Create log directory ────────────────────────────────
echo "Step 4: Creating log directory..."
mkdir -p "$LOG_DIR"

# ── Step 5: Install Python deps ────────────────────────────────
echo "Step 5: Installing Python dependencies with UV..."
(cd "$INSTALL_DIR" && uv sync)
echo "Dependencies installed successfully"

# ── Step 6: Generate user-mode service file ─────────────────────
echo "Step 6: Generating systemd user service file..."
"$SOURCE_DIR/generate_service.sh" --user

# ── Step 7: Install to user systemd ────────────────────────────
echo "Step 7: Installing systemd user service..."
mkdir -p "$SYSTEMD_DIR"
cp "$SOURCE_DIR/autodeployment.service" "$SYSTEMD_DIR/"
systemctl --user daemon-reload

# Stop existing instance if running (ignore errors)
systemctl --user stop autodeployment.service 2>/dev/null || true
systemctl --user start autodeployment.service || true

# ── Step 8: Enable linger so the service survives logout ────────
echo "Step 8: Enabling lingering for user $(whoami)..."
if command -v loginctl &> /dev/null; then
    # loginctl enable-linger may require polkit or sudo depending on distro
    if loginctl enable-linger "$(whoami)" 2>/dev/null; then
        echo "Linger enabled — service will run even when you are logged out"
    else
        echo "Warning: Could not enable linger automatically."
        echo "Run manually:  sudo loginctl enable-linger $(whoami)"
    fi
else
    echo "Warning: loginctl not found. Ensure linger is enabled for your user."
fi

# ── Step 9 (optional): Configure sudo for UPDATE_SCRIPT ────────
UPDATE_SCRIPT_NEEDS_SUDO="${UPDATE_SCRIPT_NEEDS_SUDO:-true}"
if [ "$UPDATE_SCRIPT_NEEDS_SUDO" = "true" ]; then
    echo ""
    echo "Step 9: Configuring passwordless sudo for UPDATE_SCRIPT..."
    echo "  The deployment script ($UPDATE_SCRIPT) will be called with sudo."
    echo "  This requires a one-time sudoers configuration (needs root)."
    "$INSTALL_DIR/configure_sudo.sh"
else
    echo ""
    echo "Step 9: Skipping sudo configuration (UPDATE_SCRIPT_NEEDS_SUDO=false)"
fi

echo ""
echo "============================================"
echo "User-Mode Installation Complete!"
echo "============================================"
echo ""
echo "Useful commands:"
echo "  Enable on boot:   systemctl --user enable autodeployment"
echo "  Start service:    systemctl --user start autodeployment"
echo "  Stop service:     systemctl --user stop autodeployment"
echo "  Check status:     systemctl --user status autodeployment"
echo "  View logs:        journalctl --user -u autodeployment -f"
echo "                    tail -f $LOG_DIR/autodeploymentservice.log"
echo ""
echo "Note: Linger must be enabled for the service to run without an active login session."
echo "  Verify:  loginctl show-user $(whoami) | grep Linger"
echo "  Enable:  sudo loginctl enable-linger $(whoami)"
echo ""
