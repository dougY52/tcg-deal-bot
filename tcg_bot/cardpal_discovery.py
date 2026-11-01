"""CardPal expands product discovery; only the existing live validators may alert.

Public search filters are hints (CardPal can return other languages). Every
concrete offer, seller and shop product is therefore checked again locally.
"""
from decimal import Decimal, InvalidOperation
import re
import time
from urllib.parse import urlsplit, parse_qs, urlencode

from .sources import parse_product
from .retail_research import BudgetClient

ORIGIN = 'https://www.mycardpal.com'
TYPES = ('BOOSTER_BOX', 'ELITE_TRAINER_BOX', 'BUNDLE', 'COLLECTION_BOX', 'TIN')
FRANCHISES = {'POKEMON': 'Pokémon', 'DRAGONBALL': 'Dragon Ball', 'ONEPIECE': 'One Piece'}
FORMATS = {'POKEMON': TYPES, 'DRAGONBALL': ('BOOSTER_BOX', 'COLLECTION_BOX'),
           'ONEPIECE': ('BOOSTER_BOX', 'COLLECTION_BOX', 'STARTER_DECK')}
LANGUAGES = {'DE': 'German', 'EN': 'English'}
UUID = re.compile(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}')


def scopes(cfg):
    return [f for f in cfg.get('cardpal_discovery', {}).get('franchises', ['POKEMON']) if f in FRANCHISES]


def languages(cfg, code):
    default = ['DE'] if code == 'POKEMON' else ['EN']
    return [x for x in cfg.get('market', {}).get('franchise_languages', {}).get(FRANCHISES[code], default)
            if x in LANGUAGES]


def article_id(value):
    return isinstance(value, str) and UUID.fullmatch(value) is not None


def amount(value):
    try:
        value = Decimal(str(value))
        return value if value.is_finite() and value > 0 else None
    except InvalidOperation:
        return None


def keyname(value):
    return re.sub(r'[^a-z0-9]', '', str(value).casefold())


def shop_for(offer, cfg):
    """Only an already configured German seller can become an active target.

    Provider Shopify aliases are translated to the independently configured
    retailer's own domain; no request trusts an arbitrary myshopify host.
    """
    try:
        u = urlsplit(offer.get('url', ''))
        if (u.scheme != 'https' or not u.hostname or u.username or u.password or u.port
                or '%' in u.path or '..' in u.path or u.fragment):
            return None
    except ValueError:
        return None
    vendor = offer.get('vendor') or {}
    if vendor.get('is_marketplace') is True or offer.get('is_invite') is True:
        return None
    shops = [s for s in cfg['shops'] if s.get('enabled', True) and not s.get('international')
             and not s.get('marketplace') and s['currency'] == 'EUR']
    for shop in shops:
        host = urlsplit(shop['base_url']).hostname
        if u.hostname == host or (u.hostname.endswith('.myshopify.com') and
                keyname(vendor.get('company_name')) in {keyname(shop['name']), keyname(shop['id'])}):
            return shop
    return None


def candidate_offers(detail, cfg):
    a = detail.get('article') or {}
    code = a.get('franchise_code')
    if code not in scopes(cfg) or a.get('product_type') not in FORMATS[code]:
        return []
    out = []
    for offer in detail.get('offers', [])[:200]:
        price = amount(offer.get('price'))
        lang = {'de': 'DE', 'german': 'DE', 'en': 'EN', 'english': 'EN'}.get(str(offer.get('language', '')).lower())
        if (lang not in languages(cfg, code) or
                offer.get('availability') not in ('IN_STOCK', 'PREORDER') or
                offer.get('currency') != 'EUR' or offer.get('vat_included') is not True or
                offer.get('is_invite') is True or not price or
                price > Decimal(str(cfg['preorder_watch'].get('max_price_eur', 200)))):
            continue
        out.append(offer)
    return out


def product_rows(offer, shop, client):
    """Read the retailer's product; never promote provider price/stock/language."""
    u = urlsplit(offer['url'])
    if shop['adapter'] == 'shopify':
        match = re.search(r'/products/([a-z0-9_-]+)$', u.path)
        if not match:
            return []
        handle = match[1]
        product = client.get(shop['base_url'] + '/products/' + handle + '.js')
        if product.get('handle') != handle:
            return []
        selected = parse_qs(u.query).get('variant', [None])[0]
        product['body_html'] = product.get('description', '')
        for variant in product.get('variants', []):
            if type(variant.get('price')) is not int:
                return []
            variant['price'] = str(Decimal(variant['price']) / 100)
        return [r for r in parse_product(shop, product)
                if selected is None or r['variant_id'] == selected]
    if shop['adapter'] in ('jtl', 'shopware', 'woocommerce'):
        from .web_sources import parse_woocommerce
        from .checkout import single_product
        url = shop['base_url'] + u.path
        if not re.search(shop.get('product_link_pattern', r'.+'), url):
            return []
        parser = parse_woocommerce if shop['adapter'] == 'woocommerce' else single_product
        return parser(shop, client.text(url), url)
    return []


