# OfferBerries Marketing Agent — Roadmap to 10/10

## The Contract

Every phase is gated. Nothing proceeds to the next phase until:
1. All phase acceptance criteria are met (verified against `docs/SRS.md`)
2. Backend coverage ≥ gate threshold
3. Frontend coverage ≥ gate threshold
4. A phase report is produced and signed off

**TDD is mandatory throughout.** Write the test first. Watch it fail. Write the code. Watch it pass.

---

## Coverage Gates

| Phase | Backend | Frontend |
|-------|---------|----------|
| 0 Baseline | 80% ✅ | 0% (no tests yet) |
| 1 exit | ≥ 70% ✅ | ≥ 70% ✅ |
| 2 exit | ≥ 75% ✅ | ≥ 75% ✅ |
| 3 exit | ≥ 75% ✅ | ≥ 75% ✅ |
| 4 exit | ≥ 80% ✅ | ≥ 80% ✅ |
| 5 exit | ≥ 80% ✅ | ≥ 80% ✅ |

Backend **80%** (311 tests). Frontend **85% statements / 89% lines** (167 tests, 12 test files).

---

## Phase 0 — SRS + Baseline Audit ✅
*Completed: 2026-06-18*

- Fixed 17 broken/stale tests across crew and mcp_server suites
- 246 tests passing, 80% backend coverage
- Documented all known issues in `docs/SRS.md §9`
- Created this ROADMAP.md and `docs/SRS.md`

---

## Phase 1 — Reliability, Tests & MCP Connectivity ✅
*Completed: 2026-06-18 | Gate: Backend ≥ 70% ✅ (80%) / Frontend ≥ 70% ✅ (71%)*

### What to build
- **Frontend test infrastructure** — vitest + @testing-library/react + msw (currently 0 tests)
- **MCP connectivity verification** — Inspector, Claude Code CLI, Cloudflare tunnel
- **Fix known production issues** (from SRS §9):
  - Twitter copy truncated mid-word
  - Hashtags not always stored as separate array field
  - arq worker durability under restart
- **MCP connection guide** (`docs/MCP_CONNECT.md` already exists at repo root — verify and update)

### Test files to create
```
dashboard/vitest.config.ts
dashboard/tests/setup.ts
dashboard/tests/mocks/server.ts + handlers.ts
dashboard/tests/unit/hooks/useAgentRun.test.ts
dashboard/tests/unit/hooks/usePostPreview.test.ts
dashboard/tests/unit/components/PostPreviewPanel.test.tsx
dashboard/tests/unit/components/PostCard.test.tsx
dashboard/tests/integration/QueuePage.test.tsx
```

### How to verify
```bash
# Backend
cd agent && python -m pytest --cov=crew --cov=mcp_server -q

# Frontend
cd dashboard && npx vitest run --coverage

# MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/sse

# Claude Code CLI
claude mcp list
```

---

## Phase 2 — Projects & Multi-Run Context ✅
*Completed: 2026-06-18 | Gate: Backend ≥ 75% ✅ (80%) / Frontend ≥ 75% ✅ (77%)*

### What to build
- `agent/mcp_server/services/context_service.py` — embed/store/retrieve via Atlas Vector Search
- `project_context_chunks` MongoDB collection with vector index
- Project creation seeds `brand_voice.md` as evergreen chunks
- Pipeline Step 0: retrieve project context before research
- Post-run storage: `store_run_context(run, posts)` saves research + post chunks
- `AgentRun` model gets optional `projectId` field
- Frontend: sidebar projects section, useProjects hook, CreateProjectModal, Project Overview page
- Sidebar width corrected to 260px (currently 228px in CSS token)

### Key files
```
agent/mcp_server/services/context_service.py    (new)
agent/tests/unit/test_context_service.py        (new, TDD)
agent/tests/unit/test_projects.py               (new, TDD)
dashboard/hooks/useProjects.ts                  (new)
dashboard/app/(app)/projects/[projectId]/page.tsx (new)
dashboard/app/(app)/sidebar.tsx                 (modify)
dashboard/app/globals.css                       (--sidebar-width: 260px)
```

---

## Phase 3 — Intelligence & Competitor Awareness ✅
*Completed: 2026-06-18 | Gate: Backend ≥ 75% ✅ (80%, 284 tests) / Frontend ≥ 75% ✅ (77% stmts / 80% lines, 146 tests)*

### What was built
- Perplexity fallback for competitor research when Apify is unavailable (`tools/research.py`)
- `PerformanceRating` enum (high/medium/low) + `PATCH /posts/{id}/rate` endpoint
- Performance rating buttons (🔥 / 👍 / 👎) in PostPreviewPanel — shown for approved posts
- fal.ai Flux promoted to DEFAULT visual generator via `crew/graph_config.py`
- Platform dimensions corrected: LinkedIn 1200×627 (landscape), Instagram 1080×1080, Twitter 1600×900
- `_FAL_SIZE_MAP` in `tools/visual.py` maps platform → fal.ai size string

---

## Phase 4 — Autonomy & Scheduled Runs ✅
*Completed: 2026-06-18 | Gate: Backend ≥ 80% ✅ (299 tests) / Frontend ≥ 80% ✅ (84% stmts / 88% lines, 157 tests)*

### What was built
- Schedule config fields on `ProjectDoc` and `ProjectUpdateRequest` (enabled, frequency, cron, platforms, topic_rotation, auto_approve)
- `services/scheduler_service.py` — `get_optimal_post_time()` per platform (PKT), `next_rotation_topic()` with modulo wraparound
- Optimal PKT slots: Instagram 9/12/19h any day; LinkedIn 8-10am Tue-Thu; Twitter 10/14h any day
- `AgentPipelinePanel` evolved to clickable nodes — `onStepClick` prop, `pipeline-step--clickable`, `pipeline-node--running`, `pipeline-connector--done` CSS classes
- Step output inline viewer (`pipeline-step-output`) for raw stage data
- useAgentRun polling tests (completed + failed branches); AgentError structured error branch
- Drag event tests for pipeline drop zone (dragover/dragleave/drop)

---

## Phase 5 — Analytics, Feedback & Calendar ✅
*Completed: 2026-06-18 | Gate: Backend ≥ 80% ✅ (311 tests) / Frontend ≥ 80% ✅ (85% stmts / 89% lines, 167 tests)*

### What was built
- `services/analytics_service.py`: `get_run_analytics()` (cost_per_post), `get_project_analytics()` (best_platform, avg_engagement), `get_optimal_times_from_data()` (from high-rated posts)
- Optimal times extracted from `scheduled_at` of high-rated posts only (medium/low ignored)
- `ContentCalendar.tsx` — month grid with posts on correct dates, gap-day CSS class, gap warning message
- Posts rendered as platform-colored pills; `onPostClick` callback for preview
- ContentCalendar added to vitest coverage include list

---

## The Path to 10/10

The features are 30% of the journey. The other 70%:
- Use it every week for OfferBerries' actual social media
- Rate every post's performance
- Let the project context accumulate 3 months of what works
- Scheduled runs producing content without manual intervention

**All 5 phases complete.** The agent is now test-driven, has context memory, intelligent visuals, scheduled runs, and analytics. The journey to 10/10 continues through weekly use, rating posts, and letting the context accumulate.

See `docs/SRS.md` for detailed acceptance criteria per phase.
