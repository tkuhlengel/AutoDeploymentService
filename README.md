# Gitea Webhook Auto-updater

A lightweight systemd service that receives webhooks from Gitea and automatically updates your repository when changes are pushed.

## Features

- **Smart Pull Logic**: Only performs `git pull` when the currently checked out branch is updated; performs `git fetch` for other branches
- **Webhook Security**: Validates Gitea webhook signatures using HMAC-SHA256
- **Automatic Deployment**: Runs deployment script after successful pull
- **Systemd Integration**: Runs as a reliable system service with automatic restarts
- **Comprehensive Logging**: Logs to both systemd journal and file

## How It Works

1. Gitea sends a webhook when code is pushed to any branch
2. The service receives the webhook and validates the signature
3. The service checks which branch was updated
4. If the updated branch matches the currently checked-out branch:
   - Runs `git pull` in the repository
   - Executes the deployment script via sudo
5. If a different branch was updated:
   - Runs `git fetch` to update remote tracking branches

## Files Included

- **`webhook_server.py`** - Main Flask application that handles webhooks
- **`pyproject.toml`** - UV project configuration
- **`.env.example`** - Example environment configuration
- **`install.sh`** - Main installation script
- **`generate_service.sh`** - Generates systemd service file from .env
- **`configure_sudo.sh`** - Configures passwordless sudo from .env
- **`README.md`** - This documentation

## Prerequisites

- Ubuntu/Debian Linux system
- Python 3.8 or higher
- Git repository cloned to `/home/trevor/ManagedFileTransfer`
- Gitea server with admin access to configure webhooks
- User `trevor` with appropriate permissions

## Installation

### 1. Transfer Files to Remote Server

Copy the `AutoDeploymentService` directory to your remote server:

```bash
scp -r AutoDeploymentService trevor@mftserver.kuhlengel.internal:~/
```

### 2. Edit the `.env` File
On the remote server, navigate to the `AutoDeploymentService` directory and edit the `.env` file:

```bash
cd ~/AutoDeploymentService
cp .env.example .env
vim .env
```
Update the variables as needed, especially `WEBHOOK_SECRET` and `INSTALL_DIR`.

### 3. Run Installation Script

SSH into the remote server and run the installation script:

```bash
ssh trevor@mftserver.kuhlengel.internal
cd ~/AutoDeploymentService
./install.sh
```

The script will:
- Install UV (if not already present)
- Create `/home/trevor/autoupdater` directory
- Copy necessary files
- Install Python dependencies
- Create log directory
- Install systemd service

### 3. Configure Environment

Edit the configuration file:

```bash
nano /home/trevor/autoupdater/.env
```

**Generate a secure webhook secret:**

```bash
openssl rand -hex 32
```

Update the `.env` file with your webhook secret and verify all paths are correct:

```env
WEBHOOK_SECRET=your_generated_secret_here
PORT=9000
REPO_PATH=/home/trevor/ManagedFileTransfer
UPDATE_SCRIPT=/home/trevor/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
LOG_DIR=/home/trevor/.local/log/autoupdater
```

### 4. Configure Passwordless Sudo

The service needs to run the deployment script with sudo privileges. Use the provided helper script:

```bash
cd /home/trevor/autoupdater
./configure_sudo.sh
```

This script will:
- Read the UPDATE_SCRIPT path from your .env file
- Create a sudoers configuration file for the current user
- Validate the configuration
- Show you what commands can now be run without a password

**Manual Configuration (Alternative)**

If you prefer to configure manually:

```bash
sudo visudo -f /etc/sudoers.d/autoupdater
```

Add the following line:

```
trevor ALL=(ALL) NOPASSWD: /home/trevor/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

Save and exit.

### 5. Configure Firewall (if applicable)

If you have a firewall enabled, allow incoming connections on port 9000:

```bash
sudo ufw allow 9000/tcp
sudo ufw status
```

### 6. Start the Service

Enable and start the autoupdater service:

```bash
sudo systemctl enable autoupdater
sudo systemctl start autoupdater
```

Check the service status:

```bash
sudo systemctl status autoupdater
```

You should see "active (running)" status.

## Configure Gitea Webhook

### 1. Access Webhook Settings

1. Log into your Gitea server
2. Navigate to your repository
3. Go to **Settings** → **Webhooks**
4. Click **Add Webhook** → **Gitea**

### 2. Configure Webhook

Fill in the webhook configuration:

- **Target URL**: `http://mftserver.kuhlengel.internal:9000/webhook`
- **HTTP Method**: `POST`
- **POST Content Type**: `application/json`
- **Secret**: Enter the same secret you configured in `.env`
- **Trigger On**: Select "Push events"
- **Branch filter**: Leave empty (or specify `develop` if you want to limit)
- **Active**: ✓ Checked

### 3. Test Webhook

Click **Test Delivery** to send a test webhook. Check the service logs to verify it was received:

```bash
journalctl -u autoupdater -n 50
```

## Helper Scripts

### `generate_service.sh`

Generates a systemd service file customized to your environment:

```bash
cd /home/trevor/autoupdater
./generate_service.sh
```

This script:
- Reads configuration from `.env`
- Detects the current user and group
- Finds the UV installation path
- Creates `autoupdater.service` with correct paths
- Shows you the generated service file

