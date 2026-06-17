`# OfferBerries AI Platform — Full Architecture Audit

> All claims below reference actual code. File:line citations are included so you can verify every statement.

---

## Part 1 — Research Layer: Current State

### Is Perplexity used?

**Yes, but only when `PERPLEXITY_API_KEY` is set.** If the key is absent the function returns hardcoded mock data and logs nothing. There is no error, no warning to the user, no indication in the UI that research was faked.

**Exact call site:** `main.py:293–301`

```python
resp = await client.post(
    "https://api.perplexity.ai/chat/completions",
    headers={"Authorization": f"Bearer {perplexity_key}"},
    json={
        "model": "sonar",                          # ← hardcoded, never changes
        "messages": [{"role": "user", "content": prompt}],
    },
)
```

**What is sent:** A single user message constructed at `main.py:288`:
```
"Trending {topic} for {platform} social media Pakistan SMB 2026. What pain points, hooks, and angles are working right now?"
```

No system prompt. No brand context. No previous research context. No temperature or max-token controls.

**What is returned:** `resp.json()["choices"][0]["message"]["content"]` — raw text string.

**How it's parsed** (`main.py:305`): Lines starting with `"-"` become `trending_angles`. Everything after position 5 becomes `pain_points`. This is unreliable — if Perplexity returns numbered lists, paragraphs, or headers, the parser misses everything. `suggested_hooks` gets only the first angle.

**Data freshness:** Perplexity `sonar` searches the live web at query time. Data can be minutes old. The model's training knowledge is also injected, so some facts can be months old. Perplexity returns `citations[]` in the response — **your code discards them entirely**.

### How Perplexity research works internally

Perplexity is not a scraper. It is a retrieval-augmented generation system:

```
Your prompt
    │
    ▼
Perplexity search index  ←── real-time web crawl + Bing/other index
    │  returns top ~5 URLs with snippets
    ▼
RAG context injected into LLM prompt
    │  (sonar = llama-based model fine-tuned for citations)
    ▼
LLM generates answer with inline [1][2] citations
    │
    ▼
Response JSON:
  choices[0].message.content   ← your code reads this
  citations[]                  ← your code discards this
```

**Sonar** scrapes/indexes public pages. It does NOT log into sites, does NOT execute JavaScript-heavy SPAs reliably, does NOT access paywalled content. It DOES provide recency — results from the last 24 hours are often included. Trustworthiness is high for facts about public companies and trends; low for precise numeric statistics.

### Architecture diagram — Research layer

```
Dashboard (queue/page.tsx)
    │  POST /api/proxy/agent/run {topic, platform_filter}
    ▼
Next.js Proxy (/api/proxy/[...path])
    │  adds X-API-Key header from ofb_session cookie
    ▼
Crew Runner (run_weekly.py :8001)
    │  POST /agent/run
    │  creates AgentState, fires asyncio.create_task
    ▼
LangGraph graph.py
    ├─► research_node()
    │       │  POST /mcp {method:"tools/call", name:"research_trends"}
    │       ▼
    │   MCP Server (main.py :8000)
    │       │  tool_research_trends()
    │       │  POST https://api.perplexity.ai/chat/completions
    │       │       model=sonar   ← only this, never sonar-pro
    │       │  returns ResearchBrief dict
    │       ▼
    │   also: tool_scrape_competitor() → Apify actor (async, 60s timeout)
    │
    ├─► content_node() → generate_content → OpenRouter
    ├─► visual_node()  → generate_visual  → Renderer/OpenDesign/Fal
    └─► queue_node()   → queue_post       → Postiz + MongoDB
```

---

## Part 2 — Perplexity Model Control

### Current implementation

Only `sonar` is used. `main.py:297`: `"model": "sonar"`. No parameter is accepted to change this. No UI controls it.

### What Perplexity actually exposes

| Model | Cost per 1M tokens (in+out) | Search quality | Use case |
|---|---|---|---|
| `sonar` | ~$1 | Good, fast | Daily topic research |
| `sonar-pro` | ~$3 | Better sources, more citations | Campaign planning |
| `sonar-deep-research` | ~$8 | Multi-step iterative search | Competitive analysis |
| `sonar-reasoning` | ~$5 | Chain-of-thought + search | Strategy documents |

Perplexity does **not** provide access to GPT, Claude, or Gemini. It has its own LLM family (sonar models) built on Llama-class architectures fine-tuned for retrieval. To use Claude/GPT/Gemini for content, you use OpenRouter — which you already have.

### Recommended implementation

Add `research_model` parameter to the tool call:

**`main.py` — `tool_research_trends` signature change:**
```python
async def tool_research_trends(
    topic: str,
    platform: str = "all",
    research_model: str = "sonar",          # sonar | sonar-pro | sonar-deep-research
    recency_filter: str = "week",           # month | week | day | hour
) -> dict:
```

**`main.py` — API call update:**
```python
json={
    "model": research_model,
    "messages": [{"role": "user", "content": prompt}],
    "return_citations": True,               # capture citations
    "search_recency_filter": recency_filter,
}
```

**`main.py` — capture citations:**
```python
raw = resp.json()
content = raw["choices"][0]["message"]["content"]
citations = raw.get("citations", [])       # list of URLs
```

**Frontend model picker (queue/page.tsx) — add research model selector:**
```typescript
const RESEARCH_MODELS = [
  { id: "sonar",                label: "Sonar (Cheapest)",  badge: "~$0.001/run" },
  { id: "sonar-pro",            label: "Sonar Pro",         badge: "~$0.003/run" },
  { id: "sonar-deep-research",  label: "Deep Research",     badge: "~$0.008/run" },
];
```

**Visual model picker — three tiers:**

| Tier | Research | Content | Visual |
|---|---|---|---|
| Cheapest | `sonar` | `meta-llama/llama-3.1-8b-instruct:free` | Template renderer |
| Balanced | `sonar-pro` | `google/gemini-2.5-flash` | OpenDesign |
| Premium | `sonar-deep-research` | `anthropic/claude-sonnet-4-6` | Flux (fal.ai) |

---

## Part 3 — Content Generation Flow

### Actual flow (from code)

```
research_node (graph.py:43)
    └─► tool_research_trends → ResearchBrief {
            topic, trending_angles[], pain_points[],
            suggested_hooks[], platform_notes{}
        }

