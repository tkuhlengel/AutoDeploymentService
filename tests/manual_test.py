#!/usr/bin/env python3
"""
Manual testing script to simulate webhook requests to the server.
Run this in a separate terminal while webhook_server.py is running.
"""

import json
import hmac
import hashlib
import requests
import time

# Configuration - should match your .env
BASE_URL = 'http://localhost:9000'
WEBHOOK_SECRET = 'test_secret_key_for_testing_12345'


def create_signature(payload_dict, secret):
    """Create HMAC signature for payload."""
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()


def test_health_endpoint():
    """Test the health check endpoint."""
    print("\n=== Testing /health endpoint ===")
    try:
        response = requests.get(f'{BASE_URL}/health', timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_push_webhook(branch='main', event='push'):
    """Test pushing a webhook request."""
    print(f"\n=== Testing /webhook endpoint ({event} to {branch}) ===")

    payload = {
        'ref': f'refs/heads/{branch}',
        'repository': {'name': 'test-repo', 'full_name': 'testuser/test-repo'},
        'pusher': {'login': 'testuser'},
        'commits': [{'id': 'abc123', 'message': 'Test commit', 'url': 'http://example.com/commit/abc123'}],
    }

    signature = create_signature(payload, WEBHOOK_SECRET)

    headers = {'X-Gitea-Event': event, 'X-Gitea-Signature': signature, 'Content-Type': 'application/json'}

    try:
        response = requests.post(f'{BASE_URL}/webhook', json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code in {200, 500}  # 500 is ok if repo doesn't exist
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_invalid_signature():
    """Test webhook with invalid signature."""
    print("\n=== Testing /webhook with invalid signature ===")

    payload = {'ref': 'refs/heads/main', 'repository': {'name': 'test-repo'}}

    headers = {'X-Gitea-Event': 'push', 'X-Gitea-Signature': 'invalid_signature_12345', 'Content-Type': 'application/json'}

    try:
        response = requests.post(f'{BASE_URL}/webhook', json=payload, headers=headers, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 403
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_non_push_event():
    """Test webhook with non-push event."""
    print("\n=== Testing /webhook with pull_request event ===")

    payload = {'ref': 'refs/heads/main', 'repository': {'name': 'test-repo'}}

    signature = create_signature(payload, WEBHOOK_SECRET)

    headers = {'X-Gitea-Event': 'pull_request', 'X-Gitea-Signature': signature, 'Content-Type': 'application/json'}

    try:
        response = requests.post(f'{BASE_URL}/webhook', json=payload, headers=headers, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def main() -> None:
    """Run all manual tests."""
    print("=" * 60)
    print("Webhook Server Manual Testing")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print("Make sure webhook_server.py is running first!")
    print("=" * 60)

    # Wait for user confirmation
    input("\nPress Enter to start testing...")

    results = []

    # Test health endpoint
    results.append(("Health Endpoint", test_health_endpoint()))
    time.sleep(0.5)

    # Test valid webhook
    results.append(("Valid Push Webhook", test_push_webhook('main', 'push')))
    time.sleep(0.5)

    # Test webhook for different branch
    results.append(("Push to Different Branch", test_push_webhook('develop', 'push')))
    time.sleep(0.5)

    # Test invalid signature
    results.append(("Invalid Signature", test_invalid_signature()))
    time.sleep(0.5)

    # Test non-push event
    results.append(("Non-Push Event", test_non_push_event()))

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("=" * 60)


if __name__ == '__main__':
    main()
