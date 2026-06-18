from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.llama_client import LlamaClient


@pytest.mark.anyio
async def test_client_sends_bearer_auth_and_metrics_model() -> None:
    seen_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, text="llamacpp:requests_processing 1")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as httpx_client:
        client = LlamaClient(
            Settings(
                llama_base_url="http://llama.test",
                llama_api_key="secret",
                llama_metrics_model="main-model",
            ),
            client=httpx_client,
        )
        response = await client.metrics()

    assert response.ok is True
    request = seen_requests[0]
    assert request.headers["Authorization"] == "Bearer secret"
    assert str(request.url) == "http://llama.test/metrics?model=main-model"
    assert "secret" not in repr(response)


@pytest.mark.anyio
async def test_client_fetches_slots_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as httpx_client:
        client = LlamaClient(Settings(llama_base_url="http://llama.test"), httpx_client)
        response = await client.slots()

    assert response.ok is True
    assert response.json_data == [{"id": 1}]
