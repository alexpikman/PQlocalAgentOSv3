// ═══ TELEMETRY (fake data, ready for real backend) ═══
(function () {
  'use strict';

  const HISTORY_MAX = 60;
  const history = { cpu: [], ram: [], gpu: [] };
  let currentChart = 'cpu';

  function fakeStats() {
    return {
      cpu: { percent: 2 + Math.random() * 18, name: 'Intel64 Family 6 Model 186' },
      ram: { percent: 88 + Math.random() * 8, used: 14.0 + Math.random() * 1.2, total: 15.7 },
      gpu: { percent: Math.random() * 30, name: 'NVIDIA RTX 4060 Laptop', vramUsed: 3.0 + Math.random() * 0.6, vramTotal: 8.0 },
      disks: [
        { mount: 'C:\\', percent: 91.9, used: 228.9, free: 20.2, total: 249.1 },
        { mount: 'D:\\', percent: 98.1, used: 548.2, free: 10.7, total: 558.9 }
      ]
    };
  }

  // Future backend: replace with fetch('/api/system/stats').then(r => r.json())
  async function fetchStats() {
    return fakeStats();
  }

  function setBar(id, percent) {
    const bar = document.getElementById(id);
    if (!bar) return;
    const track = bar.parentElement;
    bar.style.width = Math.min(100, Math.max(0, percent)) + '%';
    track.classList.toggle('warn', percent >= 70 && percent < 90);
    track.classList.toggle('danger', percent >= 90);
  }

  function render() {
    const state = document.getElementById('sysmon-state');
    if (state) state.textContent = 'обновлено ' + new Date().toLocaleTimeString('ru-RU');
  }

  async function tick() {
    const stats = await fetchStats();
    ['cpu', 'ram', 'gpu'].forEach((key) => {
      history[key].push(stats[key].percent);
      if (history[key].length > HISTORY_MAX) history[key].shift();
    });

    const cpuVal = document.getElementById('sysmon-cpu-val');
    const cpuName = document.getElementById('sysmon-cpu-name');
    if (cpuVal) cpuVal.textContent = Math.round(stats.cpu.percent) + '%';
    if (cpuName) cpuName.textContent = stats.cpu.name + ' · ' + Math.round(stats.cpu.percent) + '% загрузки';
    setBar('sysmon-cpu-bar', stats.cpu.percent);

    const ramVal = document.getElementById('sysmon-ram-val');
    const ramDetail = document.getElementById('sysmon-ram-detail');
    if (ramVal) ramVal.textContent = Math.round(stats.ram.percent) + '%';
    if (ramDetail) ramDetail.textContent = stats.ram.used.toFixed(1) + ' ГБ из ' + stats.ram.total.toFixed(1) + ' ГБ';
    setBar('sysmon-ram-bar', stats.ram.percent);

    const gpuVal = document.getElementById('sysmon-gpu-val');
    const gpuDetail = document.getElementById('sysmon-gpu-detail');
    if (gpuVal) gpuVal.textContent = Math.round(stats.gpu.percent) + '%';
    if (gpuDetail) gpuDetail.textContent = 'RTX 4060 · VRAM ' + stats.gpu.vramUsed.toFixed(1) + ' / ' + stats.gpu.vramTotal.toFixed(0) + ' ГБ';
    setBar('sysmon-gpu-bar', stats.gpu.percent);

    const diskList = document.getElementById('sysmon-disks');
    if (diskList) {
      diskList.innerHTML = stats.disks.map((disk) => {
        const level = disk.percent >= 90 ? 'danger' : disk.percent >= 70 ? 'warn' : '';
        return '<div class="sysmon-disk"><div class="sysmon-disk-head"><b>' + disk.mount + '</b><span>' + Math.round(disk.percent) + '%</span></div><div class="sysmon-track ' + level + '"><i style="width:' + disk.percent + '%"></i></div><div class="sysmon-detail">' + disk.used.toFixed(1) + ' ГБ занято · ' + disk.free.toFixed(1) + ' ГБ свободно</div></div>';
      }).join('');
    }

    render();
    const modal = document.getElementById('sysmon-chart-modal');
    if (modal && !modal.hidden) drawChart(currentChart);
  }

  function drawChart(kind) {
    const data = history[kind];
    if (!data || !data.length) return;
    const width = 600, height = 200, padding = 10;
    const stepX = (width - padding * 2) / (HISTORY_MAX - 1);
    const offset = HISTORY_MAX - data.length;
    const points = data.map((value, index) => {
      const x = padding + (offset + index) * stepX;
      const y = height - padding - (value / 100) * (height - padding * 2);
      return [x, y];
    });
    const line = 'M ' + points.map((point) => point[0].toFixed(1) + ' ' + point[1].toFixed(1)).join(' L ');
    const area = line + ' L ' + (padding + (HISTORY_MAX - 1) * stepX).toFixed(1) + ' ' + (height - padding) + ' L ' + padding + ' ' + (height - padding) + ' Z';
    const lineEl = document.getElementById('sysmon-chart-line');
    const areaEl = document.getElementById('sysmon-chart-area');
    const dotEl = document.getElementById('sysmon-chart-dot');
    if (lineEl) lineEl.setAttribute('d', line);
    if (areaEl) areaEl.setAttribute('d', area);
    if (dotEl) {
      const last = points[points.length - 1];
      dotEl.setAttribute('cx', last[0]);
      dotEl.setAttribute('cy', last[1]);
    }

    let grid = '';
    for (let i = 0; i <= 4; i++) {
      const y = padding + i * (height - padding * 2) / 4;
      grid += '<line class="sysmon-grid-line" x1="' + padding + '" y1="' + y + '" x2="' + (width - padding) + '" y2="' + y + '"/>';
      grid += '<text class="sysmon-axis-label" x="' + (width - padding + 4) + '" y="' + (y + 3) + '">' + (100 - i * 25) + '%</text>';
    }
    const gridEl = document.getElementById('sysmon-chart-grid');
    if (gridEl) gridEl.innerHTML = grid;

    const now = data[data.length - 1];
    const average = data.reduce((sum, value) => sum + value, 0) / data.length;
    const maximum = Math.max.apply(null, data);
    const nowEl = document.getElementById('sysmon-chart-now');
    const averageEl = document.getElementById('sysmon-chart-avg');
    const maxEl = document.getElementById('sysmon-chart-max');
    if (nowEl) nowEl.textContent = Math.round(now) + '%';
    if (averageEl) averageEl.textContent = Math.round(average) + '%';
    if (maxEl) maxEl.textContent = Math.round(maximum) + '%';
  }

  const chartTitles = {
    cpu: 'Процессор · история нагрузки',
    ram: 'Память · история нагрузки',
    gpu: 'Видеокарта · история нагрузки'
  };

  function bind() {
    document.querySelectorAll('[data-sysmon-chart]').forEach((card) => {
      card.addEventListener('click', () => {
        currentChart = card.dataset.sysmonChart;
        const title = document.getElementById('sysmon-chart-title');
        if (title) title.textContent = chartTitles[currentChart];
        const modal = document.getElementById('sysmon-chart-modal');
        if (modal) modal.hidden = false;
        drawChart(currentChart);
      });
    });

    const close = document.getElementById('sysmon-chart-close');
    if (close) close.addEventListener('click', () => {
      const modal = document.getElementById('sysmon-chart-modal');
      if (modal) modal.hidden = true;
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bind();
    tick();
    setInterval(tick, 2000);
  });
})();