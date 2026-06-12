#!/usr/bin/env bash
# Checkpoint Phase 3 — LangGraph Agent Brain
set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 3 — Agent Brain"
echo "══════════════════════════════════════════════"
echo ""

echo "CHECK 1: Crew runner health"
HEALTH=$(curl -sf http://localhost:8001/health --max-time 10 2>/dev/null || echo "{}")
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
  pass "Crew runner health ok"
else
  fail "Crew runner health failed"
fi

echo "CHECK 2: Dry run triggers successfully"
RUN=$(curl -sf -X POST http://localhost:8001/agent/run \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"topic":"HR payroll automation Pakistan","platform_filter":["linkedin","twitter"],"dry_run":true}' \
  --max-time 30 2>/dev/null || echo "{}")
RUN_ID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null || echo "")
if [[ -n "$RUN_ID" ]]; then
  pass "Agent run started: ${RUN_ID}"
else
  fail "Failed to start agent run"
  exit 1
fi

echo "  Polling run status (up to 120s)..."
STATUS="pending"
for i in $(seq 1 24); do
  sleep 5
  STATUS=$(curl -sf "http://localhost:8001/agent/status/${RUN_ID}" --max-time 10 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  echo "  Status check ${i}/24: ${STATUS}"
  [[ "$STATUS" == "completed" ]] && break
  [[ "$STATUS" == "failed" ]] && break
done

if [[ "$STATUS" == "completed" ]]; then
  pass "Agent run completed"
else
  fail "Agent run did not complete (status: ${STATUS})"
fi

STATE=$(curl -sf "http://localhost:8001/agent/status/${RUN_ID}" --max-time 10 2>/dev/null || echo "{}")

echo "CHECK 3: Research node produced brief"
ANGLES=$(echo "$STATE" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('brief',{}).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$ANGLES" -gt 0 ]] && pass "Brief has ${ANGLES} trending angles" || fail "Brief missing trending_angles"

echo "CHECK 4: Content node produced platform content"
COPY_LEN=$(echo "$STATE" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('platform_content',{}).get('linkedin',{}).get('copy','')))" 2>/dev/null || echo "0")
[[ "$COPY_LEN" -gt 0 ]] && pass "LinkedIn copy present (${COPY_LEN} chars)" || fail "LinkedIn copy missing"

echo "CHECK 5: Visual node produced assets"
VIS_FMT=$(echo "$STATE" | python3 -c "import sys,json; s=json.load(sys.stdin); print(s.get('state',{}).get('visual_assets',{}).get('linkedin',{}).get('format',''))" 2>/dev/null || echo "")
[[ "$VIS_FMT" == "png" ]] && pass "LinkedIn visual asset format=png" || fail "Visual asset missing or wrong format: '${VIS_FMT}'"

echo "CHECK 6: Dry run did NOT queue posts"
QUEUED=$(echo "$STATE" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('queued_posts',[])))" 2>/dev/null || echo "0")
[[ "$QUEUED" -eq 0 ]] && pass "No posts queued in dry run" || fail "Dry run queued ${QUEUED} posts (should be 0)"

echo "CHECK 7: Run persisted to MongoDB"
RUN_CHECK=$(docker compose exec -T mcp-server python3 - <<PYEOF 2>/dev/null
import os
from pymongo import MongoClient
client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000)
doc = client[os.environ["MONGODB_DB"]]["runs"].find_one({"run_id": "${RUN_ID}"})
client.close()
print("found" if doc else "missing")
PYEOF
)
[[ "$RUN_CHECK" == "found" ]] && pass "Run persisted to MongoDB" || fail "Run not found in MongoDB"

echo "CHECK 8: All pytest tests pass"
docker compose exec -T crew-runner python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
[[ ${PIPESTATUS[0]} -eq 0 ]] && pass "Crew runner pytest passed" || fail "Crew runner pytest failed"

echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] && echo "  ALL CHECKS PASSED ✓" && exit 0
echo "  SOME CHECKS FAILED ✗"; exit 1
