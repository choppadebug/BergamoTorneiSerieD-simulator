// Restricted CORS bridge: only public Bergamo standings and calendar operations.
const ROOT = 'https://www.bergamotornei.com';
export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    const allowed = env.ALLOWED_ORIGIN;
    const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Vary': 'Origin' };
    if (origin && origin === allowed) headers['Access-Control-Allow-Origin'] = origin;
    const reply = (data, status = 200) => new Response(JSON.stringify(data), { status, headers });
    if (origin && origin !== allowed) return reply({ error: 'Origin not allowed' }, 403);
    if (request.method !== 'GET') return reply({ error: 'GET only' }, 405);
    try {
      const query = new URL(request.url).searchParams;
      const source = new URL(query.get('url'));
      const path = source.pathname.match(/^\/it\/t-teamtable\/(\d+)\/[a-zA-Z0-9_-]+\/?$/);
      if (source.protocol !== 'https:' || !['www.bergamotornei.com', 'bergamotornei.com'].includes(source.hostname) || source.port || source.username || source.password || source.search || source.hash || !path) throw new Error('Use an HTTPS Bergamo Tornei standings URL');
      const round = query.get('round');
      if (round !== null && !/^\d{1,10}$/.test(round)) throw new Error('Invalid league identifier');
      async function load(url, body) {
        const response = await fetch(url, { method: body ? 'POST' : 'GET', body,
          redirect: 'error', signal: AbortSignal.timeout(25000) });
        if (!response.ok) throw new Error(`Source returned HTTP ${response.status}`);
        const text = await response.text();
        if (text.length > 4000000) throw new Error('Source response is too large');
        return text;
      }
      const data = { source_url: `${ROOT}${source.pathname.replace(/\/$/, '')}/`, fetched_at: new Date().toISOString() };
      const body = new URLSearchParams({ op: round ? '22' : '20', tid: path[1], round: round || 'all' });
      const response = JSON.parse(await load(`${ROOT}/system/include/ajax/public/league.php`, body));
      if (response.errors || typeof response.html !== 'string') throw new Error('Source returned an invalid response');
      if (round) data.calendar_html = response.html;
      else { data.page_html = await load(data.source_url); data.standings_html = response.html; }
      return reply(data);
    } catch (error) { return reply({ error: error.message }, 400); }
  }
};
