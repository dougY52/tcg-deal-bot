import worker, {allowedTarget, githubAuthorized} from './worker.mjs';
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

// Real RSA signatures, mocked GitHub public-key endpoint; no live credentials.
const pair = await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
  publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const jwk = {...await crypto.subtle.exportKey('jwk',pair.publicKey), kid:'test-key', alg:'RS256'};
const oidcEnv = {GITHUB_REPOSITORY:'dougY52/tcg-deal-bot',GITHUB_REPOSITORY_ID:'1375726655',GITHUB_OWNER_ID:'306408342'};
const now = Math.floor(Date.now()/1000);
const claims = {iss:'https://token.actions.githubusercontent.com',aud:'https://reader.example.workers.dev',
  repository:oidcEnv.GITHUB_REPOSITORY,repository_id:oidcEnv.GITHUB_REPOSITORY_ID,
  repository_owner_id:oidcEnv.GITHUB_OWNER_ID,ref:'refs/heads/main',
  sub:'repo:dougY52/tcg-deal-bot:ref:refs/heads/main',event_name:'schedule',
  workflow_ref:'dougY52/tcg-deal-bot/.github/workflows/cloud-watch.yml@refs/heads/main',
  exp:now+300,iat:now,nbf:now};
const base64 = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
const encoded = obj => base64(new TextEncoder().encode(JSON.stringify(obj)));
async function sign(changes={}, head={alg:'RS256',kid:'test-key'}) {
  const value = encoded(head)+'.'+encoded({...claims,...changes});
  return value+'.'+base64(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(value)));
}
try {
  // Workers rejects redirect:'error' before sending. Use manual and reject 3xx.
  globalThis.fetch=async(url,options)=> {
    assert(url==='https://token.actions.githubusercontent.com/.well-known/jwks','fixed signing-key URL');
    assert(options.redirect==='manual','Workers-compatible redirect protection');
    return new Response('',{status:302,headers:{Location:'https://untrusted.example/keys'}});
  };
  const redirectDiagnostic={};
  assert(!await githubAuthorized(await sign(),oidcEnv,claims.aud,redirectDiagnostic),'redirected signing keys rejected');
  assert(redirectDiagnostic.reason==='JWKS_HTTP','redirect rejection is explicit');
  globalThis.fetch=async(url,options)=> {
    assert(options.redirect==='manual','JWKS request must support Workers runtime');
    return Response.json({keys:[jwk]});
  };
  assert(await githubAuthorized(await sign(),oidcEnv,claims.aud),'valid signed identity');
  assert(await githubAuthorized(await sign({sub:'repo:dougY52@306408342/tcg-deal-bot@1375726655:ref:refs/heads/main'}),oidcEnv,claims.aud),'immutable subject');
  for (const change of [{repository_id:'other'},{repository:'other/repo'},{repository_owner_id:'other'},
    {ref:'refs/heads/other'},{sub:'repo:other/repo:ref:refs/heads/main'},
    {event_name:'pull_request'},{workflow_ref:'other-workflow'},
    {iss:'https://evil.test'},{aud:'other'},{exp:now-1},{iat:now+100},{nbf:now+100},{exp:now+2000}])
    assert(!await githubAuthorized(await sign(change),oidcEnv,claims.aud),'reject invalid claims '+JSON.stringify(change));
  assert(!await githubAuthorized(await sign({}, {alg:'none',kid:'test-key'}),oidcEnv,claims.aud),'reject wrong algorithm');
  const signed=await sign();
  const [head,body,signature]=signed.split('.');
  const tampered=head+'.'+encoded({...claims,iat:now-1})+'.'+signature;
  assert(!await githubAuthorized(tampered,oidcEnv,claims.aud),'reject tampered signature');
  assert(!await githubAuthorized('bad.token.signature',oidcEnv,claims.aud),'reject malformed token');
  globalThis.fetch=async()=>new Response('live product');
  assert((await worker.fetch(request(target,signed),oidcEnv)).status===200,'valid job can read');
  assert((await worker.fetch(request(target,'bad'),oidcEnv)).status===401,'invalid job denied');
  console.log('GitHub OIDC signature and authorization checks passed');
} finally {globalThis.fetch=originalFetch;}

