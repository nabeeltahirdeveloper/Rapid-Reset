const $ = (id) => document.getElementById(id);

function fmtPercent(v) { return `${Math.round(v)}%`; }
function fmtUptime(s) {
  const d = Math.floor(s / 86400); s %= 86400;
  const h = Math.floor(s / 3600); s %= 3600;
  const m = Math.floor(s / 60); s = Math.floor(s % 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(' ');
}

function createLineChart(ctx, label, color) {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label,
        data: [],
        borderColor: color,
        backgroundColor: color + '33',
        borderWidth: 2,
        tension: 0.25,
        pointRadius: 0,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { labels: { color: '#e6e9f0' } } },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { min: 0, max: 100, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

const cpuChart = createLineChart(document.getElementById('cpu-chart'), 'CPU %', '#00d1ff');
const memChart = createLineChart(document.getElementById('mem-chart'), 'Memory %', '#7c4dff');

const loadChart = new Chart(document.getElementById('load-chart'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      { label: 'Load 1m', data: [], borderColor: '#00d1ff', backgroundColor: '#00d1ff33', borderWidth: 2, tension: 0.25, pointRadius: 0, fill: true },
      { label: 'Load 5m', data: [], borderColor: '#7c4dff', backgroundColor: '#7c4dff33', borderWidth: 2, tension: 0.25, pointRadius: 0, fill: true },
      { label: 'Load 15m', data: [], borderColor: '#ff4976', backgroundColor: '#ff497633', borderWidth: 2, tension: 0.25, pointRadius: 0, fill: true },
    ]
  },
  options: {
    responsive: true,
    animation: false,
    plugins: { legend: { labels: { color: '#e6e9f0' } } },
    scales: {
      x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
      y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
    }
  }
});

function pushPoint(chart, value) {
  const ts = new Date().toLocaleTimeString();
  chart.data.labels.push(ts);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > 60) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
}

function pushLoad(loads) {
  const ts = new Date().toLocaleTimeString();
  loadChart.data.labels.push(ts);
  loadChart.data.datasets[0].data.push(loads[0] ?? 0);
  loadChart.data.datasets[1].data.push(loads[1] ?? 0);
  loadChart.data.datasets[2].data.push(loads[2] ?? 0);
  if (loadChart.data.labels.length > 60) {
    loadChart.data.labels.shift();
    loadChart.data.datasets.forEach(d => d.data.shift());
  }
  loadChart.update();
}

async function fetchMetrics() {
  try {
    const res = await fetch('/metrics');
    const json = await res.json();
    const s = json.metrics.system;
    const p = json.metrics.process;
    const svr = json.metrics.server || {};

    $('cpu-value').innerText = fmtPercent(s.cpu_percent);
    $('mem-value').innerText = fmtPercent(s.memory_percent);
    $('uptime-value').innerText = fmtUptime(s.uptime_seconds);
    $('threads-value').innerText = p.num_threads;
    $('rps-1s').innerText = (svr.rps_1s ?? 0).toString();
    $('rps-60s').innerText = (svr.rps_60s ?? 0).toString();
    $('queue-size').innerText = `${svr.queue_size ?? 0}/${svr.queue_maxsize ?? '-'}`;
    if (svr.rate_limit) {
      $('ratelimit').innerText = `${svr.rate_limit.active_clients} clients • ${svr.rate_limit.limit}/${svr.rate_limit.window_seconds}s`;
    }

    pushPoint(cpuChart, s.cpu_percent);
    pushPoint(memChart, s.memory_percent);
    if (Array.isArray(s.load_avg)) pushLoad(s.load_avg);

    // Workers
    const workers = svr.workers || [];
    const wEl = document.getElementById('workers');
    if (wEl) {
      wEl.innerHTML = '';
      workers.forEach(w => {
        const row = document.createElement('div');
        row.className = 'row';
        const badgeClass = w.busy ? 'badge-red' : 'badge-green';
        const state = w.busy ? 'BUSY' : 'IDLE';
        const path = w.last_path || '-';
        const since = w.last_started_at ? new Date(w.last_started_at * 1000).toLocaleTimeString() : '';
        row.innerHTML = `
          <div class="badge ${badgeClass}">Worker #${w.worker_id} • ${state}</div>
          <div>${path}</div>
          <div>${since}</div>
        `;
        wEl.appendChild(row);
      });
    }

    // Endpoints
    const endpoints = svr.endpoints || [];
    const eEl = document.getElementById('endpoints');
    if (eEl) {
      eEl.innerHTML = '';
      endpoints.forEach(ep => {
        const row = document.createElement('div');
        row.className = 'row';
        row.innerHTML = `
          <div class="badge badge-purple">${ep.count} hits</div>
          <div>${ep.path}</div>
          <div>${ep.avg_ms}ms avg • ${ep.max_ms}ms max</div>
        `;
        eEl.appendChild(row);
      });
    }

    // Recent requests
    const recent = svr.recent_requests || [];
    const rEl = document.getElementById('recent');
    if (rEl) {
      rEl.innerHTML = '';
      recent.slice().reverse().forEach(req => {
        const row = document.createElement('div');
        row.className = 'row';
        row.innerHTML = `
          <div class="badge badge-cyan">${req.timestamp.split('T')[1] || req.timestamp}</div>
          <div>${req.method} ${req.path}</div>
          <div>${req.response_time_ms} ms</div>
        `;
        rEl.appendChild(row);
      });
    }
  } catch (e) {
    // ignore fetch errors to keep UI running
  }
}

function tickClock() {
  $('clock').innerText = new Date().toLocaleString();
}

setInterval(fetchMetrics, 1000);
setInterval(tickClock, 1000);
tickClock();
fetchMetrics();


