"""Exact VEDES/Faix and duo seller offers; public read-only checkout evidence."""
from decimal import Decimal
import json
import re
import math
from urllib.parse import urljoin, urlsplit, parse_qs, urlencode, urlunsplit
from .web_sources import Document, normalized, structured_products, same_site, money, identifier, source_error
from .checkout import text, controls, enabled, label, BLOCK
from .http import FetchError
from .rules import language, gtin_key
from .product_types import product_kind


def clean(value):
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), str(value))


def evidence_language(row, shop):
    """Only explicit variant language or a reviewed exact identifier, never site locale."""
    lang = language(row)
    # Description must repeat this exact product name followed by an explicit language.
    if lang=='UNKNOWN':
        desc=row.get('description','')
        match=re.match(re.escape(row['title'])+r'\s*\((Deutsch|German|Englisch|English)\)',desc,re.I)
        if match:
            row['variant']='DE' if match[1].lower() in ('deutsch','german') else 'EN'
            lang=language(row)
    if lang == 'UNKNOWN':
        evidence = shop.get('product_evidence', {}).get(str(row.get('product_id', '')))
        evidence = evidence or shop.get('_gtin_evidence', {}).get(gtin_key(row.get('gtin', '')))
        if evidence and re.search(evidence['title_pattern'], row['title'], re.I):
            row['variant'] = evidence['language']
            row['language_evidence'] = evidence['url']
    return row


def relevant(title):
    return bool(re.search(r'pok[eé]mon|\bpok\b|dragon.?ball|one.?piece', title, re.I) and
                product_kind(title) in ('display','bundle','etb','box','collection','tin','mini_tin','deck_set') and
                not re.search(r'portfolio|binder|sleeves?|deck.?box|tonie|funko|lego|playmat',title,re.I))


def vedes_catalog(shop, body, page_url):
    rows = {}
    for node in Document(body).root.walk():
        if node.attrs.get('data-ga4') != 'SelectArticle':
            continue
        try:
            items = json.loads(node.attrs['data-ga4-product'])['items']
            if len(items) != 1: continue
            item = items[0]; title = clean(item['item_name'])
            if not relevant(title): continue
            # POK is a catalogue abbreviation, not evidence of the card language.
            if re.match(r'POK\b',title):title=re.sub(r'^POK\b','Pokémon',title)
            url = item['item_url']; pid = str(item['item_id']); sid = str(item['subsidiary_id'])
            if not same_site(url,shop['base_url']) or parse_qs(urlsplit(url).query).get('subsidiary[__identity]') != [sid]: continue
            row = normalized(shop,url,title,item['price'],None,sku=pid+'-'+sid+'-online',
                seller=sid,product_id=pid,seller_id=sid,gtin=item.get('item_ean',''),
                seller_verified=False,discovery_only=True)
            rows[row['key']] = evidence_language(row,shop)
        except (ValueError,KeyError,TypeError): continue
    return list(rows.values())


