# Dev Log

General development progress and decisions for the ZeroPath Security Scanner project.

## 2026-03-16 — Project Kickoff

### Environment
- Python 3.9.4, Node 20 LTS (upgraded from v24)
- Windows 10 Home
- SQLite for dev DB, Redis via docker-compose

### Phase 0: Scaffolding — COMPLETE
- Root config files in place
- Backend: FastAPI + SQLAlchemy async + Alembic + Celery
- Frontend: Next.js 14 + Tailwind CSS
- Both build/compile clean

### Phase 1: Authentication — COMPLETE
- JWT auth with bcrypt password hashing
- 4 endpoints: signup, login, refresh, me
- Frontend login/signup pages with validation
- Root page redirects based on token presence

### Phase 2: Repo Management — COMPLETE
- Repository CRUD (create, list, get by ID)
- Git clone (shallow) + Python file discovery
- Dashboard with add-repo form and repo cards
- Repo detail page with placeholder for scan history

### Phase 3: LLM Scanner Engine — COMPLETE
- Scan + Finding models with full migration
- Scanner pipeline: chunker (80k token limit), LLM prompts, dedup (SHA-256), analyzer (Claude Sonnet)
- Celery worker: clone → discover → chunk → analyze → dedup → persist
- API: POST /api/scans (create + enqueue), GET /api/scans/:id (status check)

### Phase 4: Findings Dashboard & Scan Results UI — COMPLETE
- Findings API: list by scan (severity-sorted, filterable), get individual finding
- Repo detail now returns scans array; "New Scan" button triggers scan + navigates
- Scan detail page polls every 5s, shows findings with expandable cards
- UI components: SeverityBadge (color-coded), StatusBadge (animated for running), FindingCard (collapsible)

### Phase 5: Triage Workflow — COMPLETE
- TriageStatus model: per-user-per-finding, upsert pattern
- PATCH endpoint for triage with validation (open/false_positive/resolved)
- Carry-forward: copies triage from previous scan via identity_hash matching
- Frontend: triage controls in FindingCard, filter bar (triage + severity pills)

### Phase 6: Cross-Scan Comparison — COMPLETE
- Comparison API: set operations on identity_hash across scans (new/fixed/persisting)
- ComparisonTable: 3 collapsible sections with color coding, reuses FindingCard
- Scan detail: dropdown to compare with older scans, deep-link via ?compare= param
- Repo detail: "Compare" links between consecutive complete scans

### Phase 7: README, Tests & Polish — COMPLETE
- 23 backend tests: auth (7), scans (2), scanner unit tests (14) — all pass
- Comprehensive README covering architecture, prompt design, parsing, identity hashing, trade-offs
- NavHeader: user email + logout
- Deployment: Procfile, runtime.txt, startup auto-migration

### Project Status
All 8 phases (0-7) complete. Project is ready for submission.
