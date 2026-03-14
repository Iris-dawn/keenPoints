"""KeenPoint backend — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings, ensure_dirs
from app.core.logger import logger
from app.api.routes import router


def create_app() -> FastAPI:
    ensure_dirs()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    logger.info(f"[APP] {settings.APP_NAME} v{settings.VERSION} ready")
    return app


app = create_app()
