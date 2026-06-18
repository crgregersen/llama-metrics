from __future__ import annotations

from pathlib import Path

import app.config as config_module
from app.config import Settings


def test_public_dict_does_not_include_api_key() -> None:
    settings = Settings(llama_api_key="top-secret")

    public = settings.public_dict()

    assert public["llama_api_key_configured"] is True
    assert "llama_api_key" not in public
    assert "top-secret" not in str(public)


def test_settings_loads_home_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home_config = tmp_path / "home" / ".llama-metrics" / ".env"
    home_config.parent.mkdir(parents=True)
    home_config.write_text("LLAMA_BASE_URL=http://home.example:8080\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_FILE", home_config)
    monkeypatch.delenv("LLAMA_BASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.llama_base_url == "http://home.example:8080"
    assert settings.config_file == str(home_config)


def test_local_config_overrides_home_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home_config = tmp_path / "home" / ".llama-metrics" / ".env"
    home_config.parent.mkdir(parents=True)
    home_config.write_text("LLAMA_BASE_URL=http://home.example:8080\n")
    local_config = tmp_path / ".env"
    local_config.write_text("LLAMA_BASE_URL=http://local.example:8080\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_FILE", home_config)
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_FILE", local_config)
    monkeypatch.delenv("LLAMA_BASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.llama_base_url == "http://local.example:8080"
    assert settings.config_file == str(local_config)


def test_shell_environment_overrides_config_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home_config = tmp_path / "home" / ".llama-metrics" / ".env"
    home_config.parent.mkdir(parents=True)
    home_config.write_text("LLAMA_BASE_URL=http://home.example:8080\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_FILE", home_config)
    monkeypatch.setenv("LLAMA_BASE_URL", "http://env.example:8080")

    settings = Settings.from_env()

    assert settings.llama_base_url == "http://env.example:8080"
