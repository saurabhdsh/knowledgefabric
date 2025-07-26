from fastapi import APIRouter
from app.api.v1.endpoints import upload, search, knowledge, training, database

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(database.router, prefix="/database", tags=["database"]) 