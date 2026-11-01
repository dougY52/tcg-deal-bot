import assert from 'node:assert/strict';
import {CardPalRelay, selectDrop, discordPayload, sseEvents, webhookURL} from './cardpal-relay.mjs';
const now = Date.parse('2026-11-01T22:00:00Z');
const row = {dedupe_key: 'broadcast:pokecenter-drop:de:1', template: 'Pokémon Center Deutschland Drop live',
  created_at: new Date(now - 1000).toISOString(), url: 'https://www.pokemoncenter.com/de-de/product/123/test'};
const config = {email: 'owner@example.invalid', password: 'synthetic', webhook: 'https://discord.com/api/webhooks/123456789012345678/synthetic_test_value_12345678901234567890'};
class Storage {
  constructor() { this.map = new Map(); this.alarm = null; }
  async get(k) { return structuredClone(this.map.get(k)); }
  async put(k, v) { this.map.set(k, structuredClone(v)); }
  async delete(k) { this.map.delete(k); }
  async getAlarm() { return this.alarm; }
  async setAlarm(t) { this.alarm = t; }
}
assert(webhookURL(config.webhook));
assert(!webhookURL(config.webhook + '?url=evil'));
const drop = await selectDrop(row, now);
assert(drop && drop.url.includes('/de-de/'));
for (const changes of [
  {url: 'https://www.pokemoncenter.com/en-gb/product/123/test'},
  {url: 'https://evil.example/de-de/'}, {template: 'UK drop live'},
  {template: 'Nicht für Deutschland'}, {template: 'Pokémon Center Deutschland morgen'},
  {dedupe_key: 'other-shop'}, {created_at: '2026-11-01T22:00:00'},
  {created_at: new Date(now - 3600000).toISOString()},
  {created_at: new Date(now + 60000).toISOString()},
]) assert.equal(await selectDrop({...row, ...changes}, now), null, JSON.stringify(changes));
assert.equal(await selectDrop({...row, template: 'Drop', url: ''}, now), null);
assert.deepEqual(discordPayload({...drop, title: '@everyone'}).allowed_mentions, {parse: []});
assert(discordPayload(drop).embeds[0].description.includes('nicht unabhängig bestätigt'));

const storage = new Storage(); let sent = 0;
const relay = new CardPalRelay(storage, async (url, options) => {
  assert.equal(url, config.webhook + '?wait=true'); assert.equal(options.redirect, 'manual');
  sent++; return Response.json({id: 'synthetic'});
}, () => now);
await relay.configure(config);
let health = await storage.get('health');
health.enabled_at = now - 60000;
await relay.processRows([row], config, health);
assert.equal(sent, 0, 'initial inbox is a quiet baseline');
const fresh = {...row, dedupe_key: row.dedupe_key + ':next'};
await relay.processRows([fresh], config, health);
assert.equal(sent, 1, 'new DE broadcast delivered');
await relay.processRows([fresh], config, health);
assert.equal(sent, 1, 'same event deduplicated');
const restarted = new CardPalRelay(storage, relay.network, () => now);
await restarted.processRows([fresh], config, await storage.get('health'));
assert.equal(sent, 1, 'dedupe survives process restart');
assert.equal((await restarted.status()).sent, 1);
assert(!JSON.stringify(await restarted.status()).includes(config.password), 'status excludes private configuration');
assert.equal((await restarted.status()).browser_minutes_used, 0);

let attempts = 0;
const failing = new CardPalRelay(storage, async () => { attempts++; throw new Error('SECRET_WEBHOOK'); }, () => now);
const ambiguous = {...row, dedupe_key: row.dedupe_key + ':timeout'};
await failing.processRows([ambiguous], config, health);
await failing.processRows([ambiguous], config, health);
assert.equal(attempts, 1, 'unknown Discord acknowledgement never blindly duplicated');
assert.equal((await failing.status()).delivery_unknown, 1);

