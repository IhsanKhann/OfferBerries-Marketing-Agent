#!/usr/bin/env bash
# Run this ONCE from your local machine to push fresh code to Hetzner.
# After this, CI/CD takes over: every push to main auto-deploys.
#
# Usage:
#   bash scripts/deploy.sh
#   bash scripts/deploy.sh --skip-build   (just git pull, no rebuild)
set -euo pipefail

HETZNER_IP="167.233.26.146"
REMOTE_PATH="/root"
SKIP_BUILD=false
[[ "${1:-}" == "--skip-build" ]] && SKIP_BUILD=true

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[deploy]${NC} $*"; }

info "Connecting to Hetzner (${HETZNER_IP})..."

ssh -o StrictHostKeyChecking=no "root@${HETZNER_IP}" bash -s << REMOTE
set -e
cd "${REMOTE_PATH}"

echo ">>> Pulling latest code from main..."
git pull origin main

if [ "${SKIP_BUILD}" = "false" ]; then
  echo ">>> Rebuilding services with fresh code..."
  docker compose build --no-cache mcp-server crew-runner dashboard renderer

  echo ">>> Restarting services..."
  docker compose up -d --remove-orphans

  echo ">>> Waiting 60s for health checks..."
  sleep 60
fi

echo ">>> Current service status:"
docker compose ps

echo ">>> MCP health check:"
curl -sf http://localhost:8000/health && echo ""

echo ">>> Dashboard health check:"
curl -sf http://localhost:3002/api/health && echo "" || true

echo ">>> Deploy complete."
REMOTE

info "Done. Dashboard: https://agent.offerberriesvo.com"
info "Run E2E tests: ssh root@${HETZNER_IP} 'cd ${REMOTE_PATH} && bash scripts/e2e_test.sh'"
