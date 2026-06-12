#!/usr/bin/env bash
# Checkpoint Phase 6 — Multi-Tenant + Demo + Payments
set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 6 — Multi-Tenant + Payments"
echo "══════════════════════════════════════════════"
echo ""

echo "CHECK 1: Demo session creation"
SESSION=$(curl -sf -X POST http://localhost:8000/admin/tenants/demo \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}' --max-time 15 2>/dev/null || echo "{}")
DEMO_KEY=$(echo "$SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null || echo "")
SESSION_ID=$(echo "$SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")
if echo "$DEMO_KEY" | grep -q "^ofb_demo_"; then
  pass "Demo key created: ${DEMO_KEY:0:20}..."
else
  fail "Demo key invalid: '${DEMO_KEY}'"
fi

echo "CHECK 2: Demo key works for allowed tools"
CONTENT=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${DEMO_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"generate_content","arguments":{"brief":{"topic":"demo","trending_angles":["test"],"pain_points":["pain"],"suggested_hooks":["hook"],"platform_notes":{}},"platform":"linkedin"}}}' \
  --max-time 60 2>/dev/null || echo "{}")
COPY_LEN=$(echo "$CONTENT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('result',{}).get('copy','')))" 2>/dev/null || echo "0")
[[ "$COPY_LEN" -gt 0 ]] && pass "Demo key allowed generate_content (${COPY_LEN} chars)" || fail "Demo key could not call generate_content"

echo "CHECK 3: Demo key blocked from scrape_competitor (tier=demo, limit=0)"
SCRAPE_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${DEMO_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"scrape_competitor","arguments":{"platform":"linkedin","handle":"figma"}}}' \
  --max-time 15)
[[ "$SCRAPE_CODE" == "403" || "$SCRAPE_CODE" == "429" ]] && \
  pass "scrape_competitor blocked for demo tier (${SCRAPE_CODE})" || \
  fail "Expected 403/429, got ${SCRAPE_CODE}"

echo "CHECK 4: Demo session cleanup revokes key"
if [[ -n "$SESSION_ID" ]]; then
  curl -sf -X DELETE "http://localhost:8000/admin/tenants/demo/${SESSION_ID}" \
    -H "X-API-Key: ${OWNER_API_KEY}" -o /dev/null --max-time 10
  sleep 2
  REVOKE_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/mcp \
    -H "X-API-Key: ${DEMO_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"method":"tools/list"}' --max-time 10)
  [[ "$REVOKE_CODE" == "401" ]] && pass "Revoked demo key correctly rejected (401)" || \
    fail "Revoked demo key returned ${REVOKE_CODE} (expected 401)"
else
  fail "No session_id — cleanup skipped"
fi

echo "CHECK 5: Safepay webhook rejects bad signature"
BAD_SIG_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/webhooks/safepay \
  -H "X-Safepay-Signature: bad_signature_invalid" \
  -H "Content-Type: application/json" \
  -d '{"event":"payment.success","data":{}}' --max-time 10)
[[ "$BAD_SIG_CODE" == "403" ]] && pass "Safepay webhook rejects bad signature (403)" || \
  fail "Expected 403, got ${BAD_SIG_CODE}"

echo "CHECK 6: Billing checkout link generated"
CHECKOUT=$(curl -sf -X POST http://localhost:8000/billing/checkout \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"plan":"starter_pkr","tenant_email":"test@example.com"}' --max-time 15 2>/dev/null || echo "{}")
CHECKOUT_URL=$(echo "$CHECKOUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('checkout_url',''))" 2>/dev/null || echo "")
[[ "$CHECKOUT_URL" == https* ]] && pass "Checkout URL generated: ${CHECKOUT_URL:0:40}..." || \
  fail "Checkout URL missing or invalid"

echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] && echo "  ALL CHECKS PASSED ✓" && exit 0
echo "  SOME CHECKS FAILED ✗"; exit 1
