#!/usr/bin/env bash
set -e
source "$(dirname "$0")/../.env" 2>/dev/null || true

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}: $*"; }
fail() { echo -e "${RED}FAIL${NC}: $*"; exit 1; }
warn() { echo -e "${YELLOW}WARN${NC}: $*"; }

echo "=== OfferBerries Marketing Agent — Full E2E Test ==="
echo ""

# ── 1. Infrastructure ──────────────────────────────────────────────────────
echo ">>> Testing infrastructure..."
bash "$(dirname "$0")/checkpoint_phase1.sh" || fail "Phase 1 infrastructure checks failed"

# ── 2. Demo session ────────────────────────────────────────────────────────
echo ""
echo ">>> Testing demo visitor flow..."
DEMO=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/session" \
  -H "Content-Type: application/json" -d '{}' --max-time 15)
DEMO_KEY=$(echo "$DEMO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null)
DEMO_EXPIRES=$(echo "$DEMO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expires_at',''))" 2>/dev/null)
[[ -n "$DEMO_KEY" ]] && pass "Demo session created (expires: ${DEMO_EXPIRES})" || fail "Demo session failed"

# ── 3. Demo research ───────────────────────────────────────────────────────
echo ">>> Demo: researching topic..."
BRIEF=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/research" \
  -H "Content-Type: application/json" \
  -d '{"topic":"payroll automation Pakistan"}' --max-time 60)
ANGLES=$(echo "$BRIEF" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$ANGLES" -gt 0 ]] && pass "Research returned ${ANGLES} trending angles" || fail "Research returned no angles"

# ── 4. Demo generate ───────────────────────────────────────────────────────
echo ">>> Demo: generating content..."
CONTENT=$(curl -sf -X POST "https://agent.${DOMAIN}/api/demo/generate" \
  -H "Content-Type: application/json" \
  -d "{\"brief\":${BRIEF}}" --max-time 60)
COPY_LEN=$(echo "$CONTENT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('copy','')))" 2>/dev/null || echo "0")
[[ "$COPY_LEN" -gt 50 ]] && pass "Content generated (${COPY_LEN} chars)" || fail "Content generation failed"

# ── 5. Demo visual ────────────────────────────────────────────────────────
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

# ── 6. Owner login ────────────────────────────────────────────────────────
echo ""
echo ">>> Owner: logging in..."
curl -sf -X POST "https://agent.${DOMAIN}/api/auth" \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"${OWNER_API_KEY}\"}" \
  -c /tmp/e2e-cookies.txt -o /dev/null
COOKIE_COUNT=$(grep -c "ofb_session" /tmp/e2e-cookies.txt 2>/dev/null || echo "0")
[[ "$COOKIE_COUNT" -ge 1 ]] && pass "Owner authenticated (session cookie set)" || fail "Owner login failed"

# ── 7. REST queue endpoint ────────────────────────────────────────────────
echo ">>> Testing REST /queue endpoint..."
QUEUE_RESP=$(curl -sf "https://agent.${DOMAIN}/api/proxy/queue" \
  -b /tmp/e2e-cookies.txt --max-time 15)
IS_ARRAY=$(echo "$QUEUE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if isinstance(d,list) else 'no')" 2>/dev/null || echo "no")
[[ "$IS_ARRAY" == "yes" ]] && pass "GET /queue returns array (${QUEUE_RESP:0:60}...)" || fail "GET /queue not returning array"

# ── 8. World Cup post — research ──────────────────────────────────────────
echo ""
echo ">>> World Cup test: researching FIFA World Cup 2026 topic..."
WC_BRIEF_RAW=$(curl -sf -X POST "https://agent.${DOMAIN}/mcp" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -d '{"method":"tools/call","params":{"name":"research_trends","arguments":{"topic":"FIFA World Cup 2026 Pakistan fan engagement social media","platform":"all"}}}' \
  --max-time 60)
WC_ANGLES=$(echo "$WC_BRIEF_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('result',{}).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$WC_ANGLES" -gt 0 ]] && pass "World Cup research: ${WC_ANGLES} angles found" || warn "World Cup research returned 0 angles (Perplexity key may be missing)"

# ── 9. World Cup post — generate LinkedIn content ─────────────────────────
echo ">>> World Cup test: generating LinkedIn post..."
WC_BRIEF=$(echo "$WC_BRIEF_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(__import__('json').dumps(d.get('result',{})))" 2>/dev/null || echo '{}')
WC_CONTENT_RAW=$(curl -sf -X POST "https://agent.${DOMAIN}/mcp" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -d "{\"method\":\"tools/call\",\"params\":{\"name\":\"generate_content\",\"arguments\":{\"brief\":${WC_BRIEF},\"platform\":\"linkedin\",\"product\":\"full_erp\"}}}" \
  --max-time 60)
WC_COPY_LEN=$(echo "$WC_CONTENT_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('result',{}).get('copy','')))" 2>/dev/null || echo "0")
[[ "$WC_COPY_LEN" -gt 50 ]] && pass "World Cup LinkedIn post generated (${WC_COPY_LEN} chars)" || fail "World Cup content generation failed"

# ── 10. World Cup post — render visual ────────────────────────────────────
echo ">>> World Cup test: rendering visual..."
WC_CONTENT=$(echo "$WC_CONTENT_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(__import__('json').dumps(d.get('result',{})))" 2>/dev/null || echo '{}')
WC_VISUAL_RAW=$(curl -sf -X POST "https://agent.${DOMAIN}/mcp" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -d "{\"method\":\"tools/call\",\"params\":{\"name\":\"generate_visual\",\"arguments\":{\"content\":${WC_CONTENT},\"template_id\":\"linkedin-single\",\"source\":\"template\"}}}" \
  --max-time 60)
WC_VISUAL_URL=$(echo "$WC_VISUAL_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('url',''))" 2>/dev/null || echo "")
[[ -n "$WC_VISUAL_URL" ]] && pass "World Cup visual rendered: ${WC_VISUAL_URL:0:50}..." || fail "World Cup visual generation failed"

# ── 11. World Cup post — queue to MongoDB ────────────────────────────────
echo ">>> World Cup test: queuing post to database..."
WC_COPY=$(echo "$WC_CONTENT_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('result',{}).get('copy',''); print(__import__('json').dumps(c))" 2>/dev/null || echo '""')
WC_QUEUE_RAW=$(curl -sf -X POST "https://agent.${DOMAIN}/mcp" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -d "{\"method\":\"tools/call\",\"params\":{\"name\":\"queue_post\",\"arguments\":{\"platform\":\"linkedin\",\"caption\":${WC_COPY},\"image_path\":\"\",\"preview_url\":\"${WC_VISUAL_URL}\",\"scheduled_at\":\"$(date -u -d '+24 hours' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')\"}}}" \
  --max-time 30)
WC_POST_ID=$(echo "$WC_QUEUE_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('postiz_id',''))" 2>/dev/null || echo "")
[[ -n "$WC_POST_ID" ]] && pass "World Cup post queued: ID ${WC_POST_ID:0:20}..." || fail "World Cup queue_post failed"

# ── 12. Verify post appears in frontend queue ─────────────────────────────
echo ">>> World Cup test: verifying post appears in GET /queue..."
sleep 2
QUEUE_AFTER=$(curl -sf "https://agent.${DOMAIN}/api/proxy/queue" \
  -b /tmp/e2e-cookies.txt --max-time 15)
WC_IN_QUEUE=$(echo "$QUEUE_AFTER" | python3 -c "
import sys, json
posts = json.load(sys.stdin)
ids = [p.get('postiz_id','') for p in posts]
print('yes' if '${WC_POST_ID}' in ids else 'no')
" 2>/dev/null || echo "no")
[[ "$WC_IN_QUEUE" == "yes" ]] && pass "World Cup post visible in dashboard queue" || fail "World Cup post NOT found in /queue — DB save or REST endpoint broken"

# ── 13. Owner dry-run agent ───────────────────────────────────────────────
echo ""
echo ">>> Owner: running agent (dry run)..."
RUN=$(curl -sf -X POST "https://agent.${DOMAIN}/api/proxy/agent/run" \
  -H "Content-Type: application/json" \
  -b /tmp/e2e-cookies.txt \
  -d '{"topic":"OfferBerries leave management module","dry_run":true}' --max-time 30)
RUN_ID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null)
[[ -n "$RUN_ID" ]] && pass "Agent run started: ${RUN_ID}" || fail "Agent run failed to start"

# ── 14. Poll until complete ───────────────────────────────────────────────
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
[[ "$STATUS" == "completed" ]] && pass "Agent dry-run completed" || fail "Agent run did not complete (${STATUS})"

# ── 15. Verify pipeline stages ────────────────────────────────────────────
STATE_RAW=$(curl -sf "https://agent.${DOMAIN}/api/proxy/agent/status/${RUN_ID}" \
  -b /tmp/e2e-cookies.txt --max-time 10)
BRIEF_ANGLES=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('brief',{}).get('trending_angles',[])))" 2>/dev/null || echo "0")
[[ "$BRIEF_ANGLES" -gt 0 ]] && pass "Research stage: ${BRIEF_ANGLES} angles" || fail "Research stage missing"

