"""Bounded public price research; exact products and live checkout, never snippets."""
from datetime import datetime, timezone
from decimal import Decimal
import copy
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit

from . import preorders
from .http import FetchError
from .sources import parse_product
from .rules import gtin_key


def reference_for(o, cfg, now):
    obj, error = preorders.identity(o, cfg)
    if error:
        return None
    ref = cfg.get('_researched_retail', {}).get(obj['comparison_key'])
    lifetime = min(7*86400, cfg.get('retail_research', {}).get('reference_ttl_seconds', 86400))
    if (ref and 0 <= now-ref['checked_at'] < lifetime and
            ref['source_shop'] in cfg.get('preorder_watch', {}).get('trusted_shop_ids', [])):
        return ref
    return None


def search_query(target):
    """Short exact-SKU discovery query; results still require live validation."""
    barcode = gtin_key(target.get('gtin'))
    if barcode:
        return barcode.lstrip('0')
    if target.get('set_code') and target.get('product_type') == 'display':
        return target['set_code'] + ' Display'
    title = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', target['title'])
    title = re.sub(r'\b(?:preorder|vorbestellung|vorbestellen|release|eta|lieferbar|limit)\b.*', '', title, flags=re.I)
    title = re.sub(r'\b(?:tcg|card game|sammelkartenspiel|deutsch|englisch|english|german)\b', ' ', title, flags=re.I)
    return re.sub(r'\s+', ' ', title).strip()[:100]


def benchmark_search(shop, target, client):
    """Rank exact product-format links before fetching a small detail budget.

    Generic catalog traversal can spend its entire budget on recommendations
    above the real search results. None of the listing prices are evidence.
    """
    from .web_sources import Document, parse_structured, same_site
    from .product_types import product_kind
    from .sources import plain
    def words(value):
        import unicodedata
        value=''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
        return set(re.findall(r'[a-z0-9]+',value)) - {'pokemon','tcg','deutsch','englisch','ex','en','de','box','card','game'}
    wanted=words(target['title'])
    queries=list(dict.fromkeys([search_query(target),search_query(dict(target,gtin=''))]))
    visited=set()
    for query in queries:
        url=shop['base_url']+'/search?'+urlencode({'search':query})
        body=client.text(url)
        candidates={}
        for node in Document(body).root.walk():
            if node.tag!='a' or not node.attrs.get('href'):
                continue
            link=urljoin(url,node.attrs['href'])
            if (not same_site(link,shop['base_url']) or urlsplit(link).query or
                    not re.search(shop.get('product_link_pattern',r'/products?/'),link)):
                continue
            label=plain(node.attrs.get('title','')+' '+node.text()) or urlsplit(link).path.rsplit('/',1)[-1]
            if product_kind(label)!=target['product_type']:
                continue
            overlap=len(words(label)&wanted)
            if overlap>=2:
                candidates[link]=max(overlap,candidates.get(link,0))
        for link in sorted(candidates,key=candidates.get,reverse=True)[:3]:
            if link in visited:continue
            visited.add(link)
            rows,_=parse_structured(shop,client.text(link),link)
            yield from rows


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
    def packs(o):
        return set(re.findall(r'\b(\d{1,3})\s*(?:booster(?:packs?)?|packs?)\b',
                              o['title']+' '+o.get('variant','')+' '+o.get('description',''), re.I)) - {'1'}
    first_packs, second_packs = packs(a), packs(b)
    if first_packs and second_packs and first_packs != second_packs:
        return False
    if a.get('comparison_key') == b.get('comparison_key'):
        return True
    # An omitted set code must not break an otherwise identical barcode SKU.
    # product_token retains selected variant and tin/ETB motifs.
    from .product_types import product_token
    if (gtin_key(a.get('gtin')) and gtin_key(a.get('gtin')) == gtin_key(b.get('gtin'))
            and product_token(a,a['product_type']) == product_token(b,b['product_type'])):
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
        self.product_deadline = end
        self.requests = 0

    def request(self, method, url):
        end = min(self.deadline,self.product_deadline)
        if self.requests >= self.maximum or time.monotonic() >= end:
            raise FetchError('Research budget exhausted')
        self.requests += 1
        original = getattr(self.client,'deadline',None)
        if original is not None:
            self.client.deadline = min(end,time.monotonic()+6)
        try:
            return getattr(self.client, method)(url)
        finally:
            if original is not None:
                self.client.deadline = original

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


