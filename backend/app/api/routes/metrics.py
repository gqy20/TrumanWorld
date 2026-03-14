from __future__ import annotations

from fastapi import APIRouter, Response

from app.infra.metrics import render_metrics

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus 指标",
    description="暴露进程与模拟运行指标，供 Prometheus 抓取。",
    responses={
        200: {"description": "Prometheus 文本指标（text/plain）"},
    },
    include_in_schema=False,
)
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
