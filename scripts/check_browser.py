"""Read-only deployment check. No Discord secret or send path."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tcg_bot.__main__ import load_config
from tcg_bot.browser import BrowserClient
from tcg_bot.web_sources import parse_mms

cfg=load_config('config/config.json')
client=BrowserClient()
failures=0
try:
    for shop in cfg['shops']:
        if shop['id'] not in ('mediamarkt', 'saturn'):
            continue
        try:
            url=shop['watch_urls'][0]
            rows=parse_mms(shop, client.text(url), url)
            if not rows or not any(r['seller_verified'] and r['available'] in (True, False) for r in rows):
                raise ValueError('Missing explicit stock/seller data')
            for row in rows:
                print(shop['id'], row['price'], row['currency'], 'available=', row['available'], 'seller_verified=', row['seller_verified'])
        except Exception as exc:
            print(shop['id'], type(exc).__name__)
            failures+=1
finally:
    client.close()
sys.exit(1 if failures else 0)
