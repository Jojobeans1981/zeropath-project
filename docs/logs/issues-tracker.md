# Issues Tracker

Known issues, workarounds, and tech debt for the ZeroPath project.

| # | Status | Severity | Area     | Description                                                      | Workaround / Fix                              |
|---|--------|----------|----------|------------------------------------------------------------------|-----------------------------------------------|
| 1 | Fixed  | Medium   | Backend  | `passlib` incompatible with `bcrypt>=4.1` — crashes on hash      | Pinned `bcrypt==4.0.1` in requirements.txt    |
| 2 | Fixed  | Medium   | Backend  | `greenlet` latest fails to compile on Python 3.9 + Windows       | Pinned `greenlet==3.0.3` in requirements.txt  |
| 3 | Fixed  | Low      | Backend  | `str \| None` union syntax unsupported in Python 3.9             | Use `Optional[str]` from typing               |
| 4 | Open   | Low      | Frontend | `apiFetch` error parsing doesn't unwrap `detail.error` envelope  | Fallback error messages display instead        |
| 5 | Open   | Info     | Backend  | Port 8000 occupied by another Django project on dev machine       | Use alternate port for testing                 |
| 6 | Fixed  | Low      | Frontend | `@/*` tsconfig maps to `./app/*` — double `app` in imports       | Use `@/components/` not `@/app/components/`   |
| 7 | Fixed  | Medium   | Backend  | `get_scan` lazy-loads `scan.repo` in async context → MissingGreenlet | Used `selectinload(Scan.repo)` for eager loading |
| 8 | Open   | Info     | Backend  | Celery worker needs Redis running to process queued scans         | `docker-compose up -d` to start Redis         |