content_node (graph.py:88)
    └─► FOR each platform in platform_filter:
            tool_generate_content(brief, platform, model)
                │
                ├─ system: brand_voice (MongoDB → /app/config/brand_voice.md)
                ├─ user: platform + char_limit + topic + angles + pain_points + hooks
                └─► OpenRouter → single LLM call → raw copy string
                        │
                        └─ PlatformContent {
                               copy,            ← full post text (truncated to char_limit)
                               hashtags: ["#OfferBerries", "#PakistanSMB"],  ← HARDCODED
                               cta: "Book a free demo",                       ← HARDCODED
                               estimated_reading_time,
                               word_count
                           }
```

### Answer to each sub-question

| Question | Answer |
|---|---|
| What LLM creates content? | OpenRouter, model configurable per tenant via `/config/content-model`. Default: `google/gemini-2.5-flash` |
| What creates captions? | Same single LLM call — the entire `copy` field is the caption |
| What creates hashtags? | **Hardcoded** `["#OfferBerries", "#PakistanSMB"]` — `main.py:436`. Not LLM-generated |
| What creates hooks? | Part of the copy — no separate extraction. Hooks from `brief.suggested_hooks` are injected as prompt context |
| What creates CTAs? | **Hardcoded** `"Book a free demo"` — `main.py:438`. Not LLM-generated |

**Critical gap:** Hashtags and CTAs are hardcoded constants. The LLM may write platform-appropriate hashtags inside `copy` but they are not extracted and they don't populate the `hashtags` field. The `cta` field is always the same string regardless of platform, topic, or audience.

### Visual node — Instagram special case

```python
# graph.py:151
source = "open_design" if platform == "instagram" else "template"
```

Instagram gets OpenDesign; all other platforms get the Playwright template renderer.

### Actual data flow diagram

```
User types topic in Chat → POST /agent/run
                              │
                    ┌─────────▼─────────┐
                    │   research_node   │
                    │  Perplexity sonar │
                    │  → ResearchBrief  │
                    └────────┬──────────┘
                             │ brief{}
                    ┌────────▼──────────┐
                    │   content_node    │
                    │  FOR each platform │
                    │  OpenRouter LLM   │
                    │  → PlatformContent│
                    │    .copy (text)   │
                    │    .hashtags [HC] │  ← HC = hardcoded
                    │    .cta [HC]      │
                    └────────┬──────────┘
                             │ platform_content{}
                    ┌────────▼──────────┐
                    │   visual_node     │
                    │  template/OD/fal  │
                    │  → VisualAsset    │
                    │    .url (PNG)     │
                    └────────┬──────────┘
                             │ visual_assets{}
                    ┌────────▼──────────┐
                    │   queue_node      │
                    │  → MongoDB posts  │
                    │  → Postiz (opt)   │
                    └───────────────────┘
```

---

## Part 4 — Visual Generation Pipeline

### How OpenDesign receives data

**`main.py:487–494` — open_design source path:**
```python
od_resp = await client.post(
    f"{od_url}/api/generate",
    headers={"Authorization": f"Bearer {od_token}"},
    json={
        "prompt": copy,                         # just the post copy text
        "skill": template_id,                   # e.g. "instagram-quote"
        "design_system": "offerberries",        # static string
    },
)
```

**What is sent:** Only the post copy text (`content.copy`). No brief, no brand colors, no research context, no competitor data, no platform dimensions explicitly.

**What is returned:** HTML string → piped to Playwright renderer as base64 → screenshot → PNG.

**What is NOT sent:** Research brief, competitor analysis, brand voice document, target audience, color palette, typography preferences, tone notes.

### How it should ideally work

The current path: `copy_text → OpenDesign`. The ideal path:

```
ResearchBrief
    + ContentCopy
    + BrandContext (colors, fonts, logo, voice)
    + PlatformSpecs (dimensions, safe zones)
    + VisualBrief (angle, emotion, key message)
    │
    ▼
Visual Brief Generation (LLM step)
    │  Input: all above
    │  Output: {
    │    headline: "3-hour payroll → 3-minute payroll",
    │    subtext: "OfferBerries HR Suite",
    │    visual_mood: "professional, clean, trustworthy",
    │    color_directive: "dominant indigo, white text",
    │    layout_hint: "stat-card with large number"
    │  }
    │
    ▼