def relay_articles():
    """Read only article IDs from our own authenticated Worker, never its secrets."""
    import os
    if not os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL'):
        return []
    from urllib.request import Request, build_opener
    from .http import NoRedirect
    from .cloud_reader import github_token
    import json
    origin = 'https://tcg-mms-reader.tcg-deal-bot-dougy52.workers.dev'
    token = github_token(origin, 8)
    req = Request(origin + '/cardpal/discovery', headers={
        'Authorization': 'Bearer ' + token, 'User-Agent': 'TCGRetailWatch/1.0'})
    with build_opener(NoRedirect()).open(req, timeout=8) as response:
        value = json.loads(response.read(50001))
    return [x for x in value.get('article_ids', [])[:100] if article_id(x)]


def discover(cfg, state, client, now):
    settings = cfg.get('cardpal_discovery', {})
    report = {'enabled': bool(settings.get('enabled')), 'articles': 0, 'offers': 0,
              'targets': 0, 'shops': [], 'new_sellers': [], 'errors': [], 'requests': 0}
    if not settings.get('enabled'):
        return [], report
    db = state.setdefault('cardpal_discovery', {})
    if now - db.get('checked_at', 0) < settings.get('interval_seconds', 240):
        report['not_due'] = True
        return [], report
    db['checked_at'] = now
    limited = BudgetClient(client, time.monotonic() + settings.get('budget_seconds', 25),
                           settings.get('max_requests', 20))
    ids = []
    try:
        ids.extend(relay_articles())
    except Exception as error:
        report['errors'].append('relay:' + type(error).__name__)
    families = scopes(cfg)
    article_scopes = db.setdefault('article_scopes', {})
    # One search per franchise/run. Format, language and page rotate independently.
    for code in families:
        combinations = [(kind, lang) for kind in FORMATS[code] for lang in languages(cfg, code)]
        if not combinations:
            continue
        cursor = db.setdefault('scope_cursors', {}).get(code, 0) % len(combinations)
        kind, lang = combinations[cursor]
        query_key = code + ':' + lang + ':' + kind
        offset = db.setdefault('offsets', {}).get(query_key, 0)
        params = {'franchise': code, 'language': LANGUAGES[lang], 'product_type': kind,
                  'max_price': 200, 'limit': 30, 'offset': offset, 'sort_by': 'release_date_desc'}
        try:
            rows = limited.get(ORIGIN + '/api/search/?' + urlencode(params))
            if not isinstance(rows, list) or len(rows) > 30:
                raise ValueError('Invalid search response')
            db['offsets'][query_key] = offset + 30 if len(rows) == 30 and offset < 600 else 0
            found = [r['id'] for r in rows if article_id(r.get('id')) and
                     r.get('product_type') in FORMATS[code] and
                     (r.get('has_in_stock') is True or r.get('availability_status') == 'PREORDER')]
            ids.extend(found)
            article_scopes.update({aid: code for aid in found})
            db['scope_cursors'][code] = (cursor + 1) % len(combinations)
        except Exception as error:
            report['errors'].append('search:' + type(error).__name__)
    checked = db.setdefault('articles', {})
    pending = db.setdefault('pending', {})
    pending.update({aid: now for aid in ids})
    pending = dict(sorted(((aid, at) for aid, at in pending.items() if now - at < 7 * 86400),
                          key=lambda x: x[1], reverse=True)[:1000])
    db['pending'] = pending
    # Never let a busy inbox pin the same handful of articles on every run.
    ordered = sorted(pending, key=lambda x: checked.get(x, 0))
    # A large Pokemon backlog must not crowd out DB/OP or newly received article IDs.
    groups = [[aid for aid in ordered if article_scopes.get(aid) == code] for code in families]
    groups.append([aid for aid in ordered if article_scopes.get(aid) not in families])
    ids = [group[i] for i in range(max(map(len, groups), default=0)) for group in groups if i < len(group)]
    db['article_scopes'] = {aid: code for aid, code in article_scopes.items() if aid in pending}
    targets, visited = [], set()
    for aid in ids[:settings.get('max_articles', 6)]:
        checked[aid] = now
        try:
            detail = limited.get(ORIGIN + '/api/articles/' + aid + '/detail?locale=de')
            report['articles'] += 1
            code = (detail.get('article') or {}).get('franchise_code')
            if code in families:
                db['article_scopes'][aid] = code
            for offer in candidate_offers(detail, cfg):
                report['offers'] += 1
                shop = shop_for(offer, cfg)
                if not shop:
                    name = str((offer.get('vendor') or {}).get('company_name') or 'Unbekannt')[:100]
                    if name not in report['new_sellers']:
                        report['new_sellers'].append(name)
                    continue
                identity = (shop['id'], urlsplit(offer['url']).path)
                if identity in visited:
                    continue
                visited.add(identity)
                try:
                    rows = product_rows(offer, shop, limited)
                    for row in rows:
                        from .rules import language, franchise
                        if language(row) not in languages(cfg, code) or franchise(row, cfg) != FRANCHISES[code]:
                            continue
                        row['discovered_by'] = 'cardpal'
                        row['cardpal_article_id'] = aid
                        row['discovery_checked_at'] = now
                        targets.append(row)
                    if rows and shop['name'] not in report['shops']:
                        report['shops'].append(shop['name'])
                except Exception as error:
                    report['errors'].append(shop['id'] + ':' + type(error).__name__)
        except Exception as error:
            report['errors'].append('detail:' + type(error).__name__)
    # Bounded bookkeeping; old public IDs may safely be rediscovered.
    db['articles'] = dict(sorted(checked.items(), key=lambda x: x[1])[-1000:])
    report.update(targets=len(targets), requests=limited.requests, pending_articles=len(pending))
    db['report'] = report
    return targets, report
