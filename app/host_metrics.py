from __future__ import annotations

from dataclasses import dataclass
import os
import socket
import time
from urllib.parse import urlparse

import psutil

from app.models import HostTelemetry


@dataclass(frozen=True)
class HostMetricsResult:
    telemetry: HostTelemetry
    llama_pid: int | None = None


def collect_host_metrics(llama_base_url: str) -> HostMetricsResult:
    try:
        memory = psutil.virtual_memory()
        telemetry = HostTelemetry(
            available=True,
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_used_bytes=int(memory.used),
            memory_available_bytes=int(memory.available),
            memory_total_bytes=int(memory.total),
            load_average=list(os.getloadavg()) if hasattr(os, "getloadavg") else [],
            uptime_seconds=max(0.0, time.time() - psutil.boot_time()),
        )
    except Exception as exc:
        return HostMetricsResult(
            telemetry=HostTelemetry(available=False, error=exc.__class__.__name__)
        )

    pid = find_llama_server_pid(llama_base_url)
    if pid is None:
        return HostMetricsResult(telemetry=telemetry)

    try:
        process = psutil.Process(pid)
        telemetry.llama_server_cpu_percent = process.cpu_percent(interval=None)
        telemetry.llama_server_rss_bytes = int(process.memory_info().rss)
        telemetry.llama_server_uptime_seconds = max(0.0, time.time() - process.create_time())
    except (psutil.Error, OSError) as exc:
        telemetry.error = exc.__class__.__name__

    return HostMetricsResult(telemetry=telemetry, llama_pid=pid)


def find_llama_server_pid(llama_base_url: str) -> int | None:
    parsed = urlparse(llama_base_url)
    host = parsed.hostname
    port = parsed.port
    if host and not _is_local_host(host):
        return None

    by_port = _find_process_by_port(port) if port else None
    if by_port is not None:
        return by_port

    return _find_process_by_name()


def _is_local_host(host: str) -> bool:
    host = host.lower()
    local_names = {"localhost", "127.0.0.1", "::1", socket.gethostname().lower()}
    try:
        local_names.add(socket.getfqdn().lower())
    except OSError:
        pass
    return host in local_names


def _find_process_by_port(port: int | None) -> int | None:
    if port is None:
        return None
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            for connection in process.net_connections(kind="inet"):
                if connection.status != psutil.CONN_LISTEN:
                    continue
                if connection.laddr and connection.laddr.port == port:
                    return int(process.info["pid"])
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return None


def _find_process_by_name() -> int | None:
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info.get("name") or "").lower()
            cmdline = " ".join(process.info.get("cmdline") or []).lower()
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        if "llama-server" in name or "llama-server" in cmdline:
            return int(process.info["pid"])
    return None