Visual Prompt Assembly
    │  "Professional LinkedIn post card. Headline: '3-hour payroll → 3-minute payroll'.
    │   Color: indigo #4F46E5. Clean modern corporate. High contrast. No clip art."
    │
    ▼
Visual Generation (OpenDesign / Flux / Ideogram / SDXL)
```

**Why this matters:** The current flow produces visuals that ignore the research insights. A post about "payroll errors costing 8% revenue" should have a stat-card layout with a large number. A post about "team HR management" should have a team-oriented layout. None of that flows through today.

**Implementation — new endpoint to add:**

```python
# main.py — new tool: generate_visual_brief
async def tool_generate_visual_brief(
    brief: ResearchBrief,
    content: PlatformContent,
    platform: str,
    brand_context: dict = {},
) -> dict:
    prompt = f"""You are a visual art director.
Platform: {platform}
Post copy: {content.copy[:300]}
Key research angle: {brief.trending_angles[0] if brief.trending_angles else ''}
Brand: {brand_context.get('name', 'OfferBerries')}
Brand colors: {brand_context.get('colors', '#4F46E5 indigo')}

Return JSON:
{{
  "headline": "short punchy headline for visual",
  "subtext": "supporting line",
  "visual_mood": "adjectives",
  "color_directive": "primary color instruction",
  "layout_hint": "stat-card|quote-card|announcement|illustration"
}}"""
    # Call OpenRouter with json_object response format
    ...
```

---

## Part 5 — Content Regeneration

### Current architecture gap

There is no endpoint to regenerate a single field. Once `queue_node` writes to MongoDB, the only options are approve or delete. `main.py` has `DELETE /queue/{post_id}` and `POST /queue/{post_id}/approve` — nothing else.

The MongoDB document schema (`main.py:586`) stores only:
```python
{
    "tenant_id", "platform", "caption", "caption_hash",
    "postiz_id", "preview_url", "scheduled_at", "status", "created_at"
}
```

No `brief`, no `visual_path`, no component breakdown (hook/body/hashtags/cta separate).

### Proposed schema change

```python
# New MongoDB document structure for posts collection
{
    "_id": ObjectId,
    "tenant_id": str,
    "platform": str,
    "run_id": str,              # NEW — links back to the agent run
    "brief": dict,             # NEW — full ResearchBrief snapshot
    "components": {            # NEW — separate regenerable parts
        "hook": str,
        "body": str,
        "hashtags": list[str],
        "cta": str,
    },
    "caption": str,            # assembled from components
    "caption_hash": str,
    "visual": {                # NEW — visual metadata
        "template_id": str,
        "source": str,         # template|open_design|fal
        "url": str,
        "path": str,
    },
    "postiz_id": str,
    "preview_url": str,
    "scheduled_at": str,
    "status": str,
    "created_at": datetime,
    "updated_at": datetime,    # NEW
}
```

### New API endpoints needed

```python
# PATCH /queue/{post_id}/caption  — regenerate caption only
# PATCH /queue/{post_id}/hashtags — regenerate hashtags only
# PATCH /queue/{post_id}/cta      — regenerate CTA only
# PATCH /queue/{post_id}/visual   — regenerate visual only

@app.patch("/queue/{post_id}/caption")
async def regenerate_caption(post_id: str, ...):
    post = await db["posts"].find_one({"postiz_id": post_id, "tenant_id": tenant.tenant_id})
    brief = ResearchBrief(**post["brief"])
    platform = post["platform"]
    new_content = await tool_generate_content(brief, platform, ...)
    await db["posts"].update_one(
        {"postiz_id": post_id},
        {"$set": {"caption": new_content["copy"], "updated_at": now}},
    )
    return {"caption": new_content["copy"]}

@app.patch("/queue/{post_id}/visual")
async def regenerate_visual(post_id: str, template_id: str = None, source: str = "template", ...):
    post = await db["posts"].find_one({"postiz_id": post_id, "tenant_id": tenant.tenant_id})
    content = PlatformContent(**{...post["components"], "platform": post["platform"]})
    asset = await tool_generate_visual(content, template_id or post["visual"]["template_id"], source)
    await db["posts"].update_one(
        {"postiz_id": post_id},
        {"$set": {"preview_url": asset["url"], "visual": asset, "updated_at": now}},
    )
    return asset
