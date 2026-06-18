from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import ServerStatus, Snapshot


def make_client(settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings or Settings()))


def test_health_redacts_api_key() -> None:
    client = make_client(Settings(llama_api_key="secret-token"))
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["llama_api_key_configured"] is True
    assert "secret-token" not in response.text


def test_snapshot_returns_degraded_shell() -> None:
    client = make_client()
    response = client.get("/api/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["server"]["base_url"] == "http://127.0.0.1:8080"
    assert body["slots"] == []
    assert body["gpus"] == []


def test_history_returns_current_snapshot() -> None:
    client = make_client()
    response = client.get("/api/history?window=5m")

    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "5m"
    assert len(body["snapshots"]) == 1


def test_events_returns_list() -> None:
    client = make_client()
    response = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_stream_emits_snapshot_event() -> None:
    app = create_app(Settings())

    class FiniteCollector:
        async def stream(self):
            yield Snapshot(server=ServerStatus(base_url="http://llama.test"))

    app.state.collector = FiniteCollector()
    client = TestClient(app)

    response = client.get("/api/stream")

    assert response.status_code == 200
    assert "event: snapshot" in response.text
    data_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    assert data_line.startswith("data: ")
    assert "llama_api_key" not in data_line


def test_root_serves_dashboard() -> None:
    client = make_client()
    response = client.get("/")

    assert response.status_code == 200
    assert "LlamaMetrics" in response.text
    assert "/static/app.js" in response.text


def test_no_forbidden_public_endpoints() -> None:
    client = make_client()

    assert client.post("/api/chat").status_code == 404
    assert client.post("/api/proxy").status_code == 404
    assert client.post("/api/models").status_code == 404
