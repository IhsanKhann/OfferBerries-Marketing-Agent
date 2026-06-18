# OfferBerries Marketing Agent — Software Requirements Specification
Version: 1.0  
Last Updated: 2026-06-18  
Status: ACTIVE

---

## 1. SYSTEM OVERVIEW

### 1.1 Purpose
The OfferBerries Marketing Agent is an AI-powered social media content pipeline for Pakistani B2B SMBs. It researches trending content, generates on-brand posts for LinkedIn/Twitter/Instagram/YouTube/Email, generates visuals, and schedules posts through Postiz — all driven by a 4-stage LangGraph pipeline exposed as an MCP server.

### 1.2 Users
- **Primary:** OfferBerries team using it internally for social media
- **Secondary (future):** Client tenants managing their own branded content

### 1.3 Architecture
```
Browser / Claude Code CLI / Cursor IDE
        │
        │ MCP SSE (port 8000) / REST
        ▼
┌─────────────────────────────────────────┐
│  mcp-server (FastAPI + FastMCP)         │
│  port 8000                              │
│  Tools: research, content, visual,      │
│          queue, analytics               │
│  REST: /queue, /config, /admin,         │
│         /projects, /runs                │
└───────────────┬─────────────────────────┘
                │ HTTP /mcp
                ▼
┌─────────────────────────────────────────┐
│  crew-runner (FastAPI)                  │
│  port 8001                              │
│  Routes: POST /runs, GET /runs/{id},    │
│           stage approve/edit/reject     │
└───────────────┬─────────────────────────┘
                │ arq jobs (Redis)
                ▼
┌─────────────────────────────────────────┐
│  crew-worker (arq)                      │
│  execute_pipeline_job                   │
│  rerun_stage_job                        │
│                                         │
│  Pipeline: research → content_gen →    │
│             visual_gen → scheduling    │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
   MongoDB           Redis
  (agent_runs,    (job queue,
   posts,          control
   projects,       signals,
   configs,        pub/sub)
   api_keys,
   tool_calls)
```

### 1.4 Technology Stack
| Component | Technology | Version |
|-----------|------------|---------|
| Python | 3.12+ | 3.14 (dev) |
| MCP framework | FastMCP | ≥0.9.0 |
| REST API | FastAPI | ≥0.111.0 |
| Pipeline | LangGraph | ≥0.1.0 |
| Job queue | arq | ≥0.25.0 |
| Database | MongoDB (Motor async) | ≥3.4.0 |
| Cache/queue | Redis (aioredis) | 7.x |
| Research LLM | Perplexity sonar/sonar-pro | — |
| Content LLM | OpenRouter (Claude Sonnet 4.6 default) | — |
| Visual LLM | fal.ai Flux (image), Gemini Flash (brief) | — |
| Post scheduler | Postiz | self-hosted |
| Frontend | Next.js 14 (App Router) | 14.2.4 |
| Frontend UI | React 18, TypeScript 5, Tailwind CSS | — |
| Reverse proxy | Caddy + Cloudflare tunnel | — |

---

## 2. CURRENT STATE (as of Phase 0 — 2026-06-18)

### 2.1 What Works (verified)
- All services defined in docker-compose.yml (mcp-server, crew-runner, crew-worker, redis, mongodb, postiz, renderer, caddy)
- MCP server exposes 8 tools via FastMCP SSE on port 8000
- Pipeline executes 4 stages: research → content_generation → visual_generation → scheduling
- arq worker with orphan-recovery on startup (re-enqueues stuck runs)
- Projects backend CRUD (`/projects` router) exists
- Auth with API key tiers (owner/pro/starter/demo)
- Brand voice loaded from `agent/config/brand_voice.md`
- Competitor watchlist in `agent/config/content_strategy.json` (daraz.pk, rozee.pk, easypaisa)

