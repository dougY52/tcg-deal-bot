"""Informational offer alerts with dated price evidence, including expensive offers.

Past observations come from actual web-source scans; no search snippet is MSRP.
No concurrent competitor or artificial confidence score is required.
"""
from datetime import datetime, timezone
from decimal import Decimal
from statistics import median
from .product_types import LABELS


def evidence_for(o, state, policy, now, anchors):
    evidence = [dict(a, observed_at=None, source='reviewed') for a in anchors]
    days = policy.get('price_context_days', 14)
    daily = {}
    for h in state['market_history'].values():
        if h['identity'] != o['identity']:
            continue
        for sample in h.get('samples', []):
            age = now - sample['at']
            if not sample.get('available') or not 6 * 3600 <= age <= days * 86400:
                continue
            key = (h['retailer'], int(sample['at'] // 86400))
            value = Decimal(sample['price'])
            if key not in daily or value < Decimal(daily[key]['price']):
                daily[key] = dict(kind='history', price=str(value), url=h['url'],
                                  observed_at=sample['at'], shop=h['shop'], source='web_observation')
    evidence.extend(daily.values())
    # A peer observed now is useful evidence, even when only one exists.
    peers = {}
    for h in state['market_history'].values():
        if h['identity'] != o['identity'] or h['retailer'] == o['retailer']:
            continue
        if not h['available'] or not 0 <= now - h['last_seen'] <= 7200:
            continue
        if h['retailer'] not in peers or Decimal(h['price']) < Decimal(peers[h['retailer']]['price']):
            peers[h['retailer']] = dict(kind='current_market', price=h['price'], url=h['url'],
                                       observed_at=h['last_seen'], shop=h['shop'], source='web_observation')
    evidence.extend(peers.values())
    return evidence


def assess_context(o, state, cfg, now, anchors, assessment=None):
    from .market import delivery_key
    policy = cfg['market']
    item = state['market_history'][o['key']]
    evidence = evidence_for(o, state, policy, now, anchors)
    historical = [e for e in evidence if e['kind'] == 'history']
    current = [e for e in evidence if e['kind'] == 'current_market']
    verified = [e for e in anchors if e['kind'] in ('msrp', 'observed_retail')]
    if verified:
        baseline = min(Decimal(e['price']) for e in verified)
        basis = 'Belegter Normalpreis / UVP (siehe Quelle)'
    elif anchors:
        baseline = min(Decimal(e['price']) for e in anchors)
        basis = 'Datierter Preisbeleg aus externer Quelle; keine UVP'
    elif historical:
        baseline = median(Decimal(e['price']) for e in historical)
        basis = f'Beobachteter Preisverlauf der letzten {policy.get("price_context_days", 14)} Tage; keine UVP'
    elif current:
        baseline = median(Decimal(e['price']) for e in current)
        basis = 'Aktuell beobachteter Händlerpreis; Normalpreis/UVP unbekannt'
    else:
        baseline, basis = None, 'Keine belastbare Vergleichsbasis vorhanden'
    price = Decimal(o['price'])
    delta = ((price / baseline - 1) * 100).quantize(Decimal('0.1')) if baseline else None
    if baseline is None:
        rating = dict(code='unknown', label='⚪ Preis ungeprüft – kein bestätigter Deal',
                      explanation='Bestellbares Angebot. Es fehlen datierte Vergleichspreise; eine Bewertung als günstig ist nicht möglich.')
    elif price > baseline * Decimal('1.15'):
        rating = dict(code='expensive', label='🔴 Teuer – kein guter Deal',
                      explanation=f'{delta:+.1f} % gegenüber dem Vergleichswert von {baseline:.2f} €. Als Verfügbarkeitshinweis gemeldet, nicht als Schnäppchen.')
    elif price > baseline:
        rating = dict(code='elevated', label='🟠 Über dem Vergleichspreis – kein Schnäppchen',
                      explanation=f'{delta:+.1f} % gegenüber dem Vergleichswert von {baseline:.2f} €.')
    elif price <= baseline * Decimal('0.85') and baseline - price >= Decimal('3'):
        rating = dict(code='very_good', label='🟢 Deutlich unter dem beobachteten Vergleichspreis',
                      explanation=f'{delta:+.1f} % gegenüber {baseline:.2f} €. Die Quellen und ihr Alter stehen unten.')
    else:
        rating = dict(code='fair', label='🟡 Im beobachteten Preisbereich',
                      explanation=f'{delta:+.1f} % gegenüber dem Vergleichswert von {baseline:.2f} €.')
    if not verified and baseline:
        rating['explanation'] += ' Beobachtete Händlerpreise sind keine Hersteller-UVP und können bereits erhöht sein.'
    if assessment is not None:
        assessment.update(rating)
    restock = bool(item.get('restocked_at') and now - item['restocked_at'] <= 86400)
    sent = (state.setdefault('market_offer_sent', {}).get(delivery_key(o)) if policy.get('notify_all_shops')
            else state.setdefault('market_sent', {}).get(o['identity']))
    if sent:
        improved = Decimal(sent['price']) - price >= Decimal(str(cfg['price_drop_eur'])) and price <= Decimal(sent['price']) * (1 - Decimal(str(cfg['price_drop_pct'])) / 100)
        new_episode = restock and (sent.get('offer') != o['key'] or sent.get('episode', 0) < item['episode'])
        if not improved and not new_episode:
            return None, 'duplicate_or_cooldown'
    reason = 'Bestätigter Restock' if restock else 'Neues bestellbares Angebot'
    if o.get('preorder'):
        reason = 'Bestellbare Vorbestellung – ' + reason
    return dict(o, reason=reason, rating=rating, price_context=True, evidence=evidence,
                baseline=str(baseline) if baseline else None, comparison_basis=basis,
                episode=item['episode']), 'eligible'


def context_payload(d):
    available = 'Vorbestellung bestellbar' if d.get('preorder') else 'Laut Händler bestellbar'
    if d.get('preorder'):
        available += ' · Händlertermin: ' + str(d.get('release_date') or 'nicht angegeben')
    product = LABELS.get(d.get('product_kind'), 'Versiegeltes Produkt')
    if d.get('packs'):
        product += f" · {d['packs']} Booster"
    lines = []
    # Prefer recent dated observations; show distinct sources within Discord limits.
    selected = sorted(d['evidence'], key=lambda e: (e['source'] != 'reviewed', -(e.get('observed_at') or 0)))
    seen = set()
    for e in selected:
        stamp = datetime.fromtimestamp(e['observed_at'], timezone.utc).strftime('%d.%m.%Y %H:%M UTC') if e.get('observed_at') else str(e.get('verified_on') or 'datierter Preisbeleg')
        key = (e['url'], stamp)
        if key in seen:
            continue
        seen.add(key)
        label = 'Hersteller-UVP' if e['kind'] == 'msrp' else e.get('shop', 'Handelspreis')
        lines.append(f"{label}: {Decimal(e['price']):.2f} € · {stamp} · [Quelle]({e['url']})")
        if len(lines) == 4:
            break
    basis = d['comparison_basis']
    if d['baseline'] is not None:
        basis += f"\n**{Decimal(d['baseline']):.2f} €**"
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': (d['rating']['label'] + ': ' + d['title'])[:250], 'url': d['url'],
        'color': {'expensive': 0xC01C28, 'unknown': 0x777777, 'elevated': 0xE66100, 'fair': 0xE5A50A}.get(d['rating']['code'], 0x26A269),
        'description': f"**{Decimal(d['price']):.2f} €** · {d['language']} · {d['shop_name']}\n{product}\n{available}\n**Versand zusätzlich; Endpreis im Checkout prüfen.**",
        'fields': [{'name': 'Einordnung', 'value': d['rating']['explanation']},
                   {'name': 'Vergleichsbasis', 'value': basis},
                   {'name': 'Preisquellen und Zeitpunkt', 'value': '\n'.join(lines)[:1024] or 'Noch keine unabhängige oder historische Preisquelle verfügbar. Keine UVP-Angabe.'},
                   {'name': 'Meldungsgrund', 'value': d['reason']}],
        'footer': {'text': 'Frühere Händlerpreise und Verfügbarkeit sind Beobachtungen, keine Preisgarantie.'}
    }]}
