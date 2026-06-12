#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# ── 1. Check prerequisites ─────────────────────────────────────────────────
info "Checking prerequisites..."
if ! command -v docker &>/dev/null; then
  error "Docker is not installed. Install it from https://docs.docker.com/get-docker/"
  exit 1
fi
if ! docker compose version &>/dev/null; then
  error "Docker Compose v2 is required. Update Docker or install the compose plugin."
  exit 1
fi
if ! command -v node &>/dev/null; then
  warn "Node.js not found — MongoDB seeding step will be skipped locally. It runs inside the container."
fi
info "Docker $(docker --version | cut -d' ' -f3) ready."

# ── 2. Ensure .env exists ──────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  warn ".env not found — copying .env.example"
  cp .env.example .env
  echo ""
  echo "Please fill in the following required values in .env:"
  REQUIRED_VARS=(DOMAIN MONGODB_URI SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_KEY
                 OPENROUTER_API_KEY PERPLEXITY_API_KEY APIFY_API_TOKEN FAL_API_KEY
                 N8N_BASIC_AUTH_USER N8N_BASIC_AUTH_PASSWORD
                 SAFEPAY_API_KEY TWOCHECKOUT_SELLER_ID)
  for v in "${REQUIRED_VARS[@]}"; do
    current=$(grep "^${v}=" .env | cut -d= -f2-)
    if [[ -z "$current" ]]; then
      echo -n "  Enter ${v}: "
      read -r val
      sed -i "s|^${v}=.*|${v}=${val}|" .env
    fi
  done
fi
source .env

# ── 3. Generate missing secrets ────────────────────────────────────────────
info "Generating missing secrets..."
gen_secret() {
  local key="$1"
  local length="${2:-32}"
  local current
  current=$(grep "^${key}=" .env | cut -d= -f2- | tr -d ' #' | awk '{print $1}')
  if [[ -z "$current" ]]; then
    local secret
    secret=$(openssl rand -hex "$length")
    sed -i "s|^${key}=.*|${key}=${secret}|" .env
    echo "  Generated ${key}"
  fi
}

gen_secret OWNER_API_KEY 32
gen_secret OD_API_TOKEN 32
gen_secret POSTGRES_PASSWORD 24
gen_secret NEXTAUTH_SECRET 32
gen_secret N8N_ENCRYPTION_KEY 32
gen_secret POSTIZ_SECRET 32
gen_secret GRAFANA_ADMIN_PASSWORD 16
gen_secret N8N_WEBHOOK_TOKEN 32

# Set default OWNER_TENANT_ID if missing
if [[ -z "$(grep "^OWNER_TENANT_ID=" .env | cut -d= -f2-)" ]]; then
  sed -i "s|^OWNER_TENANT_ID=.*|OWNER_TENANT_ID=00000000-0000-0000-0000-000000000001|" .env
fi

source .env

# ── 4. Pull images ─────────────────────────────────────────────────────────
info "Pulling Docker images (this may take several minutes)..."
docker compose pull

# ── 5. Start services ─────────────────────────────────────────────────────
info "Starting all services..."
docker compose up -d --build

# ── 6. Wait for health checks ──────────────────────────────────────────────
SERVICES=(redis postgres renderer mcp-server dashboard n8n)
TIMEOUT=120

info "Waiting for services to become healthy..."
for svc in "${SERVICES[@]}"; do
  elapsed=0
  echo -n "  Waiting for ${svc}..."
  while true; do
    state=$(docker compose ps --format json 2>/dev/null | \
            python3 -c "import sys,json; data=sys.stdin.read();
items=[json.loads(l) for l in data.strip().splitlines() if l.strip()];
svc=[x for x in items if '${svc}' in x.get('Name','') or '${svc}' in x.get('Service','')];
print(svc[0].get('Health','') if svc else 'unknown')" 2>/dev/null || echo "unknown")
    if [[ "$state" == "healthy" ]]; then
      echo " healthy ✓"
      break
    fi
    if [[ $elapsed -ge $TIMEOUT ]]; then
      echo " TIMEOUT"
      warn "Service ${svc} did not become healthy within ${TIMEOUT}s."
      break
    fi
    sleep 5
    elapsed=$((elapsed + 5))
    echo -n "."
  done
done

# ── 7. Seed MongoDB ────────────────────────────────────────────────────────
info "Seeding MongoDB owner tenant and API key..."
docker compose exec -T mcp-server python3 - <<'PYEOF'
import os, hashlib, datetime
from pymongo import MongoClient

uri = os.environ["MONGODB_URI"]
db_name = os.environ["MONGODB_DB"]
owner_tenant_id = os.environ["OWNER_TENANT_ID"]
owner_api_key = os.environ["OWNER_API_KEY"]

client = MongoClient(uri)
db = client[db_name]

# Seed tenant
tenants = db["tenants"]
if not tenants.find_one({"_id": owner_tenant_id}):
    tenants.insert_one({
        "_id": owner_tenant_id,
        "tier": "owner",
        "name": "Owner",
        "email": "",
        "created_at": datetime.datetime.utcnow(),
    })
    print("  Seeded owner tenant")
else:
    print("  Owner tenant already exists")

# Seed API key
api_keys = db["api_keys"]
key_hash = hashlib.sha256(owner_api_key.encode()).hexdigest()
if not api_keys.find_one({"key_hash": key_hash}):
    api_keys.insert_one({
        "key_hash": key_hash,
        "key_prefix": "ofb_owner_",
        "tenant_id": owner_tenant_id,
        "tier": "owner",
        "created_at": datetime.datetime.utcnow(),
        "revoked_at": None,
        "last_used_at": None,
    })
    print("  Seeded owner API key")
else:
    print("  Owner API key already exists")

client.close()
print("  MongoDB seeding complete")
PYEOF

# ── 8. Print summary ───────────────────────────────────────────────────────
source .env
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  OfferBerries Marketing Agent — Setup Complete     ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "  Dashboard:   https://agent.${DOMAIN}"
echo "  Design:      https://design.${DOMAIN}"
echo "  n8n:         https://n8n.${DOMAIN}"
echo "  Monitoring:  https://monitoring.${DOMAIN}"
echo ""
echo "  Owner API Key: ${OWNER_API_KEY:0:12}..."
echo ""
echo "  Next: bash scripts/checkpoint_phase1.sh"
echo ""
