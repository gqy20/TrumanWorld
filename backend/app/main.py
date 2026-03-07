from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.infra.logging import get_logger, info
from app.infra.settings import get_settings

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    
    info(f"Starting AI Truman World API in {settings.app_env} mode")
    info(f"Log level: {settings.log_level}")
    info(f"CORS allowed origins: {settings.cors_allowed_origins}")
    
    app = FastAPI(
        title="AI Truman World API",
        version="0.1.0",
        description="MVP backend for the TrumanWorld simulation system.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.include_router(api_router, prefix=settings.api_prefix)
    
    info(f"API routes registered with prefix: {settings.api_prefix}")
    return app


app = create_app()
