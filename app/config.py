from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


DEFAULT_CONFIG_DIR = Path.home() / ".llama-metrics"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".env"
LOCAL_CONFIG_FILE = Path(".env")


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_from_mapping(values: dict[str, str], name: str, default: float) -> float:
    value = values.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_from_mapping(values: dict[str, str], name: str, default: int) -> int:
    value = values.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    llama_base_url: str = "http://127.0.0.1:8080"
    llama_api_key: str = ""
    llama_metrics_model: str = ""
    llama_metrics_demo: bool = False
    observer_host: str = "0.0.0.0"
    observer_port: int = 7778
    poll_interval_seconds: float = 1.0
    history_retention_minutes: int = 30
    gpu_temperature_alert_c: float = 85.0
    gpu_vram_alert_percent: float = 90.0
    generation_throughput_drop_percent: float = 40.0
    generation_throughput_drop_window_seconds: int = 30
    config_file: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        config_file, values = load_config_values()
        return cls(
            llama_base_url=values.get("LLAMA_BASE_URL", cls.llama_base_url).rstrip("/"),
            llama_api_key=values.get("LLAMA_API_KEY", ""),
            llama_metrics_model=values.get("LLAMA_METRICS_MODEL", ""),
            llama_metrics_demo=_bool_from_env(values.get("LLAMA_METRICS_DEMO"), False),
            observer_host=values.get("OBSERVER_HOST", cls.observer_host),
            observer_port=_int_from_mapping(values, "OBSERVER_PORT", cls.observer_port),
            poll_interval_seconds=max(
                0.25,
                _float_from_mapping(
                    values,
                    "POLL_INTERVAL_SECONDS",
                    cls.poll_interval_seconds,
                ),
            ),
            history_retention_minutes=max(
                1,
                _int_from_mapping(
                    values,
                    "HISTORY_RETENTION_MINUTES", cls.history_retention_minutes
                ),
            ),
            gpu_temperature_alert_c=_float_from_mapping(
                values,
                "GPU_TEMPERATURE_ALERT_C",
                cls.gpu_temperature_alert_c,
            ),
            gpu_vram_alert_percent=_float_from_mapping(
                values,
                "GPU_VRAM_ALERT_PERCENT",
                cls.gpu_vram_alert_percent,
            ),
            generation_throughput_drop_percent=_float_from_mapping(
                values,
                "GENERATION_THROUGHPUT_DROP_PERCENT",
                cls.generation_throughput_drop_percent,
            ),
            generation_throughput_drop_window_seconds=max(
                1,
                _int_from_mapping(
                    values,
                    "GENERATION_THROUGHPUT_DROP_WINDOW_SECONDS",
                    cls.generation_throughput_drop_window_seconds,
                ),
            ),
            config_file=str(config_file) if config_file else None,
        )

    @property
    def has_llama_api_key(self) -> bool:
        return bool(self.llama_api_key)

    def public_dict(self) -> dict[str, Any]:
        return {
            "llama_base_url": self.llama_base_url,
            "llama_metrics_model": self.llama_metrics_model or None,
            "llama_metrics_demo": self.llama_metrics_demo,
            "observer_host": self.observer_host,
            "observer_port": self.observer_port,
            "poll_interval_seconds": self.poll_interval_seconds,
            "history_retention_minutes": self.history_retention_minutes,
            "gpu_temperature_alert_c": self.gpu_temperature_alert_c,
            "gpu_vram_alert_percent": self.gpu_vram_alert_percent,
            "generation_throughput_drop_percent": (
                self.generation_throughput_drop_percent
            ),
            "generation_throughput_drop_window_seconds": (
                self.generation_throughput_drop_window_seconds
            ),
            "llama_api_key_configured": self.has_llama_api_key,
            "config_file": self.config_file,
        }


def get_settings() -> Settings:
    return Settings.from_env()


def load_config_values() -> tuple[Path | None, dict[str, str]]:
    values: dict[str, str] = {}
    loaded: Path | None = None
    for path in (DEFAULT_CONFIG_FILE, LOCAL_CONFIG_FILE):
        if path.exists():
            for key, value in dotenv_values(path).items():
                if value is not None:
                    values[key] = value
            loaded = path
    values.update(os.environ)
    return loaded, values
