from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator
from collections.abc import Callable

from app.config import Settings
from app.demo import demo_snapshot
from app.host_metrics import HostMetricsResult, collect_host_metrics
from app.llama_client import LlamaClient
from app.metrics_parser import parse_prometheus_metrics
from app.models import (
    HealthState,
    HistoryResponse,
    HostTelemetry,
    InferenceMetrics,
    ServerStatus,
    Snapshot,
    SourceStatus,
    TelemetryEvent,
)
from app.nvml_client import GpuCollection, NvmlClient
from app.slots_parser import parse_slots_payload


LlamaClientFactory = Callable[[Settings], LlamaClient]
HostCollector = Callable[[str], HostMetricsResult]


class TelemetryCollector:
    def __init__(
        self,
        settings: Settings,
        llama_client_factory: LlamaClientFactory | None = None,
        nvml_client: NvmlClient | None = None,
        host_collector: HostCollector = collect_host_metrics,
    ) -> None:
        self.settings = settings
        self._llama_client_factory = llama_client_factory or LlamaClient
        self._nvml_client = nvml_client or NvmlClient()
        self._host_collector = host_collector
        self._snapshot = self._build_initial_snapshot()
        self._events: list[TelemetryEvent] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

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

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._poll_forever())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def poll_once(self) -> Snapshot:
        if self.settings.llama_metrics_demo:
            snapshot = demo_snapshot(self.settings)
        else:
            snapshot = await self._poll_real_sources()

        async with self._lock:
            self._snapshot = snapshot
        return snapshot

    def health_status(self) -> HealthState:
        return self._snapshot.status

    def history(self, window: str) -> HistoryResponse:
        return HistoryResponse(window=window, snapshots=[self._snapshot])

    def events(self) -> list[TelemetryEvent]:
        return list(self._events)

    async def stream(self) -> AsyncIterator[Snapshot]:
        while True:
            async with self._lock:
                snapshot = self._snapshot
            yield snapshot
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def _poll_forever(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def _poll_real_sources(self) -> Snapshot:
        now = datetime.now(timezone.utc)
        llama_client = self._llama_client_factory(self.settings)
        try:
            health_response, metrics_response, slots_response = await asyncio.gather(
                llama_client.health(),
                llama_client.metrics(),
                llama_client.slots(),
            )
        finally:
            await llama_client.aclose()

        metrics_status = _source_from_response(metrics_response.ok, metrics_response.error, now)
        slots_status = _source_from_response(slots_response.ok, slots_response.error, now)

        inference = InferenceMetrics()
        unknown_metrics = []
        if metrics_response.ok and metrics_response.text is not None:
            parsed_metrics = parse_prometheus_metrics(metrics_response.text)
            inference = parsed_metrics.inference
            unknown_metrics = parsed_metrics.unknown_metrics
            if parsed_metrics.errors:
                metrics_status.error = "; ".join(parsed_metrics.errors[:3])

        slots = []
        if slots_response.ok:
            if slots_response.json_data is None:
                slots_status.available = False
                slots_status.error = "invalid or missing JSON"
            else:
                slots = parse_slots_payload(
                    slots_response.json_data,
                    inference.generation_tokens_per_second,
                )

        host_result = self._host_collector(self.settings.llama_base_url)
        host_status = SourceStatus(
            available=host_result.telemetry.available,
            error=host_result.telemetry.error,
            last_success_at=now if host_result.telemetry.available else None,
        )
        gpu_result = self._nvml_client.collect(host_result.llama_pid)
        if gpu_result.status.available:
            gpu_result.status.last_success_at = now

        server_online = health_response.ok or metrics_response.ok or slots_response.ok
        status = _overall_status(
            online=server_online,
            inference=inference,
            metrics_status=metrics_status,
            slots_status=slots_status,
            gpu_status=gpu_result.status,
            host_status=host_status,
        )

        server = ServerStatus(
            online=server_online,
            status=status,
            base_url=self.settings.llama_base_url,
            last_success_at=now if server_online else None,
            pid=host_result.llama_pid,
            uptime_seconds=host_result.telemetry.llama_server_uptime_seconds,
            metrics=metrics_status,
            slots=slots_status,
        )

        return Snapshot(
            timestamp=now,
            status=status,
            server=server,
            inference=inference,
            slots=slots,
            gpus=gpu_result.gpus,
            host=host_result.telemetry,
            sources={
                "metrics": metrics_status,
                "slots": slots_status,
                "gpu": gpu_result.status,
                "host": host_status,
            },
            unknown_metrics=unknown_metrics,
        )


def _source_from_response(ok: bool, error: str | None, now: datetime) -> SourceStatus:
    return SourceStatus(
        available=ok,
        error=None if ok else error or "unavailable",
        last_success_at=now if ok else None,
    )


def _overall_status(
    online: bool,
    inference: InferenceMetrics,
    metrics_status: SourceStatus,
    slots_status: SourceStatus,
    gpu_status: SourceStatus,
    host_status: SourceStatus,
) -> HealthState:
    if not online:
        return "offline"
    if not (
        metrics_status.available
        and slots_status.available
        and gpu_status.available
        and host_status.available
    ):
        return "degraded"
    if inference.active_requests <= 0:
        return "idle"
    return "healthy"
