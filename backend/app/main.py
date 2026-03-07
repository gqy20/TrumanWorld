from fastapi import FastAPI

from app.api.router import api_router
from app.infra.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Truman World API",
        version="0.1.0",
        description="MVP backend for the TrumanWorld simulation system.",
    )
    app.state.settings = settings
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()