### 2.2 What Is Broken (found in Phase 0 audit)
| ID | Description | Severity |
|----|-------------|----------|
| B-01 | Competitor scraping via Apify: env var name mismatch (`APIFY_API_TOKEN` vs `APIFY_API_KEY`) | High |
| B-02 | Twitter copy may be truncated mid-word (no retry logic, just slice) | High |
| B-03 | Hashtags not always stored as separate array field on posts | Medium |
| B-04 | arq worker durability under restart not verified in production | Medium |
| B-05 | fal.ai visual URL blank for some runs | Medium |
| B-06 | Frontend has zero automated tests | High |
| B-07 | No project context/vector store (context_service not implemented) | High |
| B-08 | Sidebar supports no project grouping (frontend) | Medium |
| B-09 | Postiz integration untested end-to-end | Medium |
| B-10 | 9 mcp_server test files had stale imports from old module layout (fixed Phase 0) | Fixed |
| B-11 | 9 crew test failures from stale API signatures (fixed Phase 0) | Fixed |

### 2.3 Test Coverage Baseline (Phase 0)
| Suite | Tests | Passing | Coverage |
|-------|-------|---------|----------|
| Backend (crew + mcp_server) | 246 | 246 | **80%** |
| Frontend (dashboard) | 0 | 0 | 0% |

---

## 3. FEATURES BY PHASE

### PHASE 1 — Reliability & MCP Connectivity

| Feature | Acceptance Criteria |
|---------|---------------------|
| Frontend test infrastructure | vitest + @testing-library + msw installed; `npx vitest run --coverage` works |
| PostPreviewPanel tests | Hashtags render from `post.hashtags` array (not regex); edit tab works |
| useAgentRun tests | Run polling grouped by status; onComplete fires |
| usePostPreview tests | ESC closes panel; openPost/closePost state correct |
| QueuePage integration test | Posts fetch and render; approve/reject calls correct API |
| MCP Inspector connectivity | All 8 tools visible at `http://localhost:8000/sse` |
| Claude Code CLI connectivity | `claude mcp list` shows offerberries server |
| Twitter copy not truncated | Copy ≤280 chars via model retry, not string slice |
| Hashtags always array | Every post document has `hashtags: []` not embedded in copy |
| Frontend coverage ≥ 70% | `npx vitest run --coverage` reports ≥70% |

### PHASE 2 — Projects & Multi-Run Context

| Feature | Acceptance Criteria |
|---------|---------------------|
| context_service.py | embed_text, store_chunk, retrieve_relevant_context, store_run_context all tested |
| project_context_chunks collection | Atlas Vector Search index created; evergreen chunks survive |
| Brand voice seeded on project creation | `find({projectId, evergreen: true})` returns chunks after creation |
| Pipeline Step 0 | Context retrieved and injected into research brief when projectId present |
| Post-run context storage | After run completes, research + post chunks stored per project |
| AgentRun.projectId | Optional field; ungrouped runs have null projectId |
| Sidebar projects section | Projects expand to show nested runs; run count badge correct |
| Sidebar width 260px | CSS token `--sidebar-width: 260px`; test asserts width |
| CreateProjectModal | Creates project; optimistic update in sidebar |
| Project Overview page | Runs tab + Settings tab (5 sections) |
| Backend coverage ≥ 75% | pytest --cov reports ≥75% |
| Frontend coverage ≥ 75% | vitest --coverage reports ≥75% |

### PHASE 3 — Intelligence & Competitor Awareness

| Feature | Acceptance Criteria |
|---------|---------------------|
| Competitor scraping non-fatal | Pipeline continues when Apify fails; run status ≠ failed |
| Pakistani watchlist | content_strategy.json contains rozee.pk, daraz.pk, easypaisa, bykea handles |
| Perplexity competitor fallback | When Apify fails, Perplexity queried for competitor insights |
| Competitor section omitted when empty | Content prompt has no COMPETITOR section when insights=[] |
| Performance rating endpoint | PATCH /posts/{id}/rate saves performanceRating + ratedAt |
| High-rated → evergreen chunk | Posts rated "high" appear as evergreen chunks in vector store |
| Low-rated → negative example | Posts rated "low" appear with "did NOT work" prefix in vector store |
| Rating buttons in PostPreviewPanel | 🔥/👍/👎 buttons visible after post.status === "published" |
| fal.ai is default visual generator | visual.py routes to fal.ai first; OpenDesign is fallback |
| Correct platform dimensions | Instagram 1080×1080, LinkedIn 1200×627, Twitter 1600×900 |
| Visual URL saved to post | post.visualUrl set after visual stage |

### PHASE 4 — Autonomy & Scheduled Runs

