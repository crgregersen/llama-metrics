# LlamaMetrics — Project Specification

> **Project name:** LlamaMetrics  
> **Suggested repository name:** `llama-metrics`

## 1. Purpose

LlamaMetrics is a lightweight web dashboard for monitoring an existing `llama.cpp` / `llama-server` inference service.

It combines:

- Live NVIDIA GPU telemetry similar to `nvtop`
- Historical charts for GPU and inference activity
- Native `llama-server` Prometheus metrics from `/metrics`
- Per-slot request and generation state from `/slots`
- Host and process telemetry
- Authenticated access to protected llama-server endpoints when configured

The application is a **read-only observer**.

It must never start, stop, restart or reconfigure `llama-server`.

---

## 2. Design principles

1. **Passive monitoring only**  
   The monitor attaches to an already-running `llama-server` instance.

2. **No model lifecycle control**  
   No launch presets, model selection, server configuration or chat interface.

3. **Secure by default**  
   API keys remain server-side. They must never reach the browser.

4. **Useful without infrastructure**  
   The first version should not require Docker, Prometheus, Grafana or a database.

5. **Works with local and remote `llama-server` instances**  
   The monitor should support a configurable server URL including localhost, LAN and reverse-proxy deployments.

6. **Supports evolving `llama.cpp` APIs**  
   Changes in `/slots` payload shape must not crash the monitor.

7. **Designed for a browser-first workflow**  
   It should provide live cards, graphs, timelines and clear health states.

---

## 3. Supported environment

### Required

- Linux host for GPU telemetry collection
- NVIDIA GPU with NVML support
- Python 3.11 or newer
- Existing `llama.cpp` `llama-server`
- `llama-server` `/metrics` endpoint enabled through `--metrics`
- Protected `llama-server` endpoints using Bearer-token authentication
- Multiple GPUs

### Optional

- Multiple `llama-server` instances in a later release
- SQLite for persistent history in a later release

---

## 4. Architecture

```text
Browser
   │
   ▼
LlamaMetrics web service
   ├─ Polls GPU telemetry through NVML
   ├─ Polls llama-server /metrics
   ├─ Polls llama-server /slots
   ├─ Collects host and process telemetry
   ├─ Keeps recent time-series data in memory
   └─ Streams read-only updates to the browser

Existing llama-server
   ├─ Continues to run independently
   ├─ May require a Bearer token
   └─ Is never started, stopped or reconfigured by LlamaMetrics
```

The observer should normally access `llama-server` through a configured base URL such as:

```text
http://127.0.0.1:8080
```

The browser should access the observer through a separate dashboard URL such as:

```text
http://localhost:7778
```

---

## 5. Technology choices

| Area | Recommended choice | Rationale |
|---|---|---|
| Backend | Python | Direct access to NVML through `nvidia-ml-py` |
| Web framework | FastAPI | Lightweight API and Server-Sent Events support |
| GPU telemetry | NVML | Direct structured GPU metrics without parsing terminal output |
| `llama-server` telemetry | HTTP polling | Native `/metrics` and `/slots` endpoints |
| Frontend | Static HTML and TypeScript/JavaScript | Small deployment footprint |
| Charts | ECharts, Chart.js or uPlot | Good support for live time-series graphs |
| Live updates | Server-Sent Events | Simple server-to-browser streaming |
| MVP history | In-memory ring buffers | No persistence dependency |
| Later persistence | SQLite | Simple session history and comparison support |

---

## 6. Configuration

Configuration must be environment-based.

Example `.env` file:

```bash
LLAMA_BASE_URL=http://127.0.0.1:8080
LLAMA_API_KEY=
LLAMA_METRICS_MODEL=
LLAMA_METRICS_DEMO=0
OBSERVER_HOST=0.0.0.0
OBSERVER_PORT=7778
POLL_INTERVAL_SECONDS=1
HISTORY_RETENTION_MINUTES=30
GPU_TEMPERATURE_ALERT_C=85
GPU_VRAM_ALERT_PERCENT=90
GENERATION_THROUGHPUT_DROP_PERCENT=40
GENERATION_THROUGHPUT_DROP_WINDOW_SECONDS=30
```

