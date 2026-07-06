from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.security import InboundAPIKeyMiddleware
from app.core.jwt_auth import JWTAuthMiddleware
from app.db.session import init_db
from app.services.auth_service import auth_service
from app.services.legacy_data_migration import migrate_legacy_data_to_primary_admin
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_worker import job_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    auth_service.ensure_seed_users()
    fabric_store.initialize()
    migrate_legacy_data_to_primary_admin()
    job_worker.start()
    yield
    job_worker.stop()


app = FastAPI(
    title="Knowledge Fabric API",
    description="Weave — enterprise ontology discovery and knowledge graph platform",
    version="2.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

_extra_origins = [
    o.strip()
    for o in os.environ.get("KF_CORS_ORIGINS", "").split(",")
    if o.strip()
]
_cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000", *_extra_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^https://[a-zA-Z0-9._-]+\.(ngrok\.io|ngrok-free\.app|ngrok\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(InboundAPIKeyMiddleware)
app.add_middleware(JWTAuthMiddleware)
app.include_router(api_router, prefix=settings.API_V1_STR)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def root():
    return {
        "message": "Knowledge Fabric API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    checks = {"api": "healthy", "database": "unknown", "chroma": "unknown", "job_worker": "unknown"}
    try:
        from app.db.session import get_engine
        from sqlalchemy import text

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"

    try:
        from app.services.vector_service import vector_service

        _ = vector_service.documents_collection
        checks["chroma"] = "healthy"
    except Exception as exc:
        checks["chroma"] = f"unhealthy: {exc}"

    checks["job_worker"] = "running" if job_worker._thread and job_worker._thread.is_alive() else "stopped"
    overall = "healthy" if checks["database"] == "healthy" else "degraded"
    return {"status": overall, "service": "knowledge-fabric-api", "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
