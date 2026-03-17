from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware

app = FastAPI(
    title="ZeroPath Security Scanner",
    version="2.0.0",
    description="LLM-powered security scanner with AST taint analysis",
)

origins = [o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, scan_requests_per_minute=10)


@app.on_event("startup")
async def startup():
    """Run migrations on startup."""
    import subprocess
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
    except Exception:
        pass


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "engine": "hybrid-sast-llm"}


from app.routers import auth, repos, scans, findings, websocket, admin, webhooks, stats

app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(websocket.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
app.include_router(stats.router)
