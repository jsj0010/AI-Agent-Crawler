"""FastAPI 라우터 모듈."""

from app.api.routes.live import create_v1_router

__all__ = [
    "create_v1_router",
]
