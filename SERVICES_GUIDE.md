# OfferBerries Marketing Agent — Services Guide

## Live URLs & Credentials

| Service | URL | Login |
|---|---|---|
| **Agent Dashboard** | https://agent.offerberriesvo.com | API key (see below) |
| **Social Scheduler (Postiz)** | https://agent.offerberriesvo.com/postiz | Create account on first visit |
| **Automation (n8n)** | https://n8n.offerberriesvo.com | `Ihsankhan` / `Mintfever@29` |
| **Monitoring (Grafana)** | https://monitoring.offerberriesvo.com | `admin` / see .env |
| **Design API** | https://design.offerberriesvo.com | Bearer token (API only) |

**Dashboard API Key:** stored in `.env` as `OWNER_API_KEY`

---

## What Each Service Does

### Agent Dashboard (`agent.offerberriesvo.com`)
Your main control center. Login with the OWNER_API_KEY.

| Page | Purpose |
|---|---|
| **Queue** | Review and approve posts before they publish. Has "Run Agent" to kick off a campaign by topic. |
| **Analytics** | Impressions, clicks, top posts, platform breakdown, AI recommendations. |
| **Templates** | The 8 visual card designs the agent uses for images. |
| **Settings** | Connect social accounts (via Postiz), configure brand voice, posting schedule. |
| **Demo** | Sandbox — try the agent without real social accounts. |

### Social Scheduler (`/postiz`)
Full open-source social media scheduling tool (Gitroom/Postiz). Create an account on first visit — any email/password.
- Connect LinkedIn, Instagram, Twitter/X, YouTube
- Calendar view for scheduled posts
- The agent publishes through this automatically once Phase 3 is live

**Do this first:** Connect your social accounts here so they're ready when the agent starts generating content.

### n8n Automation (`n8n.offerberriesvo.com`)
Visual workflow automation. Currently empty — used in later phases for:
- "When a post gets 500+ likes → generate follow-up"
- Weekly performance email reports
- Cross-platform republishing triggers

### Grafana Monitoring (`monitoring.offerberriesvo.com`)
System metrics — server health, request rates, container resources. Useful once running real campaigns.

### Open Design (`design.offerberriesvo.com`)
API-only visual rendering daemon. The agent calls it to generate image cards. Not for direct browser use.

---

## The Full Agent Workflow (when complete)

```
You → Dashboard → type a topic ("Eid sale for clothing SMB")
         ↓
   Agent researches trending content (Perplexity + Apify scraping)
         ↓
   Agent generates captions for LinkedIn, Instagram, Twitter
         ↓
   Agent renders visual cards (announcement-card, promo-card, etc.)
         ↓
   Posts land in your Queue awaiting approval
         ↓
   You approve → Postiz schedules & publishes automatically
         ↓
   Analytics feed back → agent learns what works for your brand
```

---

## Phase Completion Status

| Phase | What it covers | Status |
|---|---|---|
| 1 | Infrastructure (12 services, TLS, auth, DB) | ✅ Complete — 12/12 checks |
| 2 | MCP Server tools (research, scrape, generate, render, queue, analytics) | 🔄 In progress |
| 3 | LangGraph agent brain (research→content→visual→publish loop) | ⏳ Pending |
| 4 | Visual templates (8 HTML card designs + Open Design skills) | ⏳ Pending |
| 5 | Analytics feedback loop (Supabase, pattern extractor) | ⏳ Pending |
| 6 | Multi-tenant + demo sessions + payments (Safepay/2Checkout) | ⏳ Pending |

---

## Infrastructure Quick Reference

**Server:** 167.233.26.146 (Hetzner)  
**Compose files:** `/root/docker-compose.yml` + `/root/docker-compose.override.yml`  
**Env file:** `/root/.env`  
**Checkpoint scripts:** `/root/scripts/checkpoint_phaseN.sh`

### 12 Docker Services
`caddy` · `crew-runner` · `dashboard` · `grafana` · `mcp-server` · `n8n` · `open-design` · `postgres` · `prometheus` · `redis` · `renderer` · `postiz`

### Key Infrastructure Notes
- **Postiz quirks:** `TEMPORAL_TLS=true` (skips broken search attribute registration); DATABASE_URL hardcoded to postgres IP `172.23.0.3` (bypasses dual-network DNS ambiguity); port `3000:3000` exposes NestJS backend
- **Postgres:** md5 auth (not scram-sha-256) for driver compatibility
- **Cloudflare DNS:** all 4 subdomains set to DNS-only (grey cloud, no proxy) — required for Let's Encrypt TLS to work
- **Caddy:** DNS-01 ACME via Cloudflare plugin; CF token needs `Zone:Zone:Read` + `Zone:DNS:Edit`
- **Temporal:** old-stack container at `172.22.0.9:7233`; needs `/opt/offerberries-marketing-agent/dynamicconfig/development-sql.yaml`

### Useful Commands (run on server as root)
```bash
# Check all services
docker compose ps

# View logs for a service
docker compose logs -f <service-name>

# Run a phase checkpoint
bash scripts/checkpoint_phase1.sh

# Restart a single service
docker compose restart <service-name>

# Rebuild and restart after code changes
docker compose up -d --build <service-name>
```
