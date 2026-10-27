"""Read-only production price/delivery audit. Never posts or changes dedup state."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from tcg_bot.__main__ import load_config
from tcg_bot.http import NoRedirect, webhook_url
from tcg_bot import preorders, price_comparison


def read_receipt(secret, message_id, opener=None):
    if not re.fullmatch(r'\d{15,22}', str(message_id)):
        return {'status': 'invalid_message_id'}
    if not secret:
        return {'status': 'secret_unavailable'}
    try:
        parsed = urllib.parse.urlsplit(webhook_url(secret))
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc,
                                      parsed.path + '/messages/' + str(message_id), '', ''))
        request = urllib.request.Request(url, method='GET', headers={'User-Agent': 'TCG-Delivery-Audit/1.0'})
        with (opener or urllib.request.build_opener(NoRedirect())).open(request, timeout=15) as response:
            data = json.load(response)
        if str(data.get('id')) != str(message_id):
            return {'status': 'receipt_mismatch'}
        # Only our own recorded bot messages. Never output the webhook or raw errors.
        embeds = data.get('embeds', [])
        text = '\n'.join([data.get('content', '')] + [
            '\n'.join([e.get('title', ''), e.get('description', '')] +
                      [f.get('name', '') + ': ' + f.get('value', '') for f in e.get('fields', [])])
            for e in embeds])
        return {'status': 'confirmed', 'timestamp': data.get('timestamp'),
                'titles': [e.get('title') for e in embeds],
                'has_cardmarket_text': bool(re.search(r'Cardmarket|CM-Trend', text)),
                'comparison_excerpt': [line[:800] for line in text.splitlines()
                                       if re.search(r'CM-Trend|Trend \*\*|Retail|UVP', line)][:16]}
    except urllib.error.HTTPError as exc:
        return {'status': 'http_error', 'http_status': exc.code}
    except Exception as exc:
        return {'status': 'read_error', 'error_type': type(exc).__name__}


def audit(state, cfg, now):
    cfg = dict(cfg, _researched_retail=state.get('retail_research', {}).get('references', {}))
    quotes = list(state.get('preorder_quotes', {}).values())
    table = state.get('preorder_products', {})
    fresh = [o for o in quotes if 0 <= now-o.get('validated_at', 0) <= 3600]
    products = []
    for o in fresh:
        result = price_comparison.assess(o, cfg, state, now)
        record = table.get(o['product_key'], {})
        sent = record.get('last_alert')
        pricing = preorders.price_check(o, quotes, cfg, now, table.values())
        drop = Decimal(str(cfg['preorder_watch'].get('price_drop_pct', 5))) / 100
        duplicate = bool(sent and sent.get('episode') == record.get('episode') and
                         Decimal(o['price']) > Decimal(sent['price']) * (1-drop))
        products.append(dict(title=o['title'], shop=o['shop'], price=o['price'], url=o['url'],
                             validated_at=o.get('validated_at'), status=o.get('availability_status'),
                             cart=o.get('add_to_cart_available'), verdict=result['code'],
                             cardmarket_trend=(result['cardmarket'] or {}).get('trend'),
                             retail=(result['retail'] or {}).get('price_eur'),
                             price_qualifies=bool(pricing), duplicate=duplicate,
                             message_id=(sent or {}).get('message_id')))
    # Recent receipts prove the new formatter; established retail receipts prove delivery.
    recent = sorted(state.get('near_retail_discord_sent', {}).values(),
                    key=lambda row: row.get('at', 0), reverse=True)
    ids = [r.get('message_id') for r in recent[:3]]
    ids += [r['message_id'] for r in sorted(products, key=lambda r: r['price'])
            if r['verdict'] in ('retail_deal', 'near_retail') and r['message_id']][:3]
    ids = list(dict.fromkeys(i for i in ids if i))[:6]
    return dict(at=datetime.fromtimestamp(now, timezone.utc).isoformat(),
                last_scan=state.get('fast_last_run'), fresh_products=len(fresh),
                with_cardmarket=sum(bool(p['cardmarket_trend']) for p in products),
                products=products, receipt_ids=ids)


def main():
    state = json.loads(Path('state.json').read_text())
    report = audit(state, load_config('config/config.json'), time.time())
    secret = os.environ.get('DISCORD_WEBHOOK_URL', '')
    report['receipts'] = {mid: read_receipt(secret, mid) for mid in report.pop('receipt_ids')}
    Path('price-delivery-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('PRICE_DELIVERY_AUDIT ' + json.dumps({k: v for k, v in report.items() if k != 'products'}, ensure_ascii=False))
    for product in report['products']:
        if product['price_qualifies'] or 'FB03' in product['title']:
            print('PRICE_DELIVERY_PRODUCT ' + json.dumps(product, ensure_ascii=False))


if __name__ == '__main__':
    main()
