from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


@dataclass(frozen=True)
class UpstreamResponse:
    ok: bool
    status_code: int | None = None
    text: str | None = None
    json_data: Any = None
    error: str | None = None


class LlamaClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.settings = settings
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def health(self) -> UpstreamResponse:
        return await self._request("GET", "/health")

    async def metrics(self) -> UpstreamResponse:
        params = {}
        if self.settings.llama_metrics_model:
            params["model"] = self.settings.llama_metrics_model
        return await self._request("GET", "/metrics", params=params)

    async def slots(self) -> UpstreamResponse:
        return await self._request("GET", "/slots")

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> UpstreamResponse:
        url = f"{self.settings.llama_base_url.rstrip('/')}{path}"
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._headers(),
                params=params or None,
            )
        except httpx.HTTPError as exc:
            return UpstreamResponse(ok=False, error=exc.__class__.__name__)

        json_data = None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                json_data = response.json()
            except ValueError:
                json_data = None

        return UpstreamResponse(
            ok=200 <= response.status_code < 300,
            status_code=response.status_code,
            text=response.text,
            json_data=json_data,
            error=None if 200 <= response.status_code < 300 else response.reason_phrase,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, text/plain;q=0.9, */*;q=0.1"}
        if self.settings.llama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llama_api_key}"
        return headers
