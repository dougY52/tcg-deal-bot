"""Bounded public price research; exact products and live checkout, never snippets."""
from datetime import datetime, timezone
from decimal import Decimal
import copy
import re
import time
from urllib.parse import urlencode

from . import preorders
from .http import FetchError
from .sources import parse_product


def reference_for(o, cfg, now):
    obj, error = preorders.identity(o, cfg)
    if error:
        return None
    ref = cfg.get('_researched_retail', {}).get(obj['comparison_key'])
    if (ref and 0 <= now-ref['checked_at'] < 86400 and
            ref['source_shop'] in cfg.get('preorder_watch', {}).get('trusted_shop_ids', [])):
        return ref
    return None


def historical_ceiling(o, cfg):
    """Expired reviewed evidence may cap renewal, never becomes fresh by itself."""
    from .price_comparison import reviewed_match_product
    known = []
    mapping = reviewed_match_product(o, cfg)
    if mapping and mapping.get('retail'):
        known.append(Decimal(mapping['retail']['price_eur']))
    for r in cfg.get('references', []):
        if preorders.reference_matches(o, r) and r['kind'] in ('msrp', 'observed_retail'):
            known.append(Decimal(r['retail_eur']))
    for r in cfg.get('preorder_watch', {}).get('price_references', []):
        if r['comparison_key'] == o['comparison_key'] and r['kind'] in ('msrp', 'observed_retail'):
            known.append(Decimal(r['price_eur']))
    old = cfg.get('_researched_retail', {}).get(o['comparison_key'])
    if old:
        known.append(Decimal(old['price_eur']))
    return min(known) if known else None


def same_product(a, b, cfg, state):
    """Reuse exact catalogue identity only; never use Cardmarket prices as retail."""
    if any(a.get(k) != b.get(k) for k in ('franchise', 'language', 'edition', 'product_type')):
        return False
    if a.get('set_code') and b.get('set_code') and a['set_code'] != b['set_code']:
        return False
    if a.get('comparison_key') == b.get('comparison_key'):
        return True
    from .price_comparison import match_product
    cache = cfg.setdefault('_research_matches', {})
    def mapped(o):
        key = tuple(str(o.get(k, '')) for k in ('title','variant','description','gtin','packs','language','edition','product_type'))
        if key not in cache:
            cache[key] = match_product(o, cfg, state)
        return cache[key]
    first, second = mapped(a), mapped(b)
    return bool(first and second and
                (first['game_id'], first['product_id']) == (second['game_id'], second['product_id']))


class BudgetClient:
    def __init__(self, client, end, maximum):
        self.client, self.deadline, self.maximum = client, end, maximum
        self.requests = 0

    def request(self, method, url):
        if self.requests >= self.maximum or time.monotonic() >= self.deadline:
            raise FetchError('Research budget exhausted')
        self.requests += 1
        return getattr(self.client, method)(url)

    def get(self, url):
        return self.request('get', url)

    def text(self, url):
        return self.request('text', url)


def trusted_live(row, shop, cfg, now):
    if (row.get('validated_at') != now or row.get('live_validated') is not True or
            row.get('available') is not True or row.get('add_to_cart_available') is not True or
            row.get('availability_status') not in ('in_stock', 'preorder') or
            row.get('currency') != 'EUR' or shop.get('international') or shop.get('marketplace')):
        return False
    rules = dict(preorders.SHOP_RULES.get(shop['id'], {}),
                 **cfg['preorder_watch'].get('shop_rules', {}).get(shop['id'], {}))
    if rules.get('strict_cart_check') and not row.get('cart_validated'):
        return False
    if rules.get('strict_variant_check') and not row.get('variant_validated'):
        return False
    return preorders.seller_confidence(row, shop, cfg['preorder_watch']) is not None


