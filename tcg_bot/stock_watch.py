"""Every-run public inventory snapshots, independent of discovery rotation.

Catalog availability schedules exact live checks; it never authorizes an alert.
Missing rows, failed requests and truncated catalogs never mean sold out.
"""
import copy
from decimal import Decimal
import time
from . import preorders
from .scanning import collect


def scan(cfg, state, client, adapters, now):
    shops = [dict(copy.deepcopy(s), _stock_scan=True, max_pages=40)
             for s in cfg['shops'] if s.get('enabled', True) and s.get('stock_watch_each_run')]
    rows, reports = [], []
    original = getattr(client, 'deadline', None)
    if original is not None:
        client.deadline = min(original, time.monotonic() + 40)
    try:
        for shop, offers, warnings, error, seconds in collect(shops, client, adapters, min(8, max(1, len(shops))), 35):
            relevant = [o for o in offers if preorders.identity(o, cfg)[0]]
            coverage = shop.get('_catalog_coverage', {})
            report = dict(shop=shop['id'], scope=shop.get('stock_collections') or ['full_product_catalog'],
                          products=coverage.get('products', 0), variants=len(offers),
                          relevant_variants=len(relevant), available_variants=sum(o['available'] for o in relevant),
                          complete=bool(coverage.get('complete')) and not error,
                          endpoints=coverage.get('endpoints', []), seconds=seconds,
                          warnings=warnings, error=error, checked_at=now)
            state.setdefault('stock_watch_coverage', {})[shop['id']] = report
            reports.append(report)
            rows.extend(relevant)
    finally:
        if original is not None:
            client.deadline = original
    return rows, reports


def live_targets(rows, cfg, state):
    """Check all affordable positives and confirm loss of previously open stock.

    A catalog's negative does not mutate the alert episode. Only the existing
    exact-product validator can do that, preventing false restocks after outages.
    """
    ceiling = Decimal(str(cfg['preorder_watch'].get('max_price_eur', 200)))
    selected = {}
    for o in rows:
        tracked = state.get('preorder_tracking', {}).get(o['key'], {})
        previous = state.get('preorder_products', {}).get(tracked.get('product_key'), {})
        was_open = previous.get('status') in ('in_stock', 'preorder')
        if (o['available'] and Decimal(o['price']) <= ceiling) or was_open:
            selected[o['key']] = o
    # Under an exceptional time limit, unattempted products go first next run.
    # Never keep the same tail of an otherwise fully read catalog deferred.
    return sorted(selected.values(), key=lambda o: state.get('fast_targets', {}).get(o['key'], {}).get('checked_at', 0))
