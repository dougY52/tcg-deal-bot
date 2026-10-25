"""Read-only deployment checks using the same adapters as the live watch."""
import json
from tcg_bot.__main__ import load_config
from tcg_bot.http import Client, FetchError
from tcg_bot.local_retail import vedes_live, duo_rows

def main():
    cfg=load_config('config/config.json');client=Client(delay=3)
    errors=[]
    try:
        for sid in ('vedes','faix','duo'):
            shop=next(s for s in cfg['shops'] if s['id']==sid)
            try:
                url=shop['health_product_url']
                rows,error=duo_rows(shop,client.text(url),url) if sid=='duo' else vedes_live(shop,client,url)
                if error or not rows:raise RuntimeError(sid+': '+str(error or 'No exact offer parsed'))
                if not any(r.get('seller_verified') for r in rows):raise RuntimeError(sid+': Seller validation failed')
                for row in rows:
                    fields=('title','variant_id','seller','price','available','channel','stock_quantity','distance_km','seller_verified','add_to_cart_available')
                    print('LOCAL_RETAIL_PROBE '+json.dumps(dict(shop=sid,discord_sent=False,**{k:row.get(k) for k in fields}),ensure_ascii=False),flush=True)
            except Exception as exc:
                limited=(sid=='vedes' and isinstance(exc,FetchError) and any(code in str(exc) for code in ('HTTP 403','HTTP 429')))
                if not limited:errors.append(sid)
                if limited:print('::warning::VEDES public access currently unavailable; scanner remains limited and sends no unvalidated alerts.',flush=True)
                print('LOCAL_RETAIL_PROBE_ERROR '+json.dumps({'shop':sid,'error':str(exc),'discord_sent':False}),flush=True)
    finally:client.close()
    if errors:raise RuntimeError('Live validation failed: '+', '.join(errors))

if __name__=='__main__':main()
