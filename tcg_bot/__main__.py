import argparse
from collections import Counter
from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

from .http import Client, send_discord, webhook_url
from .rules import assess, prefer_german, observe, alert_reason, payload, franchise
from .sources import ADAPTERS
from .web_sources import html_catalog, mms, otto
ADAPTERS.update(html_catalog=html_catalog, mms=mms, otto=otto)


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    ids = set()
    for shop in cfg['shops']:
        assert shop['id'] not in ids, 'Duplicate shop ID'
        ids.add(shop['id'])
        u = urlsplit(shop['base_url'])
        assert u.scheme == 'https' and u.hostname and not u.username and not u.password and not u.query and u.path in ('', '/'), 'Invalid shop URL'
        assert shop['adapter'] in ADAPTERS and shop['currency'] == 'EUR', 'Unsupported source'
        assert 1 <= shop['max_pages'] <= 40, 'Invalid page limit'
        shop['base_url'] = shop['base_url'].rstrip('/')
        shop['watch_handles'] = []
        shop['watch_urls'] = list(shop.get('product_urls', []))
        for url in shop.get('catalog_urls', []) + shop['watch_urls']:
            assert urlsplit(url).scheme == 'https' and urlsplit(url).netloc == u.netloc, 'Offsite source URL'
    bindings = set()
    ref_ids = set()
    for ref in cfg['references']:
        assert ref['id'] not in ref_ids, 'Duplicate reference ID'
        ref_ids.add(ref['id'])
        price = Decimal(ref['retail_eur'])
        assert price.is_finite() and price > 0, 'Invalid reference price'
        assert 0 <= ref.get('tolerance_pct', 0) <= 5, 'Tolerance must be between 0 and 5 percent'
        assert ref['kind'] in ('msrp', 'observed_retail') and ref['evidence'], 'Missing price evidence'
        assert ref['language'] in ('DE', 'EN') and ref['sealed'] is True and ref['packs'] > 0, 'Invalid identity'
        assert ref['group'] and ref['bindings'] and ref['title_pattern'], 'Missing identity'
        re.compile(ref['title_pattern'])
        assert date.fromisoformat(ref['valid_until']) >= date.fromisoformat(ref['verified_on']), 'Invalid dates'
        for evidence in ref['evidence']:
            assert evidence['url'].startswith('https://') and evidence['note'], 'Missing evidence'
        for binding in ref['bindings']:
            key = (binding['shop'], binding['handle'], binding['variant_id'])
            assert key not in bindings and binding['shop'] in ids, 'Duplicate or unknown binding'
            assert isinstance(binding['variant_id'], str) and re.fullmatch(r'[A-Za-z0-9_-]+', binding['variant_id']), 'Variant ID must be an alphanumeric string'
            assert re.fullmatch('[a-z0-9-]+', binding['handle']), 'Invalid product handle'
            re.compile(binding['variant_pattern'])
            bindings.add(key)
            shop = next(s for s in cfg['shops'] if s['id'] == binding['shop'])
            if shop['adapter'] == 'shopify':
                if binding['handle'] not in shop['watch_handles']:
                    shop['watch_handles'].append(binding['handle'])
            elif binding.get('url'):
                assert urlsplit(binding['url']).netloc == urlsplit(shop['base_url']).netloc
                if binding['url'] not in shop['watch_urls']:
                    shop['watch_urls'].append(binding['url'])
    for pattern in cfg['franchises'].values():
        re.compile(pattern)
    assert cfg['max_alerts_per_run'] is None or 1 <= cfg['max_alerts_per_run'] <= 1000
    assert cfg['restock_cooldown_hours'] >= 0
    assert cfg['price_drop_eur'] > 0 and 0 < cfg['price_drop_pct'] < 100
    return cfg


def watch_only_config(cfg):
    """Check every explicit approved binding; defer catalog discovery to hourly runs."""
    import copy
    cfg = copy.deepcopy(cfg)
    shops = []
    for shop in cfg['shops']:
        if not (shop.get('watch_handles') or shop.get('watch_urls')):
            continue
        shop['max_pages'] = 0
        shop['catalog_urls'] = []
        shop['discovery_scope'] = 'Schnellprüfung: ausschließlich explizit beobachtete Produkte.'
        shops.append(shop)
    if not shops:
        raise ValueError('No explicit watch targets configured')
    cfg['shops'] = shops
    return cfg


