// Enhanced Dashboard for HTTP/2 Rapid Reset Attack Analysis
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

class EnhancedServerDashboard {
  constructor() {
    this.serverId = $('server-id')?.textContent || 'unknown';
    this.updateInterval = 1000; // 1 second for real-time monitoring
    this.charts = {};
    this.isUpdating = false;
    this.attackDetectionThreshold = 50; // RPS threshold for attack detection
    this.currentPhase = 'normal';
    this.attackStartTime = null;
    this.init();
  }

  init() {
    this.setupCharts();
    this.startUpdating();
    this.setupEventListeners();
  }

  setupCharts() {
    // Legacy CPU/Memory charts (keep existing functionality)
    const cpuChart = this.createLineChart($('cpu-chart'), 'CPU %', '#00d1ff');
    const memChart = this.createLineChart($('mem-chart'), 'Memory %', '#7c4dff');
    
    if (cpuChart) this.charts.cpu = cpuChart;
    if (memChart) this.charts.memory = memChart;

    // Enhanced queue metrics chart
    const queueCtx = $('queue-chart')?.getContext('2d');
    if (queueCtx) {
      this.charts.queue = new Chart(queueCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Total Queue Size',
              data: [],
              borderColor: 'rgb(255, 99, 132)',
              backgroundColor: 'rgba(255, 99, 132, 0.1)',
              tension: 0.1,
              fill: true
            },
            {
              label: 'Abandoned Requests',
              data: [],
              borderColor: 'rgb(255, 159, 64)',
              backgroundColor: 'rgba(255, 159, 64, 0.1)',
              tension: 0.1,
              fill: true
            },
            {
              label: 'Active Requests',
              data: [],
              borderColor: 'rgb(54, 162, 235)',
              backgroundColor: 'rgba(54, 162, 235, 0.1)',
              tension: 0.1,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Request Count'
              }
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Queue State & Abandonment Tracking'
            }
          }
        }
      });
    }

    // Client connection tracking chart
    const connectionCtx = $('connection-chart')?.getContext('2d');
    if (connectionCtx) {
      this.charts.connections = new Chart(connectionCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Active Connections',
              data: [],
              borderColor: 'rgb(75, 192, 192)',
              backgroundColor: 'rgba(75, 192, 192, 0.1)',
              tension: 0.1,
              fill: true
            },
            {
              label: 'Disconnected Clients',
              data: [],
              borderColor: 'rgb(255, 205, 86)',
              backgroundColor: 'rgba(255, 205, 86, 0.1)',
              tension: 0.1,
              fill: true
            },
            {
              label: 'Abandoned Clients',
              data: [],
              borderColor: 'rgb(201, 203, 207)',
              backgroundColor: 'rgba(201, 203, 207, 0.1)',
              tension: 0.1,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Client Count'
              }
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Client Connection Lifecycle'
            }
          }
        }
      });
    }

    // Attack pattern detection chart
    const attackCtx = $('attack-chart')?.getContext('2d');
    if (attackCtx) {
      this.charts.attack = new Chart(attackCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Requests/sec',
              data: [],
              borderColor: 'rgb(153, 102, 255)',
              backgroundColor: 'rgba(153, 102, 255, 0.1)',
              tension: 0.1,
              yAxisID: 'y'
            },
            {
              label: 'Queue Utilization %',
              data: [],
              borderColor: 'rgb(255, 99, 132)',
              backgroundColor: 'rgba(255, 99, 132, 0.1)',
              tension: 0.1,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          interaction: {
            mode: 'index',
            intersect: false
          },
          scales: {
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: {
                display: true,
                text: 'Requests/sec'
              }
            },
            y1: {
              type: 'linear',
              display: true,
              position: 'right',
              max: 100,
              title: {
                display: true,
                text: 'Queue Utilization %'
              },
              grid: {
                drawOnChartArea: false
              }
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Attack Pattern Detection'
            }
          }
        }
      });
    }
  }

  createLineChart(ctx, label, color) {
    if (!ctx) return null;
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

  async updateDashboard() {
    if (this.isUpdating) return;
    this.isUpdating = true;

    try {
      // Fetch all metrics
      const [metricsResponse, queueResponse, connectionResponse] = await Promise.allSettled([
        fetch('/metrics'),
        fetch('/api/queue-metrics'),
        fetch('/api/client-connections')
      ]);

      // Update legacy metrics
      if (metricsResponse.status === 'fulfilled') {
        const metrics = await metricsResponse.value.json();
        if (metrics.status === 'success') {
          this.updateLegacyMetrics(metrics.metrics);
        }
      }

      // Update enhanced metrics
      if (queueResponse.status === 'fulfilled') {
        const queueData = await queueResponse.value.json();
        if (queueData.status === 'success') {
          this.updateEnhancedQueueMetrics(queueData.queue_metrics);
        }
      }

      if (connectionResponse.status === 'fulfilled') {
        const connectionData = await connectionResponse.value.json();
        if (connectionData.status === 'success') {
          this.updateConnectionMetrics(connectionData.connection_metrics);
        }
      }

      // Update attack detection
      if (metricsResponse.status === 'fulfilled' && queueResponse.status === 'fulfilled') {
        const metrics = await metricsResponse.value.json();
        const queueData = await queueResponse.value.json();
        if (metrics.status === 'success' && queueData.status === 'success') {
          this.updateAttackDetection(metrics.metrics, queueData.queue_metrics);
        }
      }

    } catch (error) {
      console.error('Failed to update enhanced dashboard:', error);
      this.displayError('Dashboard update failed: ' + error.message);
    } finally {
      this.isUpdating = false;
    }
  }

  updateLegacyMetrics(metrics) {
    const s = metrics.system;
    const p = metrics.process;
    const svr = metrics.server || {};

    // Update basic metrics
    if ($('cpu-value')) $('cpu-value').innerText = fmtPercent(s.cpu_percent);
    if ($('mem-value')) $('mem-value').innerText = fmtPercent(s.memory_percent);
    if ($('uptime-value')) $('uptime-value').innerText = fmtUptime(s.uptime_seconds);
    if ($('threads-value')) $('threads-value').innerText = p.num_threads;
    if ($('rps-1s')) $('rps-1s').innerText = (svr.rps_1s ?? 0).toString();
    if ($('rps-60s')) $('rps-60s').innerText = (svr.rps_60s ?? 0).toString();

    // Update charts
    if (this.charts.cpu) {
      this.pushPoint(this.charts.cpu, s.cpu_percent);
    }
    if (this.charts.memory) {
      this.pushPoint(this.charts.memory, s.memory_percent);
    }
  }

  pushPoint(chart, value) {
    const ts = new Date().toLocaleTimeString();
    chart.data.labels.push(ts);
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > 60) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
    chart.update('none');
  }

  updateEnhancedQueueMetrics(queueMetrics) {
    const timestamp = new Date().toLocaleTimeString();
    
    if (this.charts.queue) {
      const chart = this.charts.queue;
      chart.data.labels.push(timestamp);
      
      chart.data.datasets[0].data.push(queueMetrics.queue.total_size);
      chart.data.datasets[1].data.push(queueMetrics.metrics.total_abandoned);
      chart.data.datasets[2].data.push(queueMetrics.metrics.active_requests);
      
      this.maintainChartDataSize(chart, 30);
      chart.update('none');
    }

    // Update queue status cards
    this.updateElement('queue-size', queueMetrics.queue.total_size);
    this.updateElement('queue-utilization', queueMetrics.queue.utilization_percent.toFixed(1) + '%');
    this.updateElement('abandoned-requests', queueMetrics.metrics.total_abandoned);
    this.updateElement('abandonment-rate', queueMetrics.metrics.abandonment_rate.toFixed(2) + '%');
  }

  updateConnectionMetrics(connectionMetrics) {
    const timestamp = new Date().toLocaleTimeString();
    
    if (this.charts.connections) {
      const chart = this.charts.connections;
      chart.data.labels.push(timestamp);
      
      chart.data.datasets[0].data.push(connectionMetrics.active_clients);
      chart.data.datasets[1].data.push(connectionMetrics.disconnected_clients);
      chart.data.datasets[2].data.push(connectionMetrics.abandoned_clients);
      
      this.maintainChartDataSize(chart, 30);
      chart.update('none');
    }

    // Update connection status cards
    this.updateElement('active-connections', connectionMetrics.active_clients);
    this.updateElement('total-connections', connectionMetrics.total_connections);
    this.updateElement('reconnections', connectionMetrics.total_reconnections);
  }

  updateAttackDetection(systemMetrics, queueMetrics) {
    const timestamp = new Date().toLocaleTimeString();
    const currentRPS = systemMetrics.enhanced_queue?.metrics?.requests_per_second || systemMetrics.server?.rps_1s || 0;
    const queueUtilization = queueMetrics.queue.utilization_percent;
    
    if (this.charts.attack) {
      const chart = this.charts.attack;
      chart.data.labels.push(timestamp);
      
      chart.data.datasets[0].data.push(currentRPS);
      chart.data.datasets[1].data.push(queueUtilization);
      
      this.maintainChartDataSize(chart, 50);
      chart.update('none');
    }

    // Attack phase detection
    this.detectAndUpdatePhase(currentRPS, queueUtilization);
    
    // Update attack patterns
    this.detectAttackPatterns(systemMetrics, queueMetrics);
  }

  detectAndUpdatePhase(currentRPS, queueUtilization) {
    let newPhase = 'normal';
    
    if (currentRPS > this.attackDetectionThreshold || queueUtilization > 80) {
      newPhase = 'attack';
      if (!this.attackStartTime) {
        this.attackStartTime = Date.now();
      }
    } else if (this.attackStartTime && (Date.now() - this.attackStartTime) > 10000) {
      newPhase = 'recovery';
    }

    if (newPhase !== this.currentPhase) {
      this.currentPhase = newPhase;
      this.updatePhaseIndicators();
    }

    if (newPhase === 'normal' && this.attackStartTime && 
        (Date.now() - this.attackStartTime) > 60000) {
      this.attackStartTime = null;
    }
  }

  updatePhaseIndicators() {
    const phaseElement = $('current-phase');
    if (phaseElement) {
      phaseElement.textContent = this.currentPhase.toUpperCase();
      phaseElement.className = `badge ${this.getPhaseClass()}`;
    }

    this.updatePhaseAlerts();
  }

  getPhaseClass() {
    switch (this.currentPhase) {
      case 'attack': return 'badge-red';
      case 'recovery': return 'badge-orange';
      default: return 'badge-green';
    }
  }

  updatePhaseAlerts() {
    const alertContainer = $('phase-alerts');
    if (!alertContainer) return;

    alertContainer.innerHTML = '';

    if (this.currentPhase === 'attack') {
      alertContainer.innerHTML = `
        <div class="alert alert-danger">
          <strong>Attack Detected!</strong> High request rate and queue utilization detected.
        </div>
      `;
    } else if (this.currentPhase === 'recovery') {
      const recoveryTime = this.attackStartTime ? 
        Math.round((Date.now() - this.attackStartTime) / 1000) : 0;
      
      alertContainer.innerHTML = `
        <div class="alert alert-warning">
          <strong>Recovery Phase</strong> Server recovering from attack. Recovery time: ${recoveryTime}s
        </div>
      `;
    }
  }

  detectAttackPatterns(systemMetrics, queueMetrics) {
    const patterns = [];
    
    // Rapid reset pattern detection
    if (queueMetrics.metrics.abandonment_rate > 50) {
      patterns.push('Rapid Reset Attack');
    }
    
    // Queue overflow pattern
    if (queueMetrics.queue.utilization_percent > 90) {
      patterns.push('Queue Overflow');
    }
    
    // Connection exhaustion pattern
    if (queueMetrics.clients?.active_clients > 100) {
      patterns.push('High Connection Count');
    }

    // Update attack patterns display
    const patternsElement = $('attack-patterns');
    if (patternsElement) {
      if (patterns.length > 0) {
        patternsElement.innerHTML = patterns.map(pattern => 
          `<span class="badge badge-orange">${pattern}</span>`
        ).join(' ');
      } else {
        patternsElement.innerHTML = '<span class="badge badge-green">No Threats</span>';
      }
    }
  }

  // Profiling controls
  async startProfiling() {
    try {
      const phase = this.currentPhase;
      const response = await fetch(`/api/profiling/start/${phase}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'manual_profiling', started_by: 'dashboard' })
      });

      const result = await response.json();
      if (result.status === 'success') {
        this.displaySuccess('Profiling started for phase: ' + phase);
      } else {
        this.displayError('Failed to start profiling: ' + result.message);
      }
    } catch (error) {
      this.displayError('Profiling start error: ' + error.message);
    }
  }

  async stopProfiling() {
    try {
      const phase = this.currentPhase;
      const response = await fetch(`/api/profiling/stop/${phase}`, { method: 'POST' });

      const result = await response.json();
      if (result.status === 'success') {
        this.displaySuccess('Profiling stopped for phase: ' + phase);
      } else {
        this.displayError('Failed to stop profiling: ' + result.message);
      }
    } catch (error) {
      this.displayError('Profiling stop error: ' + error.message);
    }
  }

  // Utility methods
  updateElement(id, value) {
    const element = $(id);
    if (element) {
      element.textContent = value;
    }
  }

  maintainChartDataSize(chart, maxSize) {
    if (chart.data.labels.length > maxSize) {
      const excess = chart.data.labels.length - maxSize;
      chart.data.labels.splice(0, excess);
      chart.data.datasets.forEach(dataset => {
        dataset.data.splice(0, excess);
      });
    }
  }

  displayError(message) {
    this.showNotification(message, 'error');
  }

  displaySuccess(message) {
    this.showNotification(message, 'success');
  }

  showNotification(message, type) {
    console.log(`${type.toUpperCase()}: ${message}`);
  }

  setupEventListeners() {
    // Profiling buttons
    const startProfilingBtn = $('start-profiling');
    if (startProfilingBtn) {
      startProfilingBtn.addEventListener('click', () => this.startProfiling());
    }

    const stopProfilingBtn = $('stop-profiling');
    if (stopProfilingBtn) {
      stopProfilingBtn.addEventListener('click', () => this.stopProfiling());
    }

    // Refresh interval control
    const intervalSelect = $('refresh-interval');
    if (intervalSelect) {
      intervalSelect.addEventListener('change', (e) => {
        this.updateInterval = parseInt(e.target.value);
        this.startUpdating();
      });
    }

    // Manual refresh
    const refreshBtn = $('manual-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.updateDashboard());
    }
  }

  startUpdating() {
    this.stopUpdating();
    this.updateDashboard();
    this.updateTimer = setInterval(() => this.updateDashboard(), this.updateInterval);
  }

  stopUpdating() {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
  }
}

// Legacy support - keep the original fetchMetrics for compatibility
async function fetchMetrics() {
  if (window.enhancedDashboard) {
    // Let enhanced dashboard handle it
    return;
  }
  
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

    // Legacy workers display
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
  } catch (e) {
    // ignore fetch errors to keep UI running
  }
}

function tickClock() {
  $('clock').innerText = new Date().toLocaleString();
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
  // Try to initialize enhanced dashboard
  if ($('queue-chart') || $('connection-chart') || $('attack-chart')) {
    window.enhancedDashboard = new EnhancedServerDashboard();
  } else {
    // Fall back to legacy dashboard
    setInterval(fetchMetrics, 1000);
    setInterval(tickClock, 1000);
    tickClock();
    fetchMetrics();
  }
});
