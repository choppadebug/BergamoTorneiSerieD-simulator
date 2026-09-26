const $ = id => document.getElementById(id);
let worker, result, standingsChart, distributionChart;
let requestId = 0;
const uploads = new Map();
let manifestError = null;
const sliders = { simulations: v => Number(v).toLocaleString(), teams: v => v, legs: v => v,
  draw: v => `${v}%`, confidence: v => `${v}%`, magnitude: v => `${v}%` };
function syncControls() {
  for (const [id, format] of Object.entries(sliders)) $(`${id}-value`).textContent = format($(id).value);
  const n = +$('teams').value, legs = +$('legs').value;
  $('format-summary').textContent = `${legs * (n - 1)} matches per team · ${legs * n * (n - 1) / 2} fixtures per season`;
  $('history-controls').hidden = !$('history-enabled').checked;
}
syncControls();
$('settings').addEventListener('input', () => { syncControls(); if (result) $('stale').hidden = false; });
const sourcesReady = (async () => {
  try {
    const response = await fetch('input/manifest.json');
    if (!response.ok) throw new Error('Historical file list unavailable');
    const names = await response.json();
    $('sources').replaceChildren();
    for (const name of names) {
      const label = document.createElement('label'); label.className = 'check';
      const input = document.createElement('input'); input.type = 'checkbox'; input.checked = true; input.value = name;
      label.append(input, document.createTextNode(name)); $('sources').append(label);
    }
  } catch (error) { manifestError = error; $('sources').textContent = `${error.message}. You can still add local CSVs.`; }
})();
$('uploads').addEventListener('change', () => {
  uploads.clear();
  for (const file of $('uploads').files) uploads.set(file.name, file);
});
function busy(value) {
  $('settings').disabled = value; $('run').disabled = value; $('cancel').hidden = !value;
  $('progress').hidden = !value;
  if (value) $('progress').removeAttribute('value');
}
function fail(message) { busy(false); $('status').className = 'error'; $('status').textContent = message; }
$('cancel').addEventListener('click', () => {
  requestId++;
  worker?.terminate(); worker = null; busy(false);
  $('status').textContent = 'Cancelled. You can run again; the Python runtime will reload.';
});
$('simulation-form').addEventListener('submit', async event => {
  event.preventDefault();
  const currentRequest = ++requestId;
  busy(true); $('status').className = ''; $('status').textContent = 'Preparing simulation…';
  try {
    if (!window.Chart) throw new Error('The chart library did not load. Check your internet connection and reload.');
    const magnitude = $('history-enabled').checked ? +$('magnitude').value / 100 : 0;
    const config = { simulations: +$('simulations').value, teams: +$('teams').value, legs: +$('legs').value,
      draw_probability: +$('draw').value / 100, confidence: +$('confidence').value / 100, seed: +$('seed').value };
    const sources = [];
    if (magnitude) {
      await sourcesReady;
      if (manifestError && !uploads.size) throw manifestError;
      for (const checkbox of $('sources').querySelectorAll('input:checked')) {
        if (uploads.has(checkbox.value)) continue;
        const response = await fetch(`input/${encodeURIComponent(checkbox.value)}`);
        if (!response.ok) throw new Error(`Cannot load ${checkbox.value}`);
        sources.push({ name: checkbox.value, text: await response.text() });
      }
      for (const [name, file] of uploads) sources.push({ name, text: await file.text() });
    }
    if (currentRequest !== requestId) return;
    if (!worker) {
      worker = new Worker('worker.js', { type: 'module' });
      worker.onerror = event => { fail(`Browser runtime error: ${event.message}. Check your connection and retry.`); worker?.terminate(); worker = null; };
      worker.onmessage = ({ data }) => {
        if (data.type === 'progress') {
          const texts = { loading: 'Preparing Python in your browser. The first download can take a moment…',
            calibrating: 'Fitting historical team strengths. This can take a little longer on mobile…',
            simulating: `Simulating ${data.done.toLocaleString()} of ${data.total.toLocaleString()} seasons…` };
          $('status').textContent = texts[data.stage];
          if (data.total) $('progress').value = data.done / data.total * 100;
        } else if (data.type === 'error') fail(data.message);
        else if (data.type === 'result') {
          busy(false); result = data.result;
          try { render(); $('status').textContent = 'Simulation complete. Explore the results or adjust your assumptions.'; }
          catch (error) { fail(`Could not display results: ${error.message}`); }
        }
      };
    }
    worker.postMessage({ config, magnitude, sources });
  } catch (error) { if (currentRequest === requestId) fail(error.message); }
});
function chartOptions(yTitle, xTitle) {
  return { responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
    scales: { x: { title: { display: true, text: xTitle }, grid: { display: false } },
      y: { beginAtZero: true, title: { display: true, text: yTitle }, grid: { color: '#edf1ed' } } } };
}
function renderStandings() {
  const rows = result.rows;
  const datasets = [
    { label: 'Lower bound', data: rows.map(r => r.lower_points), borderWidth: 0, pointRadius: 0 },
    { label: 'Upper bound', data: rows.map(r => r.upper_points), borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(8,127,114,.13)' },
    { label: 'Median', data: rows.map(r => r.median_points), borderColor: '#087f72', backgroundColor: '#087f72', borderWidth: 3, pointRadius: 3 }
  ];
  if ($('show-mean').checked) datasets.push({ label: 'Mean', data: rows.map(r => r.mean_points), borderColor: '#6578ad', pointRadius: 2, borderDash: [3, 3] });
  if ($('show-benchmark').checked) datasets.push({ label: 'Top-k benchmark', data: rows.map(r => r.conservative_top_k_benchmark), borderColor: '#c34d28', pointRadius: 2, borderDash: [6, 4] });
  standingsChart?.destroy();
  standingsChart = new Chart($('standings-chart'), { type: 'line', data: { labels: rows.map(r => r.position), datasets }, options: chartOptions('Points', 'Finishing position') });
}
function fillTable(body, rows) {
  body.replaceChildren();
  for (const values of rows) {
    const tr = document.createElement('tr');
    for (const value of values) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
    body.append(tr);
  }
}
function renderDistribution() {
  if (!result) return;
  const rank = +$('focus-rank').value, row = result.rows[rank - 1];
  $('focus-rank-value').textContent = rank;
  const maxPoints = 3 * result.config.legs * (result.config.teams - 1);
  const counts = result.distributions[rank - 1];
  const labels = Array.from({ length: maxPoints + 1 }, (_, i) => i);
  const percentages = labels.map(points => 100 * (counts[points] || 0) / result.config.simulations);
  $('focus-summary').textContent = `Position ${rank}: median ${row.median_points} points, with a central ${Math.round(result.config.confidence * 100)}% range of ${row.lower_points}–${row.upper_points}.`;
  distributionChart?.destroy();
  const options = chartOptions('Simulated seasons (%)', 'Points'); options.plugins.legend.display = false;
  options.plugins.tooltip = { callbacks: { label: context => `${context.parsed.y.toFixed(2)}% · ${counts[context.label] || 0} seasons` } };
  distributionChart = new Chart($('distribution-chart'), { type: 'bar', data: { labels, datasets: [{ label: 'Frequency (%)', data: percentages,
    backgroundColor: labels.map(p => p >= row.lower_points && p <= row.upper_points ? '#087f72' : '#b7c9c1'), borderRadius: 2 }] }, options });
  fillTable($('distribution-body'), labels.filter(p => counts[p]).map(p => [p, counts[p], `${percentages[p].toFixed(2)}%`]));
}
function render() {
  const { config, calibration } = result, confidence = Math.round(config.confidence * 100);
  $('empty').hidden = true; $('results').hidden = false; $('stale').hidden = true;
  $('metric-runs').textContent = config.simulations.toLocaleString();
  $('metric-draw').textContent = `${(100 * config.draw_probability).toFixed(2)}%`;
  $('metric-strength').textContent = config.strength_spread.toFixed(2);
  $('run-summary').textContent = `${config.teams} teams · ${config.legs} legs · ${config.legs * (config.teams - 1)} games per team · Seed ${config.seed} · Historical influence ${Math.round(100 * result.magnitude)}%`;
  $('range-explanation').textContent = `Where each position lands across ${config.simulations.toLocaleString()} seasons, with central ${confidence}% prediction ranges.`;
  $('table-caption').textContent = `Points by finishing position · central ${confidence}% ranges`;
  const maximum = 3 * config.legs * (config.teams - 1);
  fillTable($('standings-body'), result.rows.map(r => [r.position, r.mean_points.toFixed(2), r.median_points,
    `${r.lower_points}–${r.upper_points}`, `${r.conservative_top_k_benchmark}${r.conservative_top_k_benchmark > maximum ? '*' : ''}`]));
  $('focus-rank').max = config.teams; $('focus-rank').value = Math.min(+$('focus-rank').value, config.teams);
  $('assumptions').textContent = calibration ? 'Anonymous teams have different strengths, drawn afresh each season and held fixed for its matches. Historical influence blends the fitted strength spread and draw rate with the baseline.' : 'All teams are equally strong. Each match uses the selected draw probability, with either team equally likely to win a decisive match.';
  $('calibration-report').replaceChildren();
  if (calibration) {
    const heading = document.createElement('p'); heading.textContent = `Historical fit: ${(calibration.draw_probability * 100).toFixed(2)}% draws; strength spread ${calibration.strength_spread.toFixed(2)}.`;
    const list = document.createElement('ul');
    for (const name of calibration.included) { const li = document.createElement('li'); li.textContent = `Included: ${name}`; list.append(li); }
    for (const [name, reason] of calibration.excluded) { const li = document.createElement('li'); li.textContent = `Skipped: ${name} — ${reason}`; list.append(li); }
    $('calibration-report').append(heading, list);
    if (calibration.strength_spread === 4) { const warning = document.createElement('p'); warning.className = 'notice'; warning.textContent = 'The fit reached its search boundary (4.0). Treat this calibration cautiously.'; $('calibration-report').append(warning); }
  }
  renderStandings(); renderDistribution();
}
$('focus-rank').addEventListener('input', renderDistribution);
for (const id of ['show-mean', 'show-benchmark']) $(id).addEventListener('change', () => { if (result) renderStandings(); });
$('download').addEventListener('click', () => {
  if (!result) return;
  const metadata = { simulations: result.config.simulations, teams: result.config.teams, legs: result.config.legs,
    confidence: result.config.confidence, seed: result.config.seed, historical_calibration: result.magnitude,
    effective_draw_probability: result.config.draw_probability, strength_spread: result.config.strength_spread };
  const rows = result.rows.map(row => ({ ...row, ...metadata })), keys = Object.keys(rows[0]);
  const csv = [keys.join(','), ...rows.map(row => keys.map(key => row[key]).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = 'bergamo-serie-d-projections.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
