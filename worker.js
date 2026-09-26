let runtime;
async function initialize() {
  const { loadPyodide } = await import('https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs');
  const py = await loadPyodide();
  for (const name of ['league_simulator.py', 'historical_calibration.py', 'web_runner.py']) {
    const response = await fetch(new URL(name, self.location.href));
    if (!response.ok) throw new Error(`Cannot load ${name}: HTTP ${response.status}`);
    py.FS.writeFile(name, await response.text());
  }
  await py.runPythonAsync('from web_runner import run_web');
  return py;
}
self.onmessage = async ({ data }) => {
  try {
    self.postMessage({ type: 'progress', stage: 'loading', done: 0, total: 0 });
    runtime ??= initialize().catch(error => { runtime = null; throw error; });
    const py = await runtime;
    py.globals.set('payload_json', JSON.stringify(data));
    py.globals.set('report_progress', (stage, done, total) => self.postMessage({ type: 'progress', stage, done, total }));
    const result = await py.runPythonAsync('run_web(payload_json, report_progress)');
    self.postMessage({ type: 'result', result: JSON.parse(result) });
  } catch (error) {
    self.postMessage({ type: 'error', message: error.message || String(error) });
  }
};
