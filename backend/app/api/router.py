from fastapi import APIRouter

from app.api.routes.assets import router as assets_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.notes import router as notes_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(assets_router)
api_router.include_router(chat_router)
api_router.include_router(notes_router)