**When to use**: 
- Initial setup (automatically called by `install.sh`)
- After moving the installation to a different directory
- After changing users
- To regenerate the service file for any reason

### `configure_sudo.sh`

Configures passwordless sudo for the deployment script:

```bash
cd /home/trevor/autoupdater
./configure_sudo.sh
```

This script:
- Reads UPDATE_SCRIPT from `.env`
- Creates `/etc/sudoers.d/autoupdater` with proper permissions
- Validates the sudoers configuration
- Confirms successful setup

**When to use**:
- After initial installation
- After changing the UPDATE_SCRIPT path in `.env`
- To re-verify sudo configuration

## Usage

Once configured, the service runs automatically. Whenever you push to your repository:

1. Gitea sends a webhook to the service
2. The service checks if the pushed branch matches the checked-out branch
3. If it matches, it pulls changes and runs the deployment script
4. All actions are logged

## Monitoring

### View Real-time Logs

**Systemd journal:**
```bash
journalctl -u autoupdater -f
```

**Log file:**
```bash
tail -f /home/trevor/.local/log/autoupdater/autoupdater.log
```

### Check Service Status

```bash
sudo systemctl status autoupdater
```

### View Recent Activity

```bash
journalctl -u autoupdater -n 100 --no-pager
```

## Troubleshooting

### Service Won't Start

**Check service status:**
```bash
sudo systemctl status autoupdater
journalctl -u autoupdater -n 50
```

**Common issues:**
- Missing `.env` file
- Invalid configuration in `.env`
- Port 9000 already in use
- UV not in PATH

### Webhooks Not Being Received

**Test the endpoint manually:**
```bash
curl http://localhost:9000/health
```

Should return:
```json
{"status":"healthy","timestamp":"..."}
```

**Check firewall:**
```bash
sudo ufw status
```

**Verify Gitea can reach the server:**
```bash
# From Gitea server
curl http://mftserver.kuhlengel.internal:9000/health
```

### Git Pull Fails

**Check repository permissions:**
```bash
ls -la /home/trevor/ManagedFileTransfer
```

**Verify git is configured:**
```bash
cd /home/trevor/ManagedFileTransfer
git status
git remote -v
```

**Check for merge conflicts:**
```bash
cd /home/trevor/ManagedFileTransfer
git status
```

### Deployment Script Fails

**Test sudo access:**
```bash
sudo /home/trevor/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

**Check script permissions:**
```bash
ls -l /home/trevor/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

**Review script output in logs:**
```bash
journalctl -u autoupdater -n 100 | grep -A 20 "Running update script"
```

### Signature Verification Fails

**Verify webhook secret matches:**
1. Check `.env` file: `cat /home/trevor/autoupdater/.env`
2. Compare with Gitea webhook configuration
3. Restart service after changing: `sudo systemctl restart autoupdater`

## Management Commands

### Restart Service
```bash
sudo systemctl restart autoupdater
```

### Stop Service
```bash
sudo systemctl stop autoupdater
```

### Disable Service
```bash
sudo systemctl disable autoupdater
```

### Reload Configuration
After changing `.env`:
```bash
sudo systemctl restart autoupdater
```

### View Service Configuration
```bash
systemctl cat autoupdater
```

## Updating the Autoupdater

To update the autoupdater itself:

1. Make changes to the files on your local machine
2. Copy updated files to the server:
   ```bash
   scp webhook_server.py trevor@mftserver.kuhlengel.internal:~/autoupdater/
   ```
3. Restart the service:
   ```bash
   ssh trevor@mftserver.kuhlengel.internal
   sudo systemctl restart autoupdater
   ```

## Security Considerations

- **Webhook Secret**: Always use a strong, randomly generated secret
- **HTTPS**: Consider using HTTPS with a reverse proxy (nginx/caddy) in production
- **Firewall**: Restrict access to port 9000 to your Gitea server IP only
- **Sudo Access**: The service has limited sudo access only to the specific deployment script
- **Service Hardening**: The systemd service includes security hardening options

## Uninstallation

To remove the autoupdater:

```bash
# Stop and disable service
sudo systemctl stop autoupdater
sudo systemctl disable autoupdater

# Remove service file
sudo rm /etc/systemd/system/autoupdater.service
sudo systemctl daemon-reload

# Remove installation directory
rm -rf /home/trevor/autoupdater

# Remove logs
rm -rf /home/trevor/.local/log/autoupdater

# Remove sudo configuration
sudo rm /etc/sudoers.d/autoupdater
```

## Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Gitea     │ Push    │   Autoupdater    │ Pull    │  Git Repository │
│   Server    ├────────>│   Webhook        ├────────>│   (develop)     │
│             │ Webhook │   Service        │         │                 │
└─────────────┘         └────────┬─────────┘         └─────────────────┘
                                 │
                                 │ Runs
                                 v
                        ┌────────────────┐
                        │   Deployment   │
                        │     Script     │
                        └────────────────┘
```

## License

This autoupdater is provided as-is for the ManagedFileTransfer project.

## Support

For issues or questions, check the logs first:
- `/home/trevor/.local/log/autoupdater/autoupdater.log`
- `journalctl -u autoupdater`
