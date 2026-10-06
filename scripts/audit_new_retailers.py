"""Public onboarding checks, using production adapters. No Discord or state writes."""
import json, time, re
from tcg_bot.web_sources import Document, structured_products
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tcg_bot.__main__ import load_config, ADAPTERS
from tcg_bot.http import Client
from tcg_bot.preorders import identity, live, seller_confidence, price_check
from tcg_bot.fast_watch import priority, remember

def inspect(body):
    doc=Document(body)
    forms=[]
    for f in doc.root.walk():
        if f.tag!='form': continue
        controls=[{'tag':n.tag,'attrs':{k:v for k,v in n.attrs.items() if k in ('name','type','disabled','class','id','data-product-id','selected','aria-disabled','aria-hidden','hidden','form') or k.startswith('data-add')},
                   'value':n.attrs.get('value') if n.attrs.get('name') in ('a','product_id','add-to-cart','variation_id','id') or (n.attrs.get('name','').startswith('lineItems[')) else None,
                   'text':n.text().strip()[:120]} for n in f.walk() if n.tag in ('input','button','select','option')]
        if re.search(r'cart|warenkorb|buy|basket|add-to',str(f.attrs)+str(controls),re.I):
            forms.append({'attrs':{k:v for k,v in f.attrs.items() if k in ('id','action','method','class','data-product_id')},'controls':controls[:30]})
    return {'payment_signals':sorted(set(re.findall(r'PayPal|Klarna|Visa|Mastercard',body,re.I))), 'h1':[n.text().strip() for n in doc.root.walk() if n.tag=='h1'][:2],
            'products':[{k:p.get(k) for k in ('name','sku','gtin13','url','offers')} for p in structured_products(doc)][:3],
            'forms':forms[:3],
            'stock':[m.group(0) for m in re.finditer(r'.{0,60}(?:lieferbar|vorrätig|ausverkauft|Vorbestell|waitlist|nur für|Bund der magischen).{0,90}',doc.root.text(),re.I)][:5]}

def audit(target, cfg):
    sid, name, base = target
    shop = next((s for s in cfg['shops'] if s['id']==sid), None)
    out = {'id':sid, 'url':base, 'configured':shop is not None, 'checks':[]}
    client=Client()
    client.deadline=time.monotonic()+60
    if not shop:
        try:
            body=client.text(base+'/')
            out.update(status='discovery_only', bytes=len(body))
            if sid=='hiveworld':
                url=base+'/shop/sammelspiele/pokemon/pokemon-ogerpon-ex-premuim-kollektion-POK-459108'
                out['probe']=inspect(client.text(url))
            if sid=='gamesisland':
                try: out['api_info']=client.text('https://api.games-island.eu/')[:2500]
                except Exception as exc: out['api_error']=str(exc)[:120]
        except Exception as exc: out.update(status='blocked', error=str(exc)[:120])
        return out
    shop=dict(shop)
    try:
        client.deadline=time.monotonic()+20
        rows, notes=ADAPTERS[shop['adapter']](shop,client)
        client.deadline=time.monotonic()+40
        hints={}
        remember(rows,cfg,hints,time.time())
        eligible=[r['offer'] for r in hints.get('fast_targets',{}).values() if float(r['offer']['price'])<=200]
        out.update(variants=len(rows), relevant=len(eligible), notes=notes)
        # Exercise an open and a closed product when available. No snippets are promoted.
        eligible.sort(key=lambda o:(not o.get('available'), priority(o)))
        picked=eligible[:2]
        closed=next((o for o in eligible if o.get('available') is False), None)
        if closed and closed not in picked: picked.append(closed)
        live_cfg=dict(cfg,_fast_lane=True)
        for old in picked:
            try:
                row, reason=live(old,shop,client,time.time())
                obj, identity_error=identity(row or old,cfg)
                trusted=bool(obj and seller_confidence(obj,shop,cfg['preorder_watch']))
                pricing=price_check(obj,[],live_cfg,time.time()) if obj and reason is None and trusted else None
                out['checks'].append(dict(url=old['url'],title=(row or old)['title'],reason=reason or identity_error,
                    price=(row or old)['price'], status=(row or {}).get('availability_status'),
                    cart=(row or {}).get('add_to_cart_available'), seller_trusted=trusted, price_qualified=bool(pricing)))
            except Exception as exc: out['checks'].append({'url':old['url'],'error':str(exc)[:120]})
    except Exception as exc: out['error']=str(exc)[:120]
    return out

def main():
    cfg=load_config('config/config.json')
    targets=json.loads(Path('config/new-retailer-targets.json').read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(lambda target:audit(target,cfg),targets))
    Path('new-retailer-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    for row in rows: print('NEW_SHOP_AUDIT '+json.dumps(row,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