def vedes_data(body, url):
    doc = Document(body)
    forms = [n for n in controls(doc.root) if n.tag=='form' and n.attrs.get('data-ga4')=='AddArticleToCart']
    if len(forms)!=1:return None
    form=forms[0]
    if form.attrs.get('method','').lower()!='post' or not urlsplit(urljoin(url,form.attrs.get('action',''))).path.endswith('/basketupdate/addtobasket'):return None
    if not same_site(urljoin(url,form.attrs.get('action','')),url):return None
    try:
        items=json.loads(form.attrs['data-ga4-product'])['items']
        if len(items)!=1:return None
        item=items[0];pid=str(item['item_id']);sid=str(item['subsidiary_id'])
        products=[p for p in structured_products(doc) if str(p.get('sku'))==pid]
        if len(products)!=1:return None
        product=products[0]
        titles={label(n.text()) for n in form.walk() if n.tag=='h1'}
        if titles!={label(product['name'])} or label(clean(item['item_name']))!=label(product['name']):return None
        selected=parse_qs(urlsplit(url).query).get('subsidiary[__identity]')
        if selected is not None and selected!=[sid]:return None
        offer_url=item['item_url']
        if not same_site(offer_url,url) or urlsplit(offer_url).path!=urlsplit(url).path or parse_qs(urlsplit(offer_url).query).get('subsidiary[__identity]')!=[sid]:return None
        status_urls={urljoin(url,n.attrs[k]) for n in form.walk() for k in ('data-subsidiaries-uri','data-options-uri') if k in n.attrs and '/status/json/' in n.attrs[k]}
        if len(status_urls)!=1:return None
        status_url=status_urls.pop()
        if not same_site(status_url,url) or '/status/json/' not in urlsplit(status_url).path or parse_qs(urlsplit(status_url).query).get('subsidiary[__identity]')!=[sid]:return None
        if urlsplit(status_url).path.rsplit('/',1)[-1]!=urlsplit(url).path.rsplit('/',1)[-1]:return None
        triggers={n.attrs['data-ff-cart-event-trigger-receive'] for n in form.walk() if 'data-ff-cart-event-trigger-receive' in n.attrs}
        if len(triggers)!=1 or not next(iter(triggers)).startswith(sid+'_'):return None
        uuid=next(iter(triggers))[len(sid)+1:]
        if not re.fullmatch(r'[a-f0-9-]{36}',uuid):return None
        if item.get('currency')!='EUR':return None
        nodes=list(controls(form))
        cart=any(n.tag=='button' and re.search(r'in den warenkorb',text(n),re.I) for n in nodes)
        if BLOCK.search(text(form)):cart=False
        services={n.attrs.get('value') for n in nodes if n.tag=='input' and n.attrs.get('data-form-target')=='service'}
        imprint=next((urljoin(url,n.attrs['data-modal']) for n in form.walk() if 'data-modal' in n.attrs and re.search('impressum',text(n),re.I)),None)
        if not imprint:
            imprint=next((urljoin(url,n.attrs['href']) for n in doc.root.walk() if n.tag=='a' and n.attrs.get('href') and text(n).strip().casefold()=='impressum'),None)
        geo=next((json.loads(n.attrs['data-current-location']) for n in doc.root.walk() if 'data-current-location' in n.attrs),{})
        return dict(doc=doc,form=form,product=product,item=item,pid=pid,sid=sid,uuid=uuid,url=offer_url,
                    status_url=status_url,cart=cart,services=services,imprint=imprint,geo=geo,
                    branch_selector=any(n.tag=='select' and n.attrs.get('data-options-uri') for n in form.walk()))
    except (KeyError,TypeError,ValueError):return None


def seller_legal(client, data, status, shop):
    url=data['imprint'];sid=data['sid'];seller=status['subsidiary']
    if (not url or not same_site(url,shop['base_url']) or
            (url != shop.get('trust_evidence') and parse_qs(urlsplit(url).query).get('subsidiary[__identity]')!=[sid])):return False
    cache=getattr(client,'_local_seller_cache',None)
    if cache is None:cache={};client._local_seller_cache=cache
    cache_key=(url,seller.get('name'),seller.get('zip'))
    if cache_key not in cache:
        legal=' '.join(text(Document(client.text(url)).root).split())
        cache[cache_key]=bool(seller.get('name') and (seller['name'].casefold() in legal.casefold() or
            (url==shop.get('trust_evidence') and shop.get('legal_name','!').casefold() in legal.casefold())) and
            seller.get('zip') and str(seller['zip']) in legal and
            re.search(r'@[a-z0-9.-]+\.[a-z]{2,}|telefon|tel\.',legal,re.I) and
            re.search(r'geschäftsführer|inhaber|vertreten|handelsregister|umsatzsteuer|ust.?id',legal,re.I))
    return cache[cache_key]


