from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="ZeroPath Security Scanner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Run migrations on startup (for Railway deployment)."""
    import subprocess
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
    except Exception:
        pass  # Migration may fail if already up to date


@app.get("/api/health")
async def health():
    return {"status": "ok"}


from app.routers import auth, repos, scans, findings, websocket, admin, webhooks

app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(websocket.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
