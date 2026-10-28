"""Bounded authenticated deployment probe. Never sends Discord notifications."""
import json
import base64
import time
from urllib.parse import urlsplit
from pathlib import Path
from tcg_bot.browser import BrowserClient
from tcg_bot.cloud_reader import settings, github_token
from tcg_bot.cloud_reader import read as reader_read
from tcg_bot.web_sources import parse_mms, parse_structured


def main():
    if settings() is None:
        print('CLOUD_READER_NOT_CONFIGURED')
        return
    endpoint, shared = settings()
    if not shared:
        token = github_token(urlsplit(endpoint)._replace(path='').geturl(), 10)
        part = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
        # Diagnostic public claims only: never log a token, signature, actor or credential.
        safe = {key:claims.get(key) for key in ('iss','aud','sub','repository','repository_id','repository_owner_id','ref','workflow_ref','event_name')}
        safe['token_age_seconds'] = round(time.time()-claims.get('iat',0))
        safe['lifetime_seconds'] = claims.get('exp',0)-claims.get('iat',0)
        print('CLOUD_READER_IDENTITY_DIAGNOSTIC ' + json.dumps(safe))
    cfg = json.loads(Path('config/config.json').read_text())
    client = BrowserClient()
    try:
        for shop_id in ('mediamarkt', 'saturn'):
            shop = next(s for s in cfg['shops'] if s['id'] == shop_id)
            url = shop['base_url'].rstrip('/') + '/de/product/_the-pokemon-company-int-41079-pokemon-kp09-top-trainer-box-sammelkarten-2974734.html'
            rows = parse_mms(shop, client.text(url), url)
            row = next((r for r in rows if r.get('variant_id') == '2974734'), None)
            if row is None:
                raise RuntimeError('Cloud reader product identity unconfirmed: ' + shop_id)
            fields = ('title','variant_id','price','available','stock_text','add_to_cart_available')
            print('CLOUD_READER_PROBE ' + json.dumps({'shop':shop_id,'parsed':True,
                'discord_sent':False, **{key:row.get(key) for key in fields}}, ensure_ascii=False))
            discovered = set()
            for catalog in shop.get('catalog_urls', [])[:2]:
                try:
                    _, links = parse_structured(shop, client.text(catalog), catalog)
                    discovered.update(links)
                except Exception as exc:
                    print('CLOUD_READER_CATALOG_ERROR ' + json.dumps({'shop':shop_id,'error':str(exc)}))
            print('CLOUD_READER_DISCOVERY ' + json.dumps({'shop':shop_id,'product_links':len(discovered),'discord_sent':False}))
            if not discovered:
                raise RuntimeError('Cloud reader catalog discovery unconfirmed: ' + shop_id)
        from tcg_bot.pokemon_center_access import PRODUCT_TARGETS, page_result
        # Ordinary public DE pages only. This diagnostic never calls a paid
        # provider, joins a queue, or promotes readable HTML into stock proof.
        for url in ('https://www.pokemoncenter.com/de-de/', PRODUCT_TARGETS[0]):
            try:
                client.check_allowed(url)
                result = page_result(reader_read(url,20),url,time.time())
                safe = {k:result[k] for k in ('status','bytes','inventory_confirmed')}
            except Exception as exc:
                safe = {'status':'unavailable','error':str(exc),'inventory_confirmed':False}
            print('POKEMON_CENTER_FREE_READER ' + json.dumps({'url':url,**safe}))
    finally:
        client.close()


if __name__ == '__main__':
    main()
