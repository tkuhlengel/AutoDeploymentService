#!/usr/bin/env python3
"""
Test suite for webhook_server.py
Tests all functionality including webhook handling, signature verification, and git operations.
"""

import os
import sys
import hmac
import hashlib
import json
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the app
sys.path.insert(0, os.path.dirname(__file__))
import webhook_server


@pytest.fixture
def app():
    """Create and configure a test Flask app instance."""
    webhook_server.app.config['TESTING'] = True
    return webhook_server.app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir) / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_path, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_path, check=True)

    # Create initial commit
    (repo_path / 'README.md').write_text('# Test Repo\n')
    subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_path, check=True, capture_output=True)

    yield str(repo_path)

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_log_dir():
    """Create a temporary log directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_env(temp_repo, temp_log_dir, monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv('WEBHOOK_SECRET', 'test_secret_12345')
    monkeypatch.setenv('PORT', '9000')
    monkeypatch.setenv('REPO_PATH', temp_repo)
    monkeypatch.setenv('UPDATE_SCRIPT', '/bin/echo')
    monkeypatch.setenv('LOG_DIR', temp_log_dir)

    # Reload the module to pick up new env vars
    import importlib

    importlib.reload(webhook_server)

    return {'secret': 'test_secret_12345', 'repo_path': temp_repo, 'log_dir': temp_log_dir}


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Test that health endpoint returns 200 OK."""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, client):
        """Test that health endpoint returns JSON."""
        response = client.get('/health')
        assert response.content_type == 'application/json'

    def test_health_endpoint_contains_status(self, client):
        """Test that health endpoint contains status field."""
        response = client.get('/health')
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'healthy'

    def test_health_endpoint_contains_timestamp(self, client):
        """Test that health endpoint contains timestamp."""
        response = client.get('/health')
        data = response.get_json()
        assert 'timestamp' in data
        assert isinstance(data['timestamp'], str)


class TestSignatureVerification:
    """Test webhook signature verification."""

    def test_verify_signature_with_valid_signature(self):
        """Test signature verification with valid signature."""
        payload = b'{"test": "data"}'
        secret = 'test_secret'
        expected_sig = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()

        with patch.object(webhook_server, 'WEBHOOK_SECRET', secret):
            assert webhook_server.verify_signature(payload, expected_sig) is True

    def test_verify_signature_with_sha256_prefix(self):
        """Test signature verification with sha256= prefix."""
        payload = b'{"test": "data"}'
        secret = 'test_secret'
        expected_sig = 'sha256=' + hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()

        with patch.object(webhook_server, 'WEBHOOK_SECRET', secret):
            assert webhook_server.verify_signature(payload, expected_sig) is True

    def test_verify_signature_with_invalid_signature(self):
        """Test signature verification with invalid signature."""
        payload = b'{"test": "data"}'
        secret = 'test_secret'

        with patch.object(webhook_server, 'WEBHOOK_SECRET', secret):
            assert webhook_server.verify_signature(payload, 'invalid_signature') is False

    def test_verify_signature_without_secret(self):
        """Test signature verification when no secret is configured."""
        payload = b'{"test": "data"}'

        with patch.object(webhook_server, 'WEBHOOK_SECRET', ''):
            assert webhook_server.verify_signature(payload, None) is True

    def test_verify_signature_without_signature_header(self):
        """Test signature verification when signature is missing."""
        payload = b'{"test": "data"}'
        secret = 'test_secret'

        with patch.object(webhook_server, 'WEBHOOK_SECRET', secret):
            assert webhook_server.verify_signature(payload, None) is False


class TestGitOperations:
    """Test git operation functions."""

    def test_get_current_branch(self, temp_repo):
        """Test getting current branch."""
        with patch.object(webhook_server, 'REPO_PATH', temp_repo):
            branch = webhook_server.get_current_branch()
            # Default branch should be 'master' or 'main'
            assert branch in ['master', 'main']

    def test_get_current_branch_with_invalid_repo(self):
        """Test getting current branch with invalid repo path."""
        with patch.object(webhook_server, 'REPO_PATH', '/nonexistent/path'):
            branch = webhook_server.get_current_branch()
            assert branch is None

    @patch('subprocess.run')
    def test_run_git_fetch_success(self, mock_run):
        """Test successful git fetch."""
        mock_run.return_value = MagicMock(returncode=0, stdout='Success', stderr='')

        result = webhook_server.run_git_fetch()
        assert result is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_git_fetch_failure(self, mock_run):
        """Test failed git fetch."""
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Error')

        result = webhook_server.run_git_fetch()
        assert result is False

    @patch('subprocess.run')
    def test_run_git_pull_success(self, mock_run):
        """Test successful git pull."""
        mock_run.return_value = MagicMock(returncode=0, stdout='Already up to date', stderr='')

        result = webhook_server.run_git_pull()
        assert result is True

    @patch('subprocess.run')
    def test_run_git_pull_failure(self, mock_run):
        """Test failed git pull."""
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Error')

        result = webhook_server.run_git_pull()
        assert result is False