Rules:

- `LLAMA_API_KEY` is optional.
- When configured, it must be sent as `Authorization: Bearer <key>`.
- Bearer-token support for protected `llama-server` endpoints is required for
  MVP.
- `LLAMA_METRICS_MODEL` is optional. When configured, it is sent as the
  `model` query parameter for `/metrics` polling.
- `LLAMA_METRICS_DEMO=1` enables generated mock telemetry for development and
  UI verification without a reachable `llama-server` or NVML.
- The key must never be returned by any API endpoint.
- The key must never appear in HTML, JavaScript bundles or browser developer tools.
- The dashboard should work with unauthenticated `llama-server` instances too.
- The default `OBSERVER_HOST` is `0.0.0.0`; deployments must treat the
  unauthenticated dashboard as network-accessible unless bound or firewalled
  differently.

---

## 7. Data sources

### 7.1 GPU telemetry through NVML

Poll once per second for each detected GPU.

Required fields:

```text
GPU index
GPU name
GPU UUID
GPU utilisation percentage
Memory utilisation percentage
VRAM used
VRAM free
VRAM total
Temperature
Power draw
Power limit
Graphics clock
Memory clock
Fan speed
PCIe generation
PCIe link width
PCIe receive throughput
PCIe transmit throughput
```

Where supported by the installed driver and hardware, also collect:

```text
Encoder utilisation
Decoder utilisation
Throttle reasons
Power-limit state
Temperature-limit state
Per-process GPU memory usage
```

The dashboard should identify the monitored `llama-server` process and show its VRAM use separately from other GPU processes.

---

### 7.2 `llama-server` `/metrics`

Poll once per second.

The monitor must parse Prometheus text exposition format and preserve unknown metrics for future display or debugging.

Minimum supported metrics:

```text
llamacpp:n_tokens_max
llamacpp:prompt_tokens_seconds
llamacpp:predicted_tokens_seconds
llamacpp:requests_processing
llamacpp:requests_deferred
```

Suggested dashboard labels:

| Metric | Label |
|---|---|
| `llamacpp:n_tokens_max` | Largest observed context |
| `llamacpp:prompt_tokens_seconds` | Prompt throughput |
| `llamacpp:predicted_tokens_seconds` | Generation throughput |
| `llamacpp:requests_processing` | Active requests |
| `llamacpp:requests_deferred` | Queued requests |

Important: `n_tokens_max` is a high-water mark since server startup. It must not be presented as the current context size.

---

### 7.3 `llama-server` `/slots`

Poll once per second.

The monitor must support slot responses where `next_token` is:

- an object
- an array
- `null`
- absent

Minimum slot data:

```text
Slot ID
Task ID
Processing state
Configured context size
Generated output tokens
Remaining output tokens
Output-token limit
Whether generation is continuing
```

Example generic slot payload:

```json
{
  "id": 0,
  "id_task": 1234,
  "is_processing": true,
  "n_ctx": 131072,
  "next_token": [
    {
      "has_next_token": true,
      "n_remain": 12000,
      "n_decoded": 4000
    }
  ]
}
```

Derived values:

```text
Output-token limit = generated tokens + remaining tokens
Output progress = generated tokens / output-token limit
Estimated remaining generation time = remaining tokens / current generation throughput
```

When no request is active, the UI should render the slot as idle.

---

### 7.4 Host and process telemetry

Poll every 2–5 seconds.

Required values:

```text
System CPU use
System memory used and available
Load average
Uptime
llama-server PID
llama-server CPU use
llama-server resident memory
llama-server uptime where detectable
```

Optional later values:

```text
CPU temperature
Disk use
Network traffic
Per-core CPU use
Container telemetry
```

---