def load_state(path):
    if not path.exists():
        return {'version': 1, 'offers': {}}
    data = json.loads(path.read_text())
    if data.get('version') != 1 or not isinstance(data.get('offers'), dict):
        raise ValueError('Invalid state: restore bot-state instead of silently starting over')
    for item in data['offers'].values():
        if not isinstance(item.get('episode'), int) or item['episode'] < 0:
            raise ValueError('Invalid state episode')
        if not isinstance(item.get('available'), bool):
            raise ValueError('Invalid state availability')
        if 'sent' in item:
            sent = item['sent']
            assert isinstance(sent['at'], (int, float)) and isinstance(sent['episode'], int)
            assert Decimal(sent['price']).is_finite() and Decimal(sent['price']) > 0
    return data


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def run(cfg, state, client, send=None, checkpoint=None, now=None):
    now = time.time() if now is None else now
    offers, errors, warnings, shops = [], [], [], []
    for shop in cfg['shops']:
        if not shop.get('enabled', True):
            continue
        try:
            rows, notes = ADAPTERS[shop['adapter']](shop, client)
            offers.extend(rows)
            shops.append({'shop': shop['id'], 'variants': len(rows), 'scope': shop.get('discovery_scope', '')})
            warnings.extend(shop['id'] + ': ' + note for note in notes)
        except Exception as exc:
            # Source errors contain no response body, query secrets, or tracebacks.
            errors.append(shop['id'] + ': ' + type(exc).__name__)
    deals, candidates, skipped = [], [], Counter()
    relevant = [o for o in offers if franchise(o, cfg)]
    observe(state, relevant)
    for offer in relevant:
        deal, reason = assess(offer, cfg)
        skipped[reason] += 1
        if deal:
            deals.append(deal)
        elif (reason == 'not_sealed_display' and re.search(r'top.trainer|elite.trainer|booster.?bundle|premium.kollektion', offer['title'], re.I)) or reason in ('missing_reference', 'reference_expired', 'identity_changed', 'language_conflict', 'seller_unverified', 'availability_unknown', 'discovery_only'):
            candidates.append({k: offer[k] for k in ('shop', 'handle', 'variant_id', 'title', 'price', 'available', 'url')} | {'reason': reason, 'seller': offer.get('seller'), 'store_status': offer.get('store_status', 'not_supported')})
    report = {'shops': shops, 'errors': errors, 'warnings': warnings, 'skipped': dict(skipped),
              'candidates': candidates, 'alerts': [], 'sent': 0, 'dry_run': send is None, 'unavailable_sources': cfg.get('unavailable_sources', []), 'local_stores': cfg.get('local_stores', {})}
    for deal in prefer_german(deals):
        reason = alert_reason(deal, state, now, cfg)
        if not reason:
            continue
        if cfg['max_alerts_per_run'] is not None and len(report['alerts']) >= cfg['max_alerts_per_run']:
            warnings.append('Alert limit reached; remaining unsent offers retry next run')
            break
        report['alerts'].append({'key': deal['key'], 'reason': reason, 'payload': payload(deal, reason)})
        if send:
            try:
                message_id = send(report['alerts'][-1]['payload'])
            except Exception as exc:
                errors.append('Discord: ' + type(exc).__name__)
                break
            item = state['offers'][deal['key']]
            item['sent'] = {'at': now, 'price': deal['price'], 'episode': item['episode'], 'message_id': message_id}
            report['sent'] += 1
            if checkpoint:
                checkpoint(state)
    for ref in cfg['references']:
        days = (date.fromisoformat(ref['valid_until']) - date.today()).days
        if days <= 14:
            warnings.append(f"Reference {ref['id']} expires in {days} days; verify evidence and renew")
    if not shops:
        errors.append('All sources failed; previous availability preserved')
    if checkpoint:
        checkpoint(state)
    return report


def summary(report):
    text = '# TCG Retail Watch\n\n'
    text += f"Modus: {'Vorschau – nichts gesendet' if report['dry_run'] else 'Discord aktiv'}\n\n"
    text += f"Quellen erfolgreich: {len(report['shops'])} · Meldungen: {report['sent']} · Vorschläge: {len(report['alerts'])}\n\n"
    text += '## Quellen\n\n' + '\n'.join(f"- {s['shop']}: {s['variants']} Varianten — {s.get('scope', '')}" for s in report['shops']) + '\n\n'
    if report.get('unavailable_sources'):
        text += '## Nicht automatisch überwachte Quellen\n\n' + '\n'.join('- ' + s['name'] + ': ' + s['reason'] for s in report['unavailable_sources']) + '\n\n'
    if report.get('local_stores'):
        text += '## Filialbestände\n\n' + report['local_stores']['status'] + '\n\n'
    text += '## Filter\n\n' + '\n'.join(f'- {k}: {v}' for k, v in report['skipped'].items()) + '\n\n'
    if report['errors'] or report['warnings']:
        text += '## Hinweise / Fehler\n\n' + '\n'.join('- ' + x for x in report['errors'] + report['warnings']) + '\n\n'
    text += '## Produkte ohne freigegebenen Vergleichspreis (max. 30)\n\n'
    for c in report['candidates'][:30]:
        safe = re.sub(r'[\[\]<>|\r\n`]', '', c['title'])[:150]
        text += f"- {c['shop']}: {safe} — {c['price']} € — {c['reason']}\n"
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/config.json')
    parser.add_argument('--state', default='state.json')
    parser.add_argument('--report', default='report.json')
    parser.add_argument('--send', action='store_true', help='Actually post eligible deals; default is dry run')
    parser.add_argument('--check-config', action='store_true')
    parser.add_argument('--watch-only', action='store_true', help='Only approved product URLs; skip catalog discovery')
    args = parser.parse_args()
    try:
        cfg = load_config(args.config)
        if args.check_config:
            print('Configuration valid')
            return 0
        if args.watch_only:
            cfg = watch_only_config(cfg)
        state_path = Path(args.state)
        state = load_state(state_path)
        send, checkpoint = None, None
        if args.send:
            secret = os.environ.get('DISCORD_WEBHOOK_URL', '')
            webhook_url(secret)
            send = lambda p: send_discord(secret, p)
            checkpoint = lambda s: save_state(state_path, s)
        report = run(cfg, state, Client(), send, checkpoint)
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        text = summary(report)
        print(text)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as fh:
                fh.write(text)
        return 1 if report['errors'] or report['warnings'] else 0
    except Exception as exc:
        # Deliberately no exception text: secrets must never be echoed.
        print('Abbruch (' + type(exc).__name__ + '): Konfiguration, Status oder Discord-Secret prüfen.', file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
