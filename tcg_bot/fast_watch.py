"""Bounded live watch ahead of rotating catalog discovery; no catalog-only alerts."""
import copy
import re
import time
from urllib.parse import urlsplit, parse_qs
from . import preorders
from .scanning import collect


def priority(o):
    text = o.get('title', '')
    if re.search(r'\bFB[ -]?\d{1,3}\b', text, re.I):
        return 0
    if preorders.candidate(o):
        return 1
    if re.search(r'pok[eé]mon', text, re.I):
        return 2
    if re.search(r'one.?piece', text, re.I):
        return 3
    if re.search(r'naruto', text, re.I):
        return 4
    return 5


def remember(rows, cfg, state, now):
    table = state.setdefault('fast_targets', {})
    for o in rows:
        obj, _ = preorders.identity(o, cfg)
        if obj:
            # Parser keys can change; a seller's concrete variant is still one target.
            aliases = [k for k, r in table.items() if r['offer']['shop'] == o['shop'] and
                       str(r['offer']['variant_id']) == str(o['variant_id']) and
                       r['offer'].get('seller') == o.get('seller')]
            alias = aliases[0] if aliases else o['key']
            for duplicate in aliases[1:]:
                del table[duplicate]
            o = dict(o, key=alias)
            old = table.get(o['key'], {})
            table[o['key']] = dict(old, offer=o, discovered_at=now)


def bootstrap(cfg, state, now):
    """Old URLs are discovery hints only. Every field is rebuilt by live()."""
    if state.get('fast_bootstrapped'):
        return
    remember([r['offer'] for r in state.get('preorder_tracking', {}).values()], cfg, state, now)
    shops = {urlsplit(s['base_url']).netloc: s for s in cfg['shops'] if s.get('enabled', True)}
    for h in state.get('market_history', {}).values():
        u = urlsplit(h.get('url', ''))
        shop = shops.get(u.netloc)
        vid = parse_qs(u.query).get('variant', [''])[0]
        if not shop or shop['adapter'] != 'shopify' or not vid.isdigit() or '/products/' not in u.path:
            continue
        handle = u.path.split('/products/')[-1]
        o = dict(shop=shop['id'], shop_name=shop['name'], seller=shop['name'], seller_verified=True,
                 key=shop['id']+':'+vid, handle=handle, variant_id=vid, title=handle.replace('-', ' '),
                 variant='', description='', price=h['price'], currency=shop['currency'], available=h['available'], url=h['url'])
        remember([o], cfg, state, now)
    for ref in cfg.get('references', []):
        for binding in ref.get('bindings', []):
            shop = next((s for s in shops.values() if s['id'] == binding['shop']), None)
            if not shop:
                continue
            handle, vid = binding['handle'], str(binding['variant_id'])
            label = urlsplit(binding['url']).path.rstrip('/').split('/')[-1] if binding.get('url') else handle
            o = dict(shop=shop['id'], shop_name=shop['name'], seller=shop['name'], seller_verified=True,
                     key=shop['id']+':'+vid, handle=handle, variant_id=vid, title=label.replace('-', ' ')+' '+ref['language'],
                     variant='', description='', price=ref['retail_eur'], currency=shop['currency'], available=False,
                     url=binding.get('url') or shop['base_url']+'/products/'+handle+'?variant='+vid)
            if o['key'] not in state.get('fast_targets', {}):
                remember([o], cfg, state, now)
    state['fast_bootstrapped'] = True


def select(cfg, state):
    shops = {s['id']: s for s in cfg['shops'] if s.get('enabled', True)}
    buckets = [[] for _ in range(6)]
    for record in state.get('fast_targets', {}).values():
        o = record['offer']
        if o['shop'] in shops:
            buckets[priority(o)].append(record)
    # Reserve checks for each franchise; oldest observation rotates all known sets.
    quotas = cfg['fast_watch'].get('quotas', [12, 8, 8, 8, 6, 4])
    selected = []
    for bucket, quota in zip(buckets, quotas):
        bucket.sort(key=lambda r: (r.get('checked_at', 0), r['offer']['key']))
        if bucket is buckets[0]:
            hot = [r for r in bucket if re.search(r'\bFB[ -]?11\b', r['offer']['title'], re.I)][:4]
            bucket = hot + [r for r in bucket if r not in hot]
        selected.extend(r['offer'] for r in bucket[:quota])
    return selected


def fetch_live(selected, cfg, client, now):
    """FB phase first; parallel hosts, serial variants per host, isolated budgets."""
    shops = {s['id']: s for s in cfg['shops'] if s.get('enabled', True)}
    result = {}
    original = getattr(client, 'deadline', None)
    end = time.monotonic() + cfg['fast_watch']['live_seconds']
    try:
        for group in range(6):
            phase_end = min(end, time.monotonic() + (45, 25, 25, 20, 15, 10)[group])
            if original is not None:
                client.deadline = phase_end
            batches = {}
            for o in selected:
                if priority(o) == group:
                    batches.setdefault(o['shop'], []).append(o)
            work = [dict(shops[sid], adapter='fast_live', _targets=rows) for sid, rows in batches.items()]
            def fetch(shop, transport):
                rows = []
                for o in shop['_targets']:
                    if time.monotonic() >= getattr(transport, 'deadline', phase_end):
                        break
                    try:
                        row, error = preorders.live(o, shops[o['shop']], transport, now)
                    except Exception as exc:
                        row, error = None, 'LIVE_CHECK_FAILED_'+type(exc).__name__
                    rows.append({'key': o['key'], 'row': row, 'error': error})
                return rows, []
            for shop, rows, _, error, _ in collect(work, client, {'fast_live': fetch}, 4, 20):
                for record in rows:
                    result[record['key']] = (record['row'], record['error'])
    finally:
        if original is not None:
            client.deadline = original
    return result


