"""Public browser deployment probe; no Discord secret, cart writes or bot state."""
import json
import platform
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tcg_bot.__main__ import load_config
from tcg_bot.browser import BrowserClient
from tcg_bot.http import FetchError
from tcg_bot.web_sources import parse_mms, parse_structured, Document, structured_products, mueller_candidate
from tcg_bot.retailers import mueller_product
from tcg_bot.drop_watch import inspect


def main():
    cfg = load_config('config/config.json')
    shops = {s['id']: s for s in cfg['shops']}
    client = BrowserClient()
    results = []
    targets = [(sid, shops[sid]['watch_urls'][0]) for sid in ('mediamarkt', 'saturn')]
    targets += [('mueller', 'https://www.mueller.de/c/spielwaren/spiele-puzzles/sammelkarten/'),
                ('pokemon-center-de', 'https://www.pokemoncenter.com/en-de'),
                ('pokemon-press-de', 'https://pokemon.gamespress.com/de')]
    try:
        for sid, url in targets:
            record = dict(shop=sid, url=url, platform=platform.system(), readable=False, checkout_confirmed=False)
            try:
                client.deadline = time.monotonic() + 40
                body = client.text(url)
                if sid in ('mediamarkt', 'saturn'):
                    rows = parse_mms(shops[sid], body, url)
                    if not rows:
                        raise FetchError('No explicit retailer product state')
                    record.update(readable=True, products=[{k:r.get(k) for k in ('title','price','available','variant_id','seller','seller_verified','add_to_cart_available')} for r in rows])
                    record['checkout_confirmed'] = any(r.get('add_to_cart_available') is True and r['seller_verified'] for r in rows)
                elif sid == 'mueller':
                    rows, _ = parse_structured(shops[sid], body, url)
                    record.update(readable=bool(rows), catalog_products=len(rows))
                    candidates = [r for r in rows if mueller_candidate(r['title'])]
                    if not candidates:
                        from urllib.parse import urljoin
                        nxt = next((urljoin(url,n.attrs['href']) for n in Document(body).root.walk()
                                    if n.tag=='a' and n.attrs.get('data-testid')=='pageLink-2' and n.attrs.get('href')), None)
                        if nxt:
                            rows, _ = parse_structured(shops[sid], client.text(nxt), nxt)
                            candidates = [r for r in rows if mueller_candidate(r['title'])]
                            record['second_page_candidates'] = len(candidates)
                    # Category entries are discovery only. Validate an actual product page.
                    if candidates:
                        candidate = candidates[0]
                        detail = client.text(candidate['url'])
                        products = structured_products(Document(detail))
                        sku = next((str(p['sku']) for p in products if p.get('sku')), candidate['variant_id'])
                        row, reason = mueller_product(shops[sid], detail, candidate['url'], sku)
                        record['detail'] = {'url': candidate['url'], 'reason':reason, 'product':{k:row.get(k) for k in ('title','price','available','variant_id','add_to_cart_available')} if row else None}
                        record['checkout_confirmed'] = bool(row and row.get('add_to_cart_available') and not reason)
                    # Stable non-TCG positive control tests the transport/parser only.
                    # It can never enter the bot's deal pipeline or send a notification.
                    control_url = 'https://www.mueller.de/p/zanzoon-pokemon-trainer-expert-PPN3159053/'
                    control, reason = mueller_product(shops[sid], client.text(control_url), control_url, '3159053')
                    record['non_tcg_control'] = {'reason':reason, 'checkout_confirmed':bool(control and control.get('add_to_cart_available') and not reason)}
                else:
                    status, events = inspect(body, {}, time.time())
                    record.update(readable=status != 'blocked_or_unreadable', status=status, signals=len(events))
            except Exception as exc:
                record['error'] = str(exc) if isinstance(exc, FetchError) else type(exc).__name__
            results.append(record)
            print('BROWSER_PROBE ' + json.dumps(record, ensure_ascii=False), flush=True)
    finally:
        client.close()
    Path('browser-report.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    # An inaccessible source remains a visible failed probe, not a passing stock test.
    return 0 if all(r['readable'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
