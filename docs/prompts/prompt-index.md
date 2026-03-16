# ZeroPath Security Scanner — Implementation Prompt Index

## Pipeline Summary
- **Source:** ZeroPath take-home spec (LLM-powered Python security scanner)
- **PRD:** `docs/PRD.md`
- **Phases:** 12 phases in `docs/phases/`
- **Total Prompts:** 38 across all phases

## Execution Order

### Phase 0: Project Scaffolding (4 prompts)
File: `docs/prompts/phase-0-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 0.1 | `.gitignore`, `.env.example`, `docker-compose.yml` | Root config files |
| 0.2 | `backend/requirements.txt`, `backend/app/config.py`, package dirs | Backend scaffolding |
| 0.3 | `backend/app/main.py`, `database.py`, `deps.py`, `scan_worker.py`, Alembic | Backend core (FastAPI + DB + Celery) |
| 0.4 | `frontend/package.json`, `lib/api.ts`, `lib/auth.ts`, app skeleton | Frontend scaffolding |

### Phase 1: Authentication System (4 prompts)
File: `docs/prompts/phase-1-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 1.1 | `models/user.py`, migration | User model + DB migration |
| 1.2 | `schemas/auth.py`, `services/auth_service.py` | Auth schemas + JWT service |
| 1.3 | `routers/auth.py`, `deps.py`, `main.py` | Auth endpoints + dependencies |
| 1.4 | `app/login/`, `app/signup/`, `app/page.tsx` | Frontend auth pages |

### Phase 2: Repository Management & Git Ops (4 prompts)
File: `docs/prompts/phase-2-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 2.1 | `models/repository.py`, migration | Repository model |
| 2.2 | `schemas/repo.py`, `services/repo_service.py`, `routers/repos.py` | Repo CRUD API |
| 2.3 | `scanner/git_ops.py` | Git clone + Python file discovery |
| 2.4 | `app/dashboard/`, `app/repos/[id]/`, `components/NavHeader.tsx` | Dashboard + repo detail UI |

### Phase 3: LLM-Powered Scanner Engine (5 prompts)
File: `docs/prompts/phase-3-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 3.1 | `models/scan.py`, `models/finding.py`, migration | Scan + Finding models |
| 3.2 | `schemas/scan.py`, `services/scan_service.py`, `routers/scans.py` | Scan creation API |
| 3.3 | `scanner/chunker.py`, `scanner/prompts.py`, `scanner/dedup.py` | Chunker + prompts + dedup |
| 3.4 | `scanner/analyzer.py` | Claude API integration + JSON parsing |
| 3.5 | `workers/scan_worker.py` | Full Celery scan pipeline |

### Phase 4: Findings Dashboard & Scan Results UI (4 prompts)
File: `docs/prompts/phase-4-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 4.1 | `services/finding_service.py`, `routers/scans.py`, `routers/findings.py` | Findings API endpoints |
| 4.2 | `components/SeverityBadge.tsx`, `StatusBadge.tsx`, `FindingCard.tsx` | UI components |
| 4.3 | `app/scans/[id]/page.tsx` | Scan detail page with polling |
| 4.4 | `app/repos/[id]/page.tsx` (extend) | Scan history + "New Scan" button |

### Phase 5: Triage Workflow (4 prompts)
File: `docs/prompts/phase-5-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 5.1 | `models/triage.py`, migration | TriageStatus model |
| 5.2 | `schemas/finding.py`, `services/finding_service.py`, `routers/findings.py` | Triage API + response extension |
| 5.3 | `services/finding_service.py`, `workers/scan_worker.py` | Triage carry-forward |
| 5.4 | `components/FindingCard.tsx`, `app/scans/[id]/page.tsx` | Triage UI + filter bar |

