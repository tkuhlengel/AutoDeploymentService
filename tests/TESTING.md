# Testing Guide for Webhook Server

This directory contains comprehensive tests for the Gitea webhook auto-updater service.

## Test Files

- `test_webhook_server.py` - Comprehensive pytest suite (31 tests)
- `manual_test.py` - Interactive manual testing script
- `.env` - Test environment configuration

## Running Automated Tests

### Run All Tests

```bash
uv run pytest test_webhook_server.py -v
```

### Run with Coverage

```bash
uv run pytest test_webhook_server.py --cov=webhook_server --cov-report=html -v
```

### Run Specific Test Classes

```bash
# Test health endpoint only
uv run pytest test_webhook_server.py::TestHealthEndpoint -v

# Test signature verification
uv run pytest test_webhook_server.py::TestSignatureVerification -v

# Test webhook endpoint
uv run pytest test_webhook_server.py::TestWebhookEndpoint -v

# Test git operations
uv run pytest test_webhook_server.py::TestGitOperations -v
```

## Test Coverage

The automated test suite includes:

### 1. Health Endpoint Tests (4 tests)
- ✓ Returns 200 OK
- ✓ Returns JSON response
- ✓ Contains "healthy" status
- ✓ Contains timestamp

### 2. Signature Verification Tests (5 tests)
- ✓ Valid signature verification
- ✓ Signature with sha256= prefix
- ✓ Invalid signature rejection
- ✓ Behavior when no secret is configured
- ✓ Missing signature header handling

### 3. Git Operations Tests (6 tests)
- ✓ Get current branch
- ✓ Get current branch with invalid repo
- ✓ Successful git fetch
- ✓ Failed git fetch
- ✓ Successful git pull
- ✓ Failed git pull

### 4. Update Script Tests (3 tests)
- ✓ Successful script execution
- ✓ Failed script execution
- ✓ Script timeout handling

### 5. Webhook Endpoint Tests (12 tests)
- ✓ Requires valid signature
- ✓ Rejects invalid signature
- ✓ Handles malformed payload
- ✓ Ignores non-push events
- ✓ Pull when pushed branch matches current
- ✓ Fetch when pushed branch differs
- ✓ Pull failure returns 500
- ✓ Update script failure returns 500
- ✓ Invalid ref returns 400
- ✓ Branch detection failure returns 500
- Plus more...

### 6. Integration Test (1 test)
- ✓ Full webhook flow with real git repository

## Manual Testing

### 1. Start the Server

```bash
uv run python webhook_server.py
```

The server will start on port 9000 (or the port specified in `.env`).

### 2. In Another Terminal, Run Manual Tests

```bash
uv run python manual_test.py
```

This will test:
- Health endpoint
- Valid push webhook
- Push to different branch
- Invalid signature (should fail with 403)
- Non-push event (should be ignored)

### 3. Test with curl

**Health Check:**
```bash
curl http://localhost:9000/health
```

**Webhook (without signature - will fail):**
```bash
curl -X POST http://localhost:9000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Gitea-Event: push" \
  -d '{"ref":"refs/heads/main","repository":{"name":"test"}}'
```

**Webhook (with signature):**
```bash
# Generate signature (requires python)
SECRET="test_secret_key_for_testing_12345"
PAYLOAD='{"ref":"refs/heads/main","repository":{"name":"test"}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -X POST http://localhost:9000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Gitea-Event: push" \
  -H "X-Gitea-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## Testing According to Service Configuration

The server is tested to work correctly when run via:

```bash
uv run webhook_server.py
```

This matches the `autodeployment.service` file which uses:
```
ExecStart=/home/trevor/.local/bin/uv run webhook_server.py
```

### Verify It Works:

1. **Check the server starts:**
   ```bash
   uv run python webhook_server.py
   ```
   
   You should see:
   ```
   INFO:webhook_server:Starting webhook server on port 9000
   INFO:webhook_server:Monitoring repository: /tmp/test_repo
   INFO:webhook_server:Update script: /bin/echo
   INFO:webhook_server:Logs directory: /tmp/autoupdater_test_logs
   ```

2. **Check logs are created:**
   ```bash
   ls -la /tmp/autoupdater_test_logs/
   cat /tmp/autoupdater_test_logs/autoupdater.log
   ```

3. **Run the test suite:**
   ```bash
   uv run pytest test_webhook_server.py -v
   ```
   
   All 31 tests should pass.

4. **Run manual tests:**
   ```bash
   # In terminal 1:
   uv run python webhook_server.py
   
   # In terminal 2:
   uv run python manual_test.py
   ```

## Expected Behavior

### When Configured Correctly:

1. **Health endpoint** - Always returns 200 with status and timestamp
2. **Valid webhook for current branch** - Pulls and runs update script
3. **Valid webhook for different branch** - Fetches only
4. **Invalid signature** - Returns 403 Forbidden
5. **Non-push events** - Returns 200 but ignores
6. **Errors** - Returns 500 with error details

### Logs

Check logs at:
- Console output (stdout/stderr)
- Log file at `$LOG_DIR/autoupdater.log`

## Continuous Integration

The test suite can be integrated into CI/CD:

```yaml
# Example GitHub Actions
- name: Install dependencies
  run: pip install uv && uv sync

- name: Run tests
  run: uv run pytest test_webhook_server.py -v --cov=webhook_server

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting Tests

### Tests Fail with "Module not found"
```bash
uv sync  # Reinstall dependencies
```

### Manual tests can't connect
- Make sure webhook_server.py is running
- Check the port in .env matches manual_test.py
- Verify firewall isn't blocking localhost:9000

### Git operation tests fail
- These use mock/temporary repositories
- Should work even without git installed (mocked tests)
- Integration test requires git to be installed

## Test Environment Variables

The `.env` file for testing contains:
```env
WEBHOOK_SECRET=test_secret_key_for_testing_12345
PORT=9000
REPO_PATH=/tmp/test_repo
UPDATE_SCRIPT=/bin/echo
LOG_DIR=/tmp/autoupdater_test_logs
```

These are safe for testing and won't affect production systems.
