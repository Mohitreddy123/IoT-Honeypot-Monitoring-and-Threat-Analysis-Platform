// Real-time dashboard behavior for Socket.IO events and Chart.js charts.

const state = {
  stats: window.initialStats || {},
  charts: {},
};

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function escapeText(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "-" : String(value);
  return div.innerHTML;
}

function setMetric(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? 0;
}

function setConnectionStatus(text, className) {
  const status = document.getElementById("socketStatus");
  if (!status) return;
  status.textContent = text;
  status.className = className;
}

function renderTables(stats) {
  const recentEvents = document.getElementById("recentEvents");
  const recentCowrie = document.getElementById("recentCowrie");
  const ipFilter = document.getElementById("filterIp")?.value.toLowerCase() || "";
  const deviceFilter = document.getElementById("filterDevice")?.value.toLowerCase() || "";
  const typeFilter = document.getElementById("filterType")?.value.toLowerCase() || "";

  const filteredEvents = (stats.recent_events || []).filter((event) => {
    const sourceIp = String(event.source_ip || "").toLowerCase();
    const device = String(event.device_name || "").toLowerCase();
    const type = String(event.event_type || "").toLowerCase();
    return sourceIp.includes(ipFilter) && device.includes(deviceFilter) && type.includes(typeFilter);
  });

  recentEvents.innerHTML = filteredEvents
    .map((event) => `
      <tr>
        <td>${escapeText(formatTime(event.timestamp))}</td>
        <td>${escapeText(event.device_name)}</td>
        <td>${escapeText(event.event_type)}</td>
        <td class="severity-${escapeText(event.severity)}">${escapeText(event.severity)}</td>
        <td class="payload" title="${escapeText(event.payload)}">${escapeText(event.payload)}</td>
        <td>${escapeText(event.source_ip)}</td>
      </tr>
    `)
    .join("");

  recentCowrie.innerHTML = (stats.recent_cowrie || [])
    .map((event) => `
      <tr>
        <td>${escapeText(formatTime(event.timestamp))}</td>
        <td>${escapeText(event.source_ip)}</td>
        <td>${escapeText(event.username)}</td>
        <td>${escapeText(event.eventid)}</td>
      </tr>
    `)
    .join("");
}

function chartData(chart) {
  return {
    labels: chart?.labels || [],
    datasets: [{
      data: chart?.values || [],
      borderColor: "#22d3ee",
      backgroundColor: ["#22d3ee", "#a78bfa", "#f59e0b", "#ef4444", "#10b981", "#60a5fa"],
      tension: 0.35,
      fill: false,
    }],
  };
}

function createCharts(stats) {
  state.charts.hour = new Chart(document.getElementById("eventsByHour"), {
    type: "line",
    data: chartData(stats.events_by_hour),
    options: chartOptions(false),
  });
  state.charts.severity = new Chart(document.getElementById("eventsBySeverity"), {
    type: "doughnut",
    data: chartData(stats.events_by_severity),
    options: chartOptions(true),
  });
  state.charts.type = new Chart(document.getElementById("eventsByType"), {
    type: "bar",
    data: chartData(stats.events_by_type),
    options: chartOptions(false),
  });
}

function chartOptions(hideAxes) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { labels: { color: "#cbd5e1" } },
    },
    scales: hideAxes ? {} : {
      x: { ticks: { color: "#94a3b8" }, grid: { color: "#1f2937" } },
      y: { beginAtZero: true, ticks: { color: "#94a3b8", precision: 0 }, grid: { color: "#1f2937" } },
    },
  };
}

function updateChart(instance, chart) {
  instance.data.labels = chart?.labels || [];
  instance.data.datasets[0].data = chart?.values || [];
  instance.update();
}

function renderStats(stats) {
  state.stats = stats;
  setMetric("totalEvents", stats.total_events);
  setMetric("totalDevices", stats.total_devices);
  setMetric("cowrieEvents", stats.cowrie_events);
  setMetric("last24h", stats.last_24h);
  renderTables(stats);

  if (state.charts.hour) {
    updateChart(state.charts.hour, stats.events_by_hour);
    updateChart(state.charts.severity, stats.events_by_severity);
    updateChart(state.charts.type, stats.events_by_type);
  }
}

