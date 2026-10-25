"""Bounded authenticated deployment probe. Never sends Discord notifications."""
import json
from pathlib import Path
from tcg_bot.browser import BrowserClient
from tcg_bot.cloud_reader import settings
from tcg_bot.web_sources import parse_mms


def main():
    if settings() is None:
        print('CLOUD_READER_NOT_CONFIGURED')
        return
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
    finally:
        client.close()


if __name__ == '__main__':
    main()