## 8. Dashboard layout

### 8.1 Header

Display:

```text
Server status
Configured llama-server URL
Last successful poll timestamp
llama-server PID
Server uptime
Detected GPU count
Configured context size where available
Configured slot count where available
```

Status states:

| State | Meaning |
|---|---|
| Healthy | `llama-server` and telemetry sources are reachable |
| Degraded | Server is reachable but one data source is unavailable |
| Offline | `llama-server` cannot be reached |
| Idle | Server is reachable but no active request exists |
| Unknown | Insufficient data to infer state |

---

### 8.2 GPU cards

Render one card per GPU.

Each card should show:

```text
GPU name
Utilisation
VRAM used / total
Temperature
Power draw / limit
Graphics clock
Memory clock
Fan speed
PCIe RX/TX
llama-server VRAM use
```

Cards should make imbalance visible across GPUs without assuming that imbalance is a fault.

---

### 8.3 Inference overview

Prominent live values:

```text
Prompt throughput
Generation throughput
Active requests
Queued requests
Largest observed context
Current inferred phase
```

The application may infer a phase from available metrics:

| Condition | Inferred phase |
|---|---|
| No active request | Idle |
| High recent prompt throughput | Prefill |
| Non-zero generation throughput | Decode |
| Deferred requests above zero | Queueing |
| Metrics stale or contradictory | Unknown |

The UI must make clear that phase detection is inferred rather than an authoritative server state.

---

### 8.4 Slot panel

Render all detected slots.

For each slot display:

```text
Slot ID
Task ID
State
Configured context size
Generated output tokens
Remaining output allowance
Output-token limit
Output completion percentage
Estimated remaining generation time
```

The layout must support one or more slots without redesign.

---

## 9. Charts

The dashboard should be graph-heavy rather than only presenting current-value cards.

### Default time windows

```text
5 minutes
30 minutes
2 hours
Current session
```

### Required charts

| Chart | Series |
|---|---|
| GPU utilisation | One line per GPU |
| VRAM use | One line per GPU |
| Power draw | One line per GPU |
| Temperature | One line per GPU |
| Graphics clock | One line per GPU |
| Memory clock | One line per GPU |
| PCIe traffic | RX and TX per GPU |
| Inference throughput | Prompt tok/s and generation tok/s |
| Request state | Active and queued requests |
| Host CPU | System CPU and llama-server CPU |
| Host memory | System memory and llama-server RSS |

Prompt and generation throughput must be plotted as separate series because they represent different stages of inference.

---

## 10. Event timeline

Maintain an event stream based on meaningful state changes.

Examples:

```text
Request started
Prefill detected
Decode detected
Request completed
Queue appeared
Context high-water mark increased
GPU temperature threshold crossed
GPU memory threshold crossed
Generation throughput dropped materially
llama-server became unreachable
llama-server became reachable
```

Events should be transition-based rather than emitted on every poll.

Suggested alerts:

```text
GPU temperature exceeds configured threshold
GPU VRAM use exceeds configured threshold
Queued request count becomes non-zero
Largest observed context exceeds configured percentage of context capacity
Generation throughput drops by more than configured percentage for a sustained period
llama-server becomes unreachable
```

---

## 11. Backend API

Required endpoints:

```text
GET /api/health
GET /api/snapshot
GET /api/history?window=5m
GET /api/events
GET /api/stream
```

### `GET /api/snapshot`

Returns current read-only telemetry.

