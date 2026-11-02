"""Public Yonkai Berlin catalog and exact product validation; GET requests only.

WooCommerce Store API is public and needs no account/key. Its positive stock
alone is insufficient: the actual product page and its public YKP storefront
data must agree. JavaScript is parsed as a JSON assignment, never executed.
"""
from decimal import Decimal
from html import unescape
import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from .checkout import BLOCK, ORDER, SOLD, label
from .sources import plain
from .web_sources import Document, normalized, same_site, structured_products

API = '/wp-json/wc/store/v1/products'


def product_label(name):
    # The storefront uses "Dragon Ball" while Woo/page names use
    # "Dragonball Super". Only normalize that known franchise prefix;
    # the remaining product name, set, language and edition must still agree.
    return re.sub(r'^dragon\s*ball(?: super)?(?= )', 'dragon ball', label(name))


def product_url(url, shop):
    p = urlsplit(url)
    return same_site(url, shop['base_url']) and p.path.startswith('/produkt/') and not p.query and not p.fragment


def price(product):
    prices = product.get('prices', {})
    value = prices.get('price', '')
    if (prices.get('currency_code') != 'EUR' or prices.get('currency_minor_unit') != 2
            or not isinstance(value, str) or not value.isdigit() or int(value) <= 0
            or prices.get('price_range') is not None):
        raise ValueError('Ambiguous EUR price')
    return str(Decimal(value) / 100)


def offer(product, shop):
    if (type(product.get('id')) is not int or product['id'] <= 0
            or not product_url(product.get('permalink', ''), shop)
            or not isinstance(product.get('name'), str)
            or not isinstance(product.get('is_in_stock'), bool)):
        raise ValueError('Invalid public product schema')
    return normalized(shop, product['permalink'], product['name'], price(product),
                      product['is_in_stock'], sku=product['id'],
                      description=plain(product.get('description', '')) + ' ' + plain(product.get('short_description', '')))


def scan(shop, client):
    endpoint = shop['base_url'] + API
    progress = {'url': endpoint, 'pages': 0, 'products': 0, 'complete': False}
    coverage = shop['_catalog_coverage'] = dict(complete=False, endpoints=[progress], products=0)
    rows, warnings, seen = [], [], set()
    for page in range(1, shop.get('max_pages', 40) + 1):
        try:
            data = client.get(f'{endpoint}?per_page=100&page={page}')
            if not isinstance(data, list):
                raise ValueError('Unexpected catalog schema')
            progress['pages'] += 1
            progress['products'] += len(data)
            for product in data:
                row = offer(product, shop)
                if row['key'] in seen:
                    raise ValueError('Repeated catalog product')
                seen.add(row['key'])
                rows.append(row)
            if len(data) < 100:
                coverage['complete'] = progress['complete'] = True
                break
        except Exception as error:
            warnings.append('Yonkai catalog incomplete: ' + type(error).__name__)
            break
    coverage['products'] = len(rows)
    if not coverage['complete'] and not warnings:
        warnings.append('Yonkai catalog page limit reached')
    return rows, warnings


def storefront(body, shop, client, now):
    """Follow only the public inventory script actually linked by this page."""
    urls = set()
    for node in Document(body).root.walk():
        if node.tag != 'script' or not node.attrs.get('src'):
            continue
        url = urljoin(shop['base_url'], node.attrs['src'])
        p = urlsplit(url)
        if (same_site(url, shop['base_url']) and p.path == '/' and not p.fragment
                and re.fullmatch(r'yk_ykp=[a-f0-9]{6,64}', p.query)):
            urls.add(url)
    if len(urls) != 1:
        raise ValueError('Ambiguous storefront inventory')
    source = client.text(next(iter(urls)) + '&_preorder_check=' + str(int(now)))
    match = re.fullmatch(r'\s*window\.YKP\s*=\s*(\[.*\])\s*;?\s*', source, re.S)
    if not match:
        raise ValueError('Unexpected storefront inventory')
    products = json.loads(match[1])
    if not isinstance(products, list):
        raise ValueError('Unexpected storefront inventory')
    return products


