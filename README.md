# LlamaMetrics

LlamaMetrics is a lightweight web dashboard for monitoring an existing
`llama.cpp` / `llama-server` inference service.

See [llama-metrics-specification.md](./llama-metrics-specification.md) for the
full project requirements.

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

## Install From GitHub

Run these commands on the machine that should host the LlamaMetrics dashboard.
This can be the same machine as `llama-server`, or another machine that can
reach it over the network.

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/crgregersen/llama-metrics.git
cd llama-metrics

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

mkdir -p ~/.llama-metrics
cp .env.example ~/.llama-metrics/.env
chmod 700 ~/.llama-metrics
chmod 600 ~/.llama-metrics/.env
```

Edit `~/.llama-metrics/.env` for your `llama-server`:

```bash
LLAMA_BASE_URL=http://127.0.0.1:8080
LLAMA_API_KEY=
LLAMA_METRICS_MODEL=
LLAMA_METRICS_DEMO=0
OBSERVER_HOST=0.0.0.0
OBSERVER_PORT=7778
```

Set `LLAMA_BASE_URL` to the existing `llama-server` address and port. For
example, if `llama-server` was started with `--port 20202` on the same machine,
use:

```bash
LLAMA_BASE_URL=http://127.0.0.1:20202
```

`LLAMA_API_KEY` is sent only from the backend to `llama-server` as
`Authorization: Bearer <key>` when configured. It is never returned by the API or
embedded in browser assets.

If your `llama-server` is protected, set `LLAMA_API_KEY` to the same Bearer token
that `llama-server` expects. For example, if your inference startup script does
this:

```bash
export LLAMA_API_KEY="$QWEN_API_KEY"
```

then either put the same token value in `~/.llama-metrics/.env`, or leave
`LLAMA_API_KEY=` empty in the file and start LlamaMetrics with:

```bash
LLAMA_API_KEY="$QWEN_API_KEY" .venv/bin/python -m app.run
```

Configuration is loaded from `~/.llama-metrics/.env` by default. A local `.env`
inside the checkout is also supported for development and overrides values from
the home-directory config. Real shell environment variables override both files.

## Demo Mode

`LLAMA_METRICS_DEMO` controls whether LlamaMetrics uses generated telemetry or
real telemetry:

```bash
LLAMA_METRICS_DEMO=0
```

Normal mode. LlamaMetrics polls the configured `LLAMA_BASE_URL`, reads
`/metrics` and `/slots`, and collects real GPU telemetry through NVML.

```bash
LLAMA_METRICS_DEMO=1
```

Demo mode. LlamaMetrics does not need a running `llama-server` or working NVIDIA
GPU/NVML stack. It generates realistic mock multi-GPU, slot, chart, and event
data so you can verify the dashboard after install or develop on a non-GPU
machine.

Use `LLAMA_METRICS_DEMO=0` for real monitoring.

## Run

Start against a real `llama-server`:

```bash
cd ~/src/llama-metrics
.venv/bin/python -m app.run
```

Open:

```text
http://DASHBOARD_SERVER_IP:7778
```

Run without `llama-server` or GPU hardware:

```bash
LLAMA_METRICS_DEMO=1 .venv/bin/python -m app.run --host 127.0.0.1
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
sudo mkdir -p /var/lib/llama-metrics
sudo cp .env.example /var/lib/llama-metrics/.env
sudo chown -R llama-metrics:llama-metrics /var/lib/llama-metrics
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
