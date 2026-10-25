// Public MediaMarkt/Saturn pages only. No account, cart, CAPTCHA or queue operations.
export function allowedTarget(value) {
  try {
    const u = new URL(value);
    return u.href === value && u.protocol === 'https:' &&
      ['www.mediamarkt.de', 'www.saturn.de'].includes(u.hostname) &&
      !u.port && !u.username && !u.password && !u.search && !u.hash &&
      !/%|\.\./.test(u.pathname) &&
      (u.pathname === '/robots.txt' ||
       /^\/de\/(product|category|brand)\/[a-zA-Z0-9_/-]+(?:\.html)?$/.test(u.pathname));
  } catch { return false; }
}

export default {
  async fetch(request, env) {
    const headers = { 'Cache-Control': 'no-store' };
    if (!env.READER_TOKEN || env.READER_TOKEN.length < 32)
      return new Response('Reader not configured', {status: 503, headers});
    if (request.headers.get('Authorization') !== `Bearer ${env.READER_TOKEN}`)
      return new Response('Unauthorized', {status: 401, headers});
    const endpoint = new URL(request.url);
    const target = endpoint.searchParams.get('url');
    if (request.method !== 'GET' || endpoint.pathname !== '/read' || !allowedTarget(target))
      return new Response('Unsupported public page', {status: 400, headers});
    try {
      const response = await fetch(target, {
        method: 'GET', redirect: 'manual', signal: AbortSignal.timeout(20000),
        headers: {'User-Agent': 'TCGRetailWatch/1.0', 'Cache-Control': 'no-cache'},
        cf: {cacheTtl: 0, cacheEverything: false},
      });
      // Never follow redirects or reinterpret an HTTP error as product data.
      let body = '';
      if (response.status === 200) {
        const reader = response.body.getReader();
        const chunks = []; let size = 0;
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          size += value.length;
          if (size > 12000000) { await reader.cancel(); throw new Error('Too large'); }
          chunks.push(value);
        }
        const bytes = new Uint8Array(size); let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
        body = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
      } else { await response.body?.cancel(); }
      return Response.json({url: target, status: response.status,
        fetched_at: Date.now() / 1000, body}, {headers});
    } catch {
      return new Response('Upstream unavailable', {status: 502, headers});
    }
  }
};