Example:

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "server": {
    "online": true,
    "pid": 12345,
    "uptime_seconds": 3600
  },
  "inference": {
    "prompt_tokens_per_second": 1500.0,
    "generation_tokens_per_second": 25.0,
    "active_requests": 1,
    "deferred_requests": 0,
    "largest_observed_context_tokens": 48000
  },
  "slots": [],
  "gpus": [],
  "host": {}
}
```

### `GET /api/stream`

Use Server-Sent Events.

Send a new snapshot at the configured polling interval.

The browser must reconnect automatically after a temporary connection failure.

---

## 12. Security requirements

1. The observer must treat `llama-server` credentials as backend-only secrets.
2. The observer must support protected `llama-server` endpoints.
3. The observer must not proxy arbitrary requests to `llama-server`.
4. The observer must not provide a chat endpoint.
5. The observer must not provide model-management endpoints.
6. The observer must not run shell commands based on browser input.
7. The observer binds to `0.0.0.0` by default for LAN visibility.
8. Deployments that require localhost-only access should set
   `OBSERVER_HOST=127.0.0.1` explicitly.
9. Optional dashboard authentication should be designed as a future extension.

Browser-facing APIs must be sanitized. They must not include raw slot payloads,
prompt text, arbitrary upstream responses, request bodies, or secret-bearing
configuration. Unknown Prometheus metrics may be exposed only as sanitized metric
names, labels and numeric values.

---

## 13. Reliability requirements

| Failure | Expected behaviour |
|---|---|
| `llama-server` is stopped | Dashboard remains available and displays server offline |
| Invalid API key | Clear backend error state without exposing credentials |
| NVML unavailable | llama metrics remain available and GPU panels show unavailable |
| One GPU unavailable | Remaining GPUs continue to display normally |
| `/slots` changes shape | Parser degrades gracefully and does not crash |
| Browser disconnects | SSE reconnects automatically |
| `llama-server` restarts | Monitor detects reset and begins a new session |
| Metrics reset | Charts mark a new session boundary |
| Poll timeout | Preserve last known values and show stale status |

---

## 14. Project structure

```text
llama-metrics/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ collector.py
│  ├─ llama_client.py
│  ├─ metrics_parser.py
│  ├─ slots_parser.py
│  ├─ nvml_client.py
│  ├─ host_metrics.py
│  ├─ models.py
│  ├─ ring_buffer.py
│  ├─ events.py
│  └─ api.py
├─ static/
│  ├─ index.html
│  ├─ app.js
│  └─ styles.css
├─ tests/
│  ├─ test_metrics_parser.py
│  ├─ test_slots_parser.py
│  ├─ test_ring_buffer.py
│  └─ test_api_auth.py
├─ systemd/
│  └─ llama-metrics.service
├─ requirements.txt
├─ .env.example
├─ README.md
└─ LICENSE
```

---

## 15. MVP acceptance criteria

The MVP is complete when all of the following are true:

1. The dashboard attaches to an existing `llama-server` instance.
2. The dashboard does not start, stop or modify `llama-server`.
3. The dashboard displays all detected NVIDIA GPUs.
4. GPU telemetry updates at least once per second.
5. GPU history charts retain at least 30 minutes of samples.
6. The dashboard reads `llama-server` `/metrics`.
7. The dashboard reads `llama-server` `/slots`.
8. The dashboard supports authenticated `llama-server` endpoints through
   optional `LLAMA_API_KEY` configuration.
9. The browser never receives the `llama-server` API key.
10. The dashboard shows prompt and generation throughput.
11. The dashboard shows active and queued request counts.
12. The dashboard shows generated and remaining output tokens for active slots.
13. The dashboard remains available when `llama-server` is offline.
14. The dashboard does not crash when `/slots` payload structure changes.
15. The dashboard can be installed and run without Docker, Prometheus or Grafana.
16. The dashboard data model and UI support multiple GPUs as a required MVP
    capability.
17. `LLAMA_METRICS_DEMO=1` provides a runnable development/demo mode without
    real GPU hardware or a reachable `llama-server`.

---


## 16. Explicit non-goals

LlamaMetrics is not:

```text
A llama-server launcher
A model manager
A chat interface
An agent interface
A benchmark runner
A replacement for Prometheus or Grafana
A remote command execution tool
A GPU overclocking or tuning tool
```

Its sole responsibility is to provide reliable, secure and useful observability for existing `llama.cpp` inference servers.