```

### UI changes needed

In `queue/page.tsx`, each pending post card should have action buttons:

```
[Approve]  [↻ Caption]  [↻ Hashtags]  [↻ Visual]  [🗑 Delete]
```

Each `↻` button calls `PATCH /api/proxy/queue/{id}/caption` etc., shows a spinner, then replaces the field inline without reloading the full list.

---

## Part 6 — Cost Analysis

### Current state

`log_tool_call` in `main.py:112` always stores `cost_estimate: 0.0`. There is no cost calculation anywhere. The `/usage` endpoint reads Redis rate-limit counters (call counts) but never converts to dollar amounts.

### Real cost per operation (2026 pricing)

**Research costs (Perplexity):**

| Model | ~Input tokens | ~Output tokens | Cost per call |
|---|---|---|---|
| `sonar` | 400 | 800 | ~$0.0014 |
| `sonar-pro` | 400 | 800 | ~$0.004 |
| `sonar-deep-research` | 2000 | 5000 | ~$0.056 |

**Content costs (OpenRouter — per platform post):**

| Model | Input (~600 tok) | Output (~300 tok) | Cost per post |
|---|---|---|---|
| Gemini 2.5 Flash | $0.075/1M | $0.30/1M | ~$0.00013 |
| GPT-4o Mini | $0.15/1M | $0.60/1M | ~$0.00027 |
| Claude Haiku 4.5 | $0.80/1M | $4.00/1M | ~$0.00168 |
| Claude Sonnet 4.6 | $3.00/1M | $15.00/1M | ~$0.0063 |
| GPT-4o | $5.00/1M | $15.00/1M | ~$0.0075 |

**Visual costs:**

| Source | Cost per image |
|---|---|
| Template renderer (Playwright) | ~$0.002 (compute only) |
| OpenDesign | TBD (self-hosted, infra cost) |
| Flux via fal.ai | ~$0.025–0.05 |
| Ideogram (if added) | ~$0.02 |
| SDXL via fal.ai | ~$0.01 |

**Apify scraping:**

| Actor | Per run (20 posts) | Compute units |
|---|---|---|
| LinkedIn scraper | ~5 CU | ~$0.025 |
| Twitter scraper | ~3 CU | ~$0.015 |
| Instagram scraper | ~4 CU | ~$0.02 |

### Cost per full campaign (3 platforms, Gemini Flash)

```
Research (sonar):                $0.0014
Content x3 platforms:            $0.0004
LinkedIn carousel x4 slides:     $0.0005
Visuals x3:                      $0.006 (template renderer)
Competitor scrape x2 handles:    $0.08
────────────────────────────────────────
Total per run (cheapest):        ~$0.088

Total per run (premium):
  sonar-deep-research:           $0.056
  Claude Sonnet x7 calls:        $0.044
  Flux visuals x3:               $0.12
  Competitor scrape:             $0.08
────────────────────────────────────────
Total per run (premium):         ~$0.30
```

**Monthly at 1 campaign/day:**

| Config | Per run | Monthly |
|---|---|---|
| Cheapest (no scrape) | $0.004 | $0.12 |
| Cheapest (with scrape) | $0.088 | $2.64 |
| Premium (with scrape) | $0.30 | $9.00 |

---

## Part 7 — Real-Time Cost Engine

### Design

**Step 1 — Token tracking middleware.** Modify `tool_generate_content` to capture actual token counts from OpenRouter's response:

```python
# main.py — in tool_generate_content, after API call
response_body = resp.json()
usage = response_body.get("usage", {})
prompt_tokens = usage.get("prompt_tokens", 0)
completion_tokens = usage.get("completion_tokens", 0)

# Price lookup from OPENROUTER_MODELS list
model_info = next((m for m in OPENROUTER_MODELS if m["id"] == actual_model), {})
pricing = model_info.get("pricing", {})
input_cost  = prompt_tokens * float(pricing.get("prompt", 0)) / 1_000_000
output_cost = completion_tokens * float(pricing.get("completion", 0)) / 1_000_000
total_cost  = input_cost + output_cost
```

**Step 2 — Enhanced `log_tool_call`:**

```python
async def log_tool_call(
    tenant_id: str,
    tool_name: str,
    status: str,
    run_id: str = "",
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    provider: str = "",         # openrouter|perplexity|apify|fal
):
    await db["tool_calls"].insert_one({
        "tenant_id": tenant_id,
        "run_id": run_id,
        "tool_name": tool_name,
        "status": status,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
        "recorded_at": datetime.now(timezone.utc),
    })
```

**Step 3 — New API endpoint `GET /runs/{run_id}/cost`:**

```python
@app.get("/runs/{run_id}/cost")
async def get_run_cost(run_id: str, ...):
    pipeline = [
        {"$match": {"run_id": run_id, "tenant_id": tenant.tenant_id}},
        {"$group": {
            "_id": "$provider",
            "total_cost": {"$sum": "$cost_usd"},
            "total_tokens": {"$sum": {"$add": ["$prompt_tokens", "$completion_tokens"]}},
            "calls": {"$sum": 1},
        }}
    ]
    breakdown = await db["tool_calls"].aggregate(pipeline).to_list(20)
    total = sum(b["total_cost"] for b in breakdown)
    return {"run_id": run_id, "total_usd": total, "breakdown": breakdown}
```

**Step 4 — Pre-run cost estimate:**

```python
@app.post("/runs/estimate")
async def estimate_run_cost(req: RunRequest, ...):
    research_cost = PERPLEXITY_COSTS.get(req.research_model, 0.002)
    content_cost_per_platform = get_model_cost_per_call(req.content_model, 600, 300)
    visual_cost = {"template": 0.002, "open_design": 0.003, "fal": 0.035}.get(req.visual_source, 0.002)
    platforms = len(req.platform_filter)
    scrape_cost = 0.025 * len(req.competitor_handles) * platforms if req.competitor_handles else 0

    total = research_cost + (content_cost_per_platform * platforms) + (visual_cost * platforms) + scrape_cost
    return {
        "estimated_usd": round(total, 4),
        "breakdown": {
            "research": research_cost,
            "content": content_cost_per_platform * platforms,
            "visuals": visual_cost * platforms,
            "scraping": scrape_cost,
        }
    }
