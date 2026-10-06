"""Public onboarding checks, using production adapters. No Discord or state writes."""
import json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tcg_bot.__main__ import load_config, ADAPTERS
from tcg_bot.http import Client
from tcg_bot.preorders import identity, live, seller_confidence, price_check
from tcg_bot.fast_watch import priority

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
        except Exception as exc: out.update(status='blocked', error=str(exc)[:120])
        return out
    shop=dict(shop)
    try:
        rows, notes=ADAPTERS[shop['adapter']](shop,client)
        eligible=[o for o in rows if identity(o,cfg)[0] and float(o['price'])<=200]
        out.update(variants=len(rows), relevant=len(eligible), notes=notes)
        # Exercise an open and a closed product when available. No snippets are promoted.
        eligible.sort(key=lambda o:(not o.get('available'), priority(o)))
        picked=eligible[:3]
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
