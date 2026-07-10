"""Feature-based access control for Weave API routes."""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import (
    FEATURE_USER_MANAGEMENT,
    ROLE_ADMIN,
    auth_service,
)

# Longest-prefix wins. Order matters for overlapping prefixes.
_PATH_FEATURE_RULES: List[Tuple[str, str]] = [
    ("/api/v1/users", FEATURE_USER_MANAGEMENT),
    ("/api/v1/knowledge/train-ml-models", "train_ml"),
    ("/api/v1/knowledge/distribute-model", "train_ml"),
    ("/api/v1/knowledge/models", "train_ml"),
    ("/api/v1/training", "train_ml"),
    ("/api/v1/knowledge/query", "test_llm"),
    ("/api/v1/knowledge/retrieve", "test_llm"),
    ("/api/v1/knowledge/import-codebase-migration", "create_knowledge"),
    ("/api/v1/knowledge/create-", "create_knowledge"),
    ("/api/v1/knowledge/preview-", "create_knowledge"),
    ("/api/v1/knowledge/test-database", "create_knowledge"),
    ("/api/v1/knowledge/test-mongodb", "create_knowledge"),
    ("/api/v1/upload", "create_knowledge"),
    ("/api/v1/database", "create_knowledge"),
    ("/api/v1/ontology/enrichment", "ontology_enrichment"),
    ("/api/v1/ontology/agent", "agent_utilities"),
    ("/api/v1/ontology", "ontology"),
    ("/api/v1/graph", "fabrics"),
    ("/api/v1/search", "context"),
    ("/api/v1/platform", "fabrics"),
]


def resolve_required_feature(path: str) -> Optional[str]:
    # Shared authenticated endpoints — no feature gate
    if path.startswith("/api/v1/knowledge/api-keys"):
        return None
    if path in ("/api/v1/knowledge/test", "/api/v1/knowledge/stats", "/api/v1/knowledge/"):
        return None
    if path.rstrip("/") == "/api/v1/knowledge":
        return None
    if "/codebase/reanalyze" in path:
        return "create_knowledge"
    if path.endswith("/migration-export") or "/migration-export" in path:
        return "fabrics"

    for prefix, feature in _PATH_FEATURE_RULES:
        if path.startswith(prefix):
            return feature
    # Fabric catalog / knowledge graph reads
    if path.startswith("/api/v1/knowledge"):
        # create/train/query already matched above; remaining knowledge routes → fabrics
        return "fabrics"
    return None


def _matches_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


class FeatureGateMiddleware(BaseHTTPMiddleware):
    """Block API calls when the authenticated user lacks the mapped feature."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/v1/"):
            return await call_next(request)
        if _matches_any(path, ("/api/v1/auth/login", "/api/v1/auth/me")):
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # JWT middleware handles unauthenticated requests
            return await call_next(request)

        feature = resolve_required_feature(path)
        if not feature:
            return await call_next(request)

        role = getattr(request.state, "role", None) or ROLE_ADMIN
        features = getattr(request.state, "allowed_features", None)
        if role == ROLE_ADMIN:
            return await call_next(request)

        if features is None:
            user = auth_service.get_user_by_id(user_id)
            if not user or not auth_service.user_has_feature(user, feature):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"You do not have access to '{feature}'."},
                )
            return await call_next(request)

        if feature not in (features or []):
            return JSONResponse(
                status_code=403,
                content={"detail": f"You do not have access to '{feature}'."},
            )
        return await call_next(request)