```

**Step 5 — UI changes (queue/page.tsx):**

Before run: Show estimated cost badge below "Run Agent" button.
After run: Show actual cost card in the right panel alongside the stepper.

```
┌─────────────────────────────┐
│ Run Cost                    │
│ Research:      $0.001       │
│ Content (3x):  $0.0004      │
│ Visuals (3x):  $0.006       │
│ ─────────────────────────── │
│ Total:         $0.0074      │
└─────────────────────────────┘
```

**Database table — MongoDB `tool_calls` (enhanced):**

| Field | Type | Description |
|---|---|---|
| `tenant_id` | str | Tenant |
| `run_id` | str | Agent run that spawned this call |
| `tool_name` | str | research_trends / generate_content / etc. |
| `provider` | str | openrouter / perplexity / apify / fal |
| `model` | str | Exact model ID |
| `prompt_tokens` | int | Input tokens |
| `completion_tokens` | int | Output tokens |
| `cost_usd` | float | Calculated cost |
| `status` | str | success / error |
| `recorded_at` | datetime | Timestamp |

---

## Part 8 — Credit System

### Design: Hetzner-style prepaid wallet

**Concept:** 1 credit = 0.001 PKR (or adjust to your margin). Users top up; each operation deducts credits. You buy API credits at cost; users pay at markup.

**Example rates (2x markup):**

| Operation | API cost | Credits deducted | Credit cost to user |
|---|---|---|---|
| Research (Sonar) | $0.001 | 5 credits | 5 PKR |
| Content (Gemini Flash) | $0.0001 | 1 credit | 1 PKR |
| Content (Claude Sonnet) | $0.006 | 30 credits | 30 PKR |
| Visual (Template) | $0.002 | 10 credits | 10 PKR |
| Visual (Flux) | $0.035 | 175 credits | 175 PKR |
| Full campaign (cheapest) | $0.004 | 20 credits | 20 PKR |
| Full campaign (premium) | $0.30 | 1,500 credits | 1,500 PKR |

**New MongoDB collections:**

```python
# wallets collection
{
    "_id": ObjectId,
    "tenant_id": str,           # indexed unique
    "balance_credits": int,     # integer to avoid float precision bugs
    "currency": "PKR",
    "updated_at": datetime,
}

# credit_ledger collection (append-only, never update)
{
    "_id": ObjectId,
    "tenant_id": str,
    "type": str,                # "topup" | "debit" | "refund" | "adjustment"
    "credits": int,             # positive = added, negative = deducted
    "balance_after": int,       # snapshot for audit trail
    "run_id": str,              # for debits — links to agent run
    "tool_name": str,           # for debits
    "cost_usd": float,          # underlying cost
    "description": str,         # human-readable
    "recorded_at": datetime,
    "safepay_ref": str,         # for topups — payment reference
}
```

**Debit flow (atomic):**

```python
async def debit_credits(tenant_id: str, credits: int, run_id: str, tool_name: str, cost_usd: float):
    async with await mongo_client.start_session() as session:
        async with session.start_transaction():
            wallet = await db["wallets"].find_one_and_update(
                {"tenant_id": tenant_id, "balance_credits": {"$gte": credits}},
                {"$inc": {"balance_credits": -credits}, "$set": {"updated_at": now}},
                return_document=True,
                session=session,
            )
            if not wallet:
                raise HTTPException(402, "Insufficient credits")
            await db["credit_ledger"].insert_one({
                "tenant_id": tenant_id,
                "type": "debit",
                "credits": -credits,
                "balance_after": wallet["balance_credits"],
                "run_id": run_id,
                "tool_name": tool_name,
                "cost_usd": cost_usd,
                "recorded_at": now,
            }, session=session)
```

**Failed run refund:**

```python
async def refund_run(run_id: str, tenant_id: str):
    debits = await db["credit_ledger"].find(
        {"run_id": run_id, "type": "debit"}
    ).to_list(100)
    total = sum(abs(d["credits"]) for d in debits)
    if total > 0:
        await credit_wallet(tenant_id, total, description=f"Refund for failed run {run_id}")
```

**Top-up flow (Safepay webhook):**

```python
# main.py /webhooks/safepay
if data.get("event") == "payment.success":
    pkr_amount = data["data"]["amount"]
    credits = pkr_amount  # 1 PKR = 1 credit at base rate
    tenant_id = data["data"]["metadata"]["tenant_id"]
    await credit_wallet(tenant_id, credits, safepay_ref=data["data"]["tracker"])
```

---

## Part 9 — Free vs Paid: What is Actually Free

| Provider | Free tier | Trial credit | Expires | Becomes paid |
|---|---|---|---|---|
| **Perplexity** | No free API tier | None for API | — | Paid from first call. ~$5/month minimum for `sonar` |
| **OpenRouter** | Free models exist (`llama:free`, `mistral:free`) | $1 signup credit | 30 days typically | Free models are rate-limited (slow, queued). Quality much lower than paid |
| **OpenAI** | No free API tier | $5 trial credit (new accounts) | 3 months | After credit expires, all calls fail |
| **Anthropic** | No free API tier | $5 trial credit (new accounts) | — | After credit, paid only |
| **Gemini (Google AI)** | 15 RPM free tier on Gemini 1.5 Flash/Pro | None | Never expires (rate-limited) | Gemini 2.5 is paid-only via AI Studio at scale |
| **OpenDesign** | Self-hosted = free infra | N/A | N/A | Your server cost only |
| **Flux (fal.ai)** | $1 trial credit | $1 signup | — | ~$0.025/image after |
| **Ideogram** | 10 free images/day | None for API | Resets daily | API access is paid |
| **Apify** | $5/month free platform credit | — | Monthly | Actor runs beyond free tier |
| **Safepay** | No charge for integration | — | — | 2.5% transaction fee |

### What your platform currently uses as "free"

- Perplexity: **Falls back to mock data if key absent** — effectively "free" but fake research
- OpenRouter: Free Llama/Mistral models are available but you hardcode Gemini Flash as default (paid)
- OpenDesign: Self-hosted — only infra cost
- Renderer (Playwright): Self-hosted — only infra cost

### Recommendation for cost-zero demo tier

```
Demo tier uses:
  Research: sonar → mock fallback (no cost)
  Content: meta-llama/llama-3.1-8b-instruct:free (via OpenRouter)
  Visual: Template renderer (self-hosted, no per-call cost)
  Scraping: Disabled (TIER_LIMITS demo.scrape_competitor = 0) ✓ already done
