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

Initial project setup. Implementation has not started yet.
