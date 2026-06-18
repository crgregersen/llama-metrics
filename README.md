# LlamaMetrics

LlamaMetrics is a planned lightweight web dashboard for monitoring an existing
`llama.cpp` / `llama-server` inference service.

The project is currently at the specification stage. See
[llama-metrics-specification.md](./llama-metrics-specification.md) for the full
project requirements.

## Goals

- Monitor NVIDIA GPU telemetry through NVML.
- Poll native `llama-server` Prometheus metrics from `/metrics`.
- Poll per-slot request state from `/slots`.
- Show live dashboard cards, charts, events, and health states.
- Keep `llama-server` credentials server-side only.
- Remain a read-only observer.

## Non-goals

LlamaMetrics will not start, stop, restart, configure, or proxy arbitrary
requests to `llama-server`. It is not a chat interface, model manager, launcher,
benchmark runner, or remote command execution tool.

## Status

MVP implementation is available with a FastAPI backend, sanitized API, demo
telemetry, multi-GPU dashboard, in-memory history, and event stream.
See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the phase gates.

## Install

Use Python 3.11 or newer:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for your `llama-server`:

```bash
LLAMA_BASE_URL=http://127.0.0.1:8080
LLAMA_API_KEY=
LLAMA_METRICS_MODEL=
LLAMA_METRICS_DEMO=0
OBSERVER_HOST=0.0.0.0
OBSERVER_PORT=7778
```

`LLAMA_API_KEY` is sent only from the backend to `llama-server` as
`Authorization: Bearer <key>` when configured. It is never returned by the API or
embedded in browser assets.

## Run

Start against a real `llama-server`:

```bash
set -a
. ./.env
set +a
.venv/bin/uvicorn app.main:app --host "$OBSERVER_HOST" --port "$OBSERVER_PORT"
```

Open:

```text
http://localhost:7778
```

Run without `llama-server` or GPU hardware:

```bash
LLAMA_METRICS_DEMO=1 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 7778
```

## API

The dashboard uses these read-only endpoints:

```text
GET /api/health
GET /api/snapshot
GET /api/history?window=5m
GET /api/events
GET /api/stream
```

There are no chat, model-management, arbitrary proxy, or command-execution
endpoints.

## Systemd

The template service is in
[systemd/llama-metrics.service](./systemd/llama-metrics.service).

Typical installation layout:

```bash
sudo useradd --system --home /opt/llama-metrics --shell /usr/sbin/nologin llama-metrics
sudo mkdir -p /opt/llama-metrics
sudo cp -a . /opt/llama-metrics/
sudo chown -R llama-metrics:llama-metrics /opt/llama-metrics
sudo cp .env.example /etc/llama-metrics.env
sudo install -m 0644 systemd/llama-metrics.service /etc/systemd/system/llama-metrics.service
sudo systemctl daemon-reload
sudo systemctl enable --now llama-metrics
```

## Security Notes

The default bind address is `0.0.0.0`, so the dashboard may be reachable from
the LAN. Bind to `127.0.0.1` or put it behind reverse-proxy authentication when
you do not want LAN access.

The app is a read-only observer. It does not start, stop, restart, configure, or
proxy arbitrary requests to `llama-server`.
