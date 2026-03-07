from fastapi import APIRouter

from app.api.routes import agents, health, runs

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(agents.router, prefix="/runs/{run_id}/agents", tags=["agents"])
