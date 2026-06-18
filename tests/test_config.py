from __future__ import annotations

from app.config import Settings


def test_public_dict_does_not_include_api_key() -> None:
    settings = Settings(llama_api_key="top-secret")

    public = settings.public_dict()

    assert public["llama_api_key_configured"] is True
    assert "llama_api_key" not in public
    assert "top-secret" not in str(public)
