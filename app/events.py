from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.models import GpuTelemetry, Snapshot, TelemetryEvent


class EventEngine:
    def __init__(self, settings: Settings, max_events: int = 500) -> None:
        self.settings = settings
        self.max_events = max_events
        self._previous: Snapshot | None = None
        self._events: list[TelemetryEvent] = []
        self._next_id = 1
        self._throughput_drop_active = False

    def update(self, snapshot: Snapshot) -> list[TelemetryEvent]:
        if self._previous is None:
            self._previous = snapshot
            return []

        previous = self._previous
        emitted: list[TelemetryEvent] = []
        emitted.extend(self._server_events(previous, snapshot))
        emitted.extend(self._request_events(previous, snapshot))
        emitted.extend(self._phase_events(previous, snapshot))
        emitted.extend(self._context_events(previous, snapshot))
        emitted.extend(self._gpu_threshold_events(previous, snapshot))
        emitted.extend(self._throughput_events(previous, snapshot))

        for event in emitted:
            self._events.append(event)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events :]

        self._previous = snapshot
        return emitted

    def events(self) -> list[TelemetryEvent]:
        return list(self._events)

    def _event(
        self,
        snapshot: Snapshot,
        kind: str,
        message: str,
        severity: str = "info",
        data: dict[str, str | int | float | bool | None] | None = None,
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            id=self._next_id,
            timestamp=snapshot.timestamp or datetime.now(timezone.utc),
            severity=severity,
            kind=kind,
            message=message,
            data=data or {},
        )
        self._next_id += 1
        return event

    def _server_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        if previous.server.online != current.server.online:
            if current.server.online:
                events.append(
                    self._event(current, "server_online", "llama-server became reachable")
                )
            else:
                events.append(
                    self._event(
                        current,
                        "server_offline",
                        "llama-server became unreachable",
                        "critical",
                    )
                )

        if previous.status != "degraded" and current.status == "degraded":
            events.append(self._event(current, "degraded", "Telemetry became degraded", "warning"))
        elif previous.status == "degraded" and current.status != "degraded":
            events.append(self._event(current, "recovered", "Telemetry recovered"))

        return events

    def _request_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        previous_active = previous.inference.active_requests > 0
        current_active = current.inference.active_requests > 0
        if not previous_active and current_active:
            events.append(self._event(current, "request_started", "Request started"))
        elif previous_active and not current_active:
            events.append(self._event(current, "request_completed", "Request completed"))

        previous_queue = previous.inference.deferred_requests > 0
        current_queue = current.inference.deferred_requests > 0
        if not previous_queue and current_queue:
            events.append(
                self._event(current, "queue_appeared", "Queued requests appeared", "warning")
            )
        elif previous_queue and not current_queue:
            events.append(self._event(current, "queue_cleared", "Queued requests cleared"))

        return events

    def _phase_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        phase = current.inference.inferred_phase
        if phase == previous.inference.inferred_phase:
            return []
        if phase == "prefill":
            return [self._event(current, "prefill_detected", "Prefill detected")]
        if phase == "decode":
            return [self._event(current, "decode_detected", "Decode detected")]
        return []

    def _context_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        before = previous.inference.largest_observed_context_tokens or 0
        after = current.inference.largest_observed_context_tokens or 0
        if after > before:
            return [
                self._event(
                    current,
                    "context_high_water_increased",
                    "Context high-water mark increased",
                    data={"tokens": after},
                )
            ]
        return []

    def _gpu_threshold_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        previous_by_index = {gpu.index: gpu for gpu in previous.gpus}

        for gpu in current.gpus:
            previous_gpu = previous_by_index.get(gpu.index)
            if _crossed(
                _temperature(previous_gpu),
                _temperature(gpu),
                self.settings.gpu_temperature_alert_c,
            ):
                events.append(
                    self._event(
                        current,
                        "gpu_temperature_threshold",
                        f"GPU {gpu.index} temperature threshold crossed",
                        "warning",
                        {"gpu_index": gpu.index, "temperature_c": gpu.temperature_c},
                    )
                )

            if _crossed(
                _vram_percent(previous_gpu),
                _vram_percent(gpu),
                self.settings.gpu_vram_alert_percent,
            ):
                events.append(
                    self._event(
                        current,
                        "gpu_vram_threshold",
                        f"GPU {gpu.index} VRAM threshold crossed",
                        "warning",
                        {"gpu_index": gpu.index, "vram_percent": _vram_percent(gpu)},
                    )
                )
        return events

    def _throughput_events(self, previous: Snapshot, current: Snapshot) -> list[TelemetryEvent]:
        previous_tps = previous.inference.generation_tokens_per_second
        current_tps = current.inference.generation_tokens_per_second
        if previous_tps is None or current_tps is None or previous_tps <= 0:
            self._throughput_drop_active = False
            return []

        threshold = previous_tps * (
            1 - self.settings.generation_throughput_drop_percent / 100
        )
        dropped = current_tps < threshold
        if dropped and not self._throughput_drop_active:
            self._throughput_drop_active = True
            return [
                self._event(
                    current,
                    "generation_throughput_drop",
                    "Generation throughput dropped materially",
                    "warning",
                    {"previous_tps": previous_tps, "current_tps": current_tps},
                )
            ]
        if not dropped:
            self._throughput_drop_active = False
        return []


def _temperature(gpu: GpuTelemetry | None) -> float | None:
    return gpu.temperature_c if gpu is not None else None


def _vram_percent(gpu: GpuTelemetry | None) -> float | None:
    if gpu is None:
        return None
    if gpu.memory_utilization_percent is not None:
        return gpu.memory_utilization_percent
    if not gpu.vram_total_bytes or gpu.vram_used_bytes is None:
        return None
    return gpu.vram_used_bytes / gpu.vram_total_bytes * 100


def _crossed(previous: float | None, current: float | None, threshold: float) -> bool:
    if current is None:
        return False
    if previous is None:
        return current >= threshold
    return previous < threshold <= current
