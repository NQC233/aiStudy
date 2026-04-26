from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.auth_bootstrap_service import ensure_default_account_and_migrate_legacy_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    """在应用启动时补齐单用户开发模式所需的测试数据。"""
    db = SessionLocal()
    try:
        ensure_default_account_and_migrate_legacy_data(db, enabled=settings.auth_default_account_enabled)
        yield
    finally:
        db.close()


def create_application() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    application = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_application()