def live(o, shop, client, now):
    vid = str(o.get('variant_id', ''))
    if not vid.isdigit() or not product_url(o['url'], shop):
        return None, 'AMBIGUOUS_VARIANT'
    stamp = '?_preorder_check=' + str(int(now))
    body = client.text(o['url'] + stamp)
    api = client.get(shop['base_url'] + API + '/' + vid + stamp)
    if (str(api.get('id')) != vid or api.get('permalink') != o['url']
            or api.get('type') != 'simple' or api.get('has_options') is not False
            or api.get('variations') or api.get('is_password_protected') is True):
        return None, 'AMBIGUOUS_VARIANT'
    page_ids = set(re.findall(r'window\.YKPID\s*=\s*(\d+)\s*;', body))
    products = [p for p in structured_products(Document(body)) if p.get('url') == o['url']]
    password_form = any(n.attrs.get('name') == 'post_password' for n in Document(body).root.walk())
    if page_ids != {vid} or len(products) != 1 or password_form:
        return None, 'AMBIGUOUS_VARIANT'
    product = products[0]
    data = product.get('offers', {})
    if (not isinstance(data, dict) or data.get('url') != o['url']
            or product_label(product.get('name', '')) != product_label(api.get('name', ''))
            or product.get('sku', '') != api.get('sku', '')
            or data.get('priceCurrency') != 'EUR'):
        return None, 'AMBIGUOUS_VARIANT'
    row = offer(api, shop)
    if Decimal(str(data.get('price'))) != Decimal(row['price']):
        return None, 'STALE_PRICE'
    matches = [p for p in storefront(body, shop, client, now) if str(p.get('id')) == vid]
    if len(matches) != 1:
        return None, 'AMBIGUOUS_VARIANT'
    item = matches[0]
    if (item.get('u') != o['url'] or type(item.get('p')) is not int
            or product_label(str(item.get('g', '')) + ' ' + str(item.get('n', ''))) != product_label(product['name'])
            or item.get('s') not in (0, 1) or type(item.get('s')) is not int):
        return None, 'AMBIGUOUS_VARIANT'
    if Decimal(item['p']) / 100 != Decimal(row['price']):
        return None, 'STALE_PRICE'
    row.update(key=o['key'], title=plain(product['name']), description=plain(product.get('description', '')),
               current_price=row['price'], product_url=o['url'], variant_validated=True,
               live_validated=True, cart_validated=False, add_to_cart_available=False,
               availability_status='unknown', preorder_status=False, release_date=None,
               shipping_cost=None, stock_text='')
    status = str(data.get('availability', '')).rsplit('/', 1)[-1]
    def reject(reason, state):
        row.update(available=False, availability_status=state, stock_text=reason)
        return row, reason
    if (status in ('OutOfStock', 'SoldOut', 'Discontinued') or api.get('is_in_stock') is False
            or item['s'] == 0 or item.get('q') == 0 or SOLD.search(row['description'])):
        return reject('OUT_OF_STOCK', 'out_of_stock')
    if status not in ('InStock', 'PreOrder') or api.get('is_in_stock') is not True:
        return reject('NO_CHECKOUT', 'unknown')
    release = item.get('pre')
    if release:
        if (not isinstance(release, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', release)
                or type(item.get('cap')) is not int or type(item.get('booked')) is not int
                or item['cap'] <= 0 or item['booked'] < 0):
            return reject('NO_CHECKOUT', 'unknown')
        if item['booked'] >= item['cap']:
            return reject('WAITLIST', 'waitlist')
    description = row['description'] + ' ' + plain(item.get('d', ''))
    if BLOCK.search(description) or re.search(r'unverbindlich|(?:nur|lediglich)\s+(?:eine\s+)?reservier|verlosung|\braffle\b', description, re.I):
        return reject('WAITLIST', 'waitlist')
    cart = api.get('add_to_cart', {})
    cart_url = unescape(str(cart.get('url', '')))
    cart_ids = parse_qs(urlsplit(cart_url).query).get('add-to-cart', [])
    if (api.get('is_purchasable') is not True or item.get('buy') is not True
            or api.get('is_on_backorder') is not False or cart_ids != [vid]
            or not same_site(urljoin(shop['base_url'], cart_url), shop['base_url'])
            or not ORDER.search(str(cart.get('text', '')))
            or type(cart.get('minimum')) is not int or cart['minimum'] != 1
            or type(cart.get('maximum')) is not int or cart['maximum'] < 1):
        return reject('NO_CHECKOUT', 'unknown')
    row.update(available=True, add_to_cart_available=True, preorder_status=bool(release),
               preorder=bool(release), release_date=release,
               availability_status='preorder' if release else 'in_stock',
               stock_text='Direkt vorbestellbar' if release else 'Auf Lager')
    if shop.get('shipping_eur') and shop.get('free_shipping_from_eur'):
        row['shipping_cost'] = ('0.00' if Decimal(row['price']) >= Decimal(shop['free_shipping_from_eur'])
                                else shop['shipping_eur'])
    return row, None
