#!/usr/bin/env bash
# Checkpoint Phase 4 — Visual Templates + Open Design
set -uo pipefail
source "$(dirname "$0")/../.env" 2>/dev/null || true

PASS=0; FAIL=0
pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*" >&2; FAIL=$((FAIL+1)); }

SAMPLE='{"copy":"Test","title":"Test Title","stat_value":"94%","stat_label":"of Pakistani SMBs waste time on manual payroll","quote":"OfferBerries saved us 3 days per month","attribution":"CEO, Karachi Textiles","step_number":1,"total_steps":4,"step_title":"Step 1","step_body":"Body text here","hook":"Stop wasting 3 days on payroll","week_label":"Week 24","emoji":"🚀","body":"Announcement body","product_name":"OfferBerries ERP","slide_number":1,"total_slides":4,"slide_title":"Slide title","slide_body":"Slide body","module_color":"hr"}'

echo "══════════════════════════════════════════════"
echo "  Checkpoint Phase 4 — Templates + Open Design"
echo "══════════════════════════════════════════════"
echo ""

echo "CHECK 1: All 8 templates render as PNG"
TEMPLATES=(linkedin-single linkedin-carousel-slide twitter-stat-card instagram-quote instagram-carousel-slide youtube-thumbnail email-header announcement-card)
ALL_OK=true
for tmpl in "${TEMPLATES[@]}"; do
  curl -sf -X POST http://localhost:3001/render \
    -H "Content-Type: application/json" \
    -d "{\"template_id\":\"${tmpl}\",\"content_data\":${SAMPLE}}" \
    --output "/tmp/check-${tmpl}.png" --max-time 30
  if file "/tmp/check-${tmpl}.png" 2>/dev/null | grep -q "PNG image"; then
    echo "    ${tmpl}: PNG ✓"
  else
    echo "    ${tmpl}: FAILED ✗"
    ALL_OK=false
  fi
done
$ALL_OK && pass "All 8 templates render as PNG" || fail "Some templates failed to render"

echo "CHECK 2: Open Design custom skills registered"
OD_SKILLS=$(curl -sf -H "Authorization: Bearer ${OD_API_TOKEN}" \
  http://localhost:7456/api/skills --max-time 10 2>/dev/null || echo "[]")
CUSTOM=$(echo "$OD_SKILLS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len([x for x in d if 'linkedin-social-post' in x.get('name','')]))" 2>/dev/null || echo "0")
[[ "$CUSTOM" -gt 0 ]] && pass "Custom OD skills registered (${CUSTOM})" || fail "Custom OD skills not found"

echo "CHECK 3: Open Design generates artifact"
ARTIFACT=$(curl -sf -X POST \
  -H "Authorization: Bearer ${OD_API_TOKEN}" \
  -H "Content-Type: application/json" \
  http://localhost:7456/api/generate \
  -d '{"prompt":"Create a LinkedIn post about OfferBerries HR payroll module","skill":"linkedin-social-post","design_system":"offerberries"}' \
  --max-time 60 2>/dev/null || echo "{}")
HTML_LEN=$(echo "$ARTIFACT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('html','')))" 2>/dev/null || echo "0")
[[ "$HTML_LEN" -gt 100 ]] && pass "OD generated artifact (${HTML_LEN} chars HTML)" || fail "OD artifact empty"

echo "CHECK 4: Renderer test suite"
if docker compose exec -T renderer node --test tests/test_render.js; then
  pass "Renderer test suite passed"
else
  fail "Renderer test suite failed"
fi

echo "CHECK 5: generate_visual with open_design source"
VISUAL=$(curl -sf -X POST http://localhost:8000/mcp \
  -H "X-API-Key: ${OWNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"generate_visual","arguments":{"content":{"platform":"linkedin","copy":"OfferBerries HR module launch","hashtags":["#HRSoftware"],"cta":"Learn more","estimated_reading_time":1,"word_count":5},"template_id":"linkedin-social-post","source":"open_design"}}}' \
  --max-time 90 2>/dev/null || echo "{}")
FORMAT=$(echo "$VISUAL" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('format',''))" 2>/dev/null || echo "")
[[ "$FORMAT" == "png" ]] && pass "generate_visual(open_design) returned png" || fail "Expected format=png, got '${FORMAT}'"

echo ""
echo "══════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] && echo "  ALL CHECKS PASSED ✓" && exit 0
echo "  SOME CHECKS FAILED ✗"; exit 1
