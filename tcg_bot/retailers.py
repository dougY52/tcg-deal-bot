"""Retailer-specific checkout evidence; public product pages only."""
import re
from urllib.parse import urlsplit, parse_qs
from .web_sources import Document, structured_products, normalized, same_site
from .sources import plain

def visible_text(node):
    if node.tag in ('script','style','template','noscript') or 'hidden' in node.attrs or node.attrs.get('aria-hidden')=='true':
        return ''
    return ' '.join(visible_text(c) if hasattr(c,'tag') else c for c in node.children)

def mueller_product(shop, body, url, variant_id):
    if not same_site(url,shop['base_url']):
        return None,'AMBIGUOUS_VARIANT'
    doc=Document(body)
    titles=[n.text().strip() for n in doc.root.walk() if n.tag=='h1']
    products=[p for p in structured_products(doc) if str(p.get('sku'))==str(variant_id)]
    if len(titles)!=1 or len(products)!=1 or plain(products[0].get('name','')).strip()!=titles[0]:
        return None,'AMBIGUOUS_VARIANT'
    product=products[0]
    offers=product.get('offers',[])
    offers=[offers] if isinstance(offers,dict) else offers
    offers=[o for o in offers if isinstance(o,dict) and same_site(o.get('url',''),shop['base_url'])
            and parse_qs(urlsplit(o['url']).query).get('itemId')==[str(variant_id)]]
    if len(offers)!=1:
        return None,'AMBIGUOUS_VARIANT'
    offer=offers[0]
    if offer.get('priceCurrency')!='EUR':
        return None,'CURRENCY_UNCONFIRMED'
    seller=offer.get('seller',{}).get('name')
    if seller not in shop.get('allowed_sellers',[]):
        return None,'SELLER_RISK'
    buttons=[n for n in doc.root.walk() if n.tag=='button'
             and n.attrs.get('data-testid')=='pdp-addToCart-button'
             and n.attrs.get('data-product-id')==str(variant_id)]
    controls=[n for n in buttons if 'disabled' not in n.attrs and 'hidden' not in n.attrs
              and n.attrs.get('aria-disabled')=='false'
              and n.attrs.get('aria-hidden')!='true'
              and re.search(r'in den warenkorb|vorbestell',n.text(),re.I)]
    stock=str(offer.get('availability','')).rsplit('/',1)[-1]
    main=' '.join(visible_text(n) for n in doc.root.walk() if n.tag=='main')
    local_only=bool(re.search(r'nicht nach Hause lieferbar|nur in (?:der )?Filiale',main,re.I))
    blocked=bool(re.search(r'aktuell nicht lieferbar|ausverkauft|benachrichtigen|warteliste|coming soon', ' '.join(n.text() for n in buttons),re.I))
    home_delivery=bool(re.search(r'Lieferung nach Hause',main,re.I))
    available=bool(stock in ('InStock','PreOrder') and len(controls)==1 and home_delivery and not local_only and not blocked)
    preorder=stock=='PreOrder' or any(re.search('vorbestell',n.text(),re.I) for n in controls)
    row=normalized(shop,offer['url'],product['name'],offer.get('price'),available,
                   sku=variant_id,description=product.get('description',''),gtin=product.get('gtin') or product.get('gtin13',''),
                   seller=seller,currency='EUR',variant_validated=True,live_validated=True,
                   add_to_cart_available=available,preorder=preorder,preorder_status=preorder,
                   availability_status='preorder' if available and preorder else 'in_stock' if available else 'out_of_stock' if stock in ('OutOfStock','SoldOut') else 'unknown',
                   shipping_cost=None,stock_text=' '.join(n.text() for n in buttons),store_status='selection_required' if local_only else 'not_checked')
    if local_only:
        return row,'LOCAL_STOCK_UNCONFIRMED'
    if not available:
        return row,'OUT_OF_STOCK' if stock in ('OutOfStock','SoldOut') else 'NO_CHECKOUT'
    return row,None
