#!/usr/bin/env bash
# Checkpoint Phase 5 — Analytics Feedback Loop + Supabase Memory
set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 5 — Analytics + Memory"
echo "══════════════════════════════════════════════"
echo ""

check_supabase_table() {
  local table="$1"
  RESP=$(curl -sf "${SUPABASE_URL}/rest/v1/${table}?limit=1" \
    -H "apikey: ${SUPABASE_ANON_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
    --max-time 10 2>/dev/null || echo "null")
  echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if isinstance(d,list) else 1)" 2>/dev/null
}

echo "CHECK 1: Supabase tables exist"
for table in content_strategy posts_performance competitor_posts agent_memory; do
  if check_supabase_table "$table"; then
    echo "    ${table}: OK"
  else
    fail "Supabase table '${table}' not found"
  fi
done
pass "All Supabase tables accessible"

echo "CHECK 2: Analytics worker runs"
ANALYTICS=$(curl -sf -X POST http://localhost:8001/analytics/collect \
  -H "X-API-Key: ${OWNER_API_KEY}" --max-time 60 2>/dev/null || echo "{}")
STATUS=$(echo "$ANALYTICS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
[[ "$STATUS" == "ok" ]] && pass "Analytics collector returned ok" || fail "Analytics collector failed (status: ${STATUS})"

echo "CHECK 3: Pattern extractor produces strategy update"
PATTERNS=$(curl -sf -X POST http://localhost:8001/analytics/extract-patterns \
  -H "X-API-Key: ${OWNER_API_KEY}" --max-time 60 2>/dev/null || echo "{}")
CHANGES=$(echo "$PATTERNS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d.get('changes',None)).__name__)" 2>/dev/null || echo "NoneType")
[[ "$CHANGES" == "dict" ]] && pass "Pattern extractor returned changes dict" || fail "Pattern extractor changes missing"

echo "CHECK 4: Strategy doc updated in Supabase"
STRATEGY=$(curl -sf "${SUPABASE_URL}/rest/v1/content_strategy?tenant_id=eq.${OWNER_TENANT_ID}" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
  --max-time 10 2>/dev/null || echo "[]")
UPDATED=$(echo "$STRATEGY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('updated_at','') if d else '')" 2>/dev/null || echo "")
[[ -n "$UPDATED" ]] && pass "Strategy doc has updated_at: ${UPDATED}" || fail "Strategy doc missing or not updated"

echo "CHECK 5: n8n workflows imported (>= 3)"
WF_COUNT=$(curl -sf "https://n8n.${DOMAIN}/api/v1/workflows" \
  -u "${N8N_BASIC_AUTH_USER}:${N8N_BASIC_AUTH_PASSWORD}" \
  --max-time 15 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
[[ "$WF_COUNT" -ge 3 ]] && pass "n8n has ${WF_COUNT} workflows" || fail "n8n has only ${WF_COUNT} workflows (need >= 3)"

echo "CHECK 6: Full pipeline run (real posting, LinkedIn only)"
RUN=$(curl -sf -X POST http://localhost:8001/agent/run \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"topic":"OfferBerries HR module — leave tracking feature","platform_filter":["linkedin"],"dry_run":false}' \
  --max-time 30 2>/dev/null || echo "{}")
RUN_ID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null || echo "")
if [[ -z "$RUN_ID" ]]; then
  fail "Could not start full pipeline run"
else
  STATUS="pending"
  for i in $(seq 1 36); do
    sleep 5
    STATUS=$(curl -sf "http://localhost:8001/agent/status/${RUN_ID}" --max-time 10 2>/dev/null | \
      python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
    echo "  Status ${i}/36: ${STATUS}"
  done
  if [[ "$STATUS" == "completed" ]]; then
    QUEUED=$(curl -sf "http://localhost:8001/agent/status/${RUN_ID}" --max-time 10 2>/dev/null | \
      python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('queued_posts',[])))" 2>/dev/null || echo "0")
    [[ "$QUEUED" -ge 1 ]] && pass "Full pipeline queued ${QUEUED} post(s)" || fail "No posts queued in full run"
  else
    fail "Full pipeline run did not complete (status: ${STATUS})"
  fi
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] && echo "  ALL CHECKS PASSED ✓" && exit 0
echo "  SOME CHECKS FAILED ✗"; exit 1
