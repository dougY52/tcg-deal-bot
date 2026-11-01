"""Read-only real catalogue audit: never sends a Discord message or stores credentials."""
import json
import time
from tcg_bot.__main__ import load_config
from tcg_bot.cardpal_discovery import discover
from tcg_bot.http import Client
from tcg_bot import preorders


def main():
    cfg = load_config('config/config.json')
    now = time.time()
    client = Client(delay=0.3)
    try:
        state, rows = {}, []
        # Two catalogue rotations include both Pokemon languages; no delivery state.
        for _ in range(2):
            state.setdefault('cardpal_discovery', {})['checked_at'] = 0
            found, report = discover(cfg, state, client, now)
            rows.extend(found)
            print(json.dumps(report, indent=2, ensure_ascii=False))
        shops = {s['id']:s for s in cfg['shops']}
        checked = []
        selected, groups = [], set()
        for row in rows:
            identity, _ = preorders.identity(row, cfg)
            if identity:
                group = (identity['franchise'], identity['language'])
                if group not in groups:
                    selected.append(row)
                    groups.add(group)
        for row in selected[:4]:
            try:
                live, error = preorders.live(row, shops[row['shop']], client, now)
                checked.append({'shop':row['shop'],'product':row['title'],
                                'live_price':live.get('price') if live else None,
                                'checkout':live.get('add_to_cart_available') if live else False,
                                'result':error or 'live_checkout_confirmed'})
            except Exception as error:
                checked.append({'shop':row['shop'],'result':type(error).__name__})
        print(json.dumps({'live_checks':checked,'discord_sent':0},indent=2,ensure_ascii=False))
        return 0 if report['articles'] else 2
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
