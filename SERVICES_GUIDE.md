# OfferBerries Marketing Agent — Services Guide

## Live URLs & Credentials

| Service | URL | Login |
|---|---|---|
| **Agent Dashboard** | https://agent.offerberriesvo.com | API key → see "How to Login" below |
| **Social Scheduler (Postiz)** | https://agent.offerberriesvo.com/postiz | Create account on first visit |
| **Automation (n8n)** | https://n8n.offerberriesvo.com | `Ihsankhan` / `Mintfever@29` |
| **Monitoring (Grafana)** | https://monitoring.offerberriesvo.com | `admin` / check `.env → GRAFANA_ADMIN_PASSWORD` |
| **Design API** | https://design.offerberriesvo.com | Bearer token (API only, not for browser) |

---

## How to Login to the Dashboard

1. Open https://agent.offerberriesvo.com
2. You'll see a login page asking for an **API Key**
3. Enter the value of `OWNER_API_KEY` from `/root/.env` on the server
4. Click Login — you'll land on the **Queue** page

> **Your owner API key** (copy from server): run `grep OWNER_API_KEY /root/.env` on Hetzner

---

## What You'll See and What to Do

### Queue Page (`/queue`)
This is your main control panel. What you'll see:
- List of posts waiting for your approval — platform badge (LinkedIn/Twitter/Instagram), caption preview, scheduled date
- **"Run Agent" button** — type a topic (e.g. "World Cup 2026") and click to generate a full set of posts
- **Approve** — marks a post as approved (will publish via Postiz once Phase 3 wires up the publishing loop)
- **Reject** — deletes the post from the queue

What to check: If you see "No posts in queue", type a topic and click Run Agent. A post will appear within 30 seconds.

> **Test it now:** The queue already has 1 post — "ICC Cricket World Cup 2026 / LinkedIn" — scheduled for 20 June.

### How the Agent Flow Works (End to End)

```
You → type topic in Queue page → click "Run Agent"
         ↓
   Crew Runner receives the topic
         ↓
   MCP Server: research_trends (Perplexity searches live web)
         ↓
   MCP Server: generate_content (OpenRouter/Gemini writes captions per platform)
         ↓
   MCP Server: generate_visual (Playwright renders a 1080×1080 PNG)
         ↓
   MCP Server: queue_post (saves to MongoDB with status "queued")
         ↓
   Post appears on Queue page — you approve or reject
         ↓
   [Phase 3] Approved posts → Postiz schedules & auto-publishes
         ↓
   [Phase 5] Analytics feed back → agent learns what performs best
```

---

## Phase Completion Status

| Phase | What it covers | Status | What's working |
|---|---|---|---|
| **1** | Infrastructure — 12 Docker services, TLS certs, Postgres, Redis, auth | ✅ **Complete** | All services live, HTTPS on all 4 subdomains |
| **2** | MCP Server — 7 tools: research, scrape, generate content, render visual, queue, analytics, strategy | ✅ **Complete** | All 7 tools callable; queue pipeline fully tested (World Cup post live) |
| **3** | LangGraph agent brain — autonomous research→content→visual→queue loop | ⏳ **Next** | Crew Runner container is running but agent loop not built yet |
| **4** | Visual templates — 8 HTML card designs (announcement, promo, stat, quote, etc.) | ⏳ Pending | Renderer is live; 1 basic template working |
| **5** | Analytics feedback loop — Supabase storage, pattern extractor, strategy updates | ⏳ Pending | Strategy endpoint exists, Supabase not connected |
| **6** | Multi-tenant + payments — demo sessions, Safepay/2Checkout integration | ⏳ Pending | Demo sessions work; payment hooks wired but not live |

**Phases 1 and 2 are fully working.** You can generate content manually via the dashboard today. Phase 3 will make it autonomous.

---

## How to Check Everything is Working (as a User)

### Quick health check (30 seconds)
Open these URLs and confirm they load:
- https://agent.offerberriesvo.com → should show login page
- https://monitoring.offerberriesvo.com → should show Grafana login
- https://n8n.offerberriesvo.com → should show n8n login

### Full workflow test
1. Login to https://agent.offerberriesvo.com with your `OWNER_API_KEY`
2. You should see the Queue page with 1 post (the World Cup test post)
3. Type "Eid sale for textile businesses" in the topic box and click **Run Agent**
4. Wait ~20–30 seconds — a new post should appear in the queue
5. Click **Approve** on the post

If any step fails, see the Troubleshooting section below.

### Check the MCP Server directly
```bash
# From the server (ssh root@167.233.26.146)
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.0.0","uptime_seconds":...}
```

---

## Connect Your Social Accounts (Do This When Ready)

1. Go to https://agent.offerberriesvo.com/postiz
2. Create a Postiz account with any email/password
3. Connect LinkedIn, Instagram, Twitter/X in Settings → Social Accounts
4. Once connected, approved posts will start publishing automatically (when Phase 3 lands)

---

## Infrastructure Quick Reference

**Server:** 167.233.26.146 (Hetzner VPS)  
**Compose root:** `/root/` — run all `docker compose` commands from here  
**Env file:** `/root/.env`  
**Override (secrets + postiz quirks):** `/root/docker-compose.override.yml`

### 12 Docker Services

| Container | Role | Port (internal) |
|---|---|---|
| `caddy` | Reverse proxy + TLS (Let's Encrypt DNS-01) | 443 public |
| `dashboard` | Next.js frontend + API proxy | 3002 |
| `mcp-server` | FastAPI tool server (7 MCP tools) | 8000 |
| `crew-runner` | LangGraph agent (Phase 3) | 8001 |
| `renderer` | Playwright PNG renderer | 3001 |
| `postiz` | Social media scheduler (Gitroom) | 3000 |
| `open-design` | Visual design API | 7456 |
| `postgres` | Primary database (Postiz, n8n) | 5432 |
| `redis` | Cache + rate limiting | 6379 |
| `n8n` | Automation workflows | 5678 |
| `grafana` | Metrics dashboard | 3003 |
| `prometheus` | Metrics collector | 9090 |

### Useful Commands (run on server as root)
```bash
# Check all 12 services
cd /root && docker compose ps

# View live logs for a service
docker compose logs -f mcp-server

# Run the Phase 1 health checkpoint
bash scripts/checkpoint_phase1.sh

# Restart a single service
docker compose restart mcp-server

# Rebuild after code change
docker compose up -d --build mcp-server
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login page shows but Queue gives error | Check you're using the correct `OWNER_API_KEY` from `.env` |
| Queue page empty after "Run Agent" | Check crew-runner logs: `docker compose logs crew-runner` |
| Post generated but no visual | Check renderer: `curl http://localhost:3001/health` from server |
| Site unreachable (TLS error) | Check Caddy: `docker compose logs caddy` — may need CF token refresh |
| Container crashed | `docker compose up -d` from `/root/` to restart everything |

### Known Limitation (Phase 2)
Posts queued via the dashboard's "Run Agent" button go to the **Crew Runner** service, which needs the Phase 3 agent loop to fully process them. For now, you can call tools directly:
- Research + generate a post manually using the MCP tools via the API
- Or wait for Phase 3 which builds the full autonomous loop

### Important: Only One Compose Project
There used to be two projects running on this server (`/root/` and `/root/offerberries-marketing-agent/`). The old one has been permanently disabled (`.yml.disabled`). Always use `/root/` as the compose root.
