# ZeroPath Security Scanner — Phase Index

## Overview
12 phases total: 8 core (0-7) + 4 stretch (8-11). Each phase document is self-contained with full context, coding standards, and acceptance criteria inlined.

## Core Phases

| Phase | Name | New Files | Key Deliverables |
|-------|------|-----------|------------------|
| 0 | [Project Scaffolding](phase-0.md) | ~25 files | FastAPI + Next.js apps, Celery + Redis, SQLAlchemy + Alembic, apiFetch wrapper |
| 1 | [Authentication System](phase-1.md) | 7 files | User model, signup/login/refresh/me endpoints, JWT tokens, frontend auth pages |
| 2 | [Repository Management & Git Ops](phase-2.md) | 8 files | Repository model, CRUD API, git clone, Python file discovery, dashboard + repo detail UI |
| 3 | [LLM-Powered Scanner Engine](phase-3.md) | 10 files | Scan/Finding models, chunker, prompts, Claude API analyzer, dedup, Celery worker pipeline |
| 4 | [Findings Dashboard & Scan Results UI](phase-4.md) | 5 files | Findings API, SeverityBadge, StatusBadge, FindingCard, scan detail page with polling |
| 5 | [Triage Workflow](phase-5.md) | 2 files | TriageStatus model, triage API, inline triage UI, filter bar, triage carry-forward |
| 6 | [Cross-Scan Comparison](phase-6.md) | 1 file | Comparison API, ComparisonTable component, compare links on repo page |
| 7 | [README, Tests & Polish](phase-7.md) | 5 files | README.md, pytest suite, loading/error/empty states, NavHeader polish, deployment config |

## Stretch Phases

| Phase | Name | New Files | Key Deliverables |
|-------|------|-----------|------------------|
| 8 | [Private Repo Auth + SARIF Export](phase-8.md) | 3 files | Encrypted GitHub token storage, authenticated clone, SARIF v2.1.0 export |
| 9 | [WebSocket Real-Time Updates](phase-9.md) | 2 files | WebSocket endpoint, Redis pub/sub, progressive finding display, polling fallback |
| 10 | [RBAC + CI/CD Webhooks](phase-10.md) | 3 files | User roles (admin/member/viewer), role-based permissions, GitHub webhook scanning |
| 11 | [Auto-Remediation + Multi-Language](phase-11.md) | 3 files | LLM fix suggestions with diff view, JavaScript/TypeScript scanning support |

## Dependency Graph

```
Phase 0 (scaffolding)
  └→ Phase 1 (auth)
      └→ Phase 2 (repos + git)
          └→ Phase 3 (scanner engine)
              └→ Phase 4 (findings UI)
                  └→ Phase 5 (triage)
                      └→ Phase 6 (comparison)
                          └→ Phase 7 (README + polish)
                              ├→ Phase 8 (private repos + SARIF)
                              ├→ Phase 9 (WebSocket)
                              ├→ Phase 10 (RBAC + webhooks)
                              └→ Phase 11 (remediation + multi-lang)
```

Stretch phases 8-11 are all independent of each other — they only depend on Phase 7 being complete. They can be implemented in any order.

## Cumulative State After Each Phase

| After Phase | Models | API Endpoints | Frontend Pages |
|-------------|--------|---------------|----------------|
| 0 | — | 1 (health) | 1 (placeholder) |
| 1 | User | 5 | 3 (login, signup, root) |
| 2 | User, Repository | 8 | 5 (+dashboard, repo detail) |
| 3 | User, Repository, Scan, Finding | 10 | 5 (no new pages) |
| 4 | same | 12 | 6 (+scan detail) |
| 5 | +TriageStatus | 13 | 6 (extended) |
| 6 | same | 14 | 6 (extended) |
| 7 | same | 14 | 6 (polished) |
| 8 | same (extended) | 16 | 6 (extended) |
| 9 | same | 16 + WS | 6 (extended) |
| 10 | same (extended) | 19 | 7 (+admin) |
| 11 | +Remediation | 21 | 7 (extended) |