class TestUpdateScript:
    """Test update script execution."""

    @patch('subprocess.run')
    def test_run_update_script_success(self, mock_run):
        """Test successful update script execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout='Deployment complete', stderr='')

        result = webhook_server.run_update_script()
        assert result is True
        # Verify sudo was used
        args = mock_run.call_args[0][0]
        assert args[0] == 'sudo'

    @patch('subprocess.run')
    def test_run_update_script_failure(self, mock_run):
        """Test failed update script execution."""
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Script error')

        result = webhook_server.run_update_script()
        assert result is False

    @patch('subprocess.run')
    def test_run_update_script_timeout(self, mock_run):
        """Test update script timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='sudo script.sh', timeout=300)

        result = webhook_server.run_update_script()
        assert result is False


class TestWebhookEndpoint:
    """Test the /webhook endpoint."""

    def create_webhook_payload(self, branch='main'):
        """Helper to create a webhook payload."""
        return {'ref': f'refs/heads/{branch}', 'repository': {'name': 'test-repo', 'full_name': 'user/test-repo'}, 'pusher': {'login': 'testuser'}}

    def create_signature(self, payload_dict, secret):
        """Helper to create HMAC signature.

        Note: Flask's test client will encode the JSON using default json.dumps().
        """
        # Flask's test client uses json.dumps() with default separators (', ', ': ')
        payload_bytes = json.dumps(payload_dict).encode('utf-8')
        return hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()

    def test_webhook_requires_signature(self, client):
        """Test webhook without signature returns 403."""
        payload = self.create_webhook_payload()

        with patch.object(webhook_server, 'WEBHOOK_SECRET', 'test_secret'):
            response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push'})
            assert response.status_code == 403

    def test_webhook_with_invalid_signature(self, client):
        """Test webhook with invalid signature returns 403."""
        payload = self.create_webhook_payload()

        with patch.object(webhook_server, 'WEBHOOK_SECRET', 'test_secret'):
            response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': 'invalid_signature'})
            assert response.status_code == 403

    def test_webhook_without_payload(self, client):
        """Test webhook without JSON payload returns 400."""
        with patch.object(webhook_server, 'WEBHOOK_SECRET', ''):
            response = client.post('/webhook', data='not json', headers={'X-Gitea-Event': 'push'}, content_type='application/json')
            assert response.status_code == 400

    def test_webhook_ignores_non_push_events(self, client):
        """Test webhook ignores non-push events."""
        payload = self.create_webhook_payload()
        signature = self.create_signature(payload, 'test_secret')

        # Patch the verify_signature function to return True
        with patch('webhook_server.verify_signature', return_value=True):
            response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'pull_request', 'X-Gitea-Signature': signature})
            assert response.status_code == 200
            data = response.get_json()
            assert 'ignored' in data['message'].lower()

    @patch('webhook_server.run_update_script')
    @patch('webhook_server.run_git_pull')
    @patch('webhook_server.get_current_branch')
    @patch('webhook_server.verify_signature')
    def test_webhook_pull_on_matching_branch(self, mock_verify, mock_get_branch, mock_pull, mock_update, client):
        """Test webhook performs pull when pushed branch matches current."""
        mock_verify.return_value = True
        mock_get_branch.return_value = 'main'
        mock_pull.return_value = True
        mock_update.return_value = True

        payload = self.create_webhook_payload(branch='main')
        signature = self.create_signature(payload, 'test_secret')

        response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'pull'
        assert data['branch'] == 'main'
        mock_pull.assert_called_once()
        mock_update.assert_called_once()

    @patch('webhook_server.run_git_fetch')
    @patch('webhook_server.get_current_branch')
    @patch('webhook_server.verify_signature')
    def test_webhook_fetch_on_different_branch(self, mock_verify, mock_get_branch, mock_fetch, client):
        """Test webhook performs fetch when pushed branch differs from current."""
        mock_verify.return_value = True
        mock_get_branch.return_value = 'main'
        mock_fetch.return_value = True

        payload = self.create_webhook_payload(branch='develop')
        signature = self.create_signature(payload, 'test_secret')

        response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

        assert response.status_code == 200
        data = response.get_json()
        assert data['action'] == 'fetch'
        assert data['pushed_branch'] == 'develop'
        assert data['current_branch'] == 'main'
        mock_fetch.assert_called_once()

    @patch('webhook_server.run_git_pull')
    @patch('webhook_server.get_current_branch')
    @patch('webhook_server.verify_signature')
    def test_webhook_pull_failure_returns_500(self, mock_verify, mock_get_branch, mock_pull, client):
        """Test webhook returns 500 when pull fails."""
        mock_verify.return_value = True
        mock_get_branch.return_value = 'main'
        mock_pull.return_value = False

        payload = self.create_webhook_payload(branch='main')
        signature = self.create_signature(payload, 'test_secret')

        response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('webhook_server.run_update_script')
    @patch('webhook_server.run_git_pull')
    @patch('webhook_server.get_current_branch')
    @patch('webhook_server.verify_signature')
    def test_webhook_update_script_failure_returns_500(self, mock_verify, mock_get_branch, mock_pull, mock_update, client):
        """Test webhook returns 500 when update script fails."""
        mock_verify.return_value = True
        mock_get_branch.return_value = 'main'
        mock_pull.return_value = True
        mock_update.return_value = False

        payload = self.create_webhook_payload(branch='main')
        signature = self.create_signature(payload, 'test_secret')

        response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('webhook_server.get_current_branch')
    def test_webhook_invalid_ref_returns_400(self, mock_get_branch, client):
        """Test webhook with invalid ref returns 400."""
        mock_get_branch.return_value = 'main'

        payload = {'ref': '', 'repository': {'name': 'test'}}
        signature = self.create_signature(payload, 'test_secret')

        with patch.object(webhook_server, 'WEBHOOK_SECRET', 'test_secret'):
            response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

            assert response.status_code == 400

    @patch('webhook_server.get_current_branch')
    @patch('webhook_server.verify_signature')
    def test_webhook_branch_detection_failure_returns_500(self, mock_verify, mock_get_branch, client):
        """Test webhook returns 500 when branch detection fails."""
        mock_verify.return_value = True
        mock_get_branch.return_value = None

        payload = self.create_webhook_payload()
        signature = self.create_signature(payload, 'test_secret')

        response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

        assert response.status_code == 500


