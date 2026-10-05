"""Daily live price information, independent of strict instant-deal pricing."""
from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from . import preorders

BERLIN = ZoneInfo('Europe/Berlin')


def day(now):
    return datetime.fromtimestamp(now, BERLIN).date().isoformat()


def safe(text, limit=150):
    return re.sub(r'[\\*_~`|<>\[\]\r\n]', '', str(text))[:limit]


def eligible(cfg, state, now):
    """Only quotes validated by this run; stale saved stock never becomes a post."""
    settings = cfg.get('daily_prices', {})
    maximum = min(Decimal(str(settings.get('max_price_eur', 200))),
                  Decimal(str(cfg.get('preorder_watch', {}).get('max_price_eur', 200))))
    seen = state.get('daily_price_delivery', {})
    sent = seen.get('products', {}) if seen.get('day') == day(now) else {}
    shops = {s['id']: s for s in cfg['shops'] if s.get('enabled', True)}
    rows = []
    for quote in state.get('preorder_quotes', {}).values():
        if quote.get('validated_at') != now:
            continue
        if (quote.get('live_validated') is not True or
                quote.get('add_to_cart_available') is not True or
                quote.get('availability_status') not in ('in_stock', 'preorder')):
            continue
        shop = shops.get(quote.get('shop'))
        if not shop or preorders.seller_confidence(quote, shop, cfg['preorder_watch']) is None:
            continue
        rules = dict(preorders.SHOP_RULES.get(shop['id'], {}),
                     **cfg['preorder_watch'].get('shop_rules', {}).get(shop['id'], {}))
        if rules.get('strict_variant_check') and not quote.get('variant_validated'):
            continue
        if rules.get('strict_cart_check') and not quote.get('cart_validated'):
            continue
        row, error = preorders.identity(quote, cfg)
        if error or row['currency'] != 'EUR':
            continue
        price = Decimal(row['price'])
        if not price.is_finite() or not 0 < price <= maximum:
            continue
        url = urlsplit(row['url'])
        if url.scheme != 'https' or url.username or url.password:
            continue
        key = row['product_key']
        if key in sent:
            continue
        last = state.get('preorder_products', {}).get(key, {}).get('last_alert', {})
        if last.get('at') and day(last['at']) == day(now):
            continue
        pricing = preorders.price_check(row, list(state.get('preorder_quotes', {}).values()),
                                        dict(cfg, _fast_lane=True), now,
                                        state.get('preorder_products', {}).values())
        # Keep the user's explicit exclusions for ordinary ME03/ME04 offers.
        if row['franchise'] == 'Pokémon' and re.search(r'wachsendes chaos|optimale ordnung|ME[ -]?0[34]\b', row['title'], re.I):
            if not pricing or price > Decimal(pricing['baseline']) * Decimal('.80'):
                continue
        row['daily_note'] = ('Innerhalb der hinterlegten Preisorientierung' if pricing
                             else 'Preisvergleich offen; kein bestätigter UVP-Deal')
        rows.append(row)
    # Each franchise gets space; within it show the lowest product prices first.
    groups = []
    for family in ('Dragon Ball', 'Pokémon', 'One Piece', 'Naruto'):
        groups.append(sorted((r for r in rows if r['franchise'] == family),
                             key=lambda r: (Decimal(r['price']), r['product_key'])))
    return [g[i] for i in range(max((len(g) for g in groups), default=0))
            for g in groups if i < len(g)]


def message(rows, now):
    local = datetime.fromtimestamp(now, BERLIN)
    lines = []
    for row in rows:
        money = lambda value: f"{Decimal(value):.2f}".replace('.', ',') + ' €'
        shipping = row.get('shipping_cost')
        costs = ('Versand offen' if shipping is None else
                 'Versand ' + money(shipping) + ' · Gesamt ' + money(Decimal(row['price']) + Decimal(shipping)))
        status = 'Vorbestellbar' if row.get('preorder_status') else 'Bestellbar'
        url = row['url'].replace(')', '%29').replace('(', '%28').replace(' ', '%20')
        lines.append(f"**{safe(row['title'], 125)}**\n"
                     f"{safe(row['seller'], 50)} · {row['language']} · **{money(row['price'])}** · {status}\n"
                     f"{costs} · {row['daily_note']}\n[Zum Angebot]({url})")
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': '📋 Tägliche Preise · ' + local.strftime('%d.%m.%Y'),
        'color': 0x3498DB,
        'description': '\n\n'.join(lines),
        'footer': {'text': 'Live geprüft ' + local.strftime('%H:%M') +
                   ' Europe/Berlin · Preisinfo, keine pauschale Kaufempfehlung'}
    }]}


def run(cfg, state, now, send=None, checkpoint=None, budget=2):
    report = {'eligible': 0, 'sent': 0, 'offers_sent': 0, 'alerts': [], 'errors': []}
    settings = cfg.get('daily_prices', {})
    if not settings.get('enabled'):
        return report
    rows = eligible(cfg, state, now)
    report['eligible'] = len(rows)
    size = settings.get('offers_per_message', 4)
    limit = min(budget, settings.get('max_messages_per_run', 2))
    batches, batch = [], []
    for row in rows:
        candidate = batch + [row]
        # Stay below Discord's 4096-char embed description limit.
        if batch and (len(candidate) > size or len(message(candidate, now)['embeds'][0]['description']) > 3900):
            batches.append(batch)
            batch = []
        if len(message([row], now)['embeds'][0]['description']) > 3900:
            continue
        batch.append(row)
    if batch:
        batches.append(batch)
    for batch in batches[:max(0, limit)]:
        payload = message(batch, now)
        report['alerts'].append({'key': 'daily-prices:' + day(now) + ':' + batch[0]['product_key'],
                                 'reason': 'daily_prices', 'payload': payload})
        if send is None:
            continue
        try:
            message_id = send(payload)
        except Exception as exc:
            report['errors'].append('Discord daily prices: ' + type(exc).__name__)
            break
        if state.get('daily_price_delivery', {}).get('day') != day(now):
            state['daily_price_delivery'] = {'day': day(now), 'products': {}}
        for row in batch:
            state['daily_price_delivery']['products'][row['product_key']] = {
                'at': now, 'price': row['price'], 'message_id': message_id}
        report['sent'] += 1
        report['offers_sent'] += len(batch)
        if checkpoint:
            checkpoint(state)
    return report
