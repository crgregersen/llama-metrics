from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


HealthState = Literal["healthy", "degraded", "offline", "idle", "unknown"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceStatus(BaseModel):
    available: bool = False
    stale: bool = False
    error: str | None = None
    last_success_at: datetime | None = None


class ServerStatus(BaseModel):
    online: bool = False
    status: HealthState = "unknown"
    base_url: str
    last_success_at: datetime | None = None
    pid: int | None = None
    uptime_seconds: float | None = None
    metrics: SourceStatus = Field(default_factory=SourceStatus)
    slots: SourceStatus = Field(default_factory=SourceStatus)


class InferenceMetrics(BaseModel):
    prompt_tokens_per_second: float | None = None
    generation_tokens_per_second: float | None = None
    active_requests: int = 0
    deferred_requests: int = 0
    largest_observed_context_tokens: int | None = None
    inferred_phase: str = "unknown"


class SlotState(BaseModel):
    slot_id: int | str | None = None
    task_id: int | str | None = None
    is_processing: bool = False
    n_ctx: int | None = None
    prompt_tokens: int | None = None
    prompt_tokens_processed: int | None = None
    prompt_tokens_cached: int | None = None
    context_used_tokens: int | None = None
    context_remaining_tokens: int | None = None
    context_usage_progress: float | None = None
    generated_tokens: int | None = None
    remaining_tokens: int | None = None
    output_token_limit: int | None = None
    output_progress: float | None = None
    has_next_token: bool | None = None
    estimated_seconds_remaining: float | None = None
    state: str = "idle"
    parse_error: str | None = None


class GpuProcess(BaseModel):
    pid: int
    name: str | None = None
    used_memory_bytes: int | None = None
    is_llama_server: bool = False


class GpuTelemetry(BaseModel):
    index: int
    name: str | None = None
    uuid: str | None = None
    available: bool = True
    error: str | None = None
    utilization_percent: float | None = None
    memory_utilization_percent: float | None = None
    vram_used_bytes: int | None = None
    vram_free_bytes: int | None = None
    vram_total_bytes: int | None = None
    temperature_c: float | None = None
    power_draw_w: float | None = None
    power_limit_w: float | None = None
    graphics_clock_mhz: int | None = None
    memory_clock_mhz: int | None = None
    fan_speed_percent: float | None = None
    pcie_generation: int | None = None
    pcie_link_width: int | None = None
    pcie_rx_bytes_per_second: int | None = None
    pcie_tx_bytes_per_second: int | None = None
    encoder_utilization_percent: float | None = None
    decoder_utilization_percent: float | None = None
    throttle_reasons: list[str] = Field(default_factory=list)
    llama_server_vram_bytes: int | None = None
    processes: list[GpuProcess] = Field(default_factory=list)


class HostTelemetry(BaseModel):
    available: bool = False
    error: str | None = None
    cpu_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_available_bytes: int | None = None
    memory_total_bytes: int | None = None
    load_average: list[float] = Field(default_factory=list)
    uptime_seconds: float | None = None
    llama_server_cpu_percent: float | None = None
    llama_server_rss_bytes: int | None = None
    llama_server_uptime_seconds: float | None = None


class MetricSample(BaseModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    value: float


class TelemetryEvent(BaseModel):
    id: int
    timestamp: datetime
    severity: Literal["info", "warning", "critical"] = "info"
    kind: str
    message: str
    data: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class Snapshot(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    status: HealthState = "unknown"
    server: ServerStatus
    inference: InferenceMetrics = Field(default_factory=InferenceMetrics)
    slots: list[SlotState] = Field(default_factory=list)
    gpus: list[GpuTelemetry] = Field(default_factory=list)
    host: HostTelemetry = Field(default_factory=HostTelemetry)
    sources: dict[str, SourceStatus] = Field(default_factory=dict)
    unknown_metrics: list[MetricSample] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    window: str
    snapshots: list[Snapshot] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: HealthState
    timestamp: datetime
    version: str
    config: dict[str, object]
