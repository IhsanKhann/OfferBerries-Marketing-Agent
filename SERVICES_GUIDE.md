# OfferBerries Marketing Agent — Complete User Guide

## Live URLs

| Service | URL | Access |
|---|---|---|
| **Agent Dashboard** | https://agent.offerberriesvo.com | API key login (see below) |
| **Social Scheduler (Postiz)** | https://agent.offerberriesvo.com/postiz | Create account on first visit |
| **Automation (n8n)** | https://n8n.offerberriesvo.com | `Ihsankhan` / `Mintfever@29` |
| **Monitoring (Grafana)** | https://monitoring.offerberriesvo.com | `admin` / check `.env → GRAFANA_ADMIN_PASSWORD` |
| **Design API** | https://design.offerberriesvo.com | Bearer token — API only |

---

## Step 1 — How to Log In

1. Open **https://agent.offerberriesvo.com**
2. You will see a login page with a single "API Key" field
3. Enter your `OWNER_API_KEY` — get it from the server:
   ```bash
   grep OWNER_API_KEY /root/.env
   ```
4. Click **Login** — you land on the **Queue** page

The session is stored as a secure cookie. You stay logged in until you click **Sign Out** in the sidebar.

---

## Dashboard Layout

The dashboard has a collapsible **left sidebar** with two sections:

**Main**
- Queue
- Runs
- Analytics
- Templates
- Usage

**Account**
- Settings
- Billing
- Tenants
- Demo

Click the `<` arrow at the top of the sidebar to collapse it to icon-only mode.

---

## Page-by-Page Guide

---

### Queue — `/queue`

**What it is:** The legacy control panel. Type a topic and trigger the old-style agent run directly from here. Shows the post queue that results from those runs.

**What you see:**
- A pipeline progress tracker (Research → Generate → Visual → Queue → Analytics → Self-Improve) with live status dots
- A list of posts waiting in queue — platform icon, caption preview, scheduled date
- An "Agent Chat" panel where you can type a topic and pick research model + platforms

**How to use it:**
1. In the "Agent Chat" panel, type a topic — e.g. `"World Cup cricket Pakistan SMBs"`
2. Select which platforms you want (LinkedIn, Twitter, Instagram, YouTube, Email)
3. Pick a research model:
   - **Sonar** (~$0.001) — fast, standard web search
   - **Sonar Pro** (~$0.004) — deeper research, better citations
   - **Deep Research** (~$0.056) — comprehensive multi-step research
4. Click **Run Agent**
5. The pipeline tracker animates as each stage completes (Research → Generate → Visual → Queue)
6. Posts appear in the queue below once done
7. Click **Approve** to mark a post ready to publish, **Reject** to discard it

> **Note:** The Queue page uses the older `/agent/run` endpoint. For the full pipeline with stage-by-stage review, use the **Runs** page instead.

---

### Runs — `/runs`

**What it is:** The main agent pipeline manager. Every run here goes through a structured 4-stage pipeline with human-in-the-loop review at each stage.

**What you see:**
- A list of all runs with status badges: Pending / Running / Awaiting Review / Completed / Failed / Cancelled
- Status filter chips at the top to filter by state
- **New Run** button (top right)
- **Refresh** button

**Run status colours:**
- Blue = Running
- Amber = Awaiting your review (paused)
- Green = Completed
- Red = Failed
- Grey = Cancelled or Pending

**How to start a new run:**
1. Click **+ New Run**
2. Fill in the form:
   - **Topic** — what you want to create content about (e.g. `"Eid sale for textile businesses"`)
   - **Platforms** — checkboxes for LinkedIn, Twitter, Instagram, YouTube, Email
   - **Research model** — choose Sonar / Sonar Pro / Deep Research
   - **Execution mode** — `supervised` (you review each stage) or `automated` (runs straight through)
   - **Stages to enable** — toggle Research, Content Generation, Visual Generation, Scheduling
3. Click **Start Run**
4. You are redirected to the **Run Detail** page