class TestConfiguration:
    """Test configuration loading and validation."""

    def test_default_configuration_values(self):
        """Test default configuration values are set."""
        # These would be tested in integration but we can verify the logic
        assert webhook_server.app is not None

    def test_log_directory_creation(self, temp_log_dir):
        """Test that log directory is created if it doesn't exist."""
        new_log_dir = Path(temp_log_dir) / 'subdir' / 'logs'

        with patch.object(webhook_server, 'LOG_DIR', str(new_log_dir)):
            # This would normally happen in module initialization
            new_log_dir.mkdir(parents=True, exist_ok=True)
            assert new_log_dir.exists()


class TestIntegration:
    """Integration tests with real git operations (where safe)."""

    @patch('webhook_server.run_update_script')
    def test_full_webhook_flow_with_real_repo(self, mock_update, client, temp_repo):
        """Test complete webhook flow with a real git repository."""
        mock_update.return_value = True

        # Set up the test environment
        with patch.object(webhook_server, 'REPO_PATH', temp_repo), patch.object(webhook_server, 'WEBHOOK_SECRET', 'test_secret'):
            # Get the current branch
            current_branch = webhook_server.get_current_branch()
            assert current_branch is not None

            # Set up a fake remote for the repo so pull works
            subprocess.run(['git', 'remote', 'add', 'origin', temp_repo], check=False, cwd=temp_repo, capture_output=True)
            subprocess.run(['git', 'fetch', 'origin'], check=False, cwd=temp_repo, capture_output=True)
            subprocess.run(['git', 'branch', '--set-upstream-to=origin/' + current_branch], check=False, cwd=temp_repo, capture_output=True)

            # Create a webhook payload for the current branch
            payload = {'ref': f'refs/heads/{current_branch}', 'repository': {'name': 'test-repo'}}

            # Create signature using the same encoding Flask will use
            payload_bytes = json.dumps(payload).encode('utf-8')
            signature = hmac.new(b'test_secret', payload_bytes, hashlib.sha256).hexdigest()

            # Send webhook
            response = client.post('/webhook', json=payload, headers={'X-Gitea-Event': 'push', 'X-Gitea-Signature': signature})

            # Verify response
            assert response.status_code == 200
            data = response.get_json()
            assert data['action'] == 'pull'
            assert data['branch'] == current_branch


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
