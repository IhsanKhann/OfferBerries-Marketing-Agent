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
| 3 exit | ≥ 75% | ≥ 75% |
| 4 exit | ≥ 80% | ≥ 80% |
| 5 exit | ≥ 80% | ≥ 80% |

Backend **80%** (269 tests). Frontend **77% statements / 80% lines** (140 tests, 11 test files).

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

## Phase 3 — Intelligence & Competitor Awareness
*Gate: Backend ≥ 75% / Frontend ≥ 75%*

### What to build
- Fix Apify env var mismatch (`APIFY_API_TOKEN` vs `APIFY_API_KEY`)
- Add Perplexity fallback for competitor research when Apify fails
- Performance rating UI (🔥 High / 👍 Medium / 👎 Low) in PostPreviewPanel
- High-rated posts → evergreen context chunks; low-rated → negative examples
- Promote fal.ai Flux to default visual generator (currently fallback)
- Correct platform dimensions: Instagram 1080×1080, LinkedIn 1200×627, Twitter 1600×900

---

## Phase 4 — Autonomy & Scheduled Runs
*Gate: Backend ≥ 80% / Frontend ≥ 80%*

### What to build
- Project schedule config (frequency, topic rotation, auto-approve)
- APScheduler service for automatic run creation
- Postiz integration fix (optimal posting times PKT)
- n8n-style pipeline node graph in /runs (clickable, 4 nodes, StepDetailPanel)
- Schedule configuration UI in Project Settings

---

## Phase 5 — Analytics, Feedback & Calendar
*Gate: Backend ≥ 80% / Frontend ≥ 80%*

### What to build
- Analytics: cost_per_post, best_platform, optimal_times_from_data
- Content calendar month view with gap warnings
- Final SRS cross-validation table (every feature ✅ ✅ ✅ ✅)

---

## The Path to 10/10

The features are 30% of the journey. The other 70%:
- Use it every week for OfferBerries' actual social media
- Rate every post's performance
- Let the project context accumulate 3 months of what works
- Scheduled runs producing content without manual intervention

**Right now:** Phase 1 — frontend tests, MCP connectivity, fix the 3 production reliability issues.

See `docs/SRS.md` for detailed acceptance criteria per phase.