CONTENT_KEYS=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('platform_content',{})))" 2>/dev/null || echo "0")
[[ "$CONTENT_KEYS" -gt 0 ]] && pass "Content stage: ${CONTENT_KEYS} platforms" || fail "Content stage missing"

VISUAL_KEYS=$(echo "$STATE_RAW" | python3 -c "import sys,json; s=json.load(sys.stdin); print(len(s.get('state',{}).get('visual_assets',{})))" 2>/dev/null || echo "0")
[[ "$VISUAL_KEYS" -gt 0 ]] && pass "Visual stage: ${VISUAL_KEYS} assets" || fail "Visual stage missing"

# ── 16. Analytics ─────────────────────────────────────────────────────────
echo ">>> Testing analytics endpoint..."
ANALYTICS=$(curl -sf "https://agent.${DOMAIN}/api/proxy/analytics" \
  -b /tmp/e2e-cookies.txt --max-time 15)
HAS_IMPRESSIONS=$(echo "$ANALYTICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'total_impressions' in d else 'no')" 2>/dev/null || echo "no")
[[ "$HAS_IMPRESSIONS" == "yes" ]] && pass "Analytics endpoint working" || fail "Analytics endpoint missing total_impressions"

echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  ALL E2E TESTS PASSED                  ${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo "  Dashboard:   https://agent.${DOMAIN}"
echo "  Design:      https://design.${DOMAIN}"
echo "  n8n:         https://n8n.${DOMAIN}"
echo ""
rm -f /tmp/e2e-cookies.txt