```

---

## Part 10 — Multi-Tenant Architecture

### Current state

The current system has a flat tenant model: `api_key → tenant_id + tier`. There are no workspaces, projects, or campaigns. All posts for a tenant share one MongoDB collection filtered by `tenant_id`.

### Proposed hierarchy

```
Platform Owner (you)
    │
    ├─► Tenant (SMB company account)
    │       ├── tier: starter|pro|owner
    │       ├── wallet: credit balance
    │       └── Workspaces (e.g., brands they manage)
    │               ├── name: "TechCorp Social"
    │               └── Projects (long-running initiatives)
    │                       ├── name: "Q3 2026 Campaign"
    │                       └── Campaigns (single topic runs)
    │                               ├── run_id
    │                               ├── topic
    │                               ├── posts[]
    │                               └── analytics{}
    │
    └─► Tenant (agency)
            └── Workspaces (one per client)
```

### Schema

```python
# tenants collection (enhanced from api_keys)
{
    "tenant_id": str,           # UUID
    "label": str,               # "Acme Corp"
    "tier": str,
    "owner_email": str,
    "created_at": datetime,
    "suspended_at": datetime | None,
    "settings": {
        "timezone": "Asia/Karachi",
        "default_platforms": ["linkedin", "twitter"],
        "brand_name": str,
    }
}

# workspaces collection
{
    "workspace_id": str,
    "tenant_id": str,           # indexed
    "name": str,
    "brand_color": str,
    "logo_url": str,
    "created_at": datetime,
}

# projects collection
{
    "project_id": str,
    "workspace_id": str,
    "tenant_id": str,
    "name": str,
    "goal": str,
    "start_date": datetime,
    "end_date": datetime,
    "status": str,              # active|paused|completed
}

# campaigns collection (replaces runs)
{
    "campaign_id": str,         # = run_id today
    "project_id": str,
    "workspace_id": str,
    "tenant_id": str,
    "topic": str,
    "platforms": list[str],
    "status": str,
    "brief": dict,
    "total_cost_usd": float,
    "created_at": datetime,
    "completed_at": datetime,
}
```

### Isolation requirements

| Layer | Current | Needed |
|---|---|---|
| Data isolation | `tenant_id` filter on all queries | Add workspace/project scope |
| Billing isolation | Single wallet per tenant | Wallet per tenant (already in Part 8 design) |
| Analytics isolation | `tenant_id` filter | Campaign-level aggregation |
| Credit isolation | Shared pool per tenant | Workspace budget caps |
| Auth isolation | Single API key per tenant | Multiple workspace-scoped keys |

---

## Part 11 — MCP Transformation

### Current MCP status

You already have an `/mcp` endpoint at `main.py:211`. It accepts JSON-RPC style:
```json
{ "method": "tools/call", "params": { "name": "research_trends", "arguments": {} } }
```

And lists tools at `tools/list`. **This is not a compliant MCP server.** The Model Context Protocol requires:
- Server-Sent Events (SSE) transport for streaming
- Proper `initialize` / `initialized` handshake
- `resources/list`, `prompts/list` in addition to `tools/list`
- JSON-RPC 2.0 (you have a custom subset)
- No auth header support in Claude Desktop (uses config file credentials)

### What exists vs what's missing

| Component | Status | Notes |
|---|---|---|
| Tool definitions | ✓ Exists | 7 tools defined |
| Tool execution | ✓ Exists | `_dispatch_tool()` works |
| SSE transport | ✗ Missing | Required for Claude Desktop |
| `initialize` handshake | ✗ Missing | MCP protocol step 1 |
| `resources` capability | ✗ Missing | Brand voice, strategy docs could be resources |
| `prompts` capability | ✗ Missing | Could expose campaign templates |
| Proper JSON-RPC 2.0 | ✗ Partial | No `id` field, no `jsonrpc` field |

### Difficulty assessment

**Low effort** (1-2 days): Convert the existing `/mcp` to proper JSON-RPC 2.0 format and add the `initialize` handshake. The business logic already works.

**Medium effort** (3-5 days): Add SSE transport so Claude Desktop can connect. FastAPI supports SSE natively via `EventSourceResponse`.

**High effort** (1-2 weeks): Full MCP compliance including resources, prompts, sampling, and the OAuth-based auth flow Claude.ai uses for remote servers.

---

## Part 12 — Claude Desktop / Claude Code MCP Integration

### Implementation plan

**Step 1 — Add MCP-compliant transport to `main.py`:**

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/mcp/sse")
async def mcp_sse(request: Request, api_key: str = Query(None)):
    """SSE endpoint for MCP clients (Claude Desktop)."""
    tenant = await get_tenant(api_key)

    async def event_stream():
        # MCP initialize response
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'offerberries-marketing', 'version': '1.0.0'}}})}\n\n"
        # Keep alive
        while True:
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/mcp/messages")
async def mcp_messages(request: Request, ...):
    """JSON-RPC 2.0 message handler."""
    body = await request.json()
    # proper jsonrpc 2.0 dispatch
    ...
```

