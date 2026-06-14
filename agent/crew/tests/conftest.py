"""Pytest configuration for crew tests."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_ENV = {
    "OWNER_API_KEY": "ofb_owner_test0000000000000000000000000000000",
    "OWNER_TENANT_ID": "owner-tenant-test",
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DB": "test_db",
    "REDIS_URL": "redis://localhost:6379",
    "MCP_SERVER_URL": "http://localhost:8000",
    "APP_ENV": "test",
}
for k, v in _TEST_ENV.items():
    os.environ.setdefault(k, v)