def vedes_rows(shop, body, url, statuses, legal_verified=False):
    data=vedes_data(body,url)
    if not data or not isinstance(statuses,list):return [],'AMBIGUOUS_VARIANT'
    selected=[s for s in statuses if str(s.get('value'))==data['sid'] and s.get('productIdentity')==data['uuid']]
    if len(selected)!=1:return [],'AMBIGUOUS_VARIANT'
    s=selected[0];seller=s.get('subsidiary',{});services=s.get('availableServices',{})
    if seller.get('country') not in ('Germany','Deutschland','DE'):return [],'OUTSIDE_GERMANY'
    if not re.fullmatch(r'[a-f0-9-]{36}',str(s.get('subsidiaryProductStatus',''))):return [],'AMBIGUOUS_VARIANT'
    stock=s.get('stock');known=type(stock) in (int,float) and math.isfinite(stock) and stock>=0
    positive=known and stock>0
    rows=[];radius=shop.get('local_region',{});geo=data['geo']
    distance=s.get('distance')
    local=(geo.get('zip')==radius.get('postal_code')=='65934' and
           abs(float(geo.get('latitude',0))-radius.get('latitude',0))<0.00001 and
           abs(float(geo.get('longitude',0))-radius.get('longitude',0))<0.00001 and
           type(distance) in (int,float) and 0<=distance<=radius.get('radius_km',0))
    for channel,service in [('online','sendHome'),('pickup','reserve')]:
        if channel=='pickup' and not local:continue
        offered=services.get(service) is True and service in data['services']
        # Keep a negative observation for a previously selectable variant.
        available=bool(positive and offered and data['cart']) if known else None
        fee=None
        if channel=='pickup':fee='0'
        elif re.fullmatch(r'\d+(?:[.,]\d{2})?\s*€',str(s.get('shippingPrice','')).strip()):
            fee=str(Decimal(s['shippingPrice'].replace('€','').replace(',','.').strip()))
        row=normalized(shop,data['url'],data['product']['name'],data['item']['price'],available,
            sku=data['pid']+'-'+data['sid']+'-'+channel,description=data['product'].get('description',''),
            gtin=data['item'].get('item_ean',''),seller=seller.get('name'),seller_id=data['sid'],product_id=data['pid'],
            seller_verified=legal_verified,platform_seller_verified=legal_verified,
            seller_evidence_url=data['imprint'],retailer_identity='vedes:'+str(data['item'].get('retailer_id',data['sid'])),
            channel=channel,shipping_cost=fee,live_validated=True,variant_validated=True,
            add_to_cart_available=available is True,availability_status='in_stock' if available else 'out_of_stock' if known and stock==0 else 'unknown',
            preorder_status=False,preorder=False,stock_text=f"{stock if known else '?'} Stück; {service}",
            store_status='confirmed' if channel=='pickup' and available else 'not_checked',
            store_id=data['sid'] if channel=='pickup' else None,store_name=seller.get('name'),
            store_address=' '.join(str(seller.get(k,'')) for k in ('street','streetNumber','zip','city')),
            distance_km=distance if local else None,stock_quantity=stock,
            store_stock_confirmed=channel=='pickup' and available is True,
            shipping_note='Reservierung; Abholbestätigung des Händlers abwarten.' if channel=='pickup' else '')
        rows.append(evidence_language(row,shop))
    if data['branch_selector']:
        for branch in statuses:
            if not isinstance(branch,dict) or branch.get('productIdentity')!=data['uuid']:continue
            sid=str(branch.get('value',''));loc=shop.get('branches',{}).get(sid)
            if not loc:continue
            details=branch.get('subsidiary',{})
            if (details.get('country') not in ('Germany','Deutschland','DE') or
                str(details.get('zip'))!=loc['postal_code'] or
                label(details.get('name',''))!=label(loc['name']) or
                not re.fullmatch(r'[a-f0-9-]{36}',str(branch.get('subsidiaryProductStatus','')))):continue
            lat1,lon1,lat2,lon2=map(math.radians,(radius['latitude'],radius['longitude'],loc['latitude'],loc['longitude']))
            distance=6371*2*math.asin(min(1,math.sqrt(math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)))
            if distance>radius['radius_km']:continue
            stock=branch.get('stock');known=type(stock) in (int,float) and math.isfinite(stock) and stock>=0
            available=known and stock>0 and branch.get('availableServices',{}).get('reserve') is True and 'reserve' in data['services'] and data['cart']
            base=next((r for r in rows if r['channel']=='online'),None)
            if not base:continue
            row=dict(base,channel='pickup',seller=details['name'],seller_id=sid,
                variant_id=data['pid']+'-'+sid+'-pickup',key=shop['id']+':'+data['pid']+'-'+sid+'-pickup',
                available=bool(available) if known else None,add_to_cart_available=bool(available),
                availability_status='in_stock' if available else 'out_of_stock' if known and stock==0 else 'unknown',
                shipping_cost='0',shipping_note='Unverbindliche Reservierung; Händlerbestätigung abwarten.',
                store_id=sid,store_name=details['name'],store_address=' '.join(str(details.get(k,'')) for k in ('street','streetNumber','zip','city')),
                distance_km=round(distance,1),stock_quantity=stock,stock_text=f'{stock} Stück; reserve',
                store_stock_confirmed=bool(available),store_status='confirmed' if available else 'not_checked')
            rows.append(row)
    return rows,None


