// Public MediaMarkt/Saturn pages only. No account, cart, CAPTCHA or queue operations.
export function allowedTarget(value) {
  try {
    const u=new URL(value);
    if (u.href!==value || u.protocol!=='https:' || u.port || u.username || u.password || u.hash || /%|\.\./.test(u.pathname)) return false;
    if (['www.mediamarkt.de','www.saturn.de'].includes(u.hostname))
      return !u.search && (u.pathname==='/robots.txt' || /^\/de\/(product|category|brand)\/[a-zA-Z0-9_/-]+(?:\.html)?$/.test(u.pathname));
    if (u.hostname==='www.duo-shop.de') return !u.search && (u.pathname==='/robots.txt' ||
      u.pathname==='/produkte/spielzeug/sammelkarten/' || /^\/offers\/[a-zA-Z0-9-]+\/$/.test(u.pathname));
    if (!['www.vedes.com','www.faix.de'].includes(u.hostname)) return false;
    if (u.pathname==='/robots.txt') return !u.search;
    const prefix=u.hostname==='www.faix.de'?'/faix-online-shop-darmstadt':'';
    if (!u.pathname.startsWith(prefix+'/')) return false;
    const path=u.pathname.slice(prefix.length), params=[...u.searchParams];
    const subsidiary=params.length===1 && params[0][0]==='subsidiary[__identity]' && /^\d{9}$/.test(params[0][1]);
    if (/^\/(m|s|k)\/[a-z0-9/-]+$/.test(path)) return !u.search;
    if (/^\/(p|status\/json)\/[a-z0-9-]+$/.test(path)) return subsidiary;
    if (path==='/c/impressum' && u.hostname==='www.faix.de') return !u.search;
    return path==='/modals/showcontentpage' && params.length===2 &&
      /^\d{9}$/.test(u.searchParams.get('subsidiary[__identity]')||'') &&
      /^[a-f0-9-]{36}$/.test(u.searchParams.get('contentPage[__identity]')||'');
  } catch { return false; }
}

// Public region preference, not a customer session; no basket/account endpoint.
const regionCookies=new Map();
async function publicResponse(target,env) {
  const u=new URL(target), headers={'User-Agent':'TCGRetailWatch/1.0','Cache-Control':'no-cache'};
  if (u.hostname==='www.duo-shop.de') {
    if (!env.BROWSER) throw new Error('Browser binding unavailable');
    const robots=u.pathname==='/robots.txt';
    const cache=robots && typeof caches!=='undefined' ? caches.default : null;
    if (cache) { const hit=await cache.match(target); if(hit)return hit; }
    const r=await env.BROWSER.quickAction('content',{url:target,
      gotoOptions:{waitUntil:'networkidle2',timeout:20000},rejectResourceTypes:['image','media','font']});
    if(!r.ok)return r;
    const raw=await r.text();
    if(raw.length>12000000)throw new Error('Too large');
    let body=raw;
    if(raw.trim().startsWith('{')) {const parsed=JSON.parse(raw);if(typeof parsed.result!=='string')throw new Error('Browser data invalid');body=parsed.result;}
    if(robots) {
      let result='';
      await new HTMLRewriter().on('pre',{text(chunk){result+=chunk.text;}}).transform(new Response(body)).text();
      if(!/^User-agent:/im.test(result))throw new Error('Robots unavailable');
      body=result;
    }
    const response=new Response(body,{headers:{'Cache-Control':robots?'public, max-age=21600':'no-store'}});
    if(cache)await cache.put(target,response.clone());
    return response;
  }
  if(['www.vedes.com','www.faix.de'].includes(u.hostname) && u.pathname!=='/robots.txt') {
    const prefix=u.hostname==='www.faix.de'?'/faix-online-shop-darmstadt':'';
    let saved=regionCookies.get(u.origin);
    if(!saved || saved.until<Date.now()) {
    const loc=await fetch(u.origin+prefix+'/geolocation/updatelocation',{
      method:'POST',redirect:'manual',headers:{...headers,'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},
      body:new URLSearchParams({'location[latitude]':'50.1038972','location[longitude]':'8.5756857','location[zip]':'65934',
        'location[city]':'Frankfurt am Main','location[country]':'Deutschland','location[countryCode]':'DE',priority:'1'}),signal:AbortSignal.timeout(10000)});
    if(!loc.ok)throw new Error('Region unavailable');
    const cookies=loc.headers.getSetCookie().map(s=>s.split(';')[0]).join('; ');
    await loc.body?.cancel();
    if(!cookies)throw new Error('Region unavailable');
    saved={cookie:cookies,until:Date.now()+300000};regionCookies.set(u.origin,saved);
    }
    headers.Cookie=saved.cookie;
  }
  return fetch(target,{method:'GET',redirect:'manual',signal:AbortSignal.timeout(20000),headers,cf:{cacheTtl:0,cacheEverything:false}});
}

// GitHub OIDC avoids a long-lived shared secret. Trust only this repository's main scan.
let keyCache;
const decode = value => Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')), c=>c.charCodeAt(0));
export async function githubAuthorized(token, env, audience, diagnostic = {}) {
  const reject = reason => { diagnostic.reason = reason; return false; };
  let stage = 'DECODE';
  try {
    if (typeof token !== 'string' || token.length > 20000) return reject('TOKEN_FORMAT');
    const parts = token.split('.');
    if (parts.length !== 3) return reject('TOKEN_FORMAT');
    const header = JSON.parse(new TextDecoder().decode(decode(parts[0])));
    const claims = JSON.parse(new TextDecoder().decode(decode(parts[1])));
    stage = 'CLAIMS';
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
    stage = 'KEY_FETCH';
    if (!keyCache || keyCache.until < now) {
      const response = await fetch('https://token.actions.githubusercontent.com/.well-known/jwks',
        {redirect:'manual',headers:{'User-Agent':'TCGRetailWatch/1.0'},signal:AbortSignal.timeout(5000),cf:{cacheTtl:300}});
      if (!response.ok) return reject('JWKS_HTTP');
      const text = await response.text();
      if (text.length > 100000) return reject('JWKS_SIZE');
      stage = 'KEY_PARSE';
      const keys = JSON.parse(text).keys;
      if (!Array.isArray(keys)) return reject('JWKS_FORMAT');
      keyCache = {keys, until:now+300};
    }
    const jwk = keyCache.keys.find(k=>k.kid===header.kid && k.kty==='RSA' && k.alg==='RS256');
    if (!jwk) return reject('KEY_NOT_FOUND');
    stage = 'KEY_IMPORT';
    const key = await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
    stage = 'SIGNATURE';
    const valid = await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));
    return valid || reject('SIGNATURE');
  } catch (e) {
    const name = ['TypeError','DataError','InvalidCharacterError','SyntaxError','OperationError','NotSupportedError','AbortError','TimeoutError'].includes(e.name) ? e.name.toUpperCase() : 'ERROR';
    return reject(('ERR_'+stage+'_'+name).slice(0,30));
  }
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
      const response = await publicResponse(target, env);
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