**How to filter runs:**
- Click the chip buttons at the top: All / Running / Awaiting Review / Completed / Failed
- Each chip filters the list in real time

---

### Run Detail — `/runs/[id]`

**What it is:** The live view of a single run. Shows each pipeline stage and lets you review, edit, approve, or reject outputs. Updates in real time via SSE (Server-Sent Events).

**The 4 stages shown in order:**

#### Stage 1 — Research
- Status: Pending → Running → Paused (when supervised)
- When paused: Shows the full **ResearchBrief** — topic summary, trending angles, pain points, competitor insights, suggested hooks, platform notes
- You can **edit any field** directly in the review card
- Click **Approve Research** to use it as-is, or **Redo** to run research again
- The brief passes directly into content generation

#### Stage 2 — Content Generation
- Generates platform-specific copy for every platform you selected
- Each platform gets: post copy, hashtags, CTA
- When paused: shows the generated output as JSON
- Click **Approve** or **Redo**

#### Stage 3 — Visual Generation
- Calls the visual brief generator first (LLM picks layout, headline, mood), then renders the image
- When paused or approved: shows the **Visual Editor Panel** (see below)
- Click **Approve** or **Redo**

**Visual Editor Panel (D3):**
This appears automatically for the visual_generation stage:
- **Preview area** — shows the rendered visual (1:1 aspect ratio)
- **Refinement instructions** — type what to change, e.g. `"make background darker, bolder headline"`
- **Model selector** — Flux (fal.ai) / OpenDesign / Template renderer
- **↻ Regenerate Visual** — sends your instruction + regenerates. Instructions are cumulative (each run builds on the previous)
- **✓ Use This Visual** — approves this visual and moves the run forward
- **Instruction history** — collapse/expand toggle showing all prior regeneration attempts with timestamps

#### Stage 4 — Scheduling
- Queues approved posts to Postiz for publishing
- Shows scheduled date/time per platform

**Bottom of the page — Cost Summary:**
After a run completes, a cost breakdown card appears showing:
- Every tool that was called (research_trends, generate_content, generate_visual_brief, generate_visual)
- Number of calls each tool made
- Cost in USD per tool
- Total run cost

**Cancel a run:**
Click the **Cancel** button (top right of the Run Detail page). Only visible while the run is not yet terminal (not completed/failed/cancelled).

---

### Analytics — `/analytics`

**What it is:** Post performance data pulled from Postiz.

**What you see:**
- 4 KPI cards: Total Impressions, Total Clicks, Best Day, Best Template
- Trend badge (Growing / Flat / Declining)
- Per-platform breakdown (impressions, clicks, engagement rate per platform)
- Top performing posts table
- AI recommendations based on the data

**How to use it:**
- Click **7d / 14d / 30d** chips at the top to change the reporting period
- Click **↻ Refresh** to reload data

> Analytics require Postiz to be connected with live social accounts. Without published posts, the report will be empty.

---

### Templates — `/templates`

**What it is:** The visual template library. Built-in templates are rendered by the Playwright renderer. You can also upload your own HTML templates.

**Built-in templates (8):**

| Template | Platform | Size |
|---|---|---|
| LinkedIn Single | LinkedIn | 1080×1080 |
| LinkedIn Carousel Slide | LinkedIn | 1080×1080 |
| Twitter Stat Card | Twitter | 1600×900 |
| Instagram Quote | Instagram | 1080×1080 |
| Instagram Carousel Slide | Instagram | 1080×1080 |
| YouTube Thumbnail | YouTube | 1280×720 |
| Email Header | Email | 600×200 |
| Announcement Card | General | 1080×1080 |

**How to use Templates:**

**Filter by platform:** Click the platform chips at the top (All / LinkedIn / Twitter / Instagram / YouTube / Email / General)

**Preview a template:** Click the **Preview** button on any card — opens a full-size modal showing a rendered PNG with sample data

**Edit a template name/description:** Click the pencil icon on any template card