def vedes_live(shop, client, url):
    stage='PRODUCT'
    try:
        body=client.text(url);data=vedes_data(body,url)
        if not data:return [],'AMBIGUOUS_VARIANT'
        stage='STOCK'
        statuses=client.get(data['status_url'])
        selected=[s for s in statuses if isinstance(s,dict) and str(s.get('value'))==data['sid'] and s.get('productIdentity')==data['uuid']] if isinstance(statuses,list) else []
        stage='SELLER'
        legal=seller_legal(client,data,selected[0],shop) if len(selected)==1 else False
        return vedes_rows(shop,body,url,statuses,legal)
    except FetchError as exc:
        raise FetchError('VEDES_'+stage+': '+str(exc)) from None


class QwikDocument(Document):
    """Decode only serialized data/text references; never evaluate page JavaScript."""
    def __init__(self,body):
        self.text_refs={};self.active_text=None;super().__init__(body)
    def handle_comment(self,value):
        self.active_text=value[2:] if re.fullmatch(r't=[a-z0-9]+',value) else None
        if self.active_text:self.text_refs[self.active_text]=''
    def handle_data(self,value):
        if self.active_text:self.text_refs[self.active_text]+=value
        super().handle_data(value)


def duo_rows(shop,body,url):
    doc=QwikDocument(body)
    try:
        state=json.loads(next(n.text() for n in doc.root.walk() if n.attrs.get('type')=='qwik/json'))
        objs=state['objs']
        def ref(value,depth=0):
            if depth>8 or not isinstance(value,str):raise ValueError('Invalid Qwik reference')
            if value.startswith('*'):return doc.text_refs[value[1:]]
            key=value.rstrip('!')
            if not re.fullmatch('[0-9a-z]+',key):raise ValueError('Invalid Qwik reference')
            result=objs[int(key,36)]
            return ref(result[1:],depth+1) if isinstance(result,str) and result.startswith('\x12') else result
        products=structured_products(doc)
        if len(products)!=1:return [],'AMBIGUOUS_VARIANT'
        p=products[0];pid=str(p['sku']);offer=p['offers']
        if not isinstance(offer,dict) or offer.get('priceCurrency')!='EUR':return [],'CURRENCY_UNCONFIRMED'
        if urlsplit(offer.get('url','')).path!=urlsplit(url).path:return [],'AMBIGUOUS_VARIANT'
        selected={}
        active_controls={id(n) for n in controls(doc.root)}
        for button in doc.root.walk():
            if button.tag!='button' or '_add-product-to-cart-btn_' not in button.attrs.get('class','') or not re.search('in den warenkorb',text(button),re.I):continue
            for capture in state.get('refs',{}).get(button.attrs.get('q:id'), '').split():
                context=ref(capture)
                if not isinstance(context,dict) or 'selectedOffer' not in context:continue
                raw=ref(context['selectedOffer'])
                if not isinstance(raw,dict):continue
                actual={k:ref(v) for k,v in raw.items()}
                actual['_cart_enabled']=id(button) in active_controls
                selected[str(actual.get('id'))]=actual
        if len(selected)!=1:return [],'AMBIGUOUS_VARIANT'
        a=next(iter(selected.values()))
        if (a['productId']!=pid or label(a['title'])!=label(p['name']) or
            not urlsplit(url).path.rstrip('/').endswith('/'+a['urlId']) or
            money(a['price'])!=money(offer['price']) or not str(a['id']).endswith('-'+pid)):
            return [],'AMBIGUOUS_VARIANT'
        delivery=[]
        for pointer in a['shipping']:
            raw=ref(pointer);s={k:ref(v) for k,v in raw.items()}
            if s.get('countryCode')=='DE' and s.get('currency')=='EUR' and s.get('selfPickup') is False and s.get('default') is True:delivery.append(s)
        if len(delivery)!=1:return [],'DELIVERY_UNCONFIRMED'
        status=str(offer.get('availability','')).rsplit('/',1)[-1]
        qty=a['quantity'];available=type(qty) in (int,float) and math.isfinite(qty) and qty>0 and status=='InStock' and a['_cart_enabled']
        seller=a['legalName'];review=shop.get('seller_evidence',{}).get(seller,{})
        trusted=review.get('verified') is True and review.get('application_id')==a['application']
        row=normalized(shop,url,p['name'],a['price'],available,sku=a['id'],description=p.get('description',''),
            seller=seller,seller_id=a['application'],product_id=pid,seller_verified=trusted,
            retailer_identity='duo:'+a['application'],live_validated=True,variant_validated=True,
            add_to_cart_available=available,availability_status='in_stock' if available else 'out_of_stock',
            preorder=False,preorder_status=False,shipping_cost=str(delivery[0]['fee']),stock_quantity=qty,
            stock_text=f'{qty} Stück verfügbar',seller_evidence_url=review.get('url'),
            gtin=shop.get('product_evidence',{}).get(pid,{}).get('gtin',''))
        return [evidence_language(row,shop)],None
    except (KeyError,ValueError,TypeError,IndexError,StopIteration):return [],'AMBIGUOUS_VARIANT'


