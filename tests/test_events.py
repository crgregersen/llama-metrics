from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.events import EventEngine
from app.models import GpuTelemetry, InferenceMetrics, ServerStatus, Snapshot


def _snapshot(
    timestamp: datetime,
    *,
    online: bool = True,
    status: str = "healthy",
    active: int = 0,
    deferred: int = 0,
    phase: str = "idle",
    context: int | None = None,
    generation_tps: float | None = None,
    gpu: GpuTelemetry | None = None,
) -> Snapshot:
    return Snapshot(
        timestamp=timestamp,
        status=status,
        server=ServerStatus(
            online=online,
            status=status,
            base_url="http://llama.test",
        ),
        inference=InferenceMetrics(
            active_requests=active,
            deferred_requests=deferred,
            inferred_phase=phase,
            largest_observed_context_tokens=context,
            generation_tokens_per_second=generation_tps,
        ),
        gpus=[gpu] if gpu is not None else [],
    )


def test_events_emit_on_transition_only() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = EventEngine(Settings())

    first = _snapshot(start, active=0, phase="idle")
    second = _snapshot(start + timedelta(seconds=1), active=1, phase="decode")

    assert engine.update(first) == []
    emitted = engine.update(second)
    repeated = engine.update(second)

    kinds = {event.kind for event in emitted}
    assert "request_started" in kinds
    assert "decode_detected" in kinds
    assert repeated == []


def test_queue_and_offline_transitions_emit_once() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = EventEngine(Settings())

    engine.update(_snapshot(start, deferred=0))
    queued = engine.update(_snapshot(start + timedelta(seconds=1), deferred=2))
    offline = engine.update(
        _snapshot(
            start + timedelta(seconds=2),
            online=False,
            status="offline",
            deferred=2,
        )
    )

    assert [event.kind for event in queued] == ["queue_appeared"]
    assert [event.kind for event in offline] == ["server_offline"]


def test_gpu_threshold_events_emit_on_crossing_only() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = EventEngine(Settings(gpu_temperature_alert_c=80, gpu_vram_alert_percent=90))

    below = GpuTelemetry(index=0, temperature_c=70, memory_utilization_percent=50)
    above = GpuTelemetry(index=0, temperature_c=85, memory_utilization_percent=94)

    engine.update(_snapshot(start, gpu=below))
    emitted = engine.update(_snapshot(start + timedelta(seconds=1), gpu=above))
    repeated = engine.update(_snapshot(start + timedelta(seconds=2), gpu=above))

    assert {event.kind for event in emitted} == {
        "gpu_temperature_threshold",
        "gpu_vram_threshold",
    }
    assert repeated == []


def test_generation_throughput_drop_emits_once_until_recovered() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = EventEngine(Settings(generation_throughput_drop_percent=40))

    engine.update(_snapshot(start, generation_tps=100))
    dropped = engine.update(_snapshot(start + timedelta(seconds=1), generation_tps=50))
    repeated = engine.update(_snapshot(start + timedelta(seconds=2), generation_tps=25))
    recovered = engine.update(_snapshot(start + timedelta(seconds=3), generation_tps=80))
    dropped_again = engine.update(_snapshot(start + timedelta(seconds=4), generation_tps=40))

    assert [event.kind for event in dropped] == ["generation_throughput_drop"]
    assert repeated == []
    assert recovered == []
    assert [event.kind for event in dropped_again] == ["generation_throughput_drop"]
