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

Specification and phased implementation planning are in progress. See
[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the build phases and
acceptance gates.

## Planned Runtime

The MVP will run from a Python virtual environment with pinned dependencies,
FastAPI, static browser assets, and no required Docker, database, Prometheus,
Grafana, or Node build step.

Default runtime settings will be environment-based:

```bash
LLAMA_BASE_URL=http://127.0.0.1:8080
LLAMA_API_KEY=
LLAMA_METRICS_MODEL=
LLAMA_METRICS_DEMO=0
OBSERVER_HOST=0.0.0.0
OBSERVER_PORT=7778
```
