// Runs against Wrangler's installed Miniflare/workerd, without additional packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const requireWrangler = createRequire(fs.realpathSync(path.resolve(process.argv[2])));
const {Miniflare, convertV4MiniflareOptions} = requireWrangler('miniflare');
const bundle = path.resolve(process.argv[3]);
// Keep Windows SQLite paths short; the full checkout path exceeds MAX_PATH.
const persist = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'tcg-cp-'));
const config = {email:'owner@example.invalid', password:'synthetic-password',pokemon_deals:true,
  webhook:'https://discord.com/api/webhooks/123456789012345678/synthetic_test_value_12345678901234567890'};
let inbox = [], sends = 0, profileWrites = 0;
let profile = {notification_enabled:true,allow_drop_notifications:true,dealz_auto_subscribe_enabled:false};
async function outbound(request) {
  const url = new URL(request.url);
  if (url.hostname === 'discord.com') { sends++; return Response.json({id:'test-receipt'}); }
  assert.equal(url.hostname, 'www.mycardpal.com');
  if (url.pathname.endsWith('/auth/login')) return Response.json({access_token:'synthetic-access-token'}, {headers:{'Set-Cookie':'refresh_token=synthetic; Secure; HttpOnly'}});
  if (url.pathname.endsWith('/users/me')) {
    if(request.method==='PUT'){profile={...profile,...await request.json()};profileWrites++;}
    return Response.json(profile);
  }
  if (url.pathname === '/api/notifications/') return Response.json({items:inbox,total:inbox.length});
  if (url.pathname.endsWith('/auth/stream-token')) return Response.json({token:'synthetic-stream-token'});
  if (url.pathname.endsWith('/notifications/stream')) {
    assert.equal(request.headers.get('Authorization'), null);
    return new Response('event: notification\ndata: {}\n\n', {headers:{'Content-Type':'text/event-stream'}});
  }
  throw new Error('Unexpected outbound request');
}
function start() {
  const options = convertV4MiniflareOptions({name:'cardpal-runtime-test',modules:true,scriptPath:bundle,
    compatibilityDate:'2026-10-24', cf:false, bindings:{GITHUB_OWNER_ID:'owner',GITHUB_REPOSITORY:'test/repo',GITHUB_REPOSITORY_ID:'1'},
    durableObjects:{CARDPAL_OWNER:{className:'CardPalOwner',useSQLite:true}}, outboundService:outbound});
  options.resourcePersistencePath = persist;
  options.verbose = true;
  options.handleUncaughtError = error => console.error('RUNTIME ERROR', error);
  return new Miniflare(options);
}
async function until(check) { for(let i=0;i<30;i++){ if(await check())return; await new Promise(r=>setTimeout(r,500)); } throw new Error('runtime timeout'); }
(async()=>{
  let mf=start(); console.log('runtime started');
  try {
    assert.equal((await mf.dispatchFetch('https://test/cardpal/status')).status,401,'private status requires OIDC');
    assert.equal((await mf.dispatchFetch('https://test/health')).status,200,'existing reader health preserved');
    console.log('route guards passed');
    let ns=await mf.getDurableObjectNamespace('CARDPAL_OWNER');
    let owner=ns.getByName('owner');
    console.log('owner stub obtained');
    await owner.configure(config); console.log('owner configured');
    await until(async()=> {const s=await owner.status();if(s.last_error)throw new Error(JSON.stringify(s));return s.baseline_at;});
    console.log('baseline alarm passed'); assert.equal(sends,0);assert.equal((await owner.status()).pokemon_deals_enabled,true);
    inbox=[{dedupe_key:'broadcast:pokecenter-drop:de:test',template:'Pokémon Center Deutschland live',
      url:'https://www.pokemoncenter.com/de-de/',created_at:new Date().toISOString()},
      {dedupe_key:'dealz|test',article_id:'b98ec690-f022-46db-a1a7-4cf3750b1450',created_at:new Date().toISOString()}];
    await until(async()=> (await owner.status()).sent===1);
    assert.equal(sends,1,'real alarm -> mocked SSE/inbox -> mocked Discord');
    await mf.dispose(); mf=start();
    ns=await mf.getDurableObjectNamespace('CARDPAL_OWNER');owner=ns.getByName('owner');
    assert.equal((await owner.status()).sent,1,'SQLite state survives runtime restart');
    const last=(await owner.status()).last_cycle_at;
    await until(async()=> (await owner.status()).last_cycle_at > last);
    assert.equal(sends,1,'restart does not resend');
    assert.equal(profileWrites,1,'subscription preferences updated once');
    assert.equal((await owner.discovery()).article_ids.length,1,'private discovery survives restart');
    assert(!JSON.stringify(await owner.status()).includes('synthetic-password'));
    console.log('Workers runtime passed: RPC, alarm delivery, SQLite restart/dedupe, private routes, reader preservation');
  } finally {await mf.dispose();fs.rmSync(persist,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
