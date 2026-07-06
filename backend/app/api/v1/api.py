from fastapi import APIRouter
from app.api.v1.endpoints import upload, search, knowledge, training, database, ontology, platform, graph, auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(database.router, prefix="/database", tags=["database"])
api_router.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"]) 