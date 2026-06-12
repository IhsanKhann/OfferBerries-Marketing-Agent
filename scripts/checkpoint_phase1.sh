#!/usr/bin/env bash
# Checkpoint Phase 1 — Infrastructure Foundation
# Exit 0 only if ALL checks pass.

set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 1 — Infrastructure"
echo "══════════════════════════════════════════════"
echo ""

# CHECK 1 — All Docker services running
echo "CHECK 1: Docker Compose services all running"
RUNNING=$(docker compose ps --format json 2>/dev/null | \
  python3 -c "
import sys, json
data = sys.stdin.read()
items = [json.loads(l) for l in data.strip().splitlines() if l.strip()]
if not items:
    print('NO_CONTAINERS')
else:
    not_running = [x.get('Service','?') for x in items if x.get('State','') != 'running']
    print(','.join(not_running) if not_running else 'OK')
" 2>/dev/null)
if [[ "$RUNNING" == "OK" ]]; then
  pass "All services are in running state"
elif [[ "$RUNNING" == "NO_CONTAINERS" ]]; then
  fail "No containers running — run: docker compose up -d --build"
else
  fail "Services not running: $RUNNING"
fi

# CHECK 2 — Caddy HTTPS on agent.DOMAIN
echo "CHECK 2: Caddy HTTPS on agent.${DOMAIN}"
if curl -sf "https://agent.${DOMAIN}/api/health" -o /dev/null --max-time 10; then
  pass "https://agent.${DOMAIN}/api/health reachable"
else
  fail "https://agent.${DOMAIN}/api/health not reachable"
fi

# CHECK 3 — Caddy HTTPS on n8n.DOMAIN
echo "CHECK 3: Caddy HTTPS on n8n.${DOMAIN}"
if curl -sf "https://n8n.${DOMAIN}/healthz" -o /dev/null --max-time 10; then
  pass "https://n8n.${DOMAIN}/healthz reachable"
else
  fail "https://n8n.${DOMAIN}/healthz not reachable"
fi

# CHECK 4 — Caddy HTTPS on design.DOMAIN
echo "CHECK 4: Caddy HTTPS on design.${DOMAIN}"
if curl -sf -H "Authorization: Bearer ${OD_API_TOKEN}" \
    "https://design.${DOMAIN}/api/health" -o /dev/null --max-time 10; then
  pass "https://design.${DOMAIN}/api/health reachable"
else
  fail "https://design.${DOMAIN}/api/health not reachable"
fi

# CHECK 5 — Renderer POST /render works
echo "CHECK 5: Renderer POST /render"
curl -sf -X POST http://localhost:3001/render \
  -H "Content-Type: application/json" \
  -d '{"template_id":"announcement-card","content_data":{"title":"Test","emoji":"🚀","body":"Test body","product_name":"OfferBerries","cta":"Learn more"},"width":1080,"height":1080}' \
  --output /tmp/test-render-p1.png --max-time 30
if file /tmp/test-render-p1.png 2>/dev/null | grep -q "PNG image"; then
  pass "Renderer returns valid PNG"
else
  fail "Renderer did not return a valid PNG"
fi

# CHECK 6 — Postiz health
echo "CHECK 6: Postiz health endpoint"
POSTIZ_RESP=$(curl -sf http://localhost:3000/api/health --max-time 10 2>/dev/null || echo "{}")
if echo "$POSTIZ_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
  pass "Postiz health ok"
else
  fail "Postiz health check failed (response: ${POSTIZ_RESP})"
fi

# CHECK 7 — n8n health
echo "CHECK 7: n8n health endpoint"
N8N_RESP=$(curl -sf http://localhost:5678/healthz --max-time 10 2>/dev/null || echo "{}")
if echo "$N8N_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
  pass "n8n health ok"
else
  fail "n8n health check failed (response: ${N8N_RESP})"
fi

# CHECK 8 — Redis reachable
echo "CHECK 8: Redis reachable"
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
  pass "Redis PONG received"
else
  fail "Redis ping failed"
fi

# CHECK 9 — Postgres reachable
echo "CHECK 9: Postgres reachable"
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER}" 2>/dev/null; then
  pass "Postgres is ready"
else
  fail "Postgres is not ready"
fi

# CHECK 10 — Open Design skill registry
echo "CHECK 10: Open Design skill registry"
OD_SKILLS=$(curl -sf -H "Authorization: Bearer ${OD_API_TOKEN}" \
  http://localhost:7456/api/skills --max-time 10 2>/dev/null || echo "[]")
SKILL_COUNT=$(echo "$OD_SKILLS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")
if [[ "$SKILL_COUNT" -gt 0 ]]; then
  pass "Open Design skill registry has ${SKILL_COUNT} skill(s)"
else
  fail "Open Design skill registry empty or unreachable"
fi

# CHECK 11 — MongoDB owner tenant seeded
echo "CHECK 11: MongoDB owner tenant seeded"
TENANT_CHECK=$(docker compose exec -T mcp-server python3 - <<'PYEOF' 2>/dev/null
import os, sys
from pymongo import MongoClient
try:
    client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000)
    doc = client[os.environ["MONGODB_DB"]]["tenants"].find_one({"_id": os.environ["OWNER_TENANT_ID"]})
    client.close()
    print("found" if doc else "missing")
except Exception as e:
    print(f"error:{e}")
PYEOF
)
if [[ "$TENANT_CHECK" == "found" ]]; then
  pass "Owner tenant document exists in MongoDB"
else
  fail "Owner tenant not found in MongoDB (result: ${TENANT_CHECK})"
fi

# CHECK 12 — MongoDB owner API key seeded
echo "CHECK 12: MongoDB owner API key seeded"
KEY_CHECK=$(docker compose exec -T mcp-server python3 - <<'PYEOF' 2>/dev/null
import os, sys, hashlib
from pymongo import MongoClient
try:
    client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000)
    key_hash = hashlib.sha256(os.environ["OWNER_API_KEY"].encode()).hexdigest()
    doc = client[os.environ["MONGODB_DB"]]["api_keys"].find_one({"key_hash": key_hash})
    client.close()
    print("found" if doc else "missing")
except Exception as e:
    print(f"error:{e}")
PYEOF
)
if [[ "$KEY_CHECK" == "found" ]]; then
  pass "Owner API key hash exists in MongoDB"
else
  fail "Owner API key not found in MongoDB (result: ${KEY_CHECK})"
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
if [[ $FAIL -eq 0 ]]; then
  echo "  ALL CHECKS PASSED ✓"
  exit 0
else
  echo "  SOME CHECKS FAILED ✗ — fix before proceeding to Phase 2"
  exit 1
fi
