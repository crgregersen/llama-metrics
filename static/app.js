const state = {
  snapshots: [],
  events: [],
  window: "5m",
  eventSource: null,
  fallbackTimer: null,
  reconnectTimer: null,
};

const palette = [
  "#0f766e",
  "#b45309",
  "#2563eb",
  "#be123c",
  "#7c3aed",
  "#15803d",
  "#c2410c",
  "#0891b2",
];

const gpuCharts = [
  { id: "util", title: "Utilisation", unit: "%", series: (index) => gpuMetricSeries(index, "utilization_percent", identity, "Util") },
  { id: "vram", title: "VRAM use", unit: "GB", series: (index) => gpuMetricSeries(index, "vram_used_bytes", bytesToGb, "VRAM") },
  { id: "power", title: "Power draw", unit: "W", series: (index) => gpuMetricSeries(index, "power_draw_w", identity, "Power") },
  { id: "temperature", title: "Temperature", unit: "C", series: (index) => gpuMetricSeries(index, "temperature_c", identity, "Temp") },
  { id: "gfx-clock", title: "Graphics clock", unit: "MHz", series: (index) => gpuMetricSeries(index, "graphics_clock_mhz", identity, "Graphics") },
  { id: "mem-clock", title: "Memory clock", unit: "MHz", series: (index) => gpuMetricSeries(index, "memory_clock_mhz", identity, "Memory") },
  { id: "pcie", title: "PCIe traffic", unit: "MB/s", series: (index) => gpuPcieSeries(index) },
];

const systemCharts = [
  { id: "throughput", title: "Inference throughput", unit: "tok/s", series: throughputSeries },
  { id: "requests", title: "Request state", unit: "requests", series: requestSeries },
  { id: "host-cpu", title: "Host CPU", unit: "%", series: hostCpuSeries },
  { id: "host-memory", title: "Host memory", unit: "GB", series: hostMemorySeries },
];

document.addEventListener("DOMContentLoaded", () => {
  bindWindowControls();
  loadHistory();
  loadEvents();
  connectStream();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
});

