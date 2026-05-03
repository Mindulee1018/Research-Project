import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.logging_config import setup_logging
from app.config.middleware import RequestContextMiddleware
from app.config.settings import get_settings
from app.controller.moderation_controller import router as moderation_router
from app.exceptions.handlers import register_exception_handlers
from app.model.response_models import GenericResponse
from app.service.moderation_service import get_moderation_service


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(log_level=logging.DEBUG if settings.app_debug else logging.INFO)
    logger = logging.getLogger(__name__)

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(moderation_router)

    @app.on_event("startup")
    def warmup_moderation_model() -> None:
        service = get_moderation_service()
        health = service.health()
        if not health.success or health.data is None or health.data.status != "ok":
            raise RuntimeError(
                f"Moderation model failed to initialize at startup: {health.message}"
            )
        logger.info("Moderation model warmup completed at startup.")

    @app.get("/", response_model=GenericResponse[dict], tags=["Root"])
    def root():
        return GenericResponse[dict].success_response(
            message="FastAPI backend is running.",
            status_code=200,
            data={"docs": "/docs"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