def payload(o):
    msg = preorders.payload(o)
    embed = msg['embeds'][0]
    if not o.get('preorder_status'):
        embed['title'] = '🔥 DRAGON BALL RESTOCK' if o['franchise'] == 'Dragon Ball' else '🔥 RETAIL / RESTOCK'
        embed['description'] = embed['description'].replace('Direkt vorbestellbar', 'Laut Live-Prüfung direkt bestellbar')
    if o['pricing']['strong']:
        embed['title'] = '🔥🔥 BESTPREIS ALERT · ' + ('PREORDER' if o.get('preorder_status') else 'RESTOCK')
    if o.get('shipping_cost') is not None:
        from decimal import Decimal
        embed['description'] += '\n💰 Gesamt: ' + str(Decimal(o['price']) + Decimal(o['shipping_cost'])) + ' €'
    return msg


def run(cfg, state, client, adapters, send=None, checkpoint=None, now=None):
    now = time.time() if now is None else now
    settings = cfg['fast_watch']
    report = dict(shops=[], errors=[], warnings=[], skipped={}, candidates=[], alerts=[], sent=0,
                  dry_run=send is None, unavailable_sources=cfg.get('unavailable_sources', []), pending_alerts=0)
    if now - state.get('fast_last_run', 0) < settings.get('min_run_gap_seconds', 240):
        report['fast_watch'] = {'skipped_recent_run': True}
        return report
    bootstrap(cfg, state, now)
    selected = select(cfg, state)
    live_cfg = copy.deepcopy(cfg)
    live_cfg['_fast_lane'] = True
    live_cfg['_fast_keys'] = [o['key'] for o in selected]
    live_cfg['_fast_groups'] = {o['key']: priority(o) for o in selected}
    live_cfg['preorder_watch'].update(max_live_checks=sum(settings['quotas']), validation_seconds=settings['live_seconds'])
    live_cfg['_fast_preloaded'] = fetch_live(selected, cfg, client, now)
    _, deals, audit = preorders.scan(selected, live_cfg, state, client, now)
    report['preorder_watch'] = audit
    remember(live_cfg.get('_fast_observed', []), cfg, state, now)
    for item in audit['candidates']:
        report['skipped'][item['reason'].replace('REJECTED - ', 'REJECTED_')] = report['skipped'].get(item['reason'].replace('REJECTED - ', 'REJECTED_'), 0) + 1
    # Only actually attempted targets move to the back of the rotation.
    for key in live_cfg.get('_fast_attempted', []):
        if key in state['fast_targets']:
            state['fast_targets'][key]['checked_at'] = now
    report['fast_watch'] = {'targets': len(state.get('fast_targets', {})), 'selected': len(selected), 'checked': audit['checked']}
    limit = cfg.get('max_alerts_per_run') or len(deals)
    report['pending_alerts'] = max(0, len(deals)-limit)
    for deal in sorted(deals, key=lambda o: (priority(o), -o['priority_score']))[:limit]:
        message = payload(deal)
        report['alerts'].append({'key': deal['key'], 'reason': 'preorder_live' if deal['preorder_status'] else 'retail_restock', 'payload': message})
        if send:
            try:
                message_id = send(message)
            except Exception as exc:
                report['errors'].append('Discord: '+type(exc).__name__)
                break
            preorders.delivered(state, deal, now, message_id)
            report['sent'] += 1
            audit['sent'] += 1
            if checkpoint:
                checkpoint(state)
    state['fast_last_run'] = now
    if checkpoint:
        checkpoint(state)
    # Slow work follows delivery, has its own bounded budget, and never posts snippets.
    catalog_state = state.setdefault('fast_catalog_checks', {})
    due = [s for s in cfg['shops'] if s.get('enabled', True) and
           now-catalog_state.get(s['id'], 0) >= settings['catalog_interval_seconds']]
    due.sort(key=lambda s: catalog_state.get(s['id'], 0))
    due = due[:settings['catalog_shops_per_run']]
    original = getattr(client, 'deadline', None)
    if original is not None:
        client.deadline = time.monotonic() + settings['catalog_seconds']
    try:
        for shop, rows, notes, error, seconds in collect(due, client, adapters, 4, 20):
            catalog_state[shop['id']] = now
            report['shops'].append({'shop': shop['id'], 'variants': len(rows), 'seconds': seconds})
            if error:
                report['errors'].append(shop['id']+': '+error)
            report['warnings'].extend(shop['id']+': '+n for n in notes)
            remember(rows, cfg, state, now)
    finally:
        if original is not None:
            client.deadline = original
    from .retailer_discovery import discover
    report['retailer_discovery'] = discover(cfg, state, client, now)
    report['fast_watch']['targets_after_discovery'] = len(state.get('fast_targets', {}))
    if checkpoint:
        checkpoint(state)
    return report