function bindWindowControls() {
  document.querySelectorAll("[data-window]").forEach((button) => {
    button.addEventListener("click", () => {
      state.window = button.dataset.window;
      document.querySelectorAll("[data-window]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      loadHistory();
    });
  });
}

async function loadHistory() {
  try {
    const response = await fetch(`/api/history?window=${encodeURIComponent(state.window)}`);
    if (!response.ok) return;
    const body = await response.json();
    state.snapshots = body.snapshots || [];
    trimSnapshots();
    render();
  } catch {
    return;
  }
}

async function loadEvents() {
  try {
    const response = await fetch("/api/events");
    if (!response.ok) return;
    const body = await response.json();
    state.events = body.events || [];
    renderEvents();
  } catch {
    return;
  }
}

async function fetchSnapshot() {
  try {
    const response = await fetch("/api/snapshot");
    if (!response.ok) return;
    addSnapshot(await response.json());
    await loadEvents();
  } catch {
    return;
  }
}

function connectStream() {
  if (state.eventSource) state.eventSource.close();
  state.eventSource = new EventSource("/api/stream");
  state.eventSource.addEventListener("snapshot", (event) => {
    stopFallback();
    addSnapshot(JSON.parse(event.data));
    loadEvents();
  });
  state.eventSource.onerror = () => {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = null;
    startFallback();
    if (!state.reconnectTimer) {
      state.reconnectTimer = setTimeout(() => {
        state.reconnectTimer = null;
        connectStream();
      }, 3000);
    }
  };
}

function startFallback() {
  if (!state.fallbackTimer) {
    state.fallbackTimer = setInterval(fetchSnapshot, 1500);
  }
}

function stopFallback() {
  if (state.fallbackTimer) {
    clearInterval(state.fallbackTimer);
    state.fallbackTimer = null;
  }
}

function addSnapshot(snapshot) {
  state.snapshots.push(snapshot);
  trimSnapshots();
  render();
}

function trimSnapshots() {
  if (state.window === "session") return;
  const seconds = windowSeconds(state.window);
  if (!seconds || state.snapshots.length === 0) return;
  const newest = Date.parse(state.snapshots[state.snapshots.length - 1].timestamp);
  const cutoff = newest - seconds * 1000;
  state.snapshots = state.snapshots.filter((snapshot) => Date.parse(snapshot.timestamp) >= cutoff);
}

function render() {
  const snapshot = state.snapshots[state.snapshots.length - 1];
  if (!snapshot) return;
  renderHeader(snapshot);
  renderOverview(snapshot);
  renderGpus(snapshot);
  renderSlots(snapshot);
  renderCharts();
  renderEvents();
}

function renderHeader(snapshot) {
  setText("server-url", snapshot.server?.base_url || "--");
  setText("last-poll", formatClockTime(snapshot.timestamp));
  setText("server-pid", snapshot.server?.pid ?? "--");
  setText("server-uptime", formatClockDuration(snapshot.server?.uptime_seconds));
  setText("gpu-count", snapshot.gpus?.length ?? 0);
  setText("slot-count", snapshot.slots?.length ?? 0);
  const status = snapshot.status || "unknown";
  const pill = document.getElementById("status-pill");
  pill.textContent = status;
  pill.className = `status-pill ${status}`;
}

function renderOverview(snapshot) {
  const inference = snapshot.inference || {};
  setText("prompt-tps", formatNumber(inference.prompt_tokens_per_second));
  setText("generation-tps", formatNumber(inference.generation_tokens_per_second));
  setText("active-requests", inference.active_requests ?? 0);
  setText("queued-requests", inference.deferred_requests ?? 0);
  setText("largest-context", formatInteger(inference.largest_observed_context_tokens));
  setText("phase", inference.inferred_phase || "unknown");
}

function renderGpus(snapshot) {
  const grid = document.getElementById("gpu-grid");
  const gpus = snapshot.gpus || [];
  if (gpus.length === 0) {
    grid.innerHTML = `<div class="empty">GPU telemetry unavailable</div>`;
    return;
  }
  grid.innerHTML = gpus.map((gpu) => `
    <article class="gpu-card">
      <div class="card-title">
        <h3>${escapeHtml(gpu.name || `GPU ${gpu.index}`)}</h3>
        <span class="badge">${escapeHtml(gpu.uuid || `index ${gpu.index}`)}</span>
      </div>
      ${bar(gpu.utilization_percent)}
      <div class="kv-grid">
        ${kv("Util", percent(gpu.utilization_percent))}
        ${kv("VRAM", `${formatBytes(gpu.vram_used_bytes)} / ${formatBytes(gpu.vram_total_bytes)}`)}
        ${kv("Temp", temp(gpu.temperature_c))}
        ${kv("Power", `${formatNumber(gpu.power_draw_w)} / ${formatNumber(gpu.power_limit_w)} W`)}
        ${kv("Graphics", mhz(gpu.graphics_clock_mhz))}
        ${kv("Memory", mhz(gpu.memory_clock_mhz))}
        ${kv("Fan", percent(gpu.fan_speed_percent))}
        ${kv("PCIe RX/TX", `${formatThroughput(gpu.pcie_rx_bytes_per_second)} / ${formatThroughput(gpu.pcie_tx_bytes_per_second)}`)}
        ${kv("llama VRAM", formatBytes(gpu.llama_server_vram_bytes))}
        ${kv("Processes", gpu.processes?.length ?? 0)}
      </div>
    </article>
  `).join("");
}

function renderSlots(snapshot) {
  const grid = document.getElementById("slot-grid");
  const slots = snapshot.slots || [];
  if (slots.length === 0) {
    grid.innerHTML = `<div class="empty">No slots reported</div>`;
    return;
  }
  grid.innerHTML = slots.map((slot) => `
    <article class="slot-card">
      <div class="card-title">
        <h3>Slot ${escapeHtml(slot.slot_id ?? "--")}</h3>
        <span class="badge">${escapeHtml(slotBadge(slot))}</span>
      </div>
      ${bar((slot.output_progress ?? 0) * 100)}
      <div class="kv-grid">
        ${kv("Task", slot.task_id ?? "--")}
        ${kv("Context", formatInteger(slot.n_ctx))}
        ${kv("Context used", formatInteger(slot.context_used_tokens))}
        ${kv("Context left", formatInteger(slot.context_remaining_tokens))}
        ${kv("Prompt", formatInteger(slot.prompt_tokens))}
        ${kv("Cached", formatInteger(slot.prompt_tokens_cached))}
        ${kv("Generated", formatInteger(slot.generated_tokens))}
        ${kv("Remaining", formatInteger(slot.remaining_tokens))}
        ${kv("Output limit", formatInteger(slot.output_token_limit))}
        ${kv("Progress", percent(slot.output_progress == null ? null : slot.output_progress * 100))}
        ${kv("Continuing", slot.has_next_token == null ? "--" : slot.has_next_token ? "yes" : "no")}
        ${kv("ETA", formatDuration(slot.estimated_seconds_remaining))}
      </div>
    </article>
  `).join("");
}

function slotBadge(slot) {
  const stateText = slot.state || "unknown";
  return slot.metrics_are_current === false && stateText === "idle"
    ? "idle - last request"
    : stateText;
}

function renderEvents() {
  const list = document.getElementById("event-list");
  const events = [...state.events].slice(-80).reverse();
  if (events.length === 0) {
    list.innerHTML = `<div class="empty">No events</div>`;
    return;
  }
  list.innerHTML = events.map((event) => `
    <div class="event-row">
      <div class="event-time">${formatTime(event.timestamp)}</div>
      <div class="event-message ${escapeHtml(event.severity || "info")}">${escapeHtml(event.message || event.kind)}</div>
    </div>
  `).join("");
}

function renderCharts() {
  buildChartGroups();

  const gpuIndexes = currentGpuIndexes();
  for (const index of gpuIndexes) {
    for (const chart of gpuCharts) {
      const canvas = document.getElementById(`chart-gpu-${index}-${chart.id}`);
      if (!canvas) continue;
      drawChart(canvas, chart.series(index)(state.snapshots), chart.unit);
    }
  }

  for (const chart of systemCharts) {
    const canvas = document.getElementById(`chart-system-${chart.id}`);
    if (!canvas) continue;
    drawChart(canvas, chart.series(state.snapshots), chart.unit);
  }
}

function buildChartGroups() {
  const container = document.getElementById("chart-groups");
  if (!container) return;

  const signature = chartLayoutSignature();
  if (container.dataset.signature === signature) return;
  container.dataset.signature = signature;

  const gpuIndexes = currentGpuIndexes();
  const gpuGroups = gpuIndexes.map((index) => {
    const gpu = latestGpu(index);
    const title = `GPU ${index}${gpu?.name ? ` - ${gpu.name}` : ""}`;
    return `
      <section class="chart-group" aria-label="${escapeHtml(title)} charts">
        <div class="chart-group-head">
          <h3>${escapeHtml(title)}</h3>
          <span>${escapeHtml(gpu?.uuid || "")}</span>
        </div>
        <div class="chart-grid">
          ${gpuCharts.map((chart) => chartCard(`gpu-${index}-${chart.id}`, chart)).join("")}
        </div>
      </section>
    `;
  }).join("");

  const noGpuGroup = gpuIndexes.length === 0
    ? `<div class="empty">GPU chart data unavailable</div>`
    : "";

  container.innerHTML = `
    ${gpuGroups || noGpuGroup}
    <section class="chart-group" aria-label="System charts">
      <div class="chart-group-head">
        <h3>System / Inference</h3>
        <span>Host, process, request and throughput telemetry</span>
      </div>
      <div class="chart-grid">
        ${systemCharts.map((chart) => chartCard(`system-${chart.id}`, chart)).join("")}
      </div>
    </section>
  `;
}

function chartCard(id, chart) {
  return `
    <article class="chart-card">
      <div class="chart-title"><strong>${chart.title}</strong><span>${chart.unit}</span></div>
      <canvas id="chart-${id}" width="640" height="260"></canvas>
    </article>
  `;
}

function chartLayoutSignature() {
  const gpuParts = currentGpuIndexes().map((index) => {
    const gpu = latestGpu(index);
    return `${index}:${gpu?.name || ""}:${gpu?.uuid || ""}`;
  });
  return `${gpuParts.join("|")}::system`;
}

function drawChart(canvas, series, unit) {
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.floor(rect.width * ratio));
  const height = Math.max(180, Math.floor(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  ctx.clearRect(0, 0, width, height);
  const styles = getComputedStyle(document.documentElement);
  const lineColor = styles.getPropertyValue("--line").trim();
  const textColor = styles.getPropertyValue("--muted").trim();
  const pad = { left: 44 * ratio, right: 12 * ratio, top: 12 * ratio, bottom: 28 * ratio };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  ctx.strokeStyle = lineColor;
  ctx.lineWidth = ratio;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(pad.left + plotW, pad.top + plotH);
  ctx.stroke();

  const allPoints = series.flatMap((item) => item.points).filter((point) => Number.isFinite(point.y));
  if (allPoints.length < 2) {
    ctx.fillStyle = textColor;
    ctx.fillText("No data", pad.left + 8 * ratio, pad.top + 24 * ratio);
    return;
  }

  const minX = Math.min(...allPoints.map((point) => point.x));
  const maxX = Math.max(...allPoints.map((point) => point.x));
  let minY = Math.min(...allPoints.map((point) => point.y));
  let maxY = Math.max(...allPoints.map((point) => point.y));
  if (minY === maxY) {
    minY -= 1;
    maxY += 1;
  }
  if (minY > 0) minY = 0;

  ctx.fillStyle = textColor;
  ctx.font = `${11 * ratio}px system-ui, sans-serif`;
  ctx.fillText(formatAxis(maxY, unit), 4 * ratio, pad.top + 9 * ratio);
  ctx.fillText(formatAxis(minY, unit), 4 * ratio, pad.top + plotH);

  series.forEach((item, index) => {
    const points = item.points.filter((point) => Number.isFinite(point.y));
    if (points.length < 2) return;
    ctx.strokeStyle = palette[index % palette.length];
    ctx.lineWidth = 2 * ratio;
    ctx.beginPath();
    points.forEach((point, pointIndex) => {
      const x = pad.left + ((point.x - minX) / Math.max(1, maxX - minX)) * plotW;
      const y = pad.top + plotH - ((point.y - minY) / (maxY - minY)) * plotH;
      if (pointIndex === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  drawLegend(ctx, series, width, height, ratio);
}

function drawLegend(ctx, series, width, height, ratio) {
  const styles = getComputedStyle(document.documentElement);
  ctx.font = `${11 * ratio}px system-ui, sans-serif`;
  let x = 48 * ratio;
  const y = height - 8 * ratio;
  series.slice(0, 4).forEach((item, index) => {
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(x, y - 8 * ratio, 8 * ratio, 8 * ratio);
    ctx.fillStyle = styles.getPropertyValue("--muted").trim();
    ctx.fillText(item.name, x + 12 * ratio, y);
    x += Math.min(130 * ratio, (item.name.length * 7 + 28) * ratio);
  });
}

function gpuMetricSeries(index, field, transform = identity, name = "Value") {
  return (snapshots) => [
    {
      name,
      points: snapshots.map((snapshot) => {
        const gpu = gpuFromSnapshot(snapshot, index);
        return { x: Date.parse(snapshot.timestamp), y: transform(gpu?.[field]) };
      }),
    },
  ];
}

function gpuPcieSeries(index) {
  return (snapshots) => [
    {
      name: "RX",
      points: snapshots.map((snapshot) => {
        const gpu = gpuFromSnapshot(snapshot, index);
        return { x: Date.parse(snapshot.timestamp), y: bytesToMb(gpu?.pcie_rx_bytes_per_second) };
      }),
    },
    {
      name: "TX",
      points: snapshots.map((snapshot) => {
        const gpu = gpuFromSnapshot(snapshot, index);
        return { x: Date.parse(snapshot.timestamp), y: bytesToMb(gpu?.pcie_tx_bytes_per_second) };
      }),
    },
  ];
}

function throughputSeries(snapshots) {
  return [
    lineFrom(snapshots, "Prompt", (snapshot) => snapshot.inference?.prompt_tokens_per_second),
    lineFrom(snapshots, "Generation", (snapshot) => snapshot.inference?.generation_tokens_per_second),
  ];
}

function requestSeries(snapshots) {
  return [
    lineFrom(snapshots, "Active", (snapshot) => snapshot.inference?.active_requests),
    lineFrom(snapshots, "Queued", (snapshot) => snapshot.inference?.deferred_requests),
  ];
}

function hostCpuSeries(snapshots) {
  return [
    lineFrom(snapshots, "System", (snapshot) => snapshot.host?.cpu_percent),
    lineFrom(snapshots, "llama-server", (snapshot) => snapshot.host?.llama_server_cpu_percent),
  ];
}

function hostMemorySeries(snapshots) {
  return [
    lineFrom(snapshots, "System used", (snapshot) => bytesToGb(snapshot.host?.memory_used_bytes)),
    lineFrom(snapshots, "llama RSS", (snapshot) => bytesToGb(snapshot.host?.llama_server_rss_bytes)),
  ];
}

function lineFrom(snapshots, name, getter) {
  return {
    name,
    points: snapshots.map((snapshot) => ({ x: Date.parse(snapshot.timestamp), y: getter(snapshot) })),
  };
}

function currentGpuIndexes() {
  const snapshot = state.snapshots[state.snapshots.length - 1];
  return (snapshot?.gpus || []).map((gpu) => gpu.index).sort((a, b) => a - b);
}

function latestGpu(index) {
  const snapshot = state.snapshots[state.snapshots.length - 1];
  return gpuFromSnapshot(snapshot, index);
}

function gpuFromSnapshot(snapshot, index) {
  return (snapshot?.gpus || []).find((gpu) => gpu.index === index);
}

function kv(label, value) {
  return `<div class="kv"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "--")}</strong></div>`;
}

function bar(value) {
  const width = clamp(Number(value) || 0, 0, 100);
  return `<div class="bar"><i style="width:${width}%"></i></div>`;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value ?? "--";
}

function formatTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleTimeString();
}

function formatClockTime(value) {
  if (!value) return "--:--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function formatClockDuration(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) return "--:--:--";
  seconds = Math.max(0, Math.floor(Number(seconds)));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const clock = [hours, minutes, secs]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return days > 0 ? `${days}d ${clock}` : clock;
}

function formatDuration(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) return "--";
  seconds = Math.max(0, Math.floor(Number(seconds)));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function formatBytes(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  const gb = Number(value) / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  return `${(Number(value) / 1024 ** 2).toFixed(0)} MB`;
}

function formatThroughput(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return `${bytesToMb(value).toFixed(1)} MB/s`;
}

function formatNumber(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function formatInteger(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return Math.round(Number(value)).toLocaleString();
}

function formatAxis(value, unit) {
  if (!Number.isFinite(value)) return "--";
  return `${Number(value).toFixed(value >= 10 ? 0 : 1)}${unit ? ` ${unit}` : ""}`;
}

function percent(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return `${Number(value).toFixed(1)}%`;
}

function temp(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return `${Number(value).toFixed(1)} C`;
}

function mhz(value) {
  if (value == null || !Number.isFinite(Number(value))) return "--";
  return `${formatInteger(value)} MHz`;
}

function bytesToGb(value) {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Number(value) / 1024 ** 3;
}

function bytesToMb(value) {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Number(value) / 1024 ** 2;
}

function windowSeconds(value) {
  if (value.endsWith("m")) return Number(value.slice(0, -1)) * 60;
  if (value.endsWith("h")) return Number(value.slice(0, -1)) * 3600;
  return null;
}

function identity(value) {
  return value == null ? null : Number(value);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
