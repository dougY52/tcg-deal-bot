"""Same-run public retailer searches. Strict identity checks precede every vote."""
from collections import defaultdict
from decimal import Decimal
from datetime import date
import time
from urllib.parse import urlencode, quote, urlsplit
from .market import normalize, complete_pack_counts
from .sources import parse_product


def enrich(offers, cfg, state, client, now):
    report = {'requests': 0, 'added': 0, 'errors': [], 'unresolved_groups': 0, 'normal_prices_rechecked': 0}
    if not cfg['market'].get('automatic_comparison') or client is None:
        return report
    offers[:] = complete_pack_counts(offers, cfg)
    groups = defaultdict(list)
    for offer in offers:
        row, _ = normalize(offer, cfg)
        if row and row['available']:
            groups[row['identity']].append(row)
    # Recheck known normal-price products using executable offers fetched in this run.
    # A lower current price can renew an observed-retail reference, never raise it.
    today = date.fromtimestamp(now).isoformat()
    references = cfg['market'].setdefault('price_references', [])
    for identity, rows in groups.items():
        known = [Decimal(r['price_eur']) for r in references
                 if r['identity'] == identity and r['kind'] in ('observed_retail', 'msrp')]
        known.extend(Decimal(row['reference']['retail_eur']) for row in rows if row.get('reference'))
        if not known:
            continue
        lowest = min(rows, key=lambda row: Decimal(row['price']))
        if Decimal(lowest['price']) <= min(known):
            references.append({'identity': identity, 'kind': 'observed_retail',
                               'price_eur': lowest['price'], 'verified_on': today, 'valid_until': today,
                               'evidence_url': lowest['url'], 'note': 'Bekannter Normalpreis im aktuellen Lauf erneut geprüft; nur Absenkung.'})
            report['normal_prices_rechecked'] += 1
    missing = [rows for rows in groups.values() if len({r['retailer'] for r in rows}) < 3]
    missing.sort(key=lambda rows: (not any(r.get('preorder') for r in rows), rows[0]['identity']))
    report['unresolved_groups'] = len(missing)
    if missing:
        offset = state.get('comparison_cursor', 0) % len(missing)
        missing = missing[offset:] + missing[:offset]
        state['comparison_cursor'] = (offset + 1) % len(missing)
    shops = [s for s in cfg['shops'] if s.get('enabled', True) and s['adapter'] == 'shopify']
    cache = state.setdefault('comparison_searches', {})
    for key in list(cache):
        if now - cache[key] > 86400:
            del cache[key]
    limit = min(30, max(0, cfg['market'].get('research_max_requests', 16)))
    deadline = min(time.monotonic() + 90, getattr(client, 'deadline', float('inf')) - 10)
    seen = {o['key'] for o in offers}
    for rows in missing:
        target = rows[0]
        alias = next((a for a in cfg['market'].get('set_aliases', []) if a['set'] == target['set'] and a.get('search_term')), {})
        query = alias.get('search_term') or target['set'].removeprefix('name:')
        if not alias and target['set'].startswith(('FB', 'OP', 'BT', 'ME', 'EB')):
            import re
            query = re.sub(r'^(FB|OP|BT|ME|EB)(\d+)$', lambda m: m[1] + m[2].zfill(2), query)
        attempted_shops = 0
        for shop in shops:
            if report['requests'] >= limit or time.monotonic() >= deadline:
                return report
            retailer = shop.get('retailer_group') or urlsplit(shop['base_url']).hostname
            key = target['identity'] + '|' + shop['id']
            if retailer in {r['retailer'] for r in rows} or now - cache.get(key, 0) < 6 * 3600:
                continue
            if attempted_shops >= 2:
                break
            attempted_shops += 1
            cache[key] = now
            try:
                report['requests'] += 1
                data = client.get(shop['base_url'] + '/search/suggest.json?' + urlencode({'q': query, 'resources[type]': 'product', 'resources[limit]': 10}))
                for product in data.get('resources', {}).get('results', {}).get('products', []):
                    handle = product.get('handle', '')
                    if not handle or '/' in handle or report['requests'] >= limit or time.monotonic() >= deadline:
                        continue
                    report['requests'] += 1
                    detail = client.get(shop['base_url'] + '/products/' + quote(handle, safe='-') + '.js')
                    if detail.get('handle') != handle:
                        continue
                    detail['body_html'] = detail.get('description', '')
                    for variant in detail['variants']:
                        if type(variant['price']) is not int:
                            raise ValueError('Invalid minor units')
                        variant['price'] = str(Decimal(variant['price']) / 100)
                    for offer in parse_product(shop, detail):
                        row, _ = normalize(offer, cfg)
                        if row and row['identity'] == target['identity'] and offer['key'] not in seen:
                            offers.append(offer); seen.add(offer['key']); report['added'] += 1
                            if row['available']:
                                rows.append(row)
                if len({r['retailer'] for r in rows}) >= 3:
                    break
            except Exception as exc:
                report['errors'].append({'shop': shop['id'], 'type': type(exc).__name__})
    return report
