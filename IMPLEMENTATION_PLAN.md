# LlamaMetrics Phased MVP Implementation Plan

## Summary

Build LlamaMetrics as a staged MVP, not one giant implementation pass. First
record the product and engineering decisions, then implement backend
foundations, parsers, collectors, history/events, dashboard, and packaging as
separate verifiable phases.

Bearer-token protected `llama-server` endpoints and multiple GPUs are required
MVP capabilities. The dashboard remains read-only and never exposes
`LLAMA_API_KEY`.

Implementation status: phases 0 through 6 have been completed in separate
commits with tests passing after each implementation phase.

## Phase 0: Record Decisions

- Update `llama-metrics-specification.md`:
  - Move Bearer authentication and multiple GPUs from optional support to MVP
    requirements.
  - Set `OBSERVER_HOST=0.0.0.0` as the default bind address.
  - Add `LLAMA_METRICS_MODEL`, `LLAMA_METRICS_DEMO`, and alert threshold
    environment variables.
  - Define sanitized API policy: no raw slot payloads, prompts, arbitrary
    upstream proxying, or API-key leakage.
- Add this `IMPLEMENTATION_PLAN.md`.
- Update `README.md` with current status and intended venv-based setup.

Acceptance gate: docs clearly describe the phased implementation and required
MVP behavior.

## Phase 1: Backend Core

- Add FastAPI app structure, pinned `requirements.txt`, `.env.example`, and
  basic startup.
- Implement config loading from environment.
- Implement data models for snapshots, server status, inference metrics, slots,
  GPUs, host/process metrics, history, and events.
- Add API shell:
  - `GET /api/health`
  - `GET /api/snapshot`
  - `GET /api/history`
  - `GET /api/events`
  - `GET /api/stream`

Acceptance gate: app starts, tests run, and endpoints return valid
empty/degraded snapshots without `llama-server` or NVML.

## Phase 2: Parsers And Llama Client

- Implement `llama-server` HTTP client for `/health`, `/metrics`, and `/slots`.
- Apply `Authorization: Bearer <LLAMA_API_KEY>` to upstream calls when
  configured.
- Support optional `/metrics?model=<LLAMA_METRICS_MODEL>`.
- Implement Prometheus parsing for known `llamacpp:*` metrics and sanitized
  unknown metric samples.
- Implement defensive slots parsing for object, array, null, absent, and
  malformed `next_token`.

Acceptance gate: parser tests cover malformed metrics/slots and API-key
non-leakage.

## Phase 3: Telemetry Collection

- Implement NVML multi-GPU collector with graceful degradation per GPU.
- Collect utilization, VRAM, temperature, power, clocks, fan, PCIe traffic,
  encoder/decoder where available, and process VRAM where supported.
- Implement host/process telemetry with best-effort local `llama-server`
  detection.
- Implement `LLAMA_METRICS_DEMO=1` mock telemetry for development without GPU
  or `llama-server`.

Acceptance gate: app works in demo mode, zero-GPU mode, offline `llama-server`
mode, and mocked multi-GPU mode.

## Phase 4: History And Events

- Implement in-memory ring buffers for 5m, 30m, 2h, and session windows.
- Implement transition-based events:
  - online/offline
  - degraded/recovered
  - request started/completed
  - queue appeared/cleared
  - prefill/decode inferred
  - context high-water increased
  - GPU temperature threshold
  - GPU VRAM threshold
  - sustained throughput drop

Acceptance gate: event tests prove transitions emit once, not every poll.

## Phase 5: Dashboard

- Build static HTML/CSS/JS frontend with no Node build step.
- Vendor chart assets locally or provide an equivalent local chart
  implementation so the dashboard works without internet access.
- Use system light/dark preference for automatic theme.
- Dashboard sections:
  - status header
  - multi-GPU cards
  - inference overview
  - slot panel
  - required charts
  - event timeline
- Use SSE for live updates and fallback polling when streaming fails.

Acceptance gate: dashboard renders in demo mode and shows live updating
multi-GPU charts.

## Phase 6: Packaging And Run Support

- Add systemd service template.
- Finalize README install/run instructions:
  - create venv
  - install requirements
  - configure `.env`
  - run with uvicorn
  - run demo mode
  - install systemd service
- Add security notes for LAN exposure because dashboard auth is not in MVP.

Acceptance gate: fresh clone can run demo mode with documented commands.

## Test Plan

- Unit tests:
  - config loading and secret redaction
  - Prometheus parsing
  - slot parsing
  - ring buffer retention/windowing
  - event transitions
  - demo telemetry generation
- API tests:
  - snapshot/history/events/stream endpoints
  - upstream Bearer auth header is applied
  - API key never appears in response bodies
  - offline/degraded states do not crash
  - no arbitrary proxy/chat/model-management endpoints exist
- Manual verification:
  - run `LLAMA_METRICS_DEMO=1`
  - open dashboard
  - verify charts and SSE updates
  - verify multi-GPU mock display
  - verify app works without `nvidia-smi` or NVML available

## Implementation Discipline

- Implement one phase at a time.
- Commit after each passing phase.
- Do not proceed to the next phase until the acceptance gate for the current
  phase passes.
- If a phase exposes a spec mismatch, update the spec in the same phase before
  continuing.

## Assumptions

- MVP supports one configured `LLAMA_BASE_URL`; multiple independent
  `llama-server` instances are later work.
- Multiple GPUs are mandatory in model and UI support, even if the development
  machine has zero GPUs.
- Dashboard login/auth is out of MVP; LAN exposure is allowed by default host
  binding and documented clearly.
- No Docker, database, Prometheus, Grafana, or Node build step is required for
  MVP.
