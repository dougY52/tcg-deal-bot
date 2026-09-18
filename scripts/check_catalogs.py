"""Read-only live check of newly connected catalogs. No Discord/state access."""
import concurrent.futures
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tcg_bot.__main__ import load_config
from tcg_bot.http import Client
from tcg_bot.sources import shopify
from tcg_bot.discovery import discovery


def check(shop):
    client = Client()
    try:
        offers, warnings = shopify(shop, client)
        return {'shop': shop['name'], 'id': shop['id'], 'ok': not warnings, 'offers': len(offers),
                'orderable_display_candidates': sum(discovery(o, cfg) is not None for o in offers), 'warnings': warnings}
    except Exception as exc:
        return {'shop': shop['name'], 'id': shop['id'], 'ok': False, 'error': type(exc).__name__}
    finally:
        client.close()


if __name__ == '__main__':
    cfg = load_config(Path(__file__).resolve().parents[1] / 'config/config.json')
    shops = [s for s in cfg['shops'] if s.get('audit_checked_on')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, shops))
    Path('catalog-check.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
    for row in results:
        print(json.dumps(row, ensure_ascii=False), flush=True)
    print(f"SUCCESS {sum(r['ok'] for r in results)}/{len(results)}")
    sys.exit(0 if results and all(r['ok'] for r in results) else 1)