| Feature | Acceptance Criteria |
|---------|---------------------|
| Project schedule config | scheduleEnabled, scheduleFrequency, scheduleCron, scheduleTopicRotation, scheduleAutoApprove saved to project |
| Scheduler service | APScheduler creates run at correct time from rotation |
| Topic rotation | Topics cycle in order; rotation index advances per run |
| Auto-approve mode | When scheduleAutoApprove=true, posts pushed to Postiz without manual approval |
| Postiz integration | queue_post calls Postiz API, returns scheduledAt, updates post document |
| Optimal posting times | get_optimal_post_time returns correct hour/day per platform PKT |
| Scheduled time label in Queue | "Scheduled for Tuesday 9:00 AM PKT" visible on post card |
| Pipeline node graph | Exactly 4 nodes; labels correct; no Analytics/Self-Improve nodes |
| StepDetailPanel | Click node → panel slides in with stage output |
| Active node animation | Running node has class `pipeline-node--running` |
| Completed connector green | Connector between completed nodes has class `pipeline-connector--completed` |
| Backend coverage ≥ 80% | ✅ already passing |
| Frontend coverage ≥ 80% | vitest reports ≥80% |

### PHASE 5 — Analytics, Feedback & Calendar

| Feature | Acceptance Criteria |
|---------|---------------------|
| Run analytics | get_run_analytics returns cost_per_post (float) |
| Project analytics | get_project_analytics returns best_platform |
| Optimal times from data | get_optimal_times_from_data returns best_hours, best_days from rated posts |
| Analytics page wired | Frontend /analytics shows real data from API |
| Calendar month view | Scheduled posts appear on correct calendar date |
| Gap warning | "no content scheduled" shown for days with no posts |
| SRS compliance table | Every feature: Implemented ✅ Tested ✅ Passing ✅ Manual ✅ |

---

## 4. DATA MODELS

### 4.1 AgentRun (agent/crew/models.py)
```
_id: str (UUID)
tenant_id: str
topic: str
clean_topic: str (optional, extracted via LLM)
platforms: list[str]
execution_mode: "automated" | "controlled"
stages_enabled: {research, content_generation, visual_generation, scheduling: bool}
stages: {stage_name: {status, output, error, started_at, completed_at}}
current_stage: str
overall_status: "pending" | "running" | "paused_for_review" | "completed" | "failed" | "cancelled"
state_snapshot: {brief, competitor_data, platform_content, visual_assets}
provided_content: str (optional)
project_id: str (optional) — Phase 2
created_at: datetime
updated_at: datetime
```

### 4.2 Post (MongoDB: posts collection)
```
_id: ObjectId
run_id: str
tenant_id: str
platform: str
copy: str
caption: str (alias for copy)
hashtags: list[str]          ← always an array, never embedded in copy
cta: str
hook: str
visual_url: str
preview_url: str
postiz_id: str
scheduled_at: datetime
status: "pending_review" | "scheduled" | "approved" | "published"
# Phase 3 additions:
impressions: int
engagements: int
clicks: int
performance_rating: "high" | "medium" | "low"
rated_at: datetime
created_at: datetime
updated_at: datetime
```

### 4.3 Project (MongoDB: projects collection)
```
_id: str
tenant_id: str
name: str
description: str
brand_voice: str (markdown override)
default_platforms: list[str]
default_model: str
default_steps: list[str]
color: str
icon: str
starred: bool
is_active: bool
archived_at: datetime
# Phase 4 additions:
schedule_enabled: bool
schedule_frequency: "daily" | "weekly" | "custom"
schedule_cron: str
schedule_platforms: list[str]
schedule_topic_rotation: list[str]
schedule_auto_approve: bool
created_at: datetime
```

### 4.4 ProjectContextChunk (Phase 2 — MongoDB: project_context_chunks)
```
_id: ObjectId
tenant_id: str
project_id: str
run_id: str (optional, null for evergreen)
chunk_type: "research" | "post" | "brand_fact"
content: str
embedding: list[float] (1536-dim for text-embedding-3-small)
evergreen: bool
performance_score: float (0.0–1.0, set when rated)
expires_at: datetime (null for evergreen)
created_at: datetime
```

---

## 5. API SPECIFICATION

