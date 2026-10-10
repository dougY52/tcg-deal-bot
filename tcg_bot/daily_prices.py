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


def eligible(cfg, state, now, daily_only=True, near_retail_only=False):
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
        if daily_only and key in sent:
            continue
        last = state.get('preorder_products', {}).get(key, {}).get('last_alert', {})
        if daily_only and not near_retail_only and last.get('at') and day(last['at']) == day(now):
            continue
        pricing = preorders.price_check(row, list(state.get('preorder_quotes', {}).values()),
                                        dict(cfg, _fast_lane=True), now,
                                        state.get('preorder_products', {}).values())
        # Keep the user's explicit exclusions for ordinary ME03/ME04 offers.
        if row['franchise'] == 'Pokémon' and re.search(r'wachsendes chaos|optimale ordnung|ME[ -]?0[34]\b', row['title'], re.I):
            if not pricing or price > Decimal(pricing['baseline']) * Decimal('.80'):
                continue
        if near_retail_only:
            if not pricing:
                continue  # Keep reference-less prices in chat, not as a Discord retail deal.
            record = state.get('preorder_products', {}).get(key, {})
            episode = record.get('episode', 0)
            prior = state.get('near_retail_discord_sent', {}).get(key)
            # One-time initial inventory catch-up: old instant deal notifications
            # belong to a separate channel and must not silence this newly enabled
            # near-retail feed forever. Do not re-send a deal alerted minutes ago.
            instant = record.get('last_alert')
            if instant and 0 <= now - instant['at'] < 900 and (
                    instant.get('episode', episode) == episode and
                    price > Decimal(str(instant['price'])) * Decimal('.95')):
                continue
            # Once the near-retail feed delivered this exact seller/variant,
            # suppress unchanged prices across calendar days. Re-alert only a
            # >= 5% price drop or genuinely new availability episode.
            if prior and prior.get('episode', episode) == episode and (
                    price > Decimal(str(prior['price'])) * Decimal('.95')):
                continue
        row['daily_note'] = (pricing['why'] if pricing
                             else 'Preisvergleich offen; kein bestätigter UVP-Deal')
        rows.append(row)
    # Each franchise gets space; within it show the lowest product prices first.
    groups = []
    for family in ('Dragon Ball', 'Pokémon', 'One Piece', 'Naruto'):
        groups.append(sorted((r for r in rows if r['franchise'] == family),
                             key=lambda r: (Decimal(r['price']), r['product_key'])))
    return [g[i] for i in range(max((len(g) for g in groups), default=0))
            for g in groups if i < len(g)]


def message(rows, now, near_retail=False):
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
                     f"{costs} · {row.get('daily_note', 'Preisvergleich offen; kein bestätigter UVP-Deal')}\n[Zum Angebot]({url})")
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': ('✅ Neue Angebote nahe Retail · ' if near_retail else '📋 Tägliche Preise · ') + local.strftime('%d.%m.%Y'),
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
    # Central chat reads this observed-price snapshot. It does not itself
    # schedule ChatGPT messages or claim saved quotes are still live.
    overview = state.get('daily_price_overview', {})
    observed = overview.get('offers', {}) if overview.get('day') == day(now) else {}
    for key, row in list(observed.items()):
        latest = state.get('preorder_products', {}).get(key, {})
        if latest.get('last_seen', 0) >= row.get('validated_at', 0) and (
                latest.get('status') not in ('in_stock', 'preorder') or
                Decimal(str(latest.get('price', row['price']))) != Decimal(row['price'])):
            observed.pop(key, None)
    for row in eligible(cfg, state, now, daily_only=False):
        observed[row['product_key']] = row
    state['daily_price_overview'] = {'day': day(now), 'updated_at': now, 'offers': observed}
    report['overview_offers'] = len(observed)
    if not settings.get('discord_enabled', False):
        report['eligible'] = len(observed)
        return report
    near_retail = bool(settings.get('discord_near_retail_only', False))
    rows = eligible(cfg, state, now, near_retail_only=near_retail)
    report['eligible'] = len(rows)
    size = settings.get('offers_per_message', 4)
    limit = min(budget, settings.get('max_messages_per_run', 2))
    batches, batch = [], []
    for row in rows:
        candidate = batch + [row]
        # Stay below Discord's 4096-char embed description limit.
        if batch and (len(candidate) > size or len(message(candidate, now, near_retail)['embeds'][0]['description']) > 3900):
            batches.append(batch)
            batch = []
        if len(message([row], now, near_retail)['embeds'][0]['description']) > 3900:
            continue
        batch.append(row)
    if batch:
        batches.append(batch)
    for batch in batches[:max(0, limit)]:
        payload = message(batch, now, near_retail)
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
            if near_retail:
                record = state.get('preorder_products', {}).get(row['product_key'], {})
                state.setdefault('near_retail_discord_sent', {})[row['product_key']] = {
                    'at': now, 'price': row['price'],
                    'episode': record.get('episode', 0), 'message_id': message_id}
        report['sent'] += 1
        report['offers_sent'] += len(batch)
        if checkpoint:
            checkpoint(state)
    return report
