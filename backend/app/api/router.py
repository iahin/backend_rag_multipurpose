from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