**Add a custom template:**
1. Click the **+ Add Template** dashed card at the end of the grid
2. Fill in: Name, Description, Platform
3. Choose **Paste Code** (type/paste HTML) or **Upload File** (select .html file)
4. Add optional CSS (or include `<style>` tags in your HTML)
5. A live preview renders as you type
6. Click **Add Template** — it appears in the grid immediately

**Delete a custom template:** Click the trash icon — click again within 3 seconds to confirm (built-in templates cannot be deleted)

**Use a template:** Click **Use Template** — this sets it as the default for the next agent run

> **Tip:** Templates support `{{variable}}` placeholders (e.g. `{{headline}}`, `{{copy}}`, `{{cta}}`). The backend auto-extracts these when you upload via the API.

---

### Usage — `/usage`

**What it is:** API usage dashboard showing how many tool calls you've made, rate limit status, and credit consumption.

**What you see:**
- Current tier and its limits per tool
- Usage counters per tool for the current period
- Reset date for rate limits

---

### Settings — `/settings`

**What it is:** All configuration for how the AI agent generates content.

**Sections:**

#### 1. OfferBerries API Access
- Shows your API key (masked) and current tier (Owner / Pro / Starter / Demo)
- **Copy** button to copy the key to clipboard
- Tier permissions grid showing which tools are enabled at your tier

#### 2. Content Generation Model
- Select which OpenRouter LLM generates your post copy
- Models grouped into: **Fast & Economical** / **Balanced** / **Premium**
- Each row shows: model name, context length, price per 1M tokens, description
- Click **Select** on any model — it saves immediately

**Default:** `google/gemini-2.5-flash` (recommended — fast and cheap)

#### 3. Brand Voice (legacy text field)
- Free-text box describing your brand's tone and style
- Example: `"Write in a direct, honest tone. No corporate jargon. Focus on ROI for Pakistani SMBs. Always include local context."`
- Click **Save Brand Voice**

#### 4. Brand Voice Profile (structured)
- **Tone** — professional / casual / witty / authoritative
- **Personality** — one-line brand personality statement
- **Writing Style** — how sentences should be structured
- **Avoid Phrases** — comma-separated words/phrases to never use
- **Platform Overrides** — per-platform tone adjustments (e.g. Twitter = punchy, LinkedIn = insight-driven)
- **Example CTAs** — sample calls-to-action to guide the LLM
- Click **Save Profile**

> The structured Voice Profile (C2) overrides the free-text brand voice. The AI now loads the default voice profile from the database and uses its `hashtag_style` and `cta_type` settings to control hashtag and CTA generation.

#### 5. Content Strategy
- **Topic Focus** — default topic domain (e.g. `hr_payroll`)
- **Format Preference** — Carousel / Single / Video Script
- Click **Save Strategy**

#### 6. Social Accounts
- Click **Manage in Postiz** to open Postiz and connect LinkedIn, Instagram, Twitter/X, YouTube

#### 7. Danger Zone
- **Clear Agent Memory** — removes agent run history (click twice to confirm)
- **Reset Strategy** — restores default topic focus and format

---

### Billing — `/billing`

**What it is:** Subscription and payment management. Shows current plan, usage this billing period, and upgrade options.

> Payment integration (Safepay/2Checkout) is wired but not live yet. Plans and usage display are functional.

---

### Tenants — `/tenants`

**What it is:** Multi-tenant management (owner-only). Create and manage sub-tenants, issue API keys, set tiers.

**How to create a tenant:**
1. Go to `/tenants`
2. Click **New Tenant**
3. Fill in name, email, tier (free / starter / pro)
4. An API key is generated — share it with the tenant
5. They can log in at the same URL with their key

---

### Demo — `/demo`

**What it is:** Create time-limited demo sessions for prospects. A demo session gets a restricted API key (tier = "demo") with limited tool calls and no publishing.

**How to create a demo:**
1. Go to `/demo`
2. Click **Create Demo Session**
3. Set expiry (e.g. 24h, 7d)
4. Share the generated API key with your prospect
5. They log in and can try the agent with read-only / limited tools

---

## How the Full Workflow Works (End to End)

```
You → Open /runs/new → Configure run (topic + platforms + mode)
              ↓
        Crew Runner starts LangGraph pipeline
              ↓
  Stage 1: MCP research_trends (Perplexity searches live web)
              ↓ [pause if supervised → you review the brief]
  Stage 2: MCP generate_content (OpenRouter/LLM writes copy per platform)
              ↓ [pause if supervised → you review content]
  Stage 3: MCP generate_visual_brief (LLM creates art-direction brief)
         → MCP generate_visual (Renderer/OpenDesign/Flux renders image)
              ↓ [pause if supervised → Visual Editor appears]
                → you refine with instructions → regenerate → approve
  Stage 4: MCP queue_post (sends to Postiz for scheduling)
              ↓
      Cost breakdown shown on Run Detail page
              ↓
  Postiz publishes at scheduled time to your connected accounts
```

---

## What the Frontend Shows — New Features

### Visual Editor Panel (D3)
Appears automatically on the Visual Generation stage card when the run is paused or approved. Shows the rendered visual with controls to refine and regenerate it without restarting the run.

### Research Model Tier Gating
The `/runs/new` form and Queue page both show only the research models your tier is allowed to use. Owner and Pro see all 3. Starter sees Sonar + Sonar Pro. Free sees Sonar only.

### Voice Profiles (C2)
Settings → Brand Voice Profile now saves to the `voice_profiles` collection. The agent loads the default profile on every content generation run and uses its `hashtag_style` (branded / contextual / educational / discovery) and `cta_type` (demo / learn_more / engagement / contextual) to control what the LLM generates.

### Template Upload (D2)
Templates page → Add Template now saves to the database (not just component state). `{{variable}}` placeholders in uploaded HTML are auto-extracted and stored.

---

## Connect Your Social Accounts

1. Go to **https://agent.offerberriesvo.com/postiz**
2. Create a Postiz account
3. Go to **Settings → Social Accounts** inside Postiz
4. Connect LinkedIn, Twitter/X, Instagram, YouTube
5. Once connected, runs that reach Stage 4 will queue posts to Postiz which auto-publishes at the scheduled time

---

## Infrastructure Reference

**Server:** Hetzner VPS — `167.233.26.146`  
**Compose root:** `/root/offerberries-marketing-agent/`  
**Env file:** `/root/offerberries-marketing-agent/.env`

### Docker Services

| Container | Role | Internal Port |
|---|---|---|
| `caddy` | Reverse proxy + TLS (Cloudflare DNS-01) | 443 public |
| `dashboard` | Next.js 14 frontend | 3002 |
| `mcp-server` | FastAPI MCP tool server | 8000 |
| `crew-runner` | LangGraph pipeline runner | 8001 |
| `renderer` | Playwright PNG renderer | 3001 |
| `open-design` | OpenDesign visual API | 7456 |
| `postiz` | Social media scheduler | 4200 |
| `postgres` | Primary database | 5432 |
| `redis` | Cache + rate limits | 6379 |
| `n8n` | Automation workflows | 5678 |
| `grafana` | Metrics dashboard | 3003 |
| `prometheus` | Metrics collector | 9090 |

### Useful Server Commands

```bash
# All containers status
cd /root/offerberries-marketing-agent && docker compose ps

# Live logs for a service
docker compose logs -f mcp-server
docker compose logs -f crew-runner
docker compose logs -f dashboard

# Restart a single service
docker compose restart mcp-server

# Rebuild after code change (CI/CD does this automatically on git push)
docker compose build mcp-server && docker compose up -d mcp-server

# Quick health checks
curl http://localhost:8000/health          # MCP server
curl http://localhost:8001/health          # Crew runner
curl http://localhost:3002/api/health      # Dashboard

# Check all 3 research models are visible
OWNER_KEY=$(grep OWNER_API_KEY .env | cut -d= -f2)
curl -s -H "X-API-Key: $OWNER_KEY" http://localhost:8000/research-models

# List voice profiles for owner tenant
curl -s -H "X-API-Key: $OWNER_KEY" http://localhost:8000/voice-profiles
```

