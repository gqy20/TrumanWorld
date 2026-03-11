from fastapi import APIRouter

from app.api.routes import agents, health, metrics, run_director, run_world, runs, system

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(metrics.router, tags=["observability"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(run_world.router, prefix="/runs", tags=["world"])
api_router.include_router(run_director.router, prefix="/runs", tags=["director"])
api_router.include_router(agents.router, prefix="/runs/{run_id}/agents", tags=["agents"])
