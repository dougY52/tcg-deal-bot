"""Bounded production-adapter smoke check, without Discord or durable-state writes."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .audit_new_retailers import audit
from tcg_bot.__main__ import load_config


def main():
    cfg = load_config('config/config.json')
    targets = [(s['id'], s['name'], s['base_url']) for s in cfg['shops']
               if s['id'] in ('comicplanet', 'kartenmeier')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda target: audit(target, cfg), targets))
    Path('added-retailer-audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for result in results:
        print('ADDED_RETAILER_AUDIT ' + json.dumps(result, ensure_ascii=False), flush=True)
    if len(results) != 2 or any(not r.get('variants') or r.get('error') or
            not any(c.get('status') in ('in_stock', 'preorder', 'out_of_stock', 'waitlist') and
                    c.get('reason') in (None, 'OUT_OF_STOCK', 'WAITLIST') and not c.get('error')
                    for c in r.get('checks', [])) for r in results):
        raise SystemExit('New retailer catalog/live-validation check incomplete; see diagnostic report.')


if __name__ == '__main__':
    main()
