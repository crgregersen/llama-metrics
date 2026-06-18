from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

from app.config import Settings
from app.models import (
    HealthState,
    HistoryResponse,
    ServerStatus,
    Snapshot,
    SourceStatus,
    TelemetryEvent,
)


class TelemetryCollector:
    """Phase 1 collector shell that returns valid degraded snapshots."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._snapshot = self._build_initial_snapshot()
        self._events: list[TelemetryEvent] = []

    def _build_initial_snapshot(self) -> Snapshot:
        now = datetime.now(timezone.utc)
        metrics_status = SourceStatus(
            available=False,
            error="collector not initialized",
        )
        slots_status = SourceStatus(
            available=False,
            error="collector not initialized",
        )
        server = ServerStatus(
            online=False,
            status="degraded",
            base_url=self.settings.llama_base_url,
            last_success_at=None,
            metrics=metrics_status,
            slots=slots_status,
        )
        return Snapshot(
            timestamp=now,
            status="degraded",
            server=server,
            sources={"metrics": metrics_status, "slots": slots_status},
        )

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def health_status(self) -> HealthState:
        return self._snapshot.status

    def history(self, window: str) -> HistoryResponse:
        return HistoryResponse(window=window, snapshots=[self._snapshot])

    def events(self) -> list[TelemetryEvent]:
        return list(self._events)

    async def stream(self) -> AsyncIterator[Snapshot]:
        while True:
            yield self._snapshot.model_copy(update={"timestamp": datetime.now(timezone.utc)})
            await asyncio.sleep(self.settings.poll_interval_seconds)
