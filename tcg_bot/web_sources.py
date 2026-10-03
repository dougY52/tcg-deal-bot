"""Public HTML adapters. No browser fingerprint spoofing, login or CAPTCHA bypass."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from .sources import plain

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, attrs or {}, []
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node): yield from child.walk()
    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

class Document(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.stack = [self.root]; self.feed(body)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs)); self.stack[-1].children.append(node)
        if tag not in VOID: self.stack.append(node)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]; break
    def handle_data(self, text):
        self.stack[-1].children.append(text)


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from walk_json(child)
    elif isinstance(value, list):
        for child in value: yield from walk_json(child)


def money(value):
    text = str(value).strip().replace('€', '').replace('\xa0', '').replace(' ', '')
    if ',' in text: text = text.replace('.', '').replace(',', '.')
    try: result = Decimal(text)
    except InvalidOperation: raise ValueError('Invalid amount') from None
    if not result.is_finite() or result <= 0: raise ValueError('Invalid amount')
    return str(result)


def same_site(url, base):
    return urlsplit(url).scheme == 'https' and urlsplit(url).netloc == urlsplit(base).netloc


def canonical(url):
    p = urlsplit(url)
    # Keep variant/store query params: different selected variants must never be merged.
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def identifier(url):
    return 'web-' + sha256(canonical(url).encode()).hexdigest()[:20]


def normalized(shop, url, title, price, stock, *, sku=None, description='', gtin='', seller=None, currency='EUR', **extra):
    url = canonical(urljoin(shop['base_url'], url))
    if not same_site(url, shop['base_url']): raise ValueError('Offsite offer URL')
    handle = identifier(url)
    vid = str(sku or int(sha256(url.encode()).hexdigest()[:15], 16))
    seller = seller or (None if shop.get('marketplace') else shop['name'])
    trusted = bool(seller and seller.casefold() in [s.casefold() for s in shop.get('allowed_sellers', [shop['name']])])
    row = {'key': shop['id'] + ':' + vid + ':' + sha256((seller or 'unknown').encode()).hexdigest()[:8],
           'shop': shop['id'], 'shop_name': shop['name'], 'handle': handle, 'variant_id': vid,
           'variant': 'Default Title', 'title': plain(title), 'description': plain(description),
           'price': money(price), 'currency': currency, 'available': stock, 'url': url,
           'gtin': str(gtin), 'seller': seller, 'seller_verified': trusted,
           'channel': 'online', 'store_status': 'not_checked'}
    row.update(extra)
    return row


def structured_products(document):
    result = []
    for node in document.root.walk():
        if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
            try: data = json.loads(node.text())
            except ValueError: continue
            result.extend(x for x in walk_json(data) if 'Product' in ([x.get('@type')] if isinstance(x.get('@type'), str) else x.get('@type', [])))
        if node.attrs.get('itemtype', '').rstrip('/').endswith('/Product'):
            props = {}
            for el in node.walk():
                key = el.attrs.get('itemprop')
                if key and key not in props:
                    props[key] = el.attrs.get('content') or el.attrs.get('href') or el.text().strip()
            if not props.get('url'):
                props['url'] = next((el.attrs['href'] for el in node.walk() if el.tag == 'a' and el.attrs.get('href')), '')
            if not props.get('sku'):
                props['sku'] = next((el.attrs.get('value') for el in node.walk() if el.tag == 'input' and el.attrs.get('name') == 'a'), None)
            result.append({'@type': 'Product', 'name': props.get('name'), 'url': props.get('url'),
                           'sku': props.get('sku'), 'description': props.get('description', ''),
                           'gtin13': props.get('gtin13', props.get('gtin', '')),
                           'offers': {'price': props.get('price'), 'priceCurrency': props.get('priceCurrency'),
                                      'availability': props.get('availability')}})
    return result


def parse_structured(shop, body, page_url):
    if shop.get('adapter') == 'woocommerce':
        return parse_woocommerce(shop, body, page_url), []
    rows, links = [], []
    for product in structured_products(Document(body)):
        url = urljoin(page_url, product.get('url') or page_url)
        if not same_site(url, shop['base_url']) or not product.get('name'): continue
        links.append(url)
        offers = product.get('offers', [])
        if isinstance(offers, dict): offers = [offers]
        for offer in offers:
            # Aggregate lowPrice is not executable; explicit PreOrder/BackOrder is orderable.
            if not isinstance(offer, dict) or offer.get('price') is None: continue
            avail = str(offer.get('availability', '')).rsplit('/', 1)[-1]
            stock = True if avail in ('InStock', 'PreOrder', 'BackOrder') else False if avail in ('OutOfStock', 'SoldOut', 'Discontinued') else None
            if offer.get('availableAtOrFrom') or 'OnSitePickup' in str(offer.get('availableDeliveryMethod', '')):
                stock = None  # Physical-store offers must never masquerade as online inventory.
            seller = offer.get('seller', {})
            seller = seller.get('name') if isinstance(seller, dict) else seller
            try:
                rows.append(normalized(shop, offer.get('url') or url, product['name'], offer['price'], stock,
                                       sku=product.get('sku'), description=product.get('description', ''),
                                       gtin=product.get('gtin13') or product.get('gtin') or '', seller=seller,
                                       currency=offer.get('priceCurrency', ''), condition=offer.get('itemCondition', product.get('itemCondition', '')), preorder=avail in ('PreOrder', 'BackOrder'), release_date=offer.get('availabilityStarts') or product.get('releaseDate') or ''))
            except ValueError: continue
    return rows, list(dict.fromkeys(links))


def html_catalog(shop, client):
    rows, notes = {}, []
    catalog = list(dict.fromkeys(shop.get('catalog_urls', [])))
    watched = list(dict.fromkeys(shop.get('watch_urls', [])))
    pages = [(url, True) for url in catalog] + [(url, False) for url in watched]
    seen, details = set(), set()
    page_count = 0
    detail_limit = shop.get('max_detail_pages', 20)
    for url, is_catalog in pages:
        if url in seen:
            continue
        seen.add(url)
        try:
            body = client.text(url)
            parsed, links = parse_structured(shop, body, url)
            if not is_catalog and shop.get('detail_description_hook'):
                sections = [n.text() for n in Document(body).root.walk() if n.attrs.get('data-hook') == shop['detail_description_hook']]
                if sections:
                    for row in parsed:
                        row['description'] += ' ' + sections[0]
            for row in parsed:
                previous = [k for k, old in rows.items() if old['url'] == row['url']]
                for key in previous:
                    del rows[key]
                rows[row['key']] = row
            if is_catalog:
                page_count += 1
                for node in Document(body).root.walk():
                    href = node.attrs.get('href') if node.tag == 'a' else None
                    if not href:
                        continue
                    target = canonical(urljoin(url, href))
                    if not same_site(target, shop['base_url']):
                        continue
                    if node.attrs.get('rel') == 'next' and page_count < shop.get('max_pages', 1) * max(1, len(catalog)):
                        pages.append((target, True))
                    if re.search(shop.get('product_link_pattern', r'/products?/|/produkt/'), target) and re.search(r'display|booster.box', href + ' ' + node.text(), re.I):
                        links.append(target)
                for link in dict.fromkeys(links):
                    if link in seen or link in details or link in watched:
                        continue
                    if len(details) >= detail_limit:
                        if 'Detail page limit reached; discovery incomplete' not in notes:
                            notes.append('Detail page limit reached; discovery incomplete')
                        break
                    if same_site(link, shop['base_url']):
                        details.add(link)
                        pages.append((link, False))
        except Exception as exc:
            notes.append('Page unavailable: ' + type(exc).__name__)
    if not rows:
        return [], notes + ['No usable structured product offers']
    return list(rows.values()), notes


def mms_state(body):
    match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(.*?)</script>', body, re.S)
    if not match: raise ValueError('Missing public page state')
    # Parse a JSON-like serialization, never execute site JavaScript.
    serialized = match[1].strip().rstrip(';')
    serialized = re.sub(r'(?<=:)undefined(?=[,}])', 'null', serialized)
    return json.loads(serialized)


def parse_mms(shop, body, url):
    state = mms_state(body)
    rows = []
    for data in state.get('routerHydrationData', {}).get('loaderData', {}).values():
        data = data.get('data', {}) if isinstance(data, dict) else {}
        if not isinstance(data, dict) or 'productAggregate' not in data or 'cofrProductAggregate' not in data: continue
        product = data['productAggregate'].get('product') or {}
        cofr = data['cofrProductAggregate']
        pricing = cofr.get('cofrPriceFeature') or {}
        price = pricing.get('price') or {}
        delivery = cofr.get('cofrDeliveryFeature') or {}
        status = (delivery.get('delivery') or {}).get('deliveryStatus')
        pickup = cofr.get('cofrPickupFeature') or {}
        online = cofr.get('cofrOnlineStatusFeature') or {}
        positive = {'AVAILABLE', 'AVAILABLE_IMMEDIATELY', 'AVAILABLE_ONLINE', 'AVAILABLE_WITHIN_REASONABLE_TIME_FRAME'}
        negative = {'NOT_AVAILABLE', 'PERMANENTLY_NOT_AVAILABLE', 'TEMPORARILY_NOT_AVAILABLE'}
        stock = True if status in positive else False if status in negative else None
        if (delivery.get('delivery') or {}).get('isZipCodeCheckNeeded'): stock = None
        if online.get('isAvailableAndBuyable') is False and stock is True: stock = None
        market = pricing.get('isProductOfTypeMarketplace')
        merchant = pricing.get('marketplaceSeller') or {}
        seller = (merchant.get('sellerName') or merchant.get('name')) if market is True else shop['name'] if market is False else None
        row = normalized(shop, url, product.get('title', ''), price.get('amount'), stock,
                         sku=product['id'], description=product.get('description', ''),
                         gtin=product.get('ean', ''), seller=seller, currency=pricing.get('currency', ''),
                         shipping_eur=delivery.get('shippingCost'), delivery_status=status,
                         preorder=bool(delivery.get('releaseDate') and delivery['releaseDate'][:10] > __import__('datetime').date.today().isoformat()),
                         store_status='selected' if pickup.get('storeId') else 'selection_required',
                         pickup_status=pickup.get('pickupStatus'), store_id=pickup.get('storeId'),
                         is_pickable=pickup.get('isProductPickable'))
        # Source must explicitly identify marketplace/direct seller; unknown is never trusted.
        if market is None: row['seller_verified'] = False
        rows.append(row)
    return rows


def mms(shop, client):
    notes, urls, rows = [], list(shop.get('watch_urls', [])), {}
    discovered = []
    for catalog in shop.get('catalog_urls', []):
        try:
            _, links = parse_structured(shop, client.text(catalog), catalog)
            discovered.extend(links)
        except Exception as exc: notes.append('Catalog unavailable: ' + type(exc).__name__)
    # Rotate discovery slices each hour so a fixed first page cannot starve other products.
    import time
    discovered = list(dict.fromkeys(discovered))
    cap = shop.get('max_product_pages', 16)
    if discovered:
        offset = (int(time.time() // 3600) * cap) % len(discovered)
        discovered = (discovered[offset:] + discovered[:offset])[:cap]
    urls = list(dict.fromkeys(urls + discovered))
    for url in urls:
        try:
            for row in parse_mms(shop, client.text(url), url): rows[row['key']] = row
        except Exception as exc: notes.append('Product page unavailable ' + urlsplit(url).path + ': ' + type(exc).__name__)
    if not rows: raise ValueError('No valid retailer products')
    return list(rows.values()), notes


def parse_otto(shop, body):
    match = re.search(r'<main[^>]*id="reptile-content"[^>]*>\s*', body)
    if not match: raise ValueError('Missing OTTO catalog state')
    data = json.JSONDecoder().raw_decode(body[match.end():])[0]
    rows = []
    for obj in walk_json(data):
        for item in obj.get('tileListItems', []):
            for v in item.get('variations', []):
                pricing = v.get('price') or {}
                if pricing.get('isStartingPrice') is not False: continue
                status = (v.get('availability') or {}).get('state')
                stock = True if status == 'AVAILABLE' else False if status in ('SOLD_OUT', 'NOT_AVAILABLE') else None
                seller = v.get('seller') or {}
                seller = seller.get('name') if isinstance(seller, dict) else seller
                try:
                    rows.append(normalized(shop, v['detailPageLink'], v['title']['full'], pricing['retailPrice'], stock,
                                           sku=v['variationId'], seller=seller,
                                           description=(v.get('availability') or {}).get('detail', ''),
                                           seller_verified=False, discovery_only=True))
                except (ValueError, KeyError): continue
    # Listing pages don't expose seller identity sufficiently. Keep as candidates only.
    return rows


def otto(shop, client):
    rows, notes = {}, []
    for url in shop.get('catalog_urls', []):
        try:
            for row in parse_otto(shop, client.text(url)): rows[row['key']] = row
        except Exception as exc: notes.append('Catalog unavailable: ' + type(exc).__name__)
    if not rows: raise ValueError('No OTTO catalog offers')
    return list(rows.values()), notes


def parse_woocommerce(shop, body, page_url):
    """Concrete WooCommerce variations, never a parent price/stock assumption."""
    doc = Document(body)
    titles = [n.text().strip() for n in doc.root.walk() if n.tag == 'h1']
    if len(titles) != 1 or not any(plain(p.get('name', '')).strip() == titles[0] for p in structured_products(doc)):
        return []
    description = ' '.join(n.text() for n in doc.root.walk() if n.attrs.get('id') == 'tab-description')
    if not description:
        description = ' '.join(plain(p.get('description','')) for p in structured_products(doc) if plain(p.get('name','')).strip() == titles[0])
    # Currency must come from this product's structured data, not shop prose.
    currencies = {str(x.get('priceCurrency')) for p in structured_products(doc) for x in walk_json(p) if x.get('priceCurrency')}
    if currencies != {'EUR'}:
        return []
    result = []
    for form in doc.root.walk():
        if form.tag != 'form' or form.attrs.get('method', '').lower() != 'post' or not form.attrs.get('data-product_id'):
            continue
        action = urljoin(page_url, form.attrs.get('action') or page_url)
        if not same_site(action, shop['base_url']):
            continue
        try:
            variations = json.loads(form.attrs.get('data-product_variations', 'null'))
        except ValueError:
            continue
        if not isinstance(variations, list):
            continue
        inputs = {n.attrs.get('name'): n.attrs.get('value') for n in form.walk() if n.tag == 'input'}
        if inputs.get('product_id') != form.attrs['data-product_id'] or inputs.get('add-to-cart') != form.attrs['data-product_id'] or 'variation_id' not in inputs:
            continue
        has_submit = any(n.tag == 'button' and n.attrs.get('type') == 'submit' and 'single_add_to_cart_button' in n.attrs.get('class','') and 'disabled' not in n.attrs and n.attrs.get('aria-disabled') != 'true' for n in form.walk())
        for v in variations:
            vid = str(v.get('variation_id', ''))
            attributes = v.get('attributes', {})
            if not vid.isdigit() or not attributes or any(not x for x in attributes.values()):
                continue
            # All attributes must have real selectable options on the product form.
            selectable = all(any(n.tag == 'select' and 'disabled' not in n.attrs and n.attrs.get('name') == name and any(child.tag == 'option' and child.attrs.get('value') == value and 'disabled' not in child.attrs for child in n.walk()) for n in form.walk()) for name,value in attributes.items())
            purchasable = has_submit and selectable and all(v.get(k) is True for k in ('is_in_stock','is_purchasable','variation_is_active','variation_is_visible'))
            stock_text = plain(v.get('availability_html', ''))
            preorder = v.get('is_pre_order') in (True, 'yes') or bool(re.search(r'vorbestell|pre[ -]?order', stock_text, re.I))
            if re.search(r'out.of.stock|sold out|ausverkauft|nicht lieferbar|nicht vorrätig|notify|waitlist|benachrichtigen', stock_text, re.I):
                purchasable = False
            if v.get('backorders_allowed') and not preorder:
                purchasable = False
            if v.get('max_qty') in (0, '0'):
                purchasable = False
            from urllib.parse import urlencode
            target = page_url.split('?')[0] + '?' + urlencode(dict(attributes, variation_id=vid))
            try:
                row = normalized(shop, target, titles[0], v.get('display_price'), bool(purchasable), sku=vid,
                                 description=description + ' ' + plain(v.get('variation_description','')),
                                 currency='EUR', preorder=preorder,
                                 variant_validated=True, live_validated=True,
                                 add_to_cart_available=bool(purchasable), cart_validated=False,
                                 stock_text=plain(v.get('availability_html', '')),
                                 availability_status='preorder' if preorder and purchasable else 'in_stock' if purchasable else 'out_of_stock',
                                 preorder_status=preorder, shipping_cost=None, release_date=None)
            except ValueError:
                continue
            row['variant'] = ' / '.join(attributes.values())
            row['current_price'] = row['price']
            row['product_url'] = target
            result.append(row)
    return result
