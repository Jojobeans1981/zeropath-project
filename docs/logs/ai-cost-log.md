# AI Cost Log

Tracks AI/LLM API usage and estimated costs for the ZeroPath project build.

| Date       | Model              | Phase | Prompts Executed | Est. Input Tokens | Est. Output Tokens | Notes                          |
|------------|--------------------|-------|------------------|-------------------|--------------------|--------------------------------|
| 2026-03-16 | Claude Opus 4.6 1M | 0     | 4                | ~15k              | ~8k                | Root config, backend/frontend scaffolding |
| 2026-03-16 | Claude Opus 4.6 1M | 1     | 4                | ~30k              | ~12k               | Auth system (models, JWT, routes, frontend pages) |
| 2026-03-16 | Claude Opus 4.6 1M | 2     | 4                | ~25k              | ~10k               | Repo management, git ops, dashboard UI |
| 2026-03-16 | Claude Opus 4.6 1M | 3     | 5                | ~40k              | ~15k               | Scan/Finding models, scanner engine, Celery worker |
| 2026-03-16 | Claude Opus 4.6 1M | 4     | 4                | ~35k              | ~14k               | Findings API, UI components, scan detail page, repo scan history |
| 2026-03-16 | Claude Opus 4.6 1M | 5     | 4                | ~35k              | ~16k               | Triage model, API, carry-forward, frontend triage UI + filters |
| 2026-03-16 | Claude Opus 4.6 1M | 6     | 2                | ~30k              | ~14k               | Comparison API, ComparisonTable, scan/repo detail extensions |
| 2026-03-16 | Claude Opus 4.6 1M | 7     | 4                | ~35k              | ~18k               | Tests (23 pass), README, NavHeader polish, deployment config |