// Public local-retailer transport cannot forward arbitrary URLs or writes.
const vedes='https://www.vedes.com/p/test-61214461?subsidiary%5B__identity%5D=100971990';
const duo='https://www.duo-shop.de/offers/pokemon-box-32E0448B/';
for(const url of [vedes,vedes.replace('/p/','/status/json/'),duo,'https://www.faix.de/faix-online-shop-darmstadt/c/impressum'])assert(allowedTarget(url),'retailer allowlist');
for(const url of [vedes+'&token=x',vedes.replace('100971990','oops'),'https://www.duo-shop.de/cart/',
  'https://www.vedes.com/basketupdate/addtobasket','https://www.vedes.com/geolocation/updatelocation'])assert(!allowedTarget(url),'no cart/private/arbitrary write');
try {
  let regionRequests=0;
  globalThis.fetch=async(url,options)=>{
    if(url.endsWith('/geolocation/updatelocation')) {
      regionRequests++;
      assert(options.method==='POST','fixed location preference only');
      assert(options.body.get('location[zip]')==='65934','actual user region');
      assert(!options.headers.Authorization && !options.headers.Cookie,'no user credentials');
      return new Response('{}',{headers:{'Set-Cookie':'anonymous-region=test; Path=/; Secure'}});
    }
    assert(url===vedes && options.method==='GET' && options.redirect==='manual','exact public product');
    assert(options.headers.Cookie==='anonymous-region=test','only anonymous region cookie');
    return new Response('product');
  };
  const result=await(await worker.fetch(request(vedes),env)).json();
  assert(result.status===200 && regionRequests===1,'region then exact product');
  globalThis.fetch=async()=>{throw new Error('duo uses browser binding');};
  const browserEnv={...env,BROWSER:{async quickAction(action,options){
    assert(action==='content' && options.url===duo,'exact public browser navigation');
    assert(options.gotoOptions.timeout===20000,'bounded browser timeout');
    return Response.json({result:'<html>current exact offer</html>'});
  }}};
  const rendered=await(await worker.fetch(request(duo),browserEnv)).json();
  assert(rendered.body==='<html>current exact offer</html>','browser envelope decoded');
  browserEnv.BROWSER.quickAction=async()=>new Response('budget reached',{status:429});
  const limited=await(await worker.fetch(request(duo),browserEnv)).json();
  assert(limited.status===429 && limited.body==='','free quota fails closed');
  globalThis.fetch=async(url)=>url===vedes?new Response('unavailable',{status:403}):new Response('canonical same-product form');
  browserEnv.BROWSER.quickAction=async()=>{throw new Error('canonical public HTML already available');};
  const canonical=await(await worker.fetch(request(vedes),browserEnv)).json();
  assert(canonical.status===200 && canonical.body==='canonical same-product form','canonical public product before browser');
  globalThis.fetch=async()=>new Response('unavailable',{status:403});
  browserEnv.BROWSER.quickAction=async(action,options)=>{
    assert(action==='content' && options.url===vedes,'VEDES ordinary browser on exact page');
    return Response.json({result:'<html>public VEDES product</html>'});
  };
  const fallback=await(await worker.fetch(request(vedes),browserEnv)).json();
  assert(fallback.status===200 && fallback.body.includes('public VEDES'),'bounded normal browser fallback');
  globalThis.fetch=async()=>new Response('rate limit',{status:429});
  browserEnv.BROWSER.quickAction=async()=>{throw new Error('must not retry rate limit with browser');};
  const rateLimited=await(await worker.fetch(request(vedes),browserEnv)).json();
  assert(rateLimited.status===429,'rate limits respected, no browser retry');
  console.log('VEDES region and duo free-browser transport checks passed');
} finally {globalThis.fetch=originalFetch;}
