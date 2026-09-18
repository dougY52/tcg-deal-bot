"""Add additional adapters through ADAPTERS. No browser/search API needed."""
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
            'currency': variant.get('price_currency', shop['currency']),
            'url': shop['base_url'] + '/products/' + quote(product['handle'], safe='-') + '?variant=' + vid,
        })
    return result


def shopify(shop, client):
    products = {}
    warnings = []
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
    for page in range(1, shop.get('max_pages', 20) + 1):
        try:
            data = client.get(f"{shop['base_url']}/products.json?limit=250&page={page}")
            rows = data['products']
            if not isinstance(rows, list):
                raise ValueError('Unexpected catalog schema')
            for p in rows:
                products.setdefault(p['handle'], p)
            if len(rows) < 250:
                break
        except Exception as exc:
            warnings.append('Catalog discovery incomplete: ' + type(exc).__name__)
            break
    # Discovery is deliberately bounded. Exact watched products are independent.
    if not products:
        raise ValueError('No valid products received')
    offers = []
    for product in products.values():
        offers.extend(parse_product(shop, product))
    return offers, warnings


ADAPTERS = {'shopify': shopify}