async function refreshStats() {
  const response = await fetch("/api/stats");
  if (response.ok) renderStats(await response.json());
}

document.addEventListener("DOMContentLoaded", () => {
  // Attempt a development-only reset requested by the dashboard.
  fetch("/api/reset", { method: "POST" })
    .then((res) => {
      if (res.ok) return res.json();
      throw new Error("reset not allowed");
    })
    .then(() => {
      console.info("Dashboard requested DB reset; refreshing stats.");
      return refreshStats();
    })
    .catch(() => {
      // Ignore reset failures — reset may be disabled in production.
    })
    .finally(() => {
      renderStats(state.stats);
      createCharts(state.stats);
    });

  if (typeof io === "undefined") {
    // Fallback: Socket.IO client unavailable (CDN blocked or not served).
    // Use polling to keep the dashboard updated and show a clear status.
    setConnectionStatus("Polling", "badge text-bg-info");
    console.warn("Socket.IO client not available; falling back to polling /api/stats every 5s.");
    refreshStats();
    setInterval(refreshStats, 5000);
  } else {
    let socket = io({ transports: ["websocket", "polling"], reconnectionAttempts: 5 });
    setConnectionStatus("Connecting", "badge text-bg-warning");

    const attachHandlers = (s) => {
      s.on("connect", () => {
        setConnectionStatus("Live", "badge text-bg-success");
        refreshStats();
      });

      s.on("disconnect", () => {
        setConnectionStatus("Offline", "badge text-bg-danger");
      });

      s.on("connect_timeout", () => {
        setConnectionStatus("Offline", "badge text-bg-danger");
      });

      s.on("reconnect_attempt", () => {
        setConnectionStatus("Reconnecting", "badge text-bg-warning");
      });

      s.on("reconnect_failed", () => {
        setConnectionStatus("Offline", "badge text-bg-danger");
      });

      s.on("new_event", refreshStats);
      s.on("new_cowrie", refreshStats);
      s.on("stats_update", renderStats);
    };

    // Try normal connection first
    attachHandlers(socket);

    // If the connection fails due to protocol mismatch, attempt polling-only fallback once
    let triedPollingFallback = false;
    socket.on("connect_error", (err) => {
      console.warn("Socket connect_error", err);
      if (!triedPollingFallback) {
        triedPollingFallback = true;
        console.info("Attempting Socket.IO polling-only fallback...");
        try {
          socket.close();
        } catch (e) {}
        socket = io({ transports: ["polling"], reconnectionAttempts: 3, timeout: 5000 });
        attachHandlers(socket);
        setConnectionStatus("Reconnecting (polling)", "badge text-bg-warning");
      } else {
        setConnectionStatus("Offline", "badge text-bg-danger");
      }
    });
  }

  socket.on("connect", () => {
    setConnectionStatus("Live", "badge text-bg-success");
    refreshStats();
  });

  socket.on("disconnect", () => {
    setConnectionStatus("Offline", "badge text-bg-danger");
  });

  socket.on("connect_error", () => {
    setConnectionStatus("Offline", "badge text-bg-danger");
  });

  socket.on("connect_timeout", () => {
    setConnectionStatus("Offline", "badge text-bg-danger");
  });

  socket.on("reconnect_attempt", () => {
    setConnectionStatus("Reconnecting", "badge text-bg-warning");
  });

  socket.on("reconnect_failed", () => {
    setConnectionStatus("Offline", "badge text-bg-danger");
  });

  socket.on("new_event", refreshStats);
  socket.on("new_cowrie", refreshStats);
  socket.on("stats_update", renderStats);

  document.querySelectorAll(".filter-input").forEach((input) => {
    input.addEventListener("input", () => renderTables(state.stats));
  });
});
