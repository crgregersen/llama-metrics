from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.collector import TelemetryCollector
from app.config import Settings
from app.models import HealthResponse


router = APIRouter()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _collector(request: Request) -> TelemetryCollector:
    return request.app.state.collector


@router.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    collector = _collector(request)
    settings = _settings(request)
    return HealthResponse(
        status=collector.health_status(),
        timestamp=collector.snapshot.timestamp,
        version=request.app.state.version,
        config=settings.public_dict(),
    )


@router.get("/api/snapshot")
async def snapshot(request: Request):
    return _collector(request).snapshot


@router.get("/api/history")
async def history(request: Request, window: str = "5m"):
    return _collector(request).history(window)


@router.get("/api/events")
async def events(request: Request):
    return {"events": _collector(request).events()}


@router.get("/api/stream")
async def stream(request: Request):
    collector = _collector(request)

    async def event_source():
        async for item in collector.stream():
            if await request.is_disconnected():
                break
            payload = item.model_dump(mode="json")
            yield f"event: snapshot\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