def listed_price(row, shop, cfg, now):
    """Unavailable benchmark listings are price evidence only, NEVER alerts."""
    return bool(cfg.get('retail_research', {}).get('allow_unavailable_anchor_prices')
        and shop['id'] in cfg['retail_research'].get('anchor_shop_ids', [])
        and shop['adapter'] in ('mms','shopware','woocommerce','jtl')
        and not shop.get('marketplace') and not shop.get('international')
        and row.get('validated_at') == now and row.get('live_validated') is True
        and (row.get('variant_validated') is True or row.get('price_identity_validated') is True)
        and row.get('currency') == 'EUR'
        and row.get('available') is False and row.get('availability_status') == 'out_of_stock'
        and row.get('seller') == shop['name']
        and preorders.seller_confidence(row, shop, cfg['preorder_watch']) is not None)


def run(cfg, state, client, now, observations=()):
    settings = cfg.get('retail_research', {})
    report = dict(requests=0, attempted=0, resolved=0, pending=0, reused=0, errors=[], results=[])
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
    # Price evidence and current availability have different lifetimes. Reuse
    # exact, genuinely observed retail without re-dating it or asserting stock.
    observed = []
    for row in quotes.values():
        stamp = row.get('validated_at', 0)
        shop = shops.get(row.get('shop'))
        if shop and 0 <= now-stamp < 86400 and trusted_live(row, shop, cfg, stamp):
            obj, error = preorders.identity(row, cfg)
            if not error:
                observed.append(obj)
    for row, error in observations:
        if not row or error != 'OUT_OF_STOCK':
            continue
        shop = shops.get(row.get('shop'))
        if shop and listed_price(dict(row,validated_at=now), shop, cfg, now):
            obj, problem = preorders.identity(dict(row,validated_at=now),cfg)
            if not problem:
                observed.append(obj)

    def evidence_for(target, row):
        if not same_product(target, row, cfg, state):
            return False
        price = Decimal(row['price'])
        ceiling = historical_ceiling(target, cfg)
        if price <= 0 or (ceiling is not None and price > ceiling):
            return False
        if ceiling is None and row['shop'] not in settings.get('anchor_shop_ids', []):
            source = retail_reference(row, cfg, now)
            return bool(source and price <= Decimal(source['price_eur']))
        return True

    def save_reference(key, target, evidence, status):
        best = min(evidence, key=lambda r: Decimal(r['price']))
        # Preserve the original timestamp even when copying to another title.
        source = retail_reference(best, cfg, now)
        stamp = best['validated_at']
        if best['shop'] not in settings.get('anchor_shop_ids', []) and source and source.get('checked_at'):
            stamp = min(stamp, source['checked_at'])
        refs[key] = dict(price_eur=best['price'], kind='observed_retail', url=best['url'],
                         verified_on=datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
                         checked_at=stamp, source_shop=best['shop'], seller=best['seller'],
                         source_available=best.get('available'),
                         note='Auf konkreter Produktseite beobachteter Händlerpreis; keine Hersteller-UVP, kein aktueller Bestandsbeleg.')
        checks[key] = {'at':now, 'retry_after':now+settings.get('retry_seconds',21600), 'status':status}
        report['resolved'] += 1
        report['results'].append({'product':target['title'], 'status':status})

    # Resolve all reusable evidence before spending network budget. A failed
    # search yesterday must not hide a new exact reference found by this scan.
    for key, target in list(missing.items()):
        evidence = [row for row in observed if evidence_for(target, row)]
        if evidence:
            save_reference(key, target, evidence, 'RESOLVED_OBSERVED_RETAIL')
            report['reused'] += 1
            del missing[key]
    # Oldest checked first: one difficult/unknown SKU cannot starve newer products.
    due = sorted(missing, key=lambda k: (checks.get(k, {}).get('at', 0), k))
    def retry_due(key):
        record=checks.get(key,{})
        # A shorter configured retry also applies to previously queued failures.
        return now >= min(record.get('retry_after',0),record.get('at',0)+settings.get('retry_seconds',21600))
    due = [k for k in due if retry_due(k)]
    targets = list(state.get('fast_targets', {}).values())
    benchmarks=[]
    for record in targets:
        if record['offer']['shop'] in settings.get('anchor_shop_ids',[]):
            obj,error=preorders.identity(record['offer'],cfg)
            if not error:benchmarks.append(obj)
    # Reserve at most half the slots for immediately checkable benchmark pages.
    # The remaining oldest-first slots keep unknown/new products progressing.
    ready=[k for k in due if any(same_product(missing[k],o,cfg,state) for o in benchmarks)]
    ready=ready[:max(1,settings.get('max_products',2)//2)]
    due=ready+[k for k in due if k not in ready]
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
    try:
        for key in due[:settings.get('max_products', 2)]:
            if time.monotonic() >= end or limited.requests >= limited.maximum:
                break
            report['attempted'] += 1
            limited.product_deadline = min(end,time.monotonic()+8)
            target = missing[key]
            evidence = []
            tested = {r['key'] for r in quotes.values() if r.get('validated_at') == now}

            def consider(row):
                shop = shops.get(row['shop'])
                obj, error = preorders.identity(row, cfg)
                if (error or not same_product(target, obj, cfg, state) or not shop or
                        not (trusted_live(row, shop, cfg, now) or listed_price(row, shop, cfg, now))):
                    return
                if evidence_for(target, obj):
                    evidence.append(obj)
            candidates = []
            for record in targets:
                o = record['offer']
                obj, error = preorders.identity(o, cfg)
                if not error and o['shop'] in shops and same_product(target, obj, cfg, state):
                    candidates.append(o)
            candidates.sort(key=lambda o: (o['shop'] not in settings.get('anchor_shop_ids', []), o.get('available') is not True))
            cursor = checks.get(key, {}).get('candidate_cursor', 0)
            if candidates:
                offset = cursor % len(candidates)
                candidates = candidates[offset:] + candidates[:offset]

            def validate(o):
                if o['key'] in tested or o['shop'] not in shops:
                    return
                tested.add(o['key'])
                try:
                    row, error = preorders.live(o, shops[o['shop']], limited, now)
                    if row and error in (None, 'OUT_OF_STOCK'):
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
                for shop in shops.values():
                    if (shop['id'] not in settings.get('anchor_shop_ids', []) or
                            shop.get('retail_search_path') != '/search' or
                            limited.requests >= limited.maximum or time.monotonic() >= end):
                        continue
                    try:
                        for o in benchmark_search(shop,target,limited):
                            obj, error = preorders.identity(o, cfg)
                            if not error and same_product(target, obj, cfg, state):
                                # The detail parser already read the exact page.
                                consider(dict(obj,validated_at=now))
                                if evidence:break
                    except Exception as exc:
                        report['errors'].append({'shop':shop['id'],'type':type(exc).__name__})
                    if evidence:
                        break
            # Search results are discovery only; their prices/availability never vote.
            if not evidence:
                query = search_query(target)
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
                status = 'RESOLVED_LIVE_RETAIL'
                save_reference(key, target, evidence, status)
            else:
                status = 'DEFERRED_BUDGET' if limited.requests >= limited.maximum or time.monotonic() >= limited.product_deadline else 'NO_VERIFIED_RETAIL_REFERENCE'
                checks[key] = {'at': now, 'retry_after': now + (300 if status == 'DEFERRED_BUDGET' else settings.get('retry_seconds', 21600)), 'status': status}
                report['results'].append({'product': target['title'], 'status': status})
            checks[key]['candidate_cursor'] = cursor + min(3, len(candidates))
    finally:
        if original is not None:
            client.deadline = original
    report['requests'] = limited.requests
    report['pending'] -= report['resolved']
    report['due'] = sum(retry_due(k) for k in missing if not reference_for(missing[k],cfg,now))
    # Bound state without extending evidence lifetime or dropping a current ceiling.
    db['checks'] = dict(sorted(checks.items(), key=lambda x: x[1]['at'], reverse=True)[:5000])
    return report