### Phase 6: Cross-Scan Comparison (2 prompts)
File: `docs/prompts/phase-6-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 6.1 | `schemas/scan.py`, `services/finding_service.py`, `routers/scans.py` | Comparison API |
| 6.2 | `components/ComparisonTable.tsx`, scan + repo pages | Comparison UI |

### Phase 7: README, Tests & Polish (4 prompts)
File: `docs/prompts/phase-7-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 7.1 | `tests/conftest.py`, `test_auth.py`, `test_scans.py`, `test_scanner.py` | Backend test suite |
| 7.2 | `README.md` | Comprehensive project documentation |
| 7.3 | All frontend pages + `NavHeader.tsx` | UX polish + NavHeader completion |
| 7.4 | `Procfile`, `runtime.txt`, deployment config | Deployment configuration |

### Phase 8 (Stretch): Private Repos + SARIF (3 prompts)
File: `docs/prompts/phase-8-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 8.1 | `services/crypto_service.py`, `models/repository.py`, worker | Encrypted token storage + private clone |
| 8.2 | `services/sarif_service.py`, `routers/scans.py` | SARIF v2.1.0 export |
| 8.3 | `app/dashboard/`, `app/scans/[id]/` | Token field + SARIF download button |

### Phase 9 (Stretch): WebSocket Updates (2 prompts)
File: `docs/prompts/phase-9-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 9.1 | `services/pubsub_service.py`, `routers/websocket.py` | Redis pub/sub + WebSocket endpoint |
| 9.2 | `workers/scan_worker.py`, `app/scans/[id]/page.tsx` | Event publishing + frontend WebSocket |

### Phase 10 (Stretch): RBAC + Webhooks (3 prompts)
File: `docs/prompts/phase-10-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 10.1 | `models/user.py`, `deps.py`, all routers | User roles + role dependency |
| 10.2 | `routers/admin.py`, `app/admin/page.tsx`, NavHeader | Admin endpoints + UI |
| 10.3 | `services/webhook_service.py`, `routers/webhooks.py` | GitHub webhook endpoint |

### Phase 11 (Stretch): Remediation + Multi-Language (3 prompts)
File: `docs/prompts/phase-11-prompts.md`
| Prompt | File Target | Description |
|--------|-------------|-------------|
| 11.1 | `models/remediation.py`, `services/remediation_service.py`, `routers/findings.py` | LLM fix generation |
| 11.2 | `scanner/git_ops.py`, `scanner/prompts.py`, `workers/scan_worker.py` | Multi-language scanning |
| 11.3 | `components/RemediationView.tsx`, `components/FindingCard.tsx` | Remediation UI + language badge |

## How to Use
1. Open `docs/prompts/phase-0-prompts.md`
2. Copy Prompt 0.1 and paste it into your coding agent
3. After the agent completes it, paste Prompt 0.2
4. Continue through all prompts in Phase 0
5. Verify the acceptance criteria at the bottom of each phase file
6. Move to Phase 1 and repeat
7. Each prompt is self-contained — no additional context needed
8. Stretch phases (8-11) are independent and can be done in any order after Phase 7

## Generated Files
```
docs/
├── PRD.md
├── phases/
│   ├── phase-index.md
│   ├── phase-0.md
│   ├── phase-1.md
│   ├── phase-2.md
│   ├── phase-3.md
│   ├── phase-4.md
│   ├── phase-5.md
│   ├── phase-6.md
│   ├── phase-7.md
│   ├── phase-8.md
│   ├── phase-9.md
│   ├── phase-10.md
│   └── phase-11.md
└── prompts/
    ├── prompt-index.md          ← you are here
    ├── phase-0-prompts.md
    ├── phase-1-prompts.md
    ├── phase-2-prompts.md
    ├── phase-3-prompts.md
    ├── phase-4-prompts.md
    ├── phase-5-prompts.md
    ├── phase-6-prompts.md
    ├── phase-7-prompts.md
    ├── phase-8-prompts.md
    ├── phase-9-prompts.md
    ├── phase-10-prompts.md
    └── phase-11-prompts.md
```