### MCP Tools (via SSE on port 8000)
| Tool | Description |
|------|-------------|
| research_trends | Perplexity research + optional Apify competitor scraping |
| generate_content | LLM content generation with brand voice injection |
| generate_visual | Visual asset via fal.ai Flux / template renderer |
| queue_post | Save to MongoDB + schedule in Postiz |
| get_run_status | MongoDB agent_runs lookup |
| list_projects | Active projects with run count |
| create_project | Create project + seed brand voice chunks (Phase 2) |
| add_brand_fact | Add evergreen knowledge chunk to project (Phase 2) |

### REST Endpoints (crew-runner port 8001)
| Method | Path | Description |
|--------|------|-------------|
| POST | /runs | Create and enqueue pipeline run |
| GET | /runs | List runs (tenant-scoped) |
| GET | /runs/{id} | Get run with stage data |
| GET | /runs/{id}/stage/{stage} | Get stage output |
| POST | /runs/{id}/stage/{stage}/approve | Resume paused stage |
| POST | /runs/{id}/stage/{stage}/edit | Override stage output + resume |
| POST | /runs/{id}/stage/{stage}/reject | Re-run stage from snapshot |
| DELETE | /runs/{id} | Cancel run |
| GET | /runs/{id}/stream | SSE event stream |
| GET | /runs/{id}/cost | Cost breakdown per tool |

### REST Endpoints (mcp-server port 8000)
| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check + tools list |
| GET | /queue | List posts by platform/status |
| POST | /queue/{id}/approve | Mark post approved |
| DELETE | /queue/{id} | Remove post |
| GET/PUT | /config/brand-voice | Brand voice CRUD |
| GET/PUT | /config/strategy | Content strategy |
| GET/PUT | /config/content-model | Model selection |
| GET | /projects | List active projects |
| POST | /projects | Create project |
| GET/PATCH/DELETE | /projects/{id} | Project CRUD |
| PATCH | /posts/{id}/rate | Rate post performance (Phase 3) |

---

## 6. PIPELINE SPECIFICATION

### Stage 1: Research
- **Input:** topic, platforms, tenant_id, project_id (optional)
- **Step 0 (Phase 2):** retrieve_relevant_context(project_id, topic) → inject into brief
- **Process:** Perplexity sonar → trending_angles, pain_points, suggested_hooks; optional Apify competitor scraping (non-fatal)
- **Output:** ResearchBrief (trending_angles, pain_points, suggested_hooks, competitor_insights, platform_notes)
- **Error handling:** Competitor failure is warning-only; Perplexity failure → stage FAILED
- **Tests required:** trends parsed correctly, competitor failure non-fatal, context injected

### Stage 2: Content Generation
- **Input:** ResearchBrief, platforms, project context (optional)
- **Process:** OpenRouter (Claude Sonnet 4.6 default) with brand voice + few-shot + context
- **Output:** dict[platform → PlatformContent(copy, hashtags[], cta, hook, char_count)]
- **Constraints:** Twitter ≤280 chars via model retry; hashtags always as list not in copy
- **Error handling:** Content failure → stage FAILED; platform with error skipped
- **Tests required:** model is Claude not Gemini, brand voice in prompt, Twitter length, hashtags as list

### Stage 3: Visual Generation
- **Input:** PlatformContent per platform
- **Process:** Gemini Flash brief → fal.ai Flux (default) → renderer template (fallback)
- **Dimensions:** Instagram 1080×1080, LinkedIn 1200×627, Twitter 1600×900
- **Output:** dict[platform → VisualAsset(url, platform, dimensions, source)]
- **Error handling:** Visual failure is non-fatal; post.visual_url may be null
- **Tests required:** fal.ai called first, correct dimensions, URL saved to post

### Stage 4: Scheduling
- **Input:** approved PlatformContent + VisualAssets
- **Process:** queue_post → Postiz API → optimal time calculation
- **Output:** list[QueuedPost(postiz_id, platform, scheduled_at)]
- **Error handling:** Postiz unavailable → local queue with mock postiz_id
- **Tests required:** Postiz API called, optimal times correct by platform

---

## 7. ACCEPTANCE CRITERIA

Complete acceptance criteria are embedded in §3 (Features by Phase) per feature row.

