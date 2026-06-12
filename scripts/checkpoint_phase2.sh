#!/usr/bin/env bash
# Checkpoint Phase 2 — MCP Server
set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 2 — MCP Server"
echo "══════════════════════════════════════════════"
echo ""

# CHECK 1
echo "CHECK 1: MCP server health endpoint"
HEALTH=$(curl -sf http://localhost:8000/health --max-time 10 2>/dev/null || echo "{}")
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
  pass "MCP server health ok"
else
  fail "MCP server health failed"
fi

# CHECK 2
echo "CHECK 2: Auth with valid owner key — tools list"
TOOLS=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list"}' --max-time 15 2>/dev/null || echo "{}")
TOOL_COUNT=$(echo "$TOOLS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('tools',[])))" 2>/dev/null || echo "0")
if [[ "$TOOL_COUNT" -ge 6 ]]; then
  pass "Tools list returned ${TOOL_COUNT} tools"
else
  fail "Expected >= 6 tools, got ${TOOL_COUNT}"
fi

# CHECK 3
echo "CHECK 3: Auth rejection with bad key"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/mcp \
  -H "X-API-Key: bad_key_invalid_12345" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list"}' --max-time 10)
if [[ "$HTTP_CODE" == "401" ]]; then
  pass "Bad API key correctly rejected with 401"
else
  fail "Expected 401 for bad key, got ${HTTP_CODE}"
fi

# CHECK 4
echo "CHECK 4: research_trends tool callable"
RESEARCH=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"research_trends","arguments":{"topic":"payroll software Pakistan"}}}' \
  --max-time 60 2>/dev/null || echo "{}")
ANGLES=$(echo "$RESEARCH" | python3 -c "import sys,json; d=json.load(sys.stdin); angles=d.get('result',{}).get('trending_angles',[]); print(len(angles))" 2>/dev/null || echo "0")
if [[ "$ANGLES" -gt 0 ]]; then
  pass "research_trends returned ${ANGLES} trending angles"
else
  fail "research_trends returned no trending angles"
fi

# CHECK 5
echo "CHECK 5: generate_content tool callable"
CONTENT=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"generate_content","arguments":{"brief":{"topic":"payroll","trending_angles":["test"],"pain_points":["manual sheets"],"suggested_hooks":["hook1"],"platform_notes":{}},"platform":"linkedin"}}}' \
  --max-time 60 2>/dev/null || echo "{}")
COPY_LEN=$(echo "$CONTENT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('result',{}).get('copy','')))" 2>/dev/null || echo "0")
if [[ "$COPY_LEN" -gt 0 ]]; then
  pass "generate_content returned ${COPY_LEN} chars of copy"
else
  fail "generate_content returned empty copy"
fi

# CHECK 6
echo "CHECK 6: generate_visual with template source"
VISUAL=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"generate_visual","arguments":{"content":{"platform":"linkedin","copy":"Test post content","hashtags":["#test"],"cta":"Learn more","estimated_reading_time":1,"word_count":3},"template_id":"linkedin-single","source":"template"}}}' \
  --max-time 60 2>/dev/null || echo "{}")
FORMAT=$(echo "$VISUAL" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('format',''))" 2>/dev/null || echo "")
if [[ "$FORMAT" == "png" ]]; then
  pass "generate_visual returned format=png"
else
  fail "generate_visual returned format='${FORMAT}' (expected 'png')"
fi

# CHECK 7
echo "CHECK 7: Rate limiting enforced for demo tier"
DEMO_KEY=$(curl -sf -X POST http://localhost:8000/admin/tenants/demo \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}' --max-time 15 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null || echo "")
if [[ -z "$DEMO_KEY" ]]; then
  fail "Could not create demo session"
else
  for i in $(seq 1 5); do
    curl -s -X POST http://localhost:8000/mcp \
      -H "X-API-Key: ${DEMO_KEY}" \
      -H "Content-Type: application/json" \
      -d '{"method":"tools/call","params":{"name":"generate_content","arguments":{"brief":{"topic":"t","trending_angles":[],"pain_points":[],"suggested_hooks":[],"platform_notes":{}},"platform":"twitter"}}}' \
      -o /dev/null --max-time 30
  done
  LIMIT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/mcp \
    -H "X-API-Key: ${DEMO_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"method":"tools/call","params":{"name":"generate_content","arguments":{"brief":{"topic":"t","trending_angles":[],"pain_points":[],"suggested_hooks":[],"platform_notes":{}},"platform":"twitter"}}}' --max-time 15)
  if [[ "$LIMIT_CODE" == "429" ]]; then
    pass "Rate limit correctly returns 429 on 6th demo call"
  else
    fail "Expected 429 rate limit, got ${LIMIT_CODE}"
  fi
fi

# CHECK 8
echo "CHECK 8: All pytest tests pass"
if docker compose exec -T mcp-server python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5; then
  pass "All MCP server pytest tests passed"
else
  fail "Some MCP server pytest tests failed"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] && echo "  ALL CHECKS PASSED ✓" && exit 0
echo "  SOME CHECKS FAILED ✗"
exit 1
