"""Official daily downloads: informational market data, never live offers or MSRP."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import time

BASE = 'https://downloads.s3.cardmarket.com/productCatalog/'
GAMES = {6: 'Pokémon', 13: 'Dragon Ball', 18: 'One Piece'}


def urls(game):
    if game not in GAMES:
        raise ValueError('Unsupported Cardmarket game')
    return (BASE+f'productList/products_nonsingles_{game}.json',
            BASE+f'priceGuide/price_guide_{game}.json')


def timestamp(value):
    try:
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value.timestamp() if value.tzinfo else None
    except (ValueError, AttributeError, OverflowError):
        return None


def positive(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = Decimal(str(value))
        return str(n) if n.is_finite() and n > 0 else None
    except InvalidOperation:
        return None


def join(catalog, guide, mappings, now):
    if catalog.get('version') != 1 or guide.get('version') != 1:
        raise ValueError('Unsupported Cardmarket schema')
    at, cat_at = timestamp(guide.get('createdAt')), timestamp(catalog.get('createdAt'))
    if at is None or not 0 <= now-at <= 48*3600 or cat_at is None or not -300 <= now-cat_at <= 90*86400:
        raise ValueError('Stale or undated Cardmarket snapshot')
    products, prices = catalog.get('products'), guide.get('priceGuides')
    if not isinstance(products, list) or not products or not isinstance(prices, list) or not prices:
        raise ValueError('Missing Cardmarket records')
    wanted = {m['product_id']:m for m in mappings}
    cats, guides = {}, {}
    for rows, target in ((products, cats), (prices, guides)):
        for row in rows:
            if row.get('idProduct') in wanted:
                if row['idProduct'] in target:
                    raise ValueError('Duplicate Cardmarket product ID')
                target[row['idProduct']] = row
    result = {}
    for pid, mapping in wanted.items():
        product, price = cats.get(pid, {}), guides.get(pid, {})
        # ID, original name and category must ALL agree; never fuzzy-match a card,
        # case, non-English or Asia edition based on a similar display title.
        if (product.get('name') != mapping['catalog_name'] or
                product.get('idCategory') != mapping['category_id'] or
                price.get('idCategory') != mapping['category_id']):
            continue
        values = {k:positive(price.get(k)) for k in ('trend','low','avg1','avg7','avg30')}
        if not values['trend']:
            continue
        result[str(pid)] = dict(values, product_id=pid, name=product['name'],
                               category_id=mapping['category_id'], at=at,
                               created_at=guide['createdAt'], currency='EUR')
    return result


def refresh(cfg, state, client, now):
    settings = cfg.get('price_comparison', {})
    if not settings.get('enabled'):
        return {'status':'disabled', 'games':[]}
    if not callable(getattr(client, 'cardmarket_json', None)):
        return {'status':'unavailable', 'games':[]}
    table = state.setdefault('cardmarket_daily', {})
    report = {'status':'ok', 'games':[]}
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    old_deadline = client.deadline
    client.deadline = min(old_deadline, time.monotonic()+35)
    try:
        for game in GAMES:
            mappings = [m for m in settings['products'] if m['game_id']==game]
            if not mappings:
                continue
            cache = table.setdefault(str(game), {})
            if cache.get('checked_day') == day or now < cache.get('retry_after', 0):
                report['games'].append({'game':game,'status':'cached' if cache.get('checked_day')==day else 'backoff','products':len(cache.get('products',{}))})
                continue
            try:
                catalog_url, guide_url = urls(game)
                catalog = client.cardmarket_json(catalog_url)
                guide = client.cardmarket_json(guide_url)
                products = join(catalog, guide, mappings, now)
                if not products:
                    raise ValueError('No matched Cardmarket products')
                table[str(game)] = {'checked_day':day, 'checked_at':now, 'products':products}
                report['games'].append({'game':game,'status':'updated','products':len(products)})
            except Exception as exc:
                # Retain dated prior data; lookup independently expires it.
                cache['retry_after'] = now+3600
                report['status'] = 'partial'
                report['games'].append({'game':game,'status':'unavailable','error':type(exc).__name__})
    finally:
        client.deadline = old_deadline
    return report


def lookup(mapping, state, now):
    row = state.get('cardmarket_daily', {}).get(str(mapping['game_id']), {}).get('products', {}).get(str(mapping['product_id']))
    if (not row or row.get('name')!=mapping['catalog_name'] or
            row.get('category_id')!=mapping['category_id'] or
            not 0 <= now-row.get('at', 0) <= 48*3600 or not positive(row.get('trend'))):
        return None
    return dict(row, source_url=urls(mapping['game_id'])[1])