def run(cfg, state, client, now):
    settings = cfg.get('retail_research', {})
    report = dict(requests=0, attempted=0, resolved=0, pending=0, errors=[], results=[])
    if not settings.get('enabled') or client is None:
        return report
    db = state.setdefault('retail_research', {})
    refs = db.setdefault('references', {})
    checks = db.setdefault('checks', {})
    cfg['_researched_retail'] = refs
    cfg['_research_matches'] = {}
    shops = {s['id']: s for s in cfg['shops'] if s.get('enabled', True)}
    quotes = state.get('preorder_quotes', {})
    from .price_comparison import retail_reference
    missing = {}
    for row in quotes.values():
        shop = shops.get(row['shop'])
        if (shop and trusted_live(row, shop, cfg, now) and
                Decimal('0') < Decimal(row['price']) <= Decimal(str(cfg['preorder_watch'].get('max_price_eur', 200))) and
                not retail_reference(row, cfg, now)):
            missing.setdefault(row['comparison_key'], row)
    report['pending'] = len(missing)
    # Oldest checked first: one difficult/unknown SKU cannot starve newer products.
    due = sorted(missing, key=lambda k: (checks.get(k, {}).get('at', 0), k))
    due = [k for k in due if now >= checks.get(k, {}).get('retry_after', 0)]
    original = getattr(client, 'deadline', None)
    end = time.monotonic()+min(30, settings.get('budget_seconds', 18))
    if original is not None:
        client.deadline = end
    limited = BudgetClient(client, end, min(20, settings.get('max_requests', 12)))
    trusted_ids = cfg['preorder_watch'].get('trusted_shop_ids', [])
    search_shops = [s for s in shops.values() if s['adapter'] == 'shopify' and
                    s['id'] in trusted_ids and not s.get('international') and not s.get('marketplace')]
    offset = db.get('shop_cursor', 0) % max(1, len(search_shops))
    search_shops = search_shops[offset:] + search_shops[:offset]
    db['shop_cursor'] = offset + 2
    targets = list(state.get('fast_targets', {}).values())
    try:
        for key in due[:settings.get('max_products', 2)]:
            if time.monotonic() >= end or limited.requests >= limited.maximum:
                break
            report['attempted'] += 1
            target = missing[key]
            ceiling = historical_ceiling(target, cfg)
            evidence = []
            tested = {r['key'] for r in quotes.values() if r.get('validated_at') == now}

            def consider(row):
                shop = shops.get(row['shop'])
                obj, error = preorders.identity(row, cfg)
                if error or not same_product(target, obj, cfg, state) or not shop or not trusted_live(row, shop, cfg, now):
                    return
                # A normal shop price can renew an existing ceiling only downward.
                # New anchors require an explicitly configured retail benchmark shop.
                price = Decimal(row['price'])
                if price <= 0 or (ceiling is not None and price > ceiling):
                    return
                if ceiling is None and shop['id'] not in settings.get('anchor_shop_ids', []):
                    # A separately reviewed reference for this exact catalogue
                    # SKU can be renewed through its freshly checked shop offer.
                    source_reference = retail_reference(obj, cfg, now)
                    if not source_reference or price > Decimal(source_reference['price_eur']):
                        return
                evidence.append(row)

            for row in quotes.values():
                consider(row)
            candidates = []
            for record in targets:
                o = record['offer']
                obj, error = preorders.identity(o, cfg)
                if not error and o['shop'] in shops and same_product(target, obj, cfg, state):
                    candidates.append(o)
            candidates.sort(key=lambda o: (o['shop'] not in settings.get('anchor_shop_ids', []), o.get('available') is not True))

            def validate(o):
                if o['key'] in tested or o['shop'] not in shops:
                    return
                tested.add(o['key'])
                try:
                    row, error = preorders.live(o, shops[o['shop']], limited, now)
                    if not error and row:
                        consider(dict(row, validated_at=now))
                except Exception as exc:
                    report['errors'].append({'shop': o['shop'], 'type': type(exc).__name__})

            for o in candidates[:3]:
                if evidence:
                    break
                validate(o)
            # Observed public search form of a benchmark retailer. Its product
            # links still need the same exact identity + live checkout validator.
            if not evidence:
                from .web_sources import html_catalog
                for shop in shops.values():
                    if (shop['id'] not in settings.get('anchor_shop_ids', []) or
                            shop.get('retail_search_path') != '/search' or
                            limited.requests >= limited.maximum or time.monotonic() >= end):
                        continue
                    search = dict(shop, catalog_urls=[shop['base_url']+'/search?'+urlencode({
                        'search': target.get('gtin') or target['title'][:140]})],
                        watch_urls=[], max_pages=1, max_detail_pages=3, rotate_catalogs=False)
                    rows, notes = html_catalog(search, limited)
                    for o in rows:
                        obj, error = preorders.identity(o, cfg)
                        if not error and same_product(target, obj, cfg, state):
                            validate(o)
                    if evidence:
                        break
            # Search results are discovery only; their prices/availability never vote.
            if not evidence:
                query = target.get('gtin') or target['title'][:140]
                for shop in [s for s in search_shops if s['id'] != target['shop']][:2]:
                    if limited.requests >= limited.maximum or time.monotonic() >= end:
                        break
                    try:
                        data = limited.get(shop['base_url']+'/search/suggest.json?'+urlencode({
                            'q': query, 'resources[type]': 'product', 'resources[limit]': 3}))
                        for hint in data.get('resources', {}).get('results', {}).get('products', [])[:3]:
                            handle = hint.get('handle', '')
                            if not re.fullmatch(r'[a-z0-9_-]+', handle):
                                continue
                            detail = limited.get(shop['base_url']+'/products/'+handle+'.js')
                            if detail.get('handle') != handle:
                                continue
                            detail = copy.deepcopy(detail)
                            detail['body_html'] = detail.get('description', '')
                            for variant in detail['variants']:
                                if type(variant['price']) is not int:
                                    raise ValueError('Invalid minor units')
                                variant['price'] = str(Decimal(variant['price']) / 100)
                            for o in parse_product(shop, detail):
                                obj, error = preorders.identity(o, cfg)
                                if not error and same_product(target, obj, cfg, state):
                                    validate(o)
                            if evidence:
                                break
                    except Exception as exc:
                        report['errors'].append({'shop': shop['id'], 'type': type(exc).__name__})
                    if evidence:
                        break
            if evidence:
                best = min(evidence, key=lambda r: Decimal(r['price']))
                stamp = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
                refs[key] = dict(price_eur=best['price'], kind='observed_retail', url=best['url'],
                                 verified_on=stamp, checked_at=now, source_shop=best['shop'],
                                 seller=best['seller'], note='Automatisch auf konkreter Produktseite bestätigter Händlerpreis; keine Hersteller-UVP.')
                status = 'RESOLVED_LIVE_RETAIL'
                report['resolved'] += 1
            else:
                status = 'DEFERRED_BUDGET' if limited.requests >= limited.maximum or time.monotonic() >= end else 'NO_VERIFIED_RETAIL_REFERENCE'
            checks[key] = {'at': now, 'retry_after': now + (300 if status == 'DEFERRED_BUDGET' else settings.get('retry_seconds', 21600)), 'status': status}
            report['results'].append({'product': target['title'], 'status': status})
    finally:
        if original is not None:
            client.deadline = original
    report['requests'] = limited.requests
    report['pending'] -= report['resolved']
    # Bound state without extending evidence lifetime or dropping a current ceiling.
    db['checks'] = dict(sorted(checks.items(), key=lambda x: x[1]['at'], reverse=True)[:5000])
    return report
