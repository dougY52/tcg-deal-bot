"""Add additional adapters through ADAPTERS. No browser/search API needed."""
from .http import FetchError
from decimal import Decimal, InvalidOperation
from html import unescape
import re
from urllib.parse import quote


def plain(value):
    return unescape(re.sub('<[^>]+>', ' ', str(value or '')))


def parse_product(shop, product):
    if not isinstance(product.get('variants'), list) or not product.get('handle'):
        raise ValueError('Unexpected product schema')
    result = []
    for variant in product['variants']:
        try:
            price = Decimal(str(variant['price']))
        except (InvalidOperation, KeyError):
            raise ValueError('Invalid variant price') from None
        if not price.is_finite() or price < 0 or not isinstance(variant.get('available'), bool):
            raise ValueError('Invalid price or availability')
        vid = str(variant['id'])
        result.append({
            'key': shop['id'] + ':' + vid, 'shop': shop['id'], 'shop_name': shop['name'],
            'handle': product['handle'], 'variant_id': vid,
            'title': plain(product['title']), 'variant': plain(variant.get('title', '')),
            'description': plain(product.get('body_html', '')),
            'price': str(price), 'available': variant['available'],
            'gtin': str(variant.get('barcode') or ''),
            'seller': shop['name'], 'seller_verified': True,
            'international': shop.get('international', False),
            'ships_to_de': shop.get('ships_to_de'),
            'import_costs': shop.get('import_costs', False),
            'shipping_note': shop.get('shipping_note', ''),
            'currency': variant.get('price_currency', shop['currency']),
            'url': shop['base_url'] + '/products/' + quote(product['handle'], safe='-') + '?variant=' + vid,
        })
    return result


def shopify(shop, client):
    products = {}
    warnings = []
    shop.setdefault('_catalog_next_pages', dict(shop.get('_catalog_pages', {})))
    # Exact approved handles are always checked, even if discovery pagination stops.
    for handle in shop.get('watch_handles', []):
        try:
            product = client.get(shop['base_url'] + '/products/' + quote(handle, safe='-') + '.js')
            product['body_html'] = product.get('description', '')
            # Shopify Ajax prices are integer minor units, unlike catalog decimal strings.
            for variant in product['variants']:
                if not isinstance(variant['price'], int):
                    raise ValueError('Expected integer Shopify Ajax price')
                variant['price'] = str(Decimal(variant['price']) / 100)
            if product['handle'] != handle:
                raise ValueError('Product identity mismatch')
            products[product['handle']] = product
        except Exception as exc:
            warnings.append('Watched product unavailable: ' + handle + ' (' + type(exc).__name__ + ')')
    endpoints = [shop['base_url'] + '/products.json']
    endpoints.extend(shop['base_url'] + '/collections/' + name + '/products.json' for name in shop.get('catalog_collections', []))
    if shop.get('rotate_collections') and len(endpoints) > 1:
        targets = endpoints[1:]
        index = shop.get('_catalog_pages', {}).get('_collection_index', 0) % len(targets)
        shop['_catalog_next_pages']['_collection_index'] = index + 1
        endpoints = [targets[index], endpoints[0]]
    for endpoint in endpoints:
        limit = shop.get('max_pages', 20)
        cursor = shop.get('_catalog_pages', {}).get(endpoint, 1)
        cursor = cursor if isinstance(cursor, int) and 1 <= cursor <= 1000 else 1
        pages = list(range(cursor, cursor + limit))
        if cursor > 1 and limit > 1:
            pages = [1] + pages[:max(0, limit - 1)]
        next_pages = shop.setdefault('_catalog_next_pages', {})
        for index, page in enumerate(pages):
            try:
                data = client.get(f"{endpoint}?limit=250&page={page}")
                rows = data['products']
                if not isinstance(rows, list):
                    raise ValueError('Unexpected catalog schema')
                for p in rows:
                    products.setdefault(p['handle'], p)
                if len(rows) < 250:
                    next_pages[endpoint] = 1
                    # A short first page proves there is no remaining catalog.
                    break
                next_pages[endpoint] = min(page + 1, 1000) if page != 1 or cursor == 1 else cursor
                if index == len(pages) - 1:
                    warnings.append('Catalog page limit reached; increase max_pages or configure targeted collections')
            except Exception as exc:
                warnings.append('Catalog discovery incomplete: ' + (str(exc) if isinstance(exc, FetchError) else type(exc).__name__))
                break
    # Discovery is deliberately bounded. Exact watched products are independent.
    if not products:
        return [], warnings + ['No valid products received']
    offers = []
    for product in products.values():
        offers.extend(parse_product(shop, product))
    return offers, warnings


ADAPTERS = {'shopify': shopify}
