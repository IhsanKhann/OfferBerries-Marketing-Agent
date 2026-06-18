"""
Pytest configuration for mcp_server tests.

Sets the required environment variables before main.py is imported so the
module-level _validate_env() check passes during test collection.
All values here are test-only stubs — no real infrastructure is contacted.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set before any test module imports main.py
_TEST_ENV = {
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DB": "test_db",
    "REDIS_URL": "redis://localhost:6379",
    "OWNER_API_KEY": "ofb_owner_test0000000000000000000000000000000",
    "OWNER_TENANT_ID": "owner-tenant-test",
    "OPENROUTER_API_KEY": "test-openrouter-key",
    "MCP_SERVER_URL": "http://localhost:8000",
    "APP_ENV": "test",
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)
