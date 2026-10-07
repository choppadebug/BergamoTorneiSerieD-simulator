(() => {
  const el = id => document.getElementById(id);
  const DEFAULT = el('live-url').value;
  let baseline, snapshot, league, matches, forecast, liveWorker, pending, busy = false, baselineBusy = false;
  let generation = 0, aborter;
  let chancesChart, finalChart, timelineChart;
  const connectionReady = fetch('live-config.json').then(r => r.ok ? r.json() : {}).then(c => {
    if (c.proxy_url) el('live-proxy').value = c.proxy_url;
  }).catch(() => {});
  function status(text, error = false) { el('live-status').textContent = text; el('live-status').className = error ? 'error' : ''; }
  function lock(value) {
    busy = value; el('live-controls').disabled = value || baselineBusy;
    el('live-cancel').hidden = !value; el('live-progress').hidden = !value;
    if (value) el('live-progress').removeAttribute('value');
    el('run').disabled = value || baselineBusy;
  }
  function stop() {
    generation++; aborter?.abort(); liveWorker?.terminate(); liveWorker = null;
    if (pending) { pending.reject(new Error('Cancelled')); pending = null; }
    lock(false); status('Cancelled. Ready to try again.');
  }
  el('live-cancel').addEventListener('click', stop);
  async function task(fn) {
    const token = ++generation; aborter = new AbortController(); lock(true);
    try { await fn(token); }
    catch (error) { if (token === generation) status(error.message, true); }
    finally { if (token === generation) lock(false); }
  }
  function python(payload) {
    if (!liveWorker) {
      liveWorker = new Worker('worker.js', { type: 'module' });
      liveWorker.onerror = event => { pending?.reject(new Error(event.message)); pending = null; liveWorker?.terminate(); liveWorker = null; };
      liveWorker.onmessage = ({ data }) => {
        if (data.type === 'progress') {
          status(data.total ? `Projecting ${data.done.toLocaleString()} / ${data.total.toLocaleString()} seasons…` : 'Preparing Python and checking source data…');
          if (data.total) el('live-progress').value = data.done / data.total * 100;
        } else if (data.type === 'error') { pending?.reject(new Error(data.message)); pending = null; }
        else if (data.type === 'result') { pending?.resolve(data.result); pending = null; }
      };
    }
    return new Promise((resolve, reject) => { pending = { resolve, reject }; liveWorker.postMessage(payload); });
  }
  function sourceURL() {
    const u = new URL(el('live-url').value);
    if (u.protocol !== 'https:' || !['bergamotornei.com', 'www.bergamotornei.com'].includes(u.hostname) || u.port || u.username || u.password || u.search || u.hash || !/^\/it\/t-teamtable\/\d+\/[\w-]+\/?$/.test(u.pathname)) throw new Error('Enter an HTTPS Bergamo Tornei standings URL, using /it/t-teamtable/ID/name/.');
    u.hostname = 'www.bergamotornei.com'; u.pathname = u.pathname.replace(/\/$/, '') + '/'; return u.href;
  }
  async function jsonFetch(url) {
    const response = await fetch(url, { cache: 'no-store', signal: aborter.signal });
    if (!response.ok) throw new Error(`Import failed (HTTP ${response.status}). Check the proxy configuration or use a snapshot file.`);
    const data = await response.json(); if (data.error) throw new Error(data.error); return data;
  }
  async function endpoint() {
    await connectionReady;
    if (el('live-proxy').value.trim()) return el('live-proxy').value.trim();
    if (['localhost', '127.0.0.1'].includes(location.hostname)) return `${location.origin}/api/live`;
    return null;
  }
  async function rawImport(url, round) {
    const proxy = await endpoint();
    if (!proxy) throw new Error('Live imports need a configured proxy. Use the default tournament snapshot or import a JSON snapshot for this URL.');
    const u = new URL(proxy); u.searchParams.set('url', url); if (round) u.searchParams.set('round', round);
    return jsonFetch(u);
  }
  function populate(data, mode) {
    if (!Array.isArray(data.leagues) || !data.leagues.length || !data.source_url || !data.fetched_at) throw new Error('Invalid standings snapshot');
    snapshot = data; snapshot.mode = mode;
    el('live-url').value = data.source_url;
    const select = el('live-league'); select.replaceChildren();
    for (const l of data.leagues) { const option = new Option(l.name, l.id); select.add(option); }
    const preferred = data.leagues.find(l => /SERIE D/i.test(l.name)); if (preferred) select.value = preferred.id;
    select.disabled = false;
    el('live-source').textContent = `${mode} · Fetched ${new Date(data.fetched_at).toLocaleString()} · ${data.source_url}`;
    if (data.refresh_warning) el('live-source').textContent += ` · ${data.refresh_warning}`;
    if (Date.now() - Date.parse(data.fetched_at) > 36 * 3600000) el('live-source').textContent += ' · Older than 36 hours: refresh before relying on this forecast.';
    chooseLeague();
  }
  function chooseLeague() {
    league = snapshot.leagues.find(l => l.id === el('live-league').value);
    matches = snapshot.calendars?.[league.id] || null; forecast = null;
    el('live-results').hidden = true;
    el('live-team').replaceChildren();
    for (const t of league.teams) el('live-team').add(new Option(t.name, t.name));
    el('live-team').disabled = false; el('live-project').disabled = false;
    el('live-current').hidden = false;
    fillTable(el('live-current-body'), league.teams.map(t => [t.name, t.points, t.played, t.wins, t.draws, t.losses, t.goals_for, t.goals_against, t.goal_difference, t.fair_play]));
    el('live-rank').max = league.teams.length; el('live-rank').value = Math.min(3, league.teams.length);
  }
  document.addEventListener('baseline-busy', ({ detail }) => { baselineBusy = detail; el('live-controls').disabled = busy || detail; });
  document.addEventListener('baseline-complete', ({ detail }) => {
    baseline = { ...detail }; el('live-section').hidden = false; el('live-legs').value = baseline.legs;
    if (forecast) el('live-stale').hidden = false;
  });
  el('live-load').addEventListener('click', () => task(async token => {
    const url = sourceURL(); status('Fetching standings…');
    const proxy = await endpoint();
    let data, mode;
    if (!proxy && url === DEFAULT) { data = await jsonFetch('data/live.json'); mode = 'Published snapshot (not a live fetch)'; }
    else { const raw = await rawImport(url); if (token !== generation) return; data = await python({ action: 'parse_standings', raw }); mode = 'Live source'; }
    if (token !== generation) return;
    populate(data, mode); status('Choose your league and team, then project the remaining season.');
  }));
  el('live-file').addEventListener('change', () => task(async token => {
    const file = el('live-file').files[0]; if (!file) return;
    const data = JSON.parse(await file.text()); if (token !== generation) return;
    populate(data, 'Imported snapshot'); status('Snapshot loaded. Select your league and team.');
  }));
  el('live-league').addEventListener('change', chooseLeague);
  el('live-team').addEventListener('change', () => { if (forecast) renderLive(); });
  el('live-prior').addEventListener('input', () => { el('live-prior-value').textContent = el('live-prior').value; if (forecast) el('live-stale').hidden = false; });
  el('live-legs').addEventListener('change', () => { if (forecast) el('live-stale').hidden = false; });
  el('live-url').addEventListener('input', () => { el('live-project').disabled = true; if (forecast) el('live-stale').hidden = false; });
  el('live-project').addEventListener('click', () => task(async token => {
    if (!baseline || !league) throw new Error('Complete a baseline simulation and import standings first.');
    if (sourceURL() !== snapshot.source_url) throw new Error('Load the changed URL before projecting.');
    const config = { ...baseline, teams: league.teams.length, legs: +el('live-legs').value };
    if (!matches) {
      status('Loading the full fixture list…');
      const raw = await rawImport(snapshot.source_url, league.id);
      if (token !== generation) return;
      const parsed = await python({ action: 'parse_calendar', raw, season_start: snapshot.season_start });
      if (token !== generation) return; matches = parsed.matches;
    }
    const projected = await python({ action: 'project_live', config, league, matches, prior_games: +el('live-prior').value });
    if (token !== generation) return;
    forecast = projected; forecast.source_url = snapshot.source_url; forecast.fetched_at = snapshot.fetched_at;
    el('live-stale').hidden = true; renderLive(); status('Forecast complete. Change team or comparison position without rerunning. Refresh standings after new results.');
  }));
  function band(label, values, color) {
    return [{ label: `${label}: lower`, data: values.map(v => v.lower_points), pointRadius: 0, borderWidth: 0 },
      { label: `${label}: upper`, data: values.map(v => v.upper_points), pointRadius: 0, borderWidth: 0, fill: '-1', backgroundColor: color === '#087f72' ? 'rgba(8,127,114,.13)' : 'rgba(195,77,40,.1)' },
      { label: `${label}: median`, data: values.map(v => v.median_points), borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 2 }];
  }
  function selectedTeam() { return forecast.teams.find(t => t.name === el('live-team').value); }
  function renderTimeline() {
    if (!forecast) return;
    const rank = +el('live-rank').value - 1, i = forecast.teams.findIndex(t => t.name === el('live-team').value);
    el('live-rank-value').textContent = rank + 1;
    timelineChart?.destroy();
    timelineChart = new Chart(el('live-timeline-chart'), { type: 'line', data: {
      labels: forecast.timeline.map(t => t.date), datasets: [
        ...band(forecast.teams[i].name, forecast.timeline.map(t => t.teams[i]), '#087f72'),
        ...band(`Position ${rank + 1}`, forecast.timeline.map(t => t.positions[rank]), '#c34d28')
      ] }, options: chartOptions('Accumulated points', 'Scheduled date') });
  }
  function forecastRows() {
    const team = selectedTeam();
    return forecast.rows.map((r, i) => {
      const f = team.finishes[i], extra = Math.max(0, r.conservative_top_k_benchmark - team.current.points);
      return [r.position, `${(f.probability * 100).toFixed(2)}%`, r.median_points, `${r.lower_points}–${r.upper_points}`,
        f.points ? `${f.points.lower_points}–${f.points.upper_points} (${Math.round(f.probability * forecast.config.simulations)} samples)` : 'No samples',
        extra > 3 * team.remaining_games ? 'Unattainable' : extra];
    });
  }
  function renderLive() {
    el('live-results').hidden = false;
    const t = selectedTeam();
    el('live-summary').textContent = `${forecast.league} · ${t.name}: ${t.current.points} points from ${t.current.played} games; ${t.remaining_games} left. Projected final median: ${t.points.median_points} (${Math.round(forecast.config.confidence * 100)}% range ${t.points.lower_points}–${t.points.upper_points}). ${forecast.config.simulations.toLocaleString()} simulations · seed ${forecast.config.seed} · effective draw rate ${(forecast.effective_draw_probability * 100).toFixed(2)}%.`;
    chancesChart?.destroy(); finalChart?.destroy();
    chancesChart = new Chart(el('live-chances-chart'), { type: 'bar', data: { labels: t.finishes.map(f => f.position), datasets: [{ label: 'Finishing chance (%)', data: t.finishes.map(f => f.probability * 100), backgroundColor: '#087f72' }] }, options: chartOptions('Probability (%)', 'Final position') });
    finalChart = new Chart(el('live-final-chart'), { type: 'line', data: { labels: forecast.rows.map(r => r.position), datasets: band('Final points', forecast.rows, '#087f72') }, options: chartOptions('Points', 'Final position') });
    fillTable(el('live-forecast-body'), forecastRows());
    el('live-warnings').replaceChildren();
    for (const warning of forecast.warnings) { const p = document.createElement('p'); p.textContent = warning; el('live-warnings').append(p); }
    renderTimeline();
  }
  el('live-rank').addEventListener('input', renderTimeline);
  el('live-download').addEventListener('click', () => {
    if (!forecast) return;
    const team = selectedTeam();
    const rows = [['Position', 'Team chance', 'Rank median', 'Rank range', 'Team conditional range', 'Extra for benchmark', 'Team', 'League', 'Source', 'Fetched at', 'Simulations', 'Confidence', 'Seed'],
      ...forecastRows().map(row => [...row, team.name, forecast.league, forecast.source_url, forecast.fetched_at, forecast.config.simulations, forecast.config.confidence, forecast.config.seed])];
    const quote = x => `"${String(x).replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;
    const blob = new Blob([rows.map(row => row.map(quote).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = 'bergamo-team-forecast.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();
