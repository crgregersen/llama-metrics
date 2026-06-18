from __future__ import annotations

import pytest

from app.collector import TelemetryCollector
from app.config import Settings
from app.demo import demo_snapshot
from app.host_metrics import HostMetricsResult, find_llama_server_pid
from app.llama_client import UpstreamResponse
from app.models import GpuTelemetry, HostTelemetry, SourceStatus
from app.nvml_client import GpuCollection, NvmlClient


class FakeLlamaClient:
    def __init__(
        self,
        health: UpstreamResponse,
        metrics: UpstreamResponse,
        slots: UpstreamResponse,
    ) -> None:
        self._health = health
        self._metrics = metrics
        self._slots = slots

    async def health(self) -> UpstreamResponse:
        return self._health

    async def metrics(self) -> UpstreamResponse:
        return self._metrics

    async def slots(self) -> UpstreamResponse:
        return self._slots

    async def aclose(self) -> None:
        return None


class FakeNvmlClient:
    def __init__(self, result: GpuCollection) -> None:
        self._result = result

    def collect(self, llama_pid: int | None = None) -> GpuCollection:
        return self._result


def test_demo_snapshot_has_multi_gpu_data() -> None:
    snapshot = demo_snapshot(Settings(llama_metrics_demo=True))

    assert snapshot.server.online is True
    assert len(snapshot.gpus) == 2
    assert all(gpu.name and gpu.vram_total_bytes for gpu in snapshot.gpus)
    assert snapshot.sources["gpu"].available is True


@pytest.mark.anyio
async def test_collector_reports_offline_without_real_network() -> None:
    collector = TelemetryCollector(
        Settings(),
        llama_client_factory=lambda _: FakeLlamaClient(
            UpstreamResponse(ok=False, error="ConnectError"),
            UpstreamResponse(ok=False, error="ConnectError"),
            UpstreamResponse(ok=False, error="ConnectError"),
        ),
        nvml_client=FakeNvmlClient(
            GpuCollection([], SourceStatus(available=False, error="NVML unavailable"))
        ),
        host_collector=lambda _: HostMetricsResult(
            telemetry=HostTelemetry(available=True)
        ),
    )

    snapshot = await collector.poll_once()

    assert snapshot.status == "offline"
    assert snapshot.server.online is False
    assert snapshot.sources["metrics"].error == "ConnectError"


@pytest.mark.anyio
async def test_collector_integrates_metrics_slots_host_and_gpus() -> None:
    collector = TelemetryCollector(
        Settings(),
        llama_client_factory=lambda _: FakeLlamaClient(
            UpstreamResponse(ok=True, status_code=200, json_data={"status": "ok"}),
            UpstreamResponse(
                ok=True,
                status_code=200,
                text="""
                llamacpp:requests_processing 1
                llamacpp:requests_deferred 0
                llamacpp:predicted_tokens_seconds 25
                """,
            ),
            UpstreamResponse(
                ok=True,
                status_code=200,
                json_data=[
                    {
                        "id": 0,
                        "is_processing": True,
                        "next_token": {"n_decoded": 10, "n_remain": 90},
                    }
                ],
            ),
        ),
        nvml_client=FakeNvmlClient(
            GpuCollection(
                [GpuTelemetry(index=0, name="GPU 0")],
                SourceStatus(available=True),
            )
        ),
        host_collector=lambda _: HostMetricsResult(
            telemetry=HostTelemetry(available=True),
            llama_pid=1234,
        ),
    )

    snapshot = await collector.poll_once()

    assert snapshot.status == "healthy"
    assert snapshot.server.pid == 1234
    assert snapshot.inference.active_requests == 1
    assert snapshot.slots[0].output_token_limit == 100
    assert snapshot.gpus[0].name == "GPU 0"


def test_nvml_unavailable_degrades_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.nvml_client.pynvml", None)

    result = NvmlClient().collect()

    assert result.gpus == []
    assert result.status.available is False
    assert result.status.error == "pynvml unavailable"


def test_remote_llama_url_does_not_attempt_local_pid_detection() -> None:
    assert find_llama_server_pid("http://example.com:8080") is None