def live(o,shop,client,now):
    if not same_site(o['url'],shop['base_url']):return None,'AMBIGUOUS_VARIANT'
    rows,error=vedes_live(shop,client,o['url']) if shop['adapter']=='vedes' else duo_rows(shop,client.text(o['url']),o['url'])
    selected=[r for r in rows if (r['variant_id']==o['variant_id'] or (o.get('discovery_only') and shop['adapter']=='duo' and r['product_id']==o.get('product_id'))) and (not o.get('seller_id') or r.get('seller_id')==o['seller_id'])]
    if len(selected)!=1:return None,error or 'AMBIGUOUS_VARIANT'
    row=selected[0]
    return row,'OUT_OF_STOCK' if row['available'] is False else None if row.get('add_to_cart_available') is True else 'NO_CHECKOUT'


def scan(shop,client):
    rows={};notes=[];urls=list(shop.get('watch_urls',[]));hints=[]
    catalogs=shop.get('catalog_urls',[])
    cursor=shop.get('_catalog_pages',{}).get('rotation',0)
    chosen=catalogs[cursor%len(catalogs)] if catalogs else None
    shop['_catalog_next_pages']={'rotation':cursor+1}
    for catalog in ([chosen] if chosen else []):
        try:
            body=client.text(catalog)
            if shop['adapter']=='vedes':hints.extend(vedes_catalog(shop,body,catalog))
            else:
                doc=Document(body)
                for n in doc.root.walk():
                    if n.tag=='a' and relevant(n.text()):
                        u=urljoin(catalog,n.attrs.get('href',''))
                        if same_site(u,shop['base_url']) and re.fullmatch(r'/offers/[a-zA-Z0-9-]+/',urlsplit(u).path):
                            match=re.search(r'-([A-Z0-9]{8})/$',urlsplit(u).path)
                            if match:
                                pid=match[1]
                                label_text=text(n).strip()
                                amount=re.search(r'([\d.,]+)\s*€\s*$',label_text)
                                if not amount:continue
                                row=normalized(shop,u,label_text[:amount.start()].strip(),amount[1],None,sku='discovery-'+pid,product_id=pid,seller_verified=False,discovery_only=True)
                                rows[row['key']]=evidence_language(row,shop)
        except Exception as exc:notes.append('catalog: '+source_error(exc))
    if shop['adapter']=='vedes':
        for h in hints:rows[h['key']]=h
        urls.extend(h['url'] for h in hints)
    if shop['adapter']=='duo':return list(rows.values()),notes
    urls=list(dict.fromkeys(urls))
    start=(cursor*shop.get('max_product_pages',1))%len(urls) if urls else 0
    urls=urls[start:]+urls[:start]
    for url in urls[:shop.get('max_product_pages',1)]:
        try:
            found,error=vedes_live(shop,client,url) if shop['adapter']=='vedes' else duo_rows(shop,client.text(url),url)
            if error:notes.append(error)
            for row in found:
                # Remove seller-ID-only discovery aliases for the same product/branch.
                for key,h in list(rows.items()):
                    if h.get('discovery_only') and h.get('product_id')==row.get('product_id') and h.get('seller_id')==row.get('seller_id'):rows.pop(key)
                rows[row['key']]=row
        except Exception as exc:notes.append('product: '+source_error(exc))
    return list(rows.values()),notes
