#!/usr/bin/env python3
"""
Gitea Webhook Auto-updater Service
Receives webhook events from Gitea and updates the ManagedFileTransfer repository.
"""

import os
import sys
import hmac
import hashlib
import subprocess
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
PORT = int(os.getenv('PORT', 9000))
REPO_PATH = os.getenv('REPO_PATH', '/home/trevor/ManagedFileTransfer')
UPDATE_SCRIPT = os.getenv('UPDATE_SCRIPT', '/home/trevor/ManagedFileTransfer/prod_config/scripts/uv_update_deployment.sh')
LOG_DIR = os.getenv('LOG_DIR', '/home/trevor/.local/log/autodeploymentservice')
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

# Setup logging
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
log_file = Path(LOG_DIR) / 'autodeploymentservice.log'

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


def verify_signature(payload, signature):
    """Verify the Gitea webhook signature."""
    if not WEBHOOK_SECRET:
        logger.warning("No webhook secret configured - skipping signature verification")
        return True

    if not signature:
        logger.error("No signature provided in request")
        return False

    # Gitea uses SHA256 HMAC
    expected_signature = hmac.new(WEBHOOK_SECRET.encode('utf-8'), payload, hashlib.sha256).hexdigest()

    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]

    return hmac.compare_digest(expected_signature, signature)


def get_current_branch():
    """Get the currently checked out branch in the repository."""
    try:
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], check=False, cwd=REPO_PATH, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            branch = result.stdout.strip()
            logger.info(f"Current branch: {branch}")
            return branch
        else:
            logger.error(f"Failed to get current branch: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error getting current branch: {e}")
        return None


def run_git_fetch() -> bool:
    """Run git fetch in the repository."""
    try:
        logger.info("Running git fetch...")
        result = subprocess.run(['git', 'fetch', '--all'], check=False, cwd=REPO_PATH, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            logger.info("Git fetch completed successfully")
            logger.debug(f"Fetch output: {result.stdout}")
            return True
        else:
            logger.error(f"Git fetch failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running git fetch: {e}")
        return False


def run_git_pull() -> bool:
    """Run git pull in the repository."""
    try:
        logger.info("Running git pull...")
        result = subprocess.run(['git', 'pull'], check=False, cwd=REPO_PATH, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            logger.info("Git pull completed successfully")
            logger.info(f"Pull output: {result.stdout}")
            return True
        else:
            logger.error(f"Git pull failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running git pull: {e}")
        return False


def run_update_script() -> bool:
    """Run the deployment update script via sudo."""
    try:
        logger.info(f"Running update script: {UPDATE_SCRIPT}")
        result = subprocess.run(
            ['sudo', UPDATE_SCRIPT],
            check=False,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )
        if result.returncode == 0:
            logger.info("Update script completed successfully")
            logger.info(f"Script output: {result.stdout}")
            return True
        else:
            logger.error(f"Update script failed with exit code {result.returncode}")
            logger.error(f"Script stderr: {result.stderr}")
            logger.info(f"Script stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Update script timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Error running update script: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200


@app.route('/', methods=['POST'])
def root_webhook():
    """Handle webhook at root path (redirect to webhook handler)."""
    return webhook()


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Gitea webhook."""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        logger.error("Invalid webhook signature")
        logger.info(f"Provided signature: {signature}")
        logger.debug(f"Payload: {request}")
        return jsonify({'error': 'Invalid signature'}), 403

    # Parse payload
    payload = request.json
    if not payload:
        logger.error("No JSON payload received")
        return jsonify({'error': 'No payload'}), 400

    # Log the webhook event
    event_type = request.headers.get('X-Gitea-Event', 'unknown')
    logger.info(f"Received webhook event: {event_type}")

    # Only process push events
    if event_type != 'push':
        logger.info(f"Ignoring non-push event: {event_type}")
        return jsonify({'message': 'Event ignored'}), 200

    # Extract branch information
    ref = payload.get('ref', '')
    pushed_branch = ref.replace('refs/heads/', '')

    if not pushed_branch:
        logger.error("Could not determine pushed branch from webhook")
        return jsonify({'error': 'Invalid ref'}), 400

    logger.info(f"Push event for branch: {pushed_branch}")

    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        return jsonify({'error': 'Could not determine current branch'}), 500

    # Determine action: pull if current branch was pushed, otherwise fetch
    if pushed_branch == current_branch:
        logger.info(f"Pushed branch '{pushed_branch}' matches current branch '{current_branch}' - performing pull")

        # Run git pull
        if not run_git_pull():
            return jsonify({'error': 'Git pull failed'}), 500

        # Run update script
        if not run_update_script():
            return jsonify({'error': 'Update script failed'}), 500

        return jsonify({'message': 'Repository updated and deployment script executed', 'branch': pushed_branch, 'action': 'pull'}), 200
    else:
        logger.info(f"Pushed branch '{pushed_branch}' differs from current branch '{current_branch}' - performing fetch only")

        # Run git fetch
        if not run_git_fetch():
            return jsonify({'error': 'Git fetch failed'}), 500

        return jsonify({'message': 'Repository fetched', 'pushed_branch': pushed_branch, 'current_branch': current_branch, 'action': 'fetch'}), 200


if __name__ == '__main__':
    logger.info(f"Starting webhook server on port {PORT}")
    logger.info(f"Monitoring repository: {REPO_PATH}")
    logger.info(f"Update script: {UPDATE_SCRIPT}")
    logger.info(f"Logs directory: {LOG_DIR}")
    logger.info(f"Debug mode: {DEBUG}")

    # Set Flask debug mode
    app.debug = DEBUG

    # Run Flask app
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG, use_reloader=DEBUG)
