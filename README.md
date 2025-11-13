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
   - No deployment script is run

## Available Endpoints

The webhook server exposes the following endpoints:

- **POST `/webhook`** - Main webhook endpoint (recommended)
- **POST `/`** - Alternative webhook endpoint (also accepts webhooks)
- **GET `/health`** - Health check endpoint, returns service status

> **Webhook Compatibility:** Both `/webhook` and `/` accept POST requests with webhook payloads. Use whichever path your webhook provider is configured for.

## Files Included

- **`webhook_server.py`** - Main Flask application that handles webhooks
- **`pyproject.toml`** - UV project configuration
- **`.env.example`** - Example environment configuration
- **`install.sh`** - Main installation script
- **`generate_service.sh`** - Generates systemd service file from .env
- **`configure_sudo.sh`** - Configures passwordless sudo from .env
- **`README.md`** - This documentation

## Prerequisites

- Ubuntu/Debian Linux system deploying a Git repository to a "deployed" folder somewhere outside the repository.
- User `<user>` on remote linux system with appropriate permissions.
- Python 3.8 or higher
- Git repository cloned to `/home/<user>/ManagedFileTransfer`
- Gitea server with sufficient repository admin access to configure webhooks.

## Installation

### 1. Transfer Files to Remote Server

Copy the `AutoDeploymentService` directory to your remote server:

```bash
scp -r AutoDeploymentService <user>@<your_server_url>:~/
```
or use `git clone` on the remote server:

```bash
git clone <AutoDeploymentService_repo_url> ~/AutoDeploymentService
```

If you use a different git clone directory, substitute it anywhere `~/AutoDeploymentService` is mentioned below.

### 2. Edit the `.env` File

On the remote server, navigate to the `AutoDeploymentService` directory and edit the `.env` file:

```bash
cd ~/AutoDeploymentService
cp .env.example .env
vim .env
```
* **Generate a secure webhook secret:**

```bash
openssl rand -hex 32
```
* Update the `.env` file with your webhook secret and verify all paths are correct:

* Update the variables as needed, especially `WEBHOOK_SECRET` and `INSTALL_DIR`. After you run the installation script, the `.env` file in the installation directory will be used, and overwritten when you re-run the installation script.

```env
WEBHOOK_SECRET=your_generated_secret_here
PORT=9000
REPO_PATH=/home/<user>/ManagedFileTransfer
UPDATE_SCRIPT=/home/<user>/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
LOG_DIR=/home/<user>/.local/log/autoupdater
```

*Note*: These variables are examples; ensure all paths reflect your actual environment.

### 3. Run Installation Script

SSH into the remote server and run the installation script:

```bash
ssh <user>@<your_server_url>
cd ~/AutoDeploymentService
./install.sh
```

The script will:
- Install the [UV package manager](https://docs.astral.sh/uv/) for the current user (if not already present). 
- Create `/home/<user>/autoupdater` directory (or other directory as specified by your `.env` file's `INSTALL_DIR` variable)
- Copy necessary files to the installation directory (`INSTALL_DIR`)
- Install Python dependencies in the installation directory using `uv sync --frozen`
- Create the log directory for the AutoDeploymentService (`LOG_DIR`)
- Generate and Install systemd service file (`SERVICE_FILE`) into `SYSTEMD_DIR`

### 4. Configure Passwordless Sudo

The service needs to run the deployment script with sudo privileges. Use the provided helper script:

```bash
cd /home/<user>/autoupdater # or your INSTALL_DIR
./configure_sudo.sh
```

This script will:
- Read the UPDATE_SCRIPT path from your `.env` file
- Create a sudoers configuration file for the current user in `/etc/sudoers.d/autoupdater`
- Validate the configuration
- Show you what commands can now be run without a password

**Manual Configuration (Alternative)**

If you prefer to configure manually:

```bash
sudo visudo -f /etc/sudoers.d/autoupdater
```
any text editory will do, like `nano` or `vim`.

Add the following line, replacing `<user>` with your username and `UPDATE_SCRIPT` with the path to your deployment script inside the git repository you want to auto-deploy on changes:

We provide an example here to a repository called `ManagedFileTransfer`, but be sure to replace it with your actual absolute path to the script. 
```
```bash
<user> ALL=(ALL) NOPASSWD: /home/<user>/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

Save and exit (`:wq` if you never used `vim` before).

### 5. Configure Firewall (if applicable)

If you have a firewall enabled, allow incoming connections on port 9000 and verify the status:

```bash
sudo ufw allow 9000/tcp
sudo ufw status
```

### 6. Start the Service

Enable and start the autoupdater service. If you named it differently, substitute `autoupdater` with your service name (`SERVICE_FILE` in your `.env`):

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

- **Target URL**: Choose one of the following:
  - `http://<your_server_url>:9000/webhook` (recommended)
  - `http://<your_server_url>:9000/` (also works)
  
  > **Note:** Both URLs work. The webhook endpoint accepts POST requests at both the root path (`/`) and the `/webhook` path for maximum compatibility with different webhook configurations.

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
cd /home/<user>/autoupdater
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
cd ~/autoupdater
./configure_sudo.sh
```
`~/autoupdater` can be any path where you clone the repository.

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
tail -f ${HOME}/.local/log/autoupdater/autoupdater.log
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
curl http://<your_server_url>:9000/health
```

### Git Pull Fails

**Check repository permissions:**
```bash
ls -la /home/<user>/ManagedFileTransfer
```

**Verify git is configured:**
```bash
cd /home/<user>/ManagedFileTransfer
git status
git remote -v
```

**Check for merge conflicts:**
```bash
cd /home/<user>/ManagedFileTransfer
git status
```

### Deployment Script Fails

**Test sudo access:**
```bash
sudo /home/<user>/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

**Check script permissions:**
```bash
ls -l /home/<user>/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh
```

**Review script output in logs:**
```bash
journalctl -u autoupdater -n 100 | grep -A 20 "Running update script"
```

### Signature Verification Fails

**Verify webhook secret matches:**
1. Check `.env` file: `cat /home/<user>/autoupdater/.env`
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
   scp webhook_server.py <user>@<your_server_url>:~/autoupdater/
   ```
3. Restart the service:
   ```bash
   ssh <user>@<your_server_url>
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
rm -rf ${HOME}/autoupdater

# Remove logs
rm -rf ${HOME}/.local/log/autoupdater

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues or questions, check the logs first:
- `${HOME}/.local/log/autoupdater/autoupdater.log`
- `journalctl -u autoupdater`
