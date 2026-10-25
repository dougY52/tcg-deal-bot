import worker, {allowedTarget} from './worker.mjs';
const assert = (value, message) => { if (!value) throw new Error(message); };
const target = 'https://www.mediamarkt.de/de/product/_pokemon-2974734.html';
const env = {READER_TOKEN: 'synthetic-test-token-0000000000000000'};
const request = (url=target, token=env.READER_TOKEN, method='GET') => new Request(
  'https://reader.example.workers.dev/read?url='+encodeURIComponent(url),
  {method, headers:{Authorization:'Bearer '+token}});
const originalFetch = globalThis.fetch;
let upstreamCalls = 0;
try {
  globalThis.fetch = async () => { upstreamCalls++; return new Response('product'); };
  assert((await worker.fetch(request(), {})).status===503,'unconfigured');
  assert((await worker.fetch(request(target,'wrong'),env)).status===401,'unauthorized');
  for (const url of ['https://evil.test/', 'https://www.mediamarkt.de/account',
      target+'?token=x', target+'#x', 'https://user@www.mediamarkt.de/de/product/x.html',
      'https://www.mediamarkt.de/de/product/../account',
      'https://www.mediamarkt.de/de/product/%2e%2e/account']) {
    assert(!allowedTarget(url),'allowlist: '+url);
    assert((await worker.fetch(request(url),env)).status===400,'invalid target');
  }
  assert((await worker.fetch(request(target,env.READER_TOKEN,'POST'),env)).status===400,'POST blocked');
  assert(upstreamCalls===0,'rejected requests never reach upstream');
  globalThis.fetch = async (url, options) => {
    assert(url===target,'exact target');
    assert(options.redirect==='manual','no redirect following');
    assert(!options.headers.Authorization && !options.headers.Cookie,'no credentials forwarded');
    assert(options.cf.cacheTtl===0,'no cached response');
    return new Response('live product');
  };
  const response = await worker.fetch(request(),env);
  const data = await response.json();
  assert(response.headers.get('cache-control')==='no-store','response no-store');
  assert(data.url===target && data.status===200 && data.body==='live product','exact response');
  assert(Math.abs(data.fetched_at-Date.now()/1000)<5,'fresh response');
  for (const status of [301,403,429,503]) {
    globalThis.fetch = async () => new Response('error page',{status});
    const data = await (await worker.fetch(request(),env)).json();
    assert(data.status===status && data.body==='','upstream status preserved');
  }
  globalThis.fetch = async () => { throw new Error('private diagnostic'); };
  assert((await worker.fetch(request(),env)).status===502,'network failure closed');
  globalThis.fetch = async () => new Response('x'.repeat(12000001));
  assert((await worker.fetch(request(),env)).status===502,'bounded response');
  console.log('Cloud reader Worker checks passed');
} finally { globalThis.fetch = originalFetch; }
