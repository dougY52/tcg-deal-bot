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
from .discovery import discovery, discovery_payload
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
        assert shop['adapter'] in ADAPTERS and shop['currency'] in ('EUR', 'GBP', 'CHF'), 'Unsupported source'
        if shop.get('international'):
            assert shop.get('ships_to_de') is True and shop.get('shipping_evidence', '').startswith('https://') and shop.get('shipping_note'), 'Missing Germany delivery evidence'
        if shop['currency'] != 'EUR':
            assert shop.get('international') and shop.get('import_costs'), 'Foreign currency must be an explicit import source'
        assert 1 <= shop['max_pages'] <= 40, 'Invalid page limit'
        assert len(shop.get('catalog_collections', [])) <= 8 and all(re.fullmatch('[a-z0-9-]+', n) for n in shop.get('catalog_collections', [])), 'Invalid collection targets'
        shop['base_url'] = shop['base_url'].rstrip('/')
        shop['watch_handles'] = list(shop.get('watch_handles', []))
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
    for guide in cfg.get('price_guides', []):
        amount = Decimal(guide['usd_per_pack'])
        assert amount.is_finite() and amount > 0 and guide['url'].startswith('https://'), 'Invalid USD guide'
        assert guide.get('packs') is None or (isinstance(guide['packs'], int) and 0 < guide['packs'] <= 100), 'Invalid guide pack count'
        assert date.fromisoformat(guide['valid_until']) >= date.fromisoformat(guide['verified_on']), 'Invalid guide dates'
        re.compile(guide['title_pattern'])
    for pattern in cfg['franchises'].values():
        re.compile(pattern)
    assert cfg['max_alerts_per_run'] is None or 1 <= cfg['max_alerts_per_run'] <= 1000
    assert cfg['restock_cooldown_hours'] >= 0
    assert cfg['price_drop_eur'] > 0 and 0 < cfg['price_drop_pct'] < 100
    if cfg.get('discoveries', {}).get('enabled'):
        assert 1 <= cfg['discoveries']['max_per_run'] <= 50
    market = cfg.get('market', {})
    if market.get('enabled'):
        assert 2 <= market['min_comparisons'] <= 10
        assert 0.90 <= market['min_confidence'] <= 1
        assert 10 <= market['discount_pct'] < 60
        assert market['min_saving_eur'] >= 5
        assert 0 < market['comparison_max_hours'] <= 24
        assert 1 <= market['history_days'] <= 180
        assert market['alert_cooldown_hours'] >= 6
        assert 1 <= market.get('price_context_days', 14) <= 30
        if 'max_offer_price_eur' in market:
            maximum = Decimal(str(market['max_offer_price_eur']))
            assert maximum.is_finite() and maximum > 0
        if 'allowed_product_types' in market:
            from .product_types import LABELS
            assert isinstance(market['allowed_product_types'], list) and market['allowed_product_types']
            assert set(market['allowed_product_types']) <= set(LABELS)
        for flag in ('expanded_products', 'price_context_mode'):
            assert isinstance(market.get(flag, False), bool)
        assert 0 <= market['near_retail_tolerance_pct'] <= 15
        if 'max_premium_eur' in market:
            assert 0 <= market['max_premium_eur'] <= 30
        assert isinstance(market.get('notify_within_price_range', False), bool)
        assert 1 <= market['anchor_max_days'] <= 30
        for alias in market.get('set_aliases', []):
            assert alias['franchise'] in cfg['franchises'] and alias['set']
            re.compile(alias['pattern'])
        for ref in market.get('price_references', []):
            price = Decimal(ref['price_eur'])
            assert price.is_finite() and price > 0 and ref['identity']
            assert ref['evidence_url'].startswith('https://')
            assert ref['kind'] in ('msrp', 'observed_retail', 'market_reference')
            assert date.fromisoformat(ref['valid_until']) >= date.fromisoformat(ref['verified_on'])
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
    if 'discovery_seen' in data and not isinstance(data['discovery_seen'], dict):
        raise ValueError('Invalid discovery state')
    for h in data.get('market_history', {}).values():
        assert isinstance(h['samples'], list) and isinstance(h['last_seen'], (int, float))
        assert isinstance(h['available'], bool) and h['identity'] and h['retailer']
        for sample in h['samples']:
            price = Decimal(sample['price'])
            assert price.is_finite() and price > 0
    return data


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def run(cfg, state, client, send=None, checkpoint=None, now=None):
    now = time.time() if now is None else now
    discoveries_enabled = cfg.get('discoveries', {}).get('enabled', False)
    if discoveries_enabled and 'discovery_seen' not in state:
        # Preserve the existing catalog baseline on upgrade, without a backlog flood.
        state['discovery_seen'] = {key: {'baseline': True} for key, item in state['offers'].items() if item.get('available') is True}
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
    if cfg.get('market', {}).get('enabled', False):
        from .market import evaluate, market_payload, delivery_key
        from .comparison import enrich
        research = enrich(offers, cfg, state, client, now)
        deals, skipped, candidates = evaluate(offers, cfg, state, now)
        report = {'shops': shops, 'errors': errors, 'warnings': warnings, 'skipped': skipped, 'price_research': research,
                  'candidates': candidates, 'alerts': [], 'sent': 0, 'dry_run': send is None,
                  'unavailable_sources': cfg.get('unavailable_sources', []), 'discovery_sent': 0,
                  'pending_alerts': max(0, len(deals) - cfg['max_alerts_per_run']) if cfg['max_alerts_per_run'] else 0}
        for deal in deals[:cfg['max_alerts_per_run']]:
            message = market_payload(deal)
            report['alerts'].append({'key': deal['key'], 'reason': deal['reason'], 'rating': deal['rating'], 'payload': message})
            if send:
                try:
                    message_id = send(message)
                except Exception as exc:
                    errors.append('Discord: ' + type(exc).__name__)
                    break
                delivery_table = 'market_offer_sent' if cfg['market'].get('notify_all_shops', False) else 'market_sent'
                key = delivery_key(deal) if cfg['market'].get('notify_all_shops', False) else deal['identity']
                state.setdefault(delivery_table, {})[key] = {
                    'at': now, 'price': deal['price'], 'offer': deal['key'],
                    'episode': deal['episode'], 'message_id': message_id}
                report['sent'] += 1
                if checkpoint:
                    checkpoint(state)
        if not any(s['variants'] for s in shops):
            errors.append('No source data; previous availability preserved')
        if checkpoint:
            checkpoint(state)
        return report
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
    report['discovery_sent'] = 0
    report['discovery_pending'] = 0
    if discoveries_enabled:
        new = {}
        for offer in relevant:
            if offer['key'] in state['discovery_seen']:
                continue
            found = discovery(offer, cfg)
            if found:
                new[offer['key']] = found
        ordered = sorted(new.values(), key=lambda o: (o['language'] != 'DE', o['key']))
        limit = cfg['discoveries']['max_per_run']
        report['discovery_pending'] = max(0, len(ordered) - limit)
        for offer in ordered[:limit]:
            message = discovery_payload(offer)
            report['alerts'].append({'key': offer['key'], 'reason': 'Neu entdeckt – Preis noch ungeprüft', 'payload': message})
            if send:
                try:
                    message_id = send(message)
                except Exception as exc:
                    errors.append('Discord discovery: ' + type(exc).__name__)
                    break
                state['discovery_seen'][offer['key']] = {'at': now, 'message_id': message_id}
                report['sent'] += 1
                report['discovery_sent'] += 1
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
    text += f"Neue Produktmeldungen: {report.get('discovery_sent', 0)} · weitere Kandidaten: {report.get('discovery_pending', 0)}\n\n"
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
        if os.environ.get('TCG_BROWSER') == '1':
            from .browser import BrowserClient
            client = BrowserClient()
        else:
            client = Client()
        client.cooldowns = state.setdefault('http_backoff', {})
        try:
            report = run(cfg, state, client, send, checkpoint)
        finally:
            client.close()
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
