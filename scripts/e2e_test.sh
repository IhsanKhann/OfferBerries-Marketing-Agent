#!/usr/bin/env bash
set -e
source "$(dirname "$0")/../.env" 2>/dev/null || true

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}: $*"; }
fail() { echo -e "${RED}FAIL${NC}: $*"; exit 1; }

echo "=== OfferBerries Marketing Agent — Full E2E Test ==="
echo ""

# 1. Infrastructure check
echo ">>> Testing infrastructure..."
bash "$(dirname "$0")/checkpoint_phase1.sh" || fail "Phase 1 infrastructure checks failed"

# 2. Demo session
echo ""
echo ">>> Testing demo visitor flow..."
DEMO=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/session" \
  -H "Content-Type: application/json" -d '{}' --max-time 15)
DEMO_KEY=$(echo "$DEMO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null)
DEMO_EXPIRES=$(echo "$DEMO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expires_at',''))" 2>/dev/null)
[[ -n "$DEMO_KEY" ]] && pass "Demo session created (expires: ${DEMO_EXPIRES})" || fail "Demo session failed"

# 3. Demo research
echo ">>> Demo: researching topic..."
BRIEF=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/research" \
  -H "Content-Type: application/json" \
  -d '{"topic":"payroll automation Pakistan"}' --max-time 60)
ANGLES=$(echo "$BRIEF" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$ANGLES" -gt 0 ]] && pass "Research returned ${ANGLES} trending angles" || fail "Research returned no angles"

# 4. Demo generate
echo ">>> Demo: generating content..."
CONTENT=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/generate" \
  -H "Content-Type: application/json" \
  -d "{\"brief\":${BRIEF}}" --max-time 60)
COPY_LEN=$(echo "$CONTENT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('copy','')))" 2>/dev/null || echo "0")
[[ "$COPY_LEN" -gt 50 ]] && pass "Content generated (${COPY_LEN} chars)" || fail "Content generation failed"

# 5. Demo visual
echo ">>> Demo: generating visual..."
VISUAL=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/visual" \
  -H "Content-Type: application/json" \
  -d "{\"content\":${CONTENT},\"template_id\":\"linkedin-single\"}" --max-time 60)
VISUAL_URL=$(echo "$VISUAL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('preview_url',''))" 2>/dev/null)
if [[ -n "$VISUAL_URL" ]]; then
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$VISUAL_URL" --max-time 15)
  [[ "$HTTP_CODE" == "200" ]] && pass "Visual accessible at ${VISUAL_URL:0:40}..." || fail "Visual URL returned ${HTTP_CODE}"
else
  fail "Visual URL empty"
fi

# 6. Owner login
echo ""
echo ">>> Owner: logging in..."
curl -sf -X POST "https://agent.${DOMAIN}/api/auth" \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"${OWNER_API_KEY}\"}" \
  -c /tmp/e2e-cookies.txt -o /dev/null
COOKIE_COUNT=$(grep -c "ofb_session" /tmp/e2e-cookies.txt 2>/dev/null || echo "0")
[[ "$COOKIE_COUNT" -ge 1 ]] && pass "Owner authenticated (session cookie set)" || fail "Owner login failed"

# 7. Owner runs agent (dry run)
echo ">>> Owner: running agent (dry run)..."
RUN=$(curl -sf -X POST "https://agent.${DOMAIN}/api/proxy/agent/run" \
  -H "Content-Type: application/json" \
  -b /tmp/e2e-cookies.txt \
  -d '{"topic":"OfferBerries leave management module","dry_run":true}' --max-time 30)
RUN_ID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null)
[[ -n "$RUN_ID" ]] && pass "Agent run started: ${RUN_ID}" || fail "Agent run failed to start"

# 8. Poll until complete
echo ">>> Polling agent status (max 3 min)..."
STATUS="pending"
for i in $(seq 1 36); do
  sleep 5
  STATUS=$(curl -sf "https://agent.${DOMAIN}/api/proxy/agent/status/${RUN_ID}" \
    -b /tmp/e2e-cookies.txt --max-time 10 | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  echo "  Status check ${i}/36: ${STATUS}"
  [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
done
[[ "$STATUS" == "completed" ]] && pass "Agent run completed" || fail "Agent run did not complete (${STATUS})"

# 9. Verify pipeline stages
STATE_RAW=$(curl -sf "https://agent.${DOMAIN}/api/proxy/agent/status/${RUN_ID}" \
  -b /tmp/e2e-cookies.txt --max-time 10)
BRIEF_ANGLES=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('brief',{}).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$BRIEF_ANGLES" -gt 0 ]] && pass "Research stage: ${BRIEF_ANGLES} angles" || fail "Research stage missing"

CONTENT_KEYS=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('platform_content',{})))" 2>/dev/null || echo "0")
[[ "$CONTENT_KEYS" -gt 0 ]] && pass "Content stage: ${CONTENT_KEYS} platforms" || fail "Content stage missing"

VISUAL_KEYS=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('visual_assets',{})))" 2>/dev/null || echo "0")
[[ "$VISUAL_KEYS" -gt 0 ]] && pass "Visual stage: ${VISUAL_KEYS} assets" || fail "Visual stage missing"

# 10. Analytics
echo ">>> Testing analytics page..."
ANALYTICS=$(curl -sf "https://agent.${DOMAIN}/api/proxy/analytics" \
  -b /tmp/e2e-cookies.txt --max-time 15)
HAS_IMPRESSIONS=$(echo "$ANALYTICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'total_impressions' in d else 'no')" 2>/dev/null || echo "no")
[[ "$HAS_IMPRESSIONS" == "yes" ]] && pass "Analytics page has data" || fail "Analytics page missing data"

echo ""
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}  ALL E2E TESTS PASSED              ${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""
echo "  Dashboard:   https://agent.${DOMAIN}"
echo "  Design:      https://design.${DOMAIN}"
echo "  n8n:         https://n8n.${DOMAIN}"
echo ""
rm -f /tmp/e2e-cookies.txt
