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

// GitHub OIDC avoids a long-lived shared secret. Trust only this repository's main scan.
let keyCache;
const decode = value => Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')), c=>c.charCodeAt(0));
export async function githubAuthorized(token, env, audience, diagnostic = {}) {
  const reject = reason => { diagnostic.reason = reason; return false; };
  try {
    if (typeof token !== 'string' || token.length > 20000) return reject('TOKEN_FORMAT');
    const parts = token.split('.');
    if (parts.length !== 3) return reject('TOKEN_FORMAT');
    const header = JSON.parse(new TextDecoder().decode(decode(parts[0])));
    const claims = JSON.parse(new TextDecoder().decode(decode(parts[1])));
    const now = Date.now()/1000;
    const repo = env.GITHUB_REPOSITORY, repoId = env.GITHUB_REPOSITORY_ID, ownerId = env.GITHUB_OWNER_ID;
    if (!repo || !repoId || !ownerId || header.alg !== 'RS256' || typeof header.kid !== 'string') return reject('TOKEN_HEADER');
    const [owner, name] = repo.split('/');
    const subjects = [`repo:${repo}:ref:refs/heads/main`, `repo:${owner}@${ownerId}/${name}@${repoId}:ref:refs/heads/main`];
    const checks = {
      ISSUER: claims.iss === 'https://token.actions.githubusercontent.com',
      AUDIENCE: claims.aud === audience,
      REPOSITORY: claims.repository === repo && claims.repository_id === repoId && claims.repository_owner_id === ownerId,
      BRANCH: claims.ref === 'refs/heads/main',
      SUBJECT: subjects.includes(claims.sub),
      WORKFLOW: claims.workflow_ref === `${repo}/.github/workflows/cloud-watch.yml@refs/heads/main`,
      EVENT: ['schedule','workflow_dispatch','push'].includes(claims.event_name),
      TIME: [claims.exp,claims.iat,claims.nbf].every(x=>typeof x==='number' && Number.isFinite(x)) &&
        claims.exp > now && claims.nbf <= now+10 && claims.iat <= now+10 && claims.iat >= now-600 && claims.exp-claims.iat <= 900,
    };
    for (const [reason, valid] of Object.entries(checks)) if (!valid) return reject(reason);
    if (!keyCache || keyCache.until < now) {
      const response = await fetch('https://token.actions.githubusercontent.com/.well-known/jwks',
        {redirect:'error',headers:{'User-Agent':'TCGRetailWatch/1.0'},signal:AbortSignal.timeout(5000),cf:{cacheTtl:300}});
      if (!response.ok) return reject('JWKS_HTTP');
      const text = await response.text();
      if (text.length > 100000) return reject('JWKS_SIZE');
      const keys = JSON.parse(text).keys;
      if (!Array.isArray(keys)) return reject('JWKS_FORMAT');
      keyCache = {keys, until:now+300};
    }
    const jwk = keyCache.keys.find(k=>k.kid===header.kid && k.kty==='RSA' && k.alg==='RS256');
    if (!jwk) return reject('KEY_NOT_FOUND');
    const key = await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
    const valid = await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));
    return valid || reject('SIGNATURE');
  } catch { return reject('VERIFY_ERROR'); }
}

export default {
  async fetch(request, env) {
    const headers = { 'Cache-Control': 'no-store' };
    const shared = env.READER_TOKEN && env.READER_TOKEN.length >= 32;
    const oidc = env.GITHUB_REPOSITORY && env.GITHUB_REPOSITORY_ID && env.GITHUB_OWNER_ID;
    if (!shared && !oidc) return new Response('Reader not configured', {status: 503, headers});
    const endpoint = new URL(request.url);
    const bearer = request.headers.get('Authorization') || '';
    const validShared = shared && bearer === `Bearer ${env.READER_TOKEN}`;
    const diagnostic = {};
    if (!validShared && !(oidc && bearer.startsWith('Bearer ') &&
        await githubAuthorized(bearer.slice(7), env, endpoint.origin, diagnostic))) {
      headers['X-TCG-Auth-Error'] = diagnostic.reason || 'MISSING_TOKEN';
      return new Response('Unauthorized', {status: 401, headers});
    }
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
