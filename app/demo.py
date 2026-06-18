from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from app.config import Settings
from app.models import (
    GpuTelemetry,
    HostTelemetry,
    InferenceMetrics,
    ServerStatus,
    SlotState,
    Snapshot,
    SourceStatus,
)


def demo_snapshot(settings: Settings) -> Snapshot:
    now = datetime.now(timezone.utc)
    tick = time.time()
    wave = (math.sin(tick / 8.0) + 1.0) / 2.0
    active = 1 if int(tick / 25) % 2 == 0 else 0
    queued = 1 if int(tick / 40) % 3 == 1 else 0
    prompt_tps = round(900 + wave * 850, 2) if active else 0.0
    generation_tps = round(18 + wave * 18, 2) if active else 0.0
    generated = int(1200 + wave * 3200) if active else 0
    remaining = int(9000 - wave * 3200) if active else 0
    output_limit = generated + remaining if active else None

    source_ok = SourceStatus(available=True, last_success_at=now)
    inference = InferenceMetrics(
        prompt_tokens_per_second=prompt_tps,
        generation_tokens_per_second=generation_tps,
        active_requests=active,
        deferred_requests=queued,
        largest_observed_context_tokens=65536,
        inferred_phase="queueing" if queued else ("decode" if active else "idle"),
    )

    return Snapshot(
        timestamp=now,
        status="healthy" if active else "idle",
        server=ServerStatus(
            online=True,
            status="healthy" if active else "idle",
            base_url=settings.llama_base_url,
            last_success_at=now,
            pid=4242,
            uptime_seconds=7200 + int(tick % 1200),
            metrics=source_ok,
            slots=source_ok,
        ),
        inference=inference,
        slots=[
            SlotState(
                slot_id=0,
                task_id=1001 if active else None,
                is_processing=bool(active),
                n_ctx=131072,
                generated_tokens=generated if active else None,
                remaining_tokens=remaining if active else None,
                output_token_limit=output_limit,
                output_progress=(generated / output_limit) if output_limit else None,
                has_next_token=bool(active),
                estimated_seconds_remaining=(
                    remaining / generation_tps if generation_tps > 0 else None
                ),
                state="generating" if active else "idle",
            ),
            SlotState(slot_id=1, is_processing=False, n_ctx=131072, state="idle"),
        ],
        gpus=[
            _demo_gpu(0, "Demo RTX 6000 Ada", 48, wave, llama_bytes=18_500_000_000),
            _demo_gpu(1, "Demo RTX 4090", 24, 1 - wave, llama_bytes=8_200_000_000),
        ],
        host=HostTelemetry(
            available=True,
            cpu_percent=round(18 + wave * 32, 2),
            memory_used_bytes=42_000_000_000,
            memory_available_bytes=86_000_000_000,
            memory_total_bytes=128_000_000_000,
            load_average=[1.2, 1.4, 1.8],
            uptime_seconds=604800 + int(tick % 10000),
            llama_server_cpu_percent=round(22 + wave * 60, 2) if active else 1.0,
            llama_server_rss_bytes=7_500_000_000,
            llama_server_uptime_seconds=7200 + int(tick % 1200),
        ),
        sources={"metrics": source_ok, "slots": source_ok, "gpu": source_ok, "host": source_ok},
    )


def _demo_gpu(
    index: int,
    name: str,
    gb: int,
    wave: float,
    llama_bytes: int,
) -> GpuTelemetry:
    total = gb * 1024**3
    used = int(total * (0.35 + wave * 0.45))
    return GpuTelemetry(
        index=index,
        name=name,
        uuid=f"DEMO-GPU-{index}",
        utilization_percent=round(20 + wave * 78, 2),
        memory_utilization_percent=round(used / total * 100, 2),
        vram_used_bytes=used,
        vram_free_bytes=total - used,
        vram_total_bytes=total,
        temperature_c=round(42 + wave * 34, 2),
        power_draw_w=round(90 + wave * 260, 2),
        power_limit_w=450.0,
        graphics_clock_mhz=int(900 + wave * 1600),
        memory_clock_mhz=int(5000 + wave * 5500),
        fan_speed_percent=round(22 + wave * 58, 2),
        pcie_generation=4,
        pcie_link_width=16,
        pcie_rx_bytes_per_second=int((20 + wave * 90) * 1024 * 1024),
        pcie_tx_bytes_per_second=int((8 + wave * 32) * 1024 * 1024),
        encoder_utilization_percent=0.0,
        decoder_utilization_percent=0.0,
        throttle_reasons=[],
        llama_server_vram_bytes=llama_bytes,
    )