---

## MCP Tool Reference

The MCP server exposes 8 tools callable by the pipeline:

| Tool | What it does | Cost |
|---|---|---|
| `research_trends` | Live web research via Perplexity | $0.0014–$0.056 per call |
| `scrape_competitor` | Scrape competitor social posts via Apify | Apify credits |
| `generate_content` | Write platform copy via OpenRouter LLM | ~$0.0003 per platform |
| `generate_visual_brief` | LLM creates art-direction brief | ~$0.0001 per platform |
| `generate_visual` | Render PNG via Renderer/OpenDesign/Flux | $0 (renderer) or Flux credits |
| `queue_post` | Send post to Postiz scheduler | Free |
| `get_analytics` | Fetch analytics from Postiz | Free |
| `update_strategy` | Update weekly content strategy doc | Free |

### Admin Endpoints (owner-only)

```bash
# List all research models (admin)
curl -H "X-API-Key: $OWNER_KEY" http://localhost:8000/admin/research-models

# Add a new research model
curl -X POST -H "X-API-Key: $OWNER_KEY" -H "Content-Type: application/json" \
  -d '{"id":"sonar-reasoning","display_name":"Sonar Reasoning","cost_usd_per_call":0.005,"credits_per_call":5,"tier_required":"starter"}' \
  http://localhost:8000/admin/research-models

# Disable a research model
curl -X PATCH -H "X-API-Key: $OWNER_KEY" -H "Content-Type: application/json" \
  -d '{"is_active":false}' \
  http://localhost:8000/admin/research-models/sonar-reasoning
```

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| Login fails | Confirm `OWNER_API_KEY` from `.env` — must match exactly, no trailing space |
| Runs page shows 0 runs | DB might be empty — start your first run via **+ New Run** |
| Run stuck on "Research" | Check `docker compose logs crew-runner` and `docker compose logs mcp-server` |
| Visual not rendering | Check `docker compose logs renderer` — Playwright might need a restart |
| Only 2 research models showing | Owner key tier might be "starter" in DB — run the tier fix command below |
| Analytics shows no data | Social accounts not connected to Postiz yet |
| Site unreachable (TLS error) | Check `docker compose logs caddy` — Cloudflare API token may have expired |

**Fix owner key tier (if research models showing wrong count):**
```bash
cd /root/offerberries-marketing-agent
OWNER_KEY=$(grep OWNER_API_KEY .env | cut -d= -f2)
docker exec offerberries-marketing-agent-mcp-server-1 python3 - << 'EOF'
import asyncio, os, hashlib
from motor.motor_asyncio import AsyncIOMotorClient
async def run():
    c = AsyncIOMotorClient(os.environ['MONGODB_URI'])
    db = c[os.environ['MONGODB_DB']]
    key = os.environ.get('OWNER_API_KEY', '')
    h = hashlib.sha256(key.encode()).hexdigest()
    r = await db['api_keys'].update_one({'key_hash': h}, {'$set': {'tier': 'owner'}})
    print('matched:', r.matched_count, 'modified:', r.modified_count)
asyncio.run(run())
EOF
docker exec offerberries-marketing-agent-redis-1 redis-cli FLUSHDB
```

---

## CI/CD — How Deploys Work

Every `git push` to `main` triggers the GitHub Actions workflow (`.github/workflows/deploy.yml`):

1. Code is `rsync`'d to `/root/offerberries-marketing-agent/` on the Hetzner server
2. Docker builds: `mcp-server`, `crew-runner`, `dashboard`, `renderer`
3. `docker compose down` then `docker compose up -d`
4. Health checks run — if `https://agent.offerberriesvo.com/api/health` doesn't return 200, the deploy is marked failed

Typical deploy time: **4–6 minutes**

Check the latest deploy at: `https://github.com/IhsanKhann/OfferBerries-Marketing-Agent/actions`