**Step 2 — Claude Desktop config (`~/.claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "offerberries": {
      "command": "curl",
      "args": [
        "-N", "-H", "Accept: text/event-stream",
        "https://agent.offerberriesvo.com/mcp/sse?api_key=YOUR_KEY"
      ]
    }
  }
}
```

**Step 3 — What the user experience becomes:**

```
User in Claude Desktop:
"Research AI SaaS trends in Pakistan and create a week's LinkedIn content"

Claude calls:
  offerberries:research_trends({topic: "AI SaaS Pakistan", research_model: "sonar-pro"})
  → Returns: ResearchBrief with 5 angles

  offerberries:generate_content({brief: ..., platform: "linkedin", model: "claude-sonnet-4-6"})
  → Returns: 5 LinkedIn posts (one per angle)

  offerberries:generate_visual({content: posts[0], template_id: "linkedin-single"})
  → Returns: visual URL

  offerberries:queue_post({platform: "linkedin", caption: ..., scheduled_at: "Mon 9:00"})
  → Returns: queued confirmation

Claude to user:
"I've created 5 LinkedIn posts for next week covering AI SaaS in Pakistan.
Post 1 is scheduled for Monday 9am PKT. Here's the first visual: [url]"
```

---

## Part 13 — OpenAI MCP Integration

OpenAI has announced MCP support for ChatGPT and the Agents SDK. The same `/mcp/messages` and `/mcp/sse` endpoints from Part 12 work for OpenAI with one difference: OpenAI uses OAuth for remote MCP servers (not API key query params).

**For OpenAI Agents SDK (Python):**

```python
from openai import OpenAI
client = OpenAI()

# OpenAI Agents SDK v1+ MCP support
tools = [{"type": "mcp", "server_url": "https://agent.offerberriesvo.com/mcp", "api_key": KEY}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Create this week's content plan"}],
    tools=tools,
)
```

**Priority difference from Claude:** OpenAI's MCP implementation currently requires the server to respond within 30 seconds for tool calls. Your `sonar-deep-research` calls can take 60-90 seconds. For OpenAI compatibility, add a webhook/polling pattern or reduce timeouts.

---

## Part 14 — Model Abstraction Layer

### Current state

Model selection is hardcoded in three places:
- Research: `main.py:297` — always `"sonar"`
- Content: `main.py:405` — default `"google/gemini-2.5-flash"`, configurable via MongoDB
- Visual: `graph.py:151` — Instagram → `"open_design"`, else `"template"`

### Proposed TypeScript abstraction layer (for Next.js API routes)

```typescript
// dashboard/lib/providers.ts

export type ResearchProvider = {
  id: string;
  name: string;
  models: { id: string; label: string; pricePerCall: number }[];
  call(topic: string, model: string): Promise<ResearchBrief>;
};

export type ContentProvider = {
  id: string;
  name: string;
  models: { id: string; label: string; pricing: { input: number; output: number } }[];
  call(brief: ResearchBrief, platform: string, model: string): Promise<PlatformContent>;
};

export type ImageProvider = {
  id: string;
  name: string;
  call(content: PlatformContent, config: VisualConfig): Promise<VisualAsset>;
};

// Concrete implementations
export const RESEARCH_PROVIDERS: ResearchProvider[] = [
  {
    id: "perplexity",
    name: "Perplexity",
    models: [
      { id: "sonar",               label: "Sonar",        pricePerCall: 0.0014 },
      { id: "sonar-pro",           label: "Sonar Pro",    pricePerCall: 0.004  },
      { id: "sonar-deep-research", label: "Deep Research",pricePerCall: 0.056  },
    ],
    call: async (topic, model) => { /* proxy to /api/proxy/research */ }
  }
];

export const CONTENT_PROVIDERS: ContentProvider[] = [
  { id: "openrouter", name: "OpenRouter", models: OPENROUTER_MODELS, call: ... },
];

export const IMAGE_PROVIDERS: ImageProvider[] = [
  { id: "template",     name: "Template Renderer", call: ... },
  { id: "open_design",  name: "OpenDesign",         call: ... },
  { id: "flux",         name: "Flux (fal.ai)",      call: ... },
  { id: "ideogram",     name: "Ideogram",           call: ... },
];
```

### Python abstraction layer (for `main.py`)

```python
# agent/mcp_server/providers/base.py
from abc import ABC, abstractmethod

class ResearchProvider(ABC):
    @abstractmethod
    async def research(self, topic: str, **kwargs) -> dict: ...

class ContentProvider(ABC):
    @abstractmethod
    async def generate(self, brief: dict, platform: str, **kwargs) -> dict: ...

class ImageProvider(ABC):
    @abstractmethod
    async def render(self, content: dict, config: dict) -> dict: ...

# agent/mcp_server/providers/perplexity.py
class PerplexityProvider(ResearchProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def research(self, topic: str, model: str = "sonar", **kwargs) -> dict:
        # move current tool_research_trends logic here
        ...

# agent/mcp_server/providers/openrouter.py
class OpenRouterProvider(ContentProvider):
    async def generate(self, brief: dict, platform: str, model: str = "google/gemini-2.5-flash", **kwargs) -> dict:
        # move current tool_generate_content logic here
        ...
```

---

## Part 15 — Recommended Future Architecture

### What you have built (inventory)

| Layer | Status | Quality |
|---|---|---|
| LangGraph orchestration | ✓ Done | Solid 4-node pipeline |
| MCP tool server | ✓ Done | REST wrapper, not true MCP |
| Auth + rate limiting | ✓ Done | SHA256 hash, Redis TTL cache |
| Multi-tier access control | ✓ Done | owner/pro/starter/demo |
| Template renderer (Playwright) | ✓ Done | Works in Docker |
| OpenDesign integration | ✓ Done | Instagram path |
| Fal.ai (Flux) integration | ✓ Done | Code exists, not tested |
| Postiz scheduling | ✓ Done | Resilient fallback if offline |
| Analytics (MongoDB) | ✓ Done | Post counts, no social platform data |
| Design system (Next.js) | ✓ Done | Full token system, 20 pages |
| Billing (Safepay) | ✓ Done | Checkout flow ready |
| Monitoring (Grafana) | ✓ Done | Stack deployed |
| Cost tracking | ✗ Missing | `cost_estimate` always 0.0 |
| Per-component regeneration | ✗ Missing | No API, no UI |
| Visual briefs (LLM → visual) | ✗ Missing | Copy is passed raw |
| Hashtag/CTA generation | ✗ Missing | Hardcoded strings |
| Credit/wallet system | ✗ Missing | Subscriptions only |
| True MCP protocol | ✗ Missing | SSE + JSON-RPC 2.0 |
| Research model picker | ✗ Missing | Always `sonar` |
| Perplexity citations | ✗ Missing | Discarded in response |
| Workspace/project hierarchy | ✗ Missing | Flat tenant model |

### Priority matrix

**Must build next (blocks revenue or correctness):**

1. **Fix hardcoded hashtags and CTAs.** `main.py:436–438`. These should be LLM-generated per platform and topic. 2-hour fix. High user-visible impact.

2. **Research model picker.** Add `research_model` parameter to `tool_research_trends`. Add UI chip group in queue page. Users on free tiers use `sonar`; premium users unlock `sonar-deep-research`. 1-day work.

3. **Real cost tracking.** Replace `cost_estimate: 0.0` with actual token math. Required before you can bill per-usage or show users what they're spending. 2-day work.

4. **Per-post regeneration.** Add `PATCH /queue/{id}/caption|hashtags|visual` endpoints and corresponding UI buttons. Users need this to edit AI output without re-running the full agent. 2-day work.

5. **Save brief in post document.** Store `brief` and `visual` metadata in MongoDB at queue time. Prerequisite for regeneration. 1-hour fix.

**Should build soon (enables product differentiation):**

6. **Visual brief generation step.** Add LLM → visual brief → OpenDesign/Flux pipeline. This is the biggest quality improvement available — visuals currently ignore research context.

7. **Perplexity citations display.** Surface `citations[]` in the Queue chat panel so users can see sources. Trust differentiator.

8. **Credit/wallet system.** Prerequisite for pay-as-you-go pricing. Needed before scaling beyond yourself.

9. **True MCP server (SSE + JSON-RPC 2.0).** Unlocks Claude Desktop and OpenAI Agents integrations. Major distribution channel.

10. **Workspace/project hierarchy.** Needed before onboarding agency clients.

**Can build later:**

11. Model abstraction layer (clean code, not user-visible)
12. Multi-agent parallelism (run all platforms simultaneously instead of sequentially)
13. Strategy feedback loop (analytics → automatic brief improvement)
14. Ideogram/SDXL visual providers
15. Competitor watchlist management UI
16. Campaign calendar view

### Architecture for three use cases

**Personal use (current):**
```
Single owner key → LangGraph → MCP tools → MongoDB + Redis
```
Production-ready today. Only gap is cost visibility.

**SaaS use (next 90 days):**
```
Safepay checkout → wallet top-up → credit debit per tool call
Multi-tenant dashboard → workspace per user → campaign history
Per-run cost receipt emailed via Resend
```
Requires: credit system (Part 8) + cost tracking (Part 7) + workspace model (Part 10).

**MCP/API use (next 6 months):**
```
Claude Desktop config → SSE handshake → JSON-RPC tool calls
OpenAI Agents SDK → POST /mcp/messages → tool dispatch
Zapier/n8n trigger → webhook → agent run → completion callback
```
Requires: proper MCP transport (Part 12) + async completion webhooks + per-call API key billing.

---

### The single highest-leverage next action

**Fix the three hardcoded strings.** `main.py:436–438`:

```python
# Current (wrong):
hashtags=["#OfferBerries", "#PakistanSMB"],
cta="Book a free demo",

# Fix: extract from LLM output or generate separately
```

This costs 2 hours, improves every single post the system generates, and removes the most embarrassing gap between the "AI-generated content" promise and the actual output. Every user who sees `#OfferBerries #PakistanSMB` on every post regardless of topic will immediately distrust the platform.

After that: cost tracking → research model picker → regeneration buttons. In that order.