Global criteria that apply to all features:
- All CSS in `globals.css`; no inline styles
- All toasts via Sonner only
- All backend routes use tenant auth middleware
- API responses follow existing envelope format `{success, data, error}`
- Sidebar always 260px (Phase 2+)

---

## 8. PHASE COMPLETION CHECKLIST

### Phase 0 ✅
- [x] 246 tests passing, 0 failing
- [x] Backend coverage 80%
- [x] All stale test imports fixed (17 tests fixed)
- [x] Known issues documented in §9
- [x] SRS.md created
- [x] ROADMAP.md created

### Phase 1
- [ ] vitest infrastructure installed in dashboard/
- [ ] PostPreviewPanel tests passing (hashtags as pills)
- [ ] useAgentRun tests passing
- [ ] usePostPreview tests passing
- [ ] QueuePage integration test passing
- [ ] Frontend coverage ≥ 70%
- [ ] MCP Inspector shows 8 tools at localhost:8000/sse
- [ ] `claude mcp list` shows offerberries
- [ ] Twitter copy not truncated (model retry, not slice)
- [ ] Hashtags always stored as array on post documents
- [ ] SRS.md updated with Phase 1 results

### Phase 2
- [ ] context_service.py implemented and tested
- [ ] project_context_chunks collection + Atlas vector index
- [ ] Brand voice seeded on project creation
- [ ] Pipeline Step 0 context retrieval
- [ ] Post-run store_run_context
- [ ] AgentRun.projectId field
- [ ] Sidebar shows projects with collapsible runs
- [ ] Sidebar width 260px in CSS token
- [ ] CreateProjectModal
- [ ] Project Overview page (2 tabs)
- [ ] Input bar project chip
- [ ] Context awareness banner
- [ ] Backend ≥ 75%, Frontend ≥ 75%
- [ ] SRS.md updated

### Phase 3
- [ ] Apify env var fixed, non-fatal, Pakistani watchlist
- [ ] Perplexity fallback for competitor research
- [ ] Performance rating endpoint + UI
- [ ] High/low rated posts stored in context
- [ ] fal.ai is default, correct dimensions
- [ ] Visual URLs saved to posts
- [ ] Backend ≥ 75%, Frontend ≥ 75%
- [ ] SRS.md updated

### Phase 4
- [ ] Project schedule config fields
- [ ] APScheduler service, topic rotation
- [ ] Auto-approve mode
- [ ] Postiz integration end-to-end
- [ ] Optimal posting times helper
- [ ] Scheduled time label in Queue page
- [ ] Pipeline node graph (4 nodes, StepDetailPanel)
- [ ] Backend ≥ 80%, Frontend ≥ 80%
- [ ] SRS.md updated

### Phase 5
- [ ] Run + project analytics functions
- [ ] Analytics page wired to real data
- [ ] Calendar month view
- [ ] Gap warning
- [ ] SRS compliance table (all ✅)
- [ ] Final PHASE 5 report

---

## 9. KNOWN ISSUES LOG

| ID | Description | Severity | Phase | Status |
|----|-------------|----------|-------|--------|
| B-01 | Apify env var mismatch (APIFY_API_TOKEN vs APIFY_API_KEY) | High | 3 | Open |
| B-02 | Twitter copy truncated mid-word (slice not retry) | High | 1 | Open |
| B-03 | Hashtags not always stored as separate array | Medium | 1 | Open |
| B-04 | arq worker restart durability not verified in production | Medium | 1 | Open |
| B-05 | fal.ai visual URL blank for some runs | Medium | 3 | Open |
| B-06 | Frontend: zero automated tests | High | 1 | Open |
| B-07 | context_service not implemented (no vector store) | High | 2 | Open |
| B-08 | Sidebar has no project grouping | Medium | 2 | Open |
| B-09 | Postiz integration not tested end-to-end | Medium | 4 | Open |
| B-10 | 9 mcp_server tests had stale imports | Low | 0 | Fixed 2026-06-18 |
| B-11 | 9 crew tests failed from stale API signatures | Low | 0 | Fixed 2026-06-18 |

---

## 10. CHANGE LOG

| Date | Phase | Change | Author |
|------|-------|--------|--------|
| 2026-06-18 | 0 | Initial SRS created; 17 stale tests fixed; baseline coverage 80% | Claude |
