"""Bounded public retailer onboarding audit. No credentials, carts or notifications."""
import json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
from tcg_bot.http import Client
from tcg_bot.web_sources import Document, structured_products, same_site
from tcg_bot.sources import shopify
from tcg_bot.preorders import live, identity
from tcg_bot.__main__ import load_config

PAT = re.compile(r'dragon.?ball|fusion.world|naruto|one.?piece|pok[eé]mon',re.I)
SEALED = re.compile(r'display|booster.?box|trainer.?box|collection|kollektion|bundle|special.?box',re.I)
def inspect(body):
    doc=Document(body)
    forms=[]
    for f in doc.root.walk():
        if f.tag!='form': continue
        controls=[{'tag':n.tag,'attrs':{k:v for k,v in n.attrs.items() if k in ('name','type','disabled','class','id','data-product-id') or k.startswith('data-add')},
                   'value':n.attrs.get('value') if n.attrs.get('name') in ('a','product_id','add-to-cart','variation_id','id') else None,
                   'text':n.text().strip()[:120]} for n in f.walk() if n.tag in ('input','button','select')]
        if re.search(r'cart|warenkorb|buy|basket|add-to',str(f.attrs)+str(controls),re.I):
            forms.append({'attrs':{k:v for k,v in f.attrs.items() if k in ('id','action','method','class','data-product_id')},'controls':controls[:14]})
    return {'h1':[n.text().strip() for n in doc.root.walk() if n.tag=='h1'][:2],
            'products':[{k:p.get(k) for k in ('name','sku','gtin13','url','offers')} for p in structured_products(doc)][:3],
            'forms':forms[:3],
            'stock':[m.group(0) for m in re.finditer(r'.{0,60}(?:lieferbar|vorrätig|ausverkauft|Vorbestell|waitlist|nur für|Bund der magischen).{0,90}',doc.root.text(),re.I)][:5]}
def audit(target):
    sid,name,base=target
    client=Client();client.deadline=time.monotonic()+55
    out={'id':sid,'base_url':base}
    try:
        body=client.text(base+'/')
        out['platform']='shopify' if 'Shopify' in body else 'woocommerce' if 'woocommerce' in body else 'shopware' if 'shopware' in body.lower() else 'jtl' if 'jtl' in body.lower() else 'unknown'
        doc=Document(body)
        links=[(n.text().strip(),urljoin(base+'/',n.attrs['href'])) for n in doc.root.walk() if n.tag=='a' and n.attrs.get('href')]
        links=list(dict.fromkeys((n,u) for n,u in links if same_site(u,base)))
        out['legal_links']=[u for n,u in links if re.search(r'impressum|legal.notice|zahlung|payment|versand',n+' '+u,re.I)][:8]
        out['categories']=[u for n,u in links if PAT.search(n+' '+u)][:12]
        out['legal']=[]
        for url in [u for n,u in links if re.search(r'impressum|legal.notice',n+' '+u,re.I)][:1]:
            try:
                legal=Document(client.text(url))
                texts=[n.text() for n in legal.root.walk() if n.tag=='main']
                text=' '.join(texts) or legal.root.text()
                idx=re.search(r'Angaben gemäß|Angaben gem|Impressum|Verantwortlich|Anbieter',text,re.I)
                out['legal'].append({'url':url,'text':text[idx.start() if idx else 0:][:3000]})
            except Exception as exc: out['legal'].append({'url':url,'error':str(exc)[:140]})
        shop={'id':sid,'name':name,'base_url':base,'currency':'EUR','adapter':out['platform'],'max_pages':1}
        out['pages']=[]
        if out['platform']=='shopify':
            rows,notes=shopify(shop,client)
            cfg=load_config('config/config.json')
            matches=[o for o in rows if PAT.search(o['title']) and SEALED.search(o['title'])]
            out['catalog_count']=len(rows);out['relevant']=len(matches);out['notes']=notes
            out['samples']=[{k:o.get(k) for k in ('title','price','available','url','variant_id','gtin')} for o in matches[:8]]
            for o in sorted(matches,key=lambda o:(not o['available'],not bool(re.search('dragon|naruto',o['title'],re.I))))[:2]:
                try:
                    row,reason=live(o,shop,client,time.time())
                    obj,why=identity(row or o,cfg)
                    out['pages'].append({'url':o['url'],'live_reason':reason,'identity_reason':why,'live':{k:(row or {}).get(k) for k in ('title','price','availability_status','add_to_cart_available','variant','gtin')}})
                except Exception as exc:out['pages'].append({'url':o['url'],'error':str(exc)[:140]})
        else:
            candidates=[u for n,u in links if PAT.search(n+' '+u) and SEALED.search(n+' '+u)]
            if not candidates and out['categories']:
                url=out['categories'][0]
                page=client.text(url);d=Document(page)
                candidates=[urljoin(url,n.attrs['href']) for n in d.root.walk() if n.tag=='a' and n.attrs.get('href') and PAT.search(n.text()+' '+n.attrs['href']) and SEALED.search(n.text()+' '+n.attrs['href'])]
                out['category_inspection']=inspect(page)
            for url in list(dict.fromkeys(u for u in candidates if same_site(u,base)))[:2]:
                try:out['pages'].append({'url':url,'inspection':inspect(client.text(url))})
                except Exception as exc:out['pages'].append({'url':url,'error':str(exc)[:140]})
    except Exception as exc:out['error']=str(exc)[:160]
    return out
def main():
    targets=json.loads(Path('config/new-retailer-targets.json').read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(audit,targets))
    Path('new-retailer-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    for row in results: print('NEW_SHOP_AUDIT '+json.dumps(row,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
