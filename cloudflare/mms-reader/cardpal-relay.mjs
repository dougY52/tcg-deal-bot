// Owner-only CardPal transport. Optional Pokemon deal subscriptions are explicit.
const API = 'https://www.mycardpal.com/api';
export const WINDOW_MS = 240000;
const MAX_AGE = 15 * 60000;
export class RelayError extends Error { constructor(code) { super(code); this.code = code; } }
export const safeError = e => e instanceof RelayError ? e.code : 'NETWORK_OR_RUNTIME_ERROR';
export function germanyURL(value) {
  try {
    if (typeof value !== 'string' || value.length > 2000) return null;
    const u = new URL(value);
    if (u.protocol !== 'https:' || u.hostname !== 'www.pokemoncenter.com' || u.port || u.username || u.password ||
        /%|\.\./.test(value.split('?')[0]) || !/^\/(de-de|en-de)(\/[A-Za-z0-9_/-]*)?$/.test(u.pathname)) return null;
    return u.origin + u.pathname;
  } catch { return null; }
}
export function webhookURL(value) {
  return typeof value === 'string' && /^https:\/\/discord\.com\/api\/webhooks\/\d{16,22}\/[A-Za-z0-9_-]{30,200}$/.test(value);
}
export async function selectDrop(row, now) {
  if (!row || typeof row.dedupe_key !== 'string' || !/^broadcast:pokecenter-drop(?:$|[:|_-])/.test(row.dedupe_key)) return null;
  const text = [row.article_name, row.template].filter(x => typeof x === 'string').join(' ').slice(0, 4000);
  const link = germanyURL(row.url);
  const other = /\b(?:UK|US|USA|United Kingdom|United States|Großbritannien)\b|\b(?:not|nicht|kein\w*)\s+(?:(?:for|für|in)\s+)?(?:Deutschland|Germany|DE)\b/i;
  if (other.test(text) || (row.url && !link)) return null;
  if (!link && !/\b(?:Deutschland|Germany)\b|Pok[eé]mon\s*Center\s+DE\b/i.test(text)) return null;
  // A teaser, ended drop or mere backend listing is not an open drop.
  if (/\b(?:coming soon|bald|demnächst|morgen|sold out|ausverkauft|beendet|backend|gerücht|rumou?r)\b/i.test(text)) return null;
  if (typeof row.created_at !== 'string' || !/(?:Z|[+-]\d\d:\d\d)$/.test(row.created_at)) return null;
  const published = Date.parse(row.created_at);
  if (!Number.isFinite(published) || published > now + 30000 || now - published > MAX_AGE) return null;
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(row.dedupe_key));
  const key = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
  const title = text.replace(/https?:\/\/\S+/g, '').replace(/[@<>*_`\[\]\\]/g, '').trim().slice(0, 300);
  return {key, title, url: link || 'https://www.pokemoncenter.com/de-de/', published, observed: now};
}
export function discordPayload(drop) {
  return {allowed_mentions: {parse: []}, embeds: [{title: '🚨 DROP GEMELDET · POKÉMON CENTER DE',
    description: (drop.title ? drop.title + '\n\n' : '') +
      'Quelle: **CardPal Deutschland-Meldung**\n' +
      'Bestand und Warteschlange nicht unabhängig bestätigt.\n' +
      `[Pokémon Center Deutschland öffnen](${drop.url})`,
    color: 3447003, timestamp: new Date(drop.published).toISOString(),
    footer: {text: 'CardPal → Discord · keine Vorhersage eines künftigen Drops'}}]};
}

// Strictly bounded streaming parser; heartbeat comments never produce an alert.
export async function* sseEvents(body) {
  const reader = body.getReader(), decoder = new TextDecoder('utf-8', {fatal: true});
  let buffer = '', event = 'message', data = [], size = 0, events = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) return;
      size += chunk.value.byteLength;
      if (size > 1048576) throw new RelayError('STREAM_SIZE_LIMIT');
      buffer += decoder.decode(chunk.value, {stream: true});
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end).replace(/\r$/, ''); buffer = buffer.slice(end + 1);
        if (line.length > 16384) throw new RelayError('STREAM_LINE_LIMIT');
        if (!line) {
          if (data.length) {
            if (++events > 300) throw new RelayError('STREAM_EVENT_LIMIT');
            yield {event, data: data.join('\n')};
          }
          event = 'message'; data = [];
        } else if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (buffer.length > 16384) throw new RelayError('STREAM_LINE_LIMIT');
    }
  } finally { try { await reader.cancel(); } catch {} }
}

export class CardPalRelay {
  constructor(storage, network = (input, init) => fetch(input, init), clock = Date.now) {
    this.storage = storage; this.network = network; this.clock = clock;
    this.session = null; this.running = false;
  }
  async status() {
    const h = await this.storage.get('health') || {};
    return {...h, configured: !!await this.storage.get('config'), next_alarm: await this.storage.getAlarm(),
      browser_minutes_used: 0, shop_drop_latency_verified: false};
  }
  async discovery() {
    const rows = await this.storage.get('discovery') || {};
    return {article_ids: Object.entries(rows).filter(([, at]) => this.clock() - at < 86400000)
      .sort((a, b) => b[1] - a[1]).map(([id]) => id).slice(0, 100)};
  }
  async configure(input) {
    if (!input || typeof input.email !== 'string' || !input.email.includes('@') || input.email.length > 320 ||
        typeof input.password !== 'string' || input.password.length < 1 || input.password.length > 2000 ||
        !webhookURL(input.webhook)) throw new RelayError('INVALID_CONFIGURATION');
    const previous = await this.storage.get('config');
    const requested = input.deal_franchises ?? previous?.deal_franchises ?? ['POKEMON'];
    if (!Array.isArray(requested) || !requested.length || requested.length > 3 ||
        requested.some(f => !['POKEMON', 'DRAGONBALL', 'ONEPIECE'].includes(f)))
      throw new RelayError('INVALID_DEAL_FRANCHISES');
    const config = {email: input.email, password: input.password, webhook: input.webhook,
      pokemon_deals: input.pokemon_deals === true || previous?.pokemon_deals === true,
      deal_franchises: [...new Set(requested)].sort()};
    if (previous && (previous.email !== config.email || previous.password !== config.password)) {
      await this.storage.delete('session'); this.session = null;
    }
    await this.storage.put('config', config);
    if (!previous) await this.storage.put('health', {status: 'configured', enabled_at: this.clock(), sent: 0});
    if (config.pokemon_deals && (!previous?.pokemon_deals ||
        JSON.stringify(config.deal_franchises) !== JSON.stringify(previous?.deal_franchises))) this.cycleAbort?.abort();
    if (!this.running) await this.storage.setAlarm(this.clock() + 1000);
    return this.status();
  }
  async request(path, options = {}, stream = false) {
    if (++this.requests > 40) throw new RelayError('CYCLE_REQUEST_LIMIT');
    const headers = new Headers(options.headers);
    headers.set('Accept', stream ? 'text/event-stream' : 'application/json');
    headers.set('Cache-Control', 'no-cache');
    if (!stream && this.session?.token) headers.set('Authorization', 'Bearer ' + this.session.token);
    if (this.session?.cookie) headers.set('Cookie', this.session.cookie);
    let response;
    try { response = await this.network(API + path, {...options, headers, redirect: 'manual',
      signal: options.signal || AbortSignal.timeout(15000)}); }
    catch { throw new RelayError('CARDPAL_NETWORK'); }
    if (response.status !== 200) {
      await response.body?.cancel();
      if (response.status === 401) { this.session = null; await this.storage.delete('session'); }
      throw new RelayError('CARDPAL_HTTP_' + response.status);
    }
    const cookies = response.headers.getSetCookie();
    if (cookies.length && this.session) {
      const jar = new Map((this.session.cookie || '').split('; ').filter(Boolean).map(x => [x.split('=')[0], x]));
      for (const cookie of cookies) { const pair = cookie.split(';')[0]; jar.set(pair.split('=')[0], pair); }
      this.session.cookie = [...jar.values()].join('; ');
    }
    if (stream) {
      if (!response.headers.get('content-type')?.startsWith('text/event-stream')) {
        await response.body?.cancel(); throw new RelayError('CARDPAL_NOT_SSE');
      }
      return response;
    }
    if (!response.headers.get('content-type')?.startsWith('application/json')) {
      await response.body?.cancel(); throw new RelayError('CARDPAL_NOT_JSON');
    }
    const reader = response.body.getReader(); let bytes = 0; const chunks = [];
    try {
      while (true) { const {done, value} = await reader.read(); if (done) break;
        bytes += value.length; if (bytes > 1000000) throw new RelayError('CARDPAL_SIZE_LIMIT'); chunks.push(value); }
    } finally { try { await reader.cancel(); } catch {} }
    const joined = new Uint8Array(bytes); let offset = 0;
    for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length; }
    try { return JSON.parse(new TextDecoder().decode(joined)); }
    catch { throw new RelayError('CARDPAL_INVALID_JSON'); }
  }
  async authenticate(config) {
    this.session ||= await this.storage.get('session');
    if (this.session?.expires > this.clock() + WINDOW_MS + 60000) return;
    let value;
    if (this.session?.cookie) {
      // Refresh the owner's existing login; never ask for a Google/Apple password.
      value = await this.request('/auth/refresh', {method: 'POST'});
    } else {
      this.session = {};
      value = await this.request('/auth/login', {method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({username: config.email, password: config.password})});
    }
    if (typeof value.access_token !== 'string' || value.access_token.length < 10 || value.access_token.length > 20000)
      throw new RelayError('CARDPAL_INVALID_TOKEN');
    this.session.token = value.access_token;
    let expires = this.clock() + 10 * 60000;
    try { const exp = JSON.parse(atob(value.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).exp;
      if (Number.isFinite(exp)) expires = exp * 1000; } catch {}
    this.session.expires = expires;
    await this.storage.put('session', this.session);
  }
  async inbox() {
    const rows = [];
    for (let offset = 0; offset < 250; offset += 50) {
      const v = await this.request('/notifications/?limit=50&offset=' + offset);
      if (!Array.isArray(v.items) || v.items.length > 50) throw new RelayError('CARDPAL_INBOX_SCHEMA');
      rows.push(...v.items);
      if (v.items.length < 50 || rows.length >= v.total) break;
    }
    return rows;
  }
  async processRows(rows, config, health) {
    const now = this.clock(), receipts = await this.storage.get('receipts') || {};
    if (config.pokemon_deals) {
      const discovery = await this.storage.get('discovery') || {};
      for (const row of rows) {
        if (typeof row.dedupe_key === 'string' && row.dedupe_key.startsWith('dealz|') &&
            typeof row.article_id === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(row.article_id)) {
          const at = Date.parse(row.created_at);
          if (Number.isFinite(at) && at <= now + 30000 && now - at < 86400000)
            discovery[row.article_id] = at;
        }
      }
      const bounded = Object.fromEntries(Object.entries(discovery).filter(([, at]) => now - at < 86400000)
        .sort((a, b) => b[1] - a[1]).slice(0, 100));
      await this.storage.put('discovery', bounded);
      health.discovery_articles = Object.keys(bounded).length;
    }
    const baseline = !health.baseline_at;
    for (const row of rows.slice().reverse()) {
      const drop = await selectDrop(row, now);
      if (!drop) continue;
      if (receipts[drop.key]) continue;
      if (baseline || drop.published < health.enabled_at) { receipts[drop.key] = {status: 'baseline', at: now}; continue; }
      // Commit before external delivery. After a timeout/crash, do not blindly
      // send again: Discord webhooks do not offer an idempotency key.
      receipts[drop.key] = {status: 'inflight', at: now};
      await this.storage.put('receipts', receipts);
      let response;
      try { response = await this.network(config.webhook + '?wait=true', {method: 'POST', redirect: 'manual',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(discordPayload(drop)),
        signal: AbortSignal.timeout(15000)}); }
      catch { receipts[drop.key].status = 'delivery_unknown'; health.delivery_unknown = (health.delivery_unknown || 0) + 1; }
      if (response) {
        if (response.status === 429) {
          delete receipts[drop.key]; await response.body?.cancel();
          await this.storage.put('receipts', receipts); throw new RelayError('DISCORD_RATE_LIMIT');
        }
        if (response.ok) {
          receipts[drop.key].status = 'sent'; health.sent = (health.sent || 0) + 1;
          health.last_delivery_at = this.clock();
          health.last_publication_to_delivery_seconds = Math.max(0, (this.clock() - drop.published) / 1000);
        } else {
          receipts[drop.key].status = response.status >= 500 ? 'delivery_unknown' : 'delivery_rejected';
          health.delivery_errors = (health.delivery_errors || 0) + 1;
        }
        await response.body?.cancel();
      }
      await this.storage.put('receipts', receipts);
      await this.storage.put('health', health);
    }
    health.baseline_at ||= now; health.last_inbox_at = now;
    // 15-minute eligibility bounds make old receipts safe to prune.
    const recent = Object.entries(receipts).filter(([, v]) => now - v.at < 7 * 86400000).slice(-1000);
    await this.storage.put('receipts', Object.fromEntries(recent));
    await this.storage.put('health', health);
  }
  async cycle() {
    if (this.running) return;
    this.running = true; this.requests = 0;
    let health = await this.storage.get('health') || {}, delay = 1000;
    const config = await this.storage.get('config');
    if (!config) { this.running = false; return; }
    // Durable watchdog survives a process crash, independently of GitHub/PC.
    await this.storage.setAlarm(this.clock() + WINDOW_MS + 60000);
    const stop = new AbortController(); let timer;
    this.cycleAbort = stop;
    try {
      await this.authenticate(config);
      let settings = await this.request('/users/me');
      const requested = config.deal_franchises || ['POKEMON'];
      const applied = health.deal_franchises_applied || (health.pokemon_settings_applied ? ['POKEMON'] : []);
      if (config.pokemon_deals && requested.some(f => !applied.includes(f))) {
        const franchises = settings.dealz_auto_subscribe_enabled && Array.isArray(settings.dealz_auto_subscribe_franchises)
          ? [...new Set([...settings.dealz_auto_subscribe_franchises, ...requested])] : requested;
        const existing = Number(settings.dealz_threshold_percent);
        const threshold = existing > 0 ? Math.min(existing, 5) : 5;
        await this.request('/users/me', {method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({notification_enabled: true, allow_drop_notifications: true,
            dealz_auto_subscribe_enabled: true, dealz_auto_subscribe_franchises: franchises,
            dealz_threshold_percent: threshold})});
        settings = await this.request('/users/me');
        if (settings.dealz_auto_subscribe_enabled !== true ||
            !requested.every(f => settings.dealz_auto_subscribe_franchises?.includes(f)))
          throw new RelayError('TCG_DEALS_NOT_ENABLED');
        health.pokemon_settings_applied = true;
        health.deal_franchises_applied = [...new Set([...applied, ...requested])];
        health.dealz_threshold_percent = settings.dealz_threshold_percent;
      }
      if (config.pokemon_deals) health.pokemon_deals_enabled = settings.dealz_auto_subscribe_enabled === true &&
        settings.dealz_auto_subscribe_franchises?.includes('POKEMON') === true;
      if (config.pokemon_deals) {
        health.subscribed_franchises = requested.filter(f => settings.dealz_auto_subscribe_enabled === true &&
          settings.dealz_auto_subscribe_franchises?.includes(f));
        health.tcg_deals_enabled = health.subscribed_franchises.length === requested.length;
      }
      if (settings.notification_enabled === false || settings.allow_drop_notifications === false)
        throw new RelayError('CARDPAL_DROPS_DISABLED');
      await this.processRows(await this.inbox(), config, health);
      const token = await this.request('/auth/stream-token');
      if (typeof token.token !== 'string' || token.token.length > 20000 || token.token.length < 10)
        throw new RelayError('CARDPAL_STREAM_TOKEN');
      timer = setTimeout(() => stop.abort(), WINDOW_MS);
      const response = await this.request('/notifications/stream?token=' + encodeURIComponent(token.token), {signal: stop.signal}, true);
      health.status = 'stream_connected'; health.last_stream_at = this.clock(); health.failures = 0;
      delete health.last_error;
      await this.storage.put('health', health);
      for await (const item of sseEvents(response.body)) {
        if (item.event !== 'notification') continue;
        await this.processRows(await this.inbox(), config, health);
      }
      // Provider EOF reconnects with backoff; not a tight login loop.
      delay = 5000;
    } catch (error) {
      if (!stop.signal.aborted) {
        health.failures = (health.failures || 0) + 1;
        health.status = 'retry_wait'; health.last_error = safeError(error);
        delay = Math.min(300000, 15000 * 2 ** Math.min(health.failures - 1, 5));
      }
    } finally {
      clearTimeout(timer); stop.abort();
      this.cycleAbort = null;
      health.last_cycle_at = this.clock();
      await this.storage.put('health', health);
      await this.storage.setAlarm(this.clock() + delay);
      this.running = false;
    }
  }
}
