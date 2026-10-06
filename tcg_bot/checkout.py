"""Read-only checkout evidence for single-product JTL and WooCommerce pages."""
import re
from urllib.parse import urljoin, urlsplit
from .web_sources import Document, Node, structured_products, normalized, same_site, money
from .sources import plain

ORDER = re.compile(r'add to (?:cart|basket|bag)|in den warenkorb|zum warenkorb|vorbestell|pre.?order|jetzt kaufen', re.I)
BLOCK = re.compile(r'waitlist|warteliste|notify me|benachrichtigen|invitation only|coming soon|nur (?:für|an).{0,40}(?:mitglied|freigeschalt|turnier)|exklusiv.{0,30}mitglied', re.I)
SOLD = re.compile(r'out.of.stock|sold out|ausverkauft|nicht (?:mehr )?(?:lieferbar|vorrätig|verfügbar)', re.I)

def text(node):
    if node.tag in ('script', 'style', 'template', 'noscript') or 'hidden' in node.attrs:
        return ''
    return ' '.join(text(c) if isinstance(c, Node) else c for c in node.children)

def label(value):
    return re.sub(r'[\W_]+', ' ', plain(value).casefold()).strip()

def enabled(node):
    return ('disabled' not in node.attrs and 'hidden' not in node.attrs and
            node.attrs.get('aria-disabled') != 'true' and node.attrs.get('aria-hidden') != 'true' and
            not re.search(r'(?:^|\s)(?:disabled|hidden|btn-hidden)(?:\s|$)', node.attrs.get('class', '')))

def controls(node):
    """Honor hidden/disabled ancestors, including disabled fieldsets."""
    if not enabled(node):
        return
    yield node
    for c in node.children:
        if isinstance(c, Node):
            yield from controls(c)

def product_data(body, url):
    doc = Document(body)
    titles = [text(n).strip() for n in doc.root.walk() if n.tag == 'h1']
    if len(titles) != 1:
        return None
    # JSON-LD can repeat a product in multiple graphs; contradictory entries fail closed.
    products = [p for p in structured_products(doc) if label(p.get('name', '')) == label(titles[0])]
    unique = {}
    for p in products:
        if p.get('url') and (not same_site(urljoin(url, p['url']), url) or urlsplit(urljoin(url, p['url'])).path.rstrip('/') != urlsplit(url).path.rstrip('/')):
            continue
        offers = p.get('offers', [])
        offers = offers if isinstance(offers, list) else [offers]
        for offer in offers:
            if not isinstance(offer, dict) or offer.get('priceCurrency') != 'EUR' or offer.get('price') is None:
                continue
            if offer.get('url') and (not same_site(urljoin(url, offer['url']), url) or urlsplit(urljoin(url, offer['url'])).path.rstrip('/') != urlsplit(url).path.rstrip('/')):
                continue
            if offer.get('availableAtOrFrom') or 'OnSitePickup' in str(offer.get('availableDeliveryMethod', '')):
                continue
            unique[(str(p.get('sku', '')), str(offer['price']), str(offer.get('availability', '')))] = (p, offer)
    if len(unique) != 1:
        return None
    p, offer = next(iter(unique.values()))
    if not p.get('sku'):
        return None
    return doc, titles[0], p, offer

def single_product(shop, body, url):
    """A dedicated form is bound to the page SKU; selectable variants fail closed."""
    data = product_data(body, url)
    if not data:
        return []
    doc, title, product, offer = data
    avail = str(offer.get('availability', '')).rsplit('/', 1)[-1]
    description = plain(product.get('description', ''))
    forms = []
    for f in doc.root.walk():
        if f.tag != 'form' or f.attrs.get('method', '').lower() != 'post' or not enabled(f):
            continue
        action = urljoin(url, f.attrs.get('action') or url)
        if not same_site(action, shop['base_url']) or urlsplit(action).path.rstrip('/') != urlsplit(url).path.rstrip('/'):
            continue
        nodes = list(controls(f))
        inputs = {n.attrs.get('name'): n.attrs.get('value', '') for n in nodes if n.tag == 'input'}
        # Variant selectors/configurators require a dedicated variant validator.
        if any(n.tag == 'select' and n.attrs.get('name') not in ('quantity','anzahl') or
               n.tag == 'input' and (n.attrs.get('type') == 'radio' or n.attrs.get('name', '').startswith(('attribute_', 'eigenschaft'))) for n in nodes):
            continue
        if shop['adapter'] == 'jtl':
            if f.attrs.get('id') != 'buy_form' or not inputs.get('a', '').isdigit():
                continue
            article = inputs['a']
            if not any(n.attrs.get('name') == 'anzahl' and n.attrs.get('data-product-id') == article for n in nodes):
                continue
            buttons = [n for n in nodes if n.tag == 'button' and n.attrs.get('type','submit') == 'submit' and n.attrs.get('name') == 'inWarenkorb']
        else:
            if 'cart' not in f.attrs.get('class', '').split() or f.attrs.get('data-product_variations'):
                continue
            buttons = [n for n in nodes if n.tag == 'button' and n.attrs.get('type','submit') == 'submit' and
                       'single_add_to_cart_button' in n.attrs.get('class','') and n.attrs.get('name') == 'add-to-cart' and n.attrs.get('value','').isdigit()]
            article = buttons[0].attrs['value'] if len(buttons) == 1 else ''
        if len(buttons) != 1 or not article:
            continue
        forms.append((f, buttons[0], article))
    allowed = len(forms) == 1
    stock_text = text(forms[0][0]) if allowed else ''
    cart_text = text(forms[0][1]) if allowed else ''
    restricted = BLOCK.search(description + ' ' + stock_text)
    sold = avail in ('OutOfStock', 'SoldOut', 'Discontinued') or SOLD.search(stock_text)
    preorder = avail == 'PreOrder' or bool(re.search(r'vorbestell|pre[ -]?order', description + ' ' + cart_text, re.I))
    # BackOrder alone is not a commitment to fulfil an order.
    orderable = bool(allowed and ORDER.search(cart_text) and not restricted and not sold and
                     avail in ('InStock','PreOrder') and not SOLD.search(cart_text))
    available = False if sold else True if orderable else None
    try:
        row = normalized(shop, url, title, offer['price'], available, sku=product['sku'],
                         description=description, gtin=product.get('gtin13') or product.get('gtin') or '',
                         currency='EUR', live_validated=True, variant_validated=allowed,
                         add_to_cart_available=orderable, cart_validated=False,
                         availability_status='out_of_stock' if sold else 'preorder' if orderable and preorder else 'in_stock' if orderable else 'unknown',
                         preorder=preorder, preorder_status=preorder, stock_text=stock_text[:300],
                         shipping_cost=None, release_date=None)
    except ValueError:
        return []
    row.update(current_price=row['price'], product_url=url)
    if allowed:
        row['cart_product_id'] = forms[0][2]
    return [row]