let calls = [], networkMode = 'ok';
const state2 = new Storage();
const transport = async (url, options) => {
  calls.push(url.split('?')[0]);
  const h = new Headers(options.headers);
  assert.equal(options.redirect, 'manual');
  if (networkMode === 'fail') return new Response('PRIVATE', {status: 503});
  if (url.endsWith('/auth/login')) return Response.json({access_token: 'synthetic-access-token'}, {headers: {'Set-Cookie': 'refresh_token=synthetic; HttpOnly; Secure'}});
  if (url.endsWith('/users/me')) return Response.json({notification_enabled: true, allow_drop_notifications: true});
  if (url.includes('/notifications/?')) return Response.json({items: [], total: 0});
  if (url.endsWith('/auth/stream-token')) { assert.equal(h.get('Authorization'), 'Bearer synthetic-access-token'); return Response.json({token: 'synthetic-stream-token'}); }
  if (url.includes('/notifications/stream?')) {
    assert.equal(h.get('Authorization'), null, 'SSE uses only its scoped token');
    assert.equal(h.get('Cookie'), 'refresh_token=synthetic');
    return new Response('event: notification\ndata: {}\n\n: ping\n\n', {headers: {'Content-Type': 'text/event-stream'}});
  }
  throw new Error('unexpected endpoint');
};
const live = new CardPalRelay(state2, transport, () => now);
await live.configure(config); await live.cycle();
assert.equal((await live.status()).status, 'stream_connected');
assert.equal(calls.filter(x => x.endsWith('/auth/login')).length, 1);
await live.cycle();
assert.equal(calls.filter(x => x.endsWith('/auth/login')).length, 1, 'reuses persisted session');
assert.equal((await live.status()).sent, 0, 'heartbeat and empty inbox stay quiet');
networkMode = 'fail'; await live.cycle();
assert.equal((await live.status()).last_error, 'CARDPAL_HTTP_503');
assert.equal(await state2.getAlarm(), now + 15000, 'durable retry after failure');
assert(!JSON.stringify(await live.status()).includes('PRIVATE'));

const frames = [];
for await (const item of sseEvents(new Response(': ping\r\nevent: notification\r\ndata: {}\r\n\r\n').body)) frames.push(item);
assert.deepEqual(frames, [{event: 'notification', data: '{}'}]);
console.log('CardPal relay checks passed: Germany filter, baseline, delivery, persistent dedupe, timeout, SSE auth, reconnect, no browser');

// General Pokemon source activation is scoped; its raw alerts are NOT sent as deals.
let profile = {notification_enabled:true,allow_drop_notifications:true,
  dealz_auto_subscribe_enabled:false,dealz_auto_subscribe_franchises:[],dealz_threshold_percent:30};
let profileWrites=0;
const generalState=new Storage();
const general=new CardPalRelay(generalState,async(url,options)=>{
  if(url.endsWith('/users/me')) {
    if(options.method==='PUT') {
      const update=JSON.parse(options.body);profileWrites++;
      assert.deepEqual(Object.keys(update).sort(),['notification_enabled','allow_drop_notifications','dealz_auto_subscribe_enabled','dealz_auto_subscribe_franchises','dealz_threshold_percent'].sort());
      profile={...profile,...update};
    }
    return Response.json(profile);
  }
  return transport(url,options);
},()=>now);
networkMode='ok';
await general.configure({...config,pokemon_deals:true});await general.cycle();
assert.equal((await general.status()).pokemon_deals_enabled,true);
assert.equal(profile.dealz_threshold_percent,5);
assert.deepEqual(profile.dealz_auto_subscribe_franchises,['POKEMON']);
await general.cycle();assert.equal(profileWrites,1,'account preferences written only once');
const notice={dedupe_key:'dealz|new|pokemon',article_id:'b98ec690-f022-46db-a1a7-4cf3750b1450',created_at:new Date(now).toISOString()};
await general.processRows([notice],{...config,pokemon_deals:true},await generalState.get('health'));
assert.deepEqual((await general.discovery()).article_ids,[notice.article_id]);
assert.equal((await general.status()).sent,0,'general alerts are discovery only until shop validation');
profile.dealz_auto_subscribe_enabled=false;await general.cycle();
assert.equal(profileWrites,1,'later owner settings are not silently overwritten');
assert.equal((await general.status()).pokemon_deals_enabled,false);
console.log('Pokemon subscriptions and private discovery queue checks passed');
