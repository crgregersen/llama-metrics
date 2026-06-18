from __future__ import annotations

from dataclasses import dataclass

import psutil

from app.models import GpuProcess, GpuTelemetry, SourceStatus

try:
    import pynvml
except Exception:  # pragma: no cover - depends on host installation
    pynvml = None


@dataclass(frozen=True)
class GpuCollection:
    gpus: list[GpuTelemetry]
    status: SourceStatus


class NvmlClient:
    def collect(self, llama_pid: int | None = None) -> GpuCollection:
        if pynvml is None:
            return GpuCollection(
                gpus=[],
                status=SourceStatus(available=False, error="pynvml unavailable"),
            )

        try:
            pynvml.nvmlInit()
            count = int(pynvml.nvmlDeviceGetCount())
        except Exception as exc:
            return GpuCollection(
                gpus=[],
                status=SourceStatus(available=False, error=exc.__class__.__name__),
            )

        gpus: list[GpuTelemetry] = []
        errors: list[str] = []
        for index in range(count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                gpus.append(_collect_gpu(index, handle, llama_pid))
            except Exception as exc:
                errors.append(f"gpu {index}: {exc.__class__.__name__}")
                gpus.append(
                    GpuTelemetry(
                        index=index,
                        available=False,
                        error=exc.__class__.__name__,
                    )
                )

        return GpuCollection(
            gpus=gpus,
            status=SourceStatus(
                available=bool(gpus) and not errors,
                error="; ".join(errors) if errors else None,
            ),
        )


def _collect_gpu(index: int, handle, llama_pid: int | None) -> GpuTelemetry:
    memory = _safe(lambda: pynvml.nvmlDeviceGetMemoryInfo(handle))
    utilization = _safe(lambda: pynvml.nvmlDeviceGetUtilizationRates(handle))
    processes = _collect_processes(handle, llama_pid)

    return GpuTelemetry(
        index=index,
        name=_decode(_safe(lambda: pynvml.nvmlDeviceGetName(handle))),
        uuid=_decode(_safe(lambda: pynvml.nvmlDeviceGetUUID(handle))),
        utilization_percent=_getattr_number(utilization, "gpu"),
        memory_utilization_percent=_getattr_number(utilization, "memory"),
        vram_used_bytes=_getattr_int(memory, "used"),
        vram_free_bytes=_getattr_int(memory, "free"),
        vram_total_bytes=_getattr_int(memory, "total"),
        temperature_c=_safe(
            lambda: float(
                pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            )
        ),
        power_draw_w=_milliwatts_to_watts(
            _safe(lambda: pynvml.nvmlDeviceGetPowerUsage(handle))
        ),
        power_limit_w=_milliwatts_to_watts(_power_limit(handle)),
        graphics_clock_mhz=_safe(
            lambda: int(
                pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
            )
        ),
        memory_clock_mhz=_safe(
            lambda: int(pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM))
        ),
        fan_speed_percent=_safe(lambda: float(pynvml.nvmlDeviceGetFanSpeed(handle))),
        pcie_generation=_safe(lambda: int(pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle))),
        pcie_link_width=_safe(lambda: int(pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle))),
        pcie_rx_bytes_per_second=_pcie_throughput(
            handle,
            getattr(pynvml, "NVML_PCIE_UTIL_RX_BYTES", None),
        ),
        pcie_tx_bytes_per_second=_pcie_throughput(
            handle,
            getattr(pynvml, "NVML_PCIE_UTIL_TX_BYTES", None),
        ),
        encoder_utilization_percent=_util_tuple_first(
            _safe(lambda: pynvml.nvmlDeviceGetEncoderUtilization(handle))
        ),
        decoder_utilization_percent=_util_tuple_first(
            _safe(lambda: pynvml.nvmlDeviceGetDecoderUtilization(handle))
        ),
        throttle_reasons=_throttle_reasons(handle),
        llama_server_vram_bytes=sum(
            process.used_memory_bytes or 0
            for process in processes
            if process.is_llama_server
        )
        or None,
        processes=processes,
    )


def _safe(callback, default=None):
    try:
        value = callback()
    except Exception:
        return default
    return value if value is not None else default


def _decode(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _getattr_number(value, name: str) -> float | None:
    if value is None:
        return None
    attr = getattr(value, name, None)
    return float(attr) if attr is not None else None


def _getattr_int(value, name: str) -> int | None:
    if value is None:
        return None
    attr = getattr(value, name, None)
    return int(attr) if attr is not None else None


def _milliwatts_to_watts(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 1000.0, 3)


def _power_limit(handle) -> int | None:
    return _safe(
        lambda: pynvml.nvmlDeviceGetEnforcedPowerLimit(handle),
        _safe(lambda: pynvml.nvmlDeviceGetPowerManagementLimit(handle)),
    )


def _pcie_throughput(handle, counter) -> int | None:
    if counter is None:
        return None
    kb_per_second = _safe(lambda: pynvml.nvmlDeviceGetPcieThroughput(handle, counter))
    if kb_per_second is None:
        return None
    return int(kb_per_second) * 1024


def _util_tuple_first(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, tuple) and value:
        return float(value[0])
    return None


def _throttle_reasons(handle) -> list[str]:
    reasons = _safe(lambda: pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle))
    if reasons is None:
        return []

    known = [
        ("gpu_idle", "NVML_CLOCKS_THROTTLE_REASON_GPU_IDLE"),
        ("application_clocks", "NVML_CLOCKS_THROTTLE_REASON_APPLICATIONS_CLOCKS_SETTING"),
        ("sw_power_cap", "NVML_CLOCKS_THROTTLE_REASON_SW_POWER_CAP"),
        ("hw_slowdown", "NVML_CLOCKS_THROTTLE_REASON_HW_SLOWDOWN"),
        ("sync_boost", "NVML_CLOCKS_THROTTLE_REASON_SYNC_BOOST"),
        ("sw_thermal", "NVML_CLOCKS_THROTTLE_REASON_SW_THERMAL_SLOWDOWN"),
        ("hw_thermal", "NVML_CLOCKS_THROTTLE_REASON_HW_THERMAL_SLOWDOWN"),
        ("hw_power_brake", "NVML_CLOCKS_THROTTLE_REASON_HW_POWER_BRAKE_SLOWDOWN"),
    ]
    return [
        label
        for label, constant_name in known
        if reasons & getattr(pynvml, constant_name, 0)
    ]


def _collect_processes(handle, llama_pid: int | None) -> list[GpuProcess]:
    by_pid: dict[int, int | None] = {}
    for getter_name in ("nvmlDeviceGetComputeRunningProcesses", "nvmlDeviceGetGraphicsRunningProcesses"):
        getter = getattr(pynvml, getter_name, None)
        if getter is None:
            continue
        for process in _safe(lambda getter=getter: getter(handle), []):
            pid = int(getattr(process, "pid"))
            used = getattr(process, "usedGpuMemory", None)
            if used is not None and used < 0:
                used = None
            current = by_pid.get(pid)
            by_pid[pid] = used if current is None else (current or 0) + (used or 0)

    return [
        GpuProcess(
            pid=pid,
            name=_process_name(pid),
            used_memory_bytes=used,
            is_llama_server=llama_pid is not None and pid == llama_pid,
        )
        for pid, used in sorted(by_pid.items())
    ]


def _process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name()
    except (psutil.Error, OSError):
        return None
