"""Conservative product identity, independent retailer market and durable history.

Only actual observed offers enter the market. No MSRP or confidence is invented.
Uncertain identities stay in the report, never in Discord.
"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from statistics import median
import unicodedata
from urllib.parse import urlsplit

from .rules import BAD, PREORDER, franchise, language, reference_matches


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def normalize(o, cfg):
    title = o['title'] + ' ' + o.get('variant', '')
    text = title + ' ' + o.get('description', '')
    family = franchise(dict(o, description=''), cfg)
    if not family:
        return None, 'irrelevant'
    if re.search(BAD, title, re.I) or not re.search(r'display|booster[ -]?box', title, re.I):
        return None, 'not_sealed_display'
    if re.search(r'einzelbooster|single booster|\b1\s*(?:booster|pack)\b|\b[2-9]\s*[x×]\s*(?:display|booster.box)', o.get('variant', ''), re.I):
        return None, 'ambiguous_variant'
    preorder = bool(o.get('preorder') or re.search(PREORDER, title, re.I) or re.search(r'\b(?:vorbestell\w*|pre[ -]?order\w*|vorverkauf|lieferbar ab|versand (?:ab|ca))\b', o.get('description', ''), re.I))
    release = o.get('release_date', '')
    if not release:
        match = re.search(r'(?:Release|Erscheinungsdatum|Liefertermin|Veröffentlichung)\s*[:–-]?\s*(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})', text, re.I)
        release = match.group(1) if match else ''
    if re.search(r'unperfektion|verpackung\w*\s+(?:kann|könn|beschädigt)|beschädigt|damaged|b-ware|nicht versiegelt|unsealed|resealed', text, re.I):
        return None, 'condition_uncertain'
    if o.get('condition', '').rsplit('/', 1)[-1] in ('UsedCondition', 'DamagedCondition', 'RefurbishedCondition'):
        return None, 'condition_uncertain'
    if o.get('seller_verified') is not True or o.get('discovery_only'):
        return None, 'seller_unverified'
    if o.get('international') or o.get('import_costs') or o['currency'] != 'EUR':
        return None, 'outside_german_market'
    try:
        price = Decimal(o['price'])
        if not price.is_finite() or price <= 0:
            raise ValueError()
    except (ValueError, InvalidOperation):
        return None, 'invalid_price'
    if not isinstance(o.get('available'), bool):
        return None, 'availability_unknown'
    refs = [(r, b) for r, b in reference_matches(o, cfg)
            if re.search(r['title_pattern'], o['title'], re.I)
            and (b is None or re.fullmatch(b['variant_pattern'], o.get('variant', '')))]
    ref = refs[0][0] if len(refs) == 1 else None
    lang = language(o)
    if lang == 'UNKNOWN' and ref:
        lang = ref['language']
    if lang not in ('DE', 'EN') or (ref and lang != ref['language']):
        return None, 'language_uncertain'
    packs = {int(n) for n in re.findall(r'(?<![\w-])(\d{1,3})\s*(?:[x×]\s*)?(?:boosters?|packs?|boosterpacks?)\b', text, re.I)}
    packs.update(int(n) for n in re.findall(r'\b(\d{1,2})er[ -]+(?:booster[ -]+)?display\b', title, re.I))
    # A sentence describing one pack does not contradict the display pack count.
    packs.discard(1)
    if ref:
        packs.add(ref['packs'])
    if len(packs) != 1 or not 6 <= next(iter(packs)) <= 60:
        return None, 'pack_count_uncertain'
    packs = packs.pop()
    edition_hits = re.findall(r'\b(1st|2nd|3rd|first|second|third|erste|zweite|dritte|1\.?|2\.?|3\.?)\s*(?:edition|auflage)\b', title, re.I)
    editions = {'1st': '1', 'first': '1', 'erste': '1', '2nd': '2', 'second': '2', 'zweite': '2', '3rd': '3', 'third': '3', 'dritte': '3'}
    edition_set = {editions.get(x.lower(), x.rstrip('.')) for x in edition_hits}
    if len(edition_set) > 1:
        return None, 'edition_uncertain'
    edition = next(iter(edition_set), 'unspecified')
    system = ('fusion-world' if re.search(r'fusion\s*world|\bfb\d', title, re.I) else 'masters') if family == 'Dragon Ball' else family
    if re.search(r'weiss|weiß|weiss schwarz', title, re.I):
        system += ':weiss-schwarz'
    elif re.search(r'union arena', title, re.I):
        system += ':union-arena'
    elif re.search(r'universus', title, re.I):
        system += ':universus'
    elif family in ('JoJo', 'Fairy Tail', 'Bleach', 'My Hero Academia', 'Naruto'):
        system += ':mythos' if re.search('mythos', title, re.I) else ':unspecified'
    patterns = {'Dragon Ball': r'\b(BT|B|FB|EX|EB)[ -]?(\d{1,3})\b', 'Digimon': r'\b(BT|EX|RB)[ -]?(\d{1,3})\b', 'One Piece': r'\b(OP|EB|PRB)[ -]?(\d{1,3})\b', 'Pokémon': r'\b(SV|SWSH|XY|SM|ME)[ -]?(\d{1,3}(?:\.\d)?)\b'}
    codes = set()
    for prefix, number in re.findall(patterns.get(family, r'(?!)()()'), title, re.I):
        prefix = prefix.upper()
        if family == 'Dragon Ball' and system == 'masters' and prefix == 'B':
            prefix = 'BT'
        codes.add(prefix + format(Decimal(number).normalize(), 'f'))
    if len(codes) > 1:
        return None, 'set_uncertain'
    set_name = next(iter(codes), '')
    # Reviewed aliases bridge named sets without allowing arbitrary fuzzy matching.
    aliases = [a for a in cfg.get('market', {}).get('set_aliases', [])
               if a['franchise'] == family and re.search(a['pattern'], folded(title), re.I)]
    if len(aliases) == 1:
        if set_name and set_name != aliases[0]['set']:
            return None, 'set_conflict'
        set_name = aliases[0]['set']
        alias_system = aliases[0].get('system')
        if alias_system:
            if system not in (family + ':unspecified', alias_system):
                return None, 'set_system_conflict'
            system = alias_system
    if not set_name:
        clean = folded(title)
        clean = re.sub(r'\b(?:vorbestellung|preorder|pre-order|pre order)\b|\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}', ' ', clean)
        # Edition and pack size already have dedicated identity fields.
        clean = re.sub(r'\b(?:1st|2nd|3rd|first|second|third|erste|zweite|dritte|[123]\.?)\s*(?:edition|auflage)\b', ' ', clean)
        clean = re.sub(r'\b\d{1,2}er[ -]+(?:booster[ -]+)?display\b', ' ', clean)
        clean = re.sub(r'\b(?:sealed|factory sealed)\b', ' ', clean)
        clean = re.sub(cfg['franchises'][family], ' ', clean, flags=re.I)
        clean = re.sub(r'\b\d+\s*(?:booster|packs?)\b|\b(?:default title|trading card game|card game|tcg|booster|display|box|englisch|english|deutsch|german|eng|en|de|ger|ovp|sealed|original|neu)\b', ' ', clean)
        clean = re.sub(r'[^a-z0-9]+', ' ', clean).strip()
        if len(clean) < 4:
            return None, 'set_unknown'
        set_name = 'name:' + clean
    treatment = 'special' if re.search(r'premium|special|anniversary|collector|reprint|unlimited', title, re.I) else 'standard'
    group = '|'.join((system, set_name, edition, str(packs), treatment))
    identity = group + '|' + lang
    shop = next((s for s in cfg['shops'] if s['id'] == o['shop']), {})
    retailer = shop.get('retailer_group') or urlsplit(shop.get('base_url', o['url'])).hostname
    return dict(o, identity=identity, group=group, language=lang, packs=packs,
                edition=edition, set=set_name, system=system, retailer=retailer,
                condition_normalized='new-retailer-display', reference=ref, preorder=preorder, release_date=release), 'normalized'


def update_history(state, rows, now, policy):
    history = state.setdefault('market_history', {})
    ttl = policy.get('history_days', 90) * 86400
    for key in list(history):
        if now - history[key]['last_seen'] > ttl:
            del history[key]
    for o in rows:
        legacy = state.get('offers', {}).get(o['key'], {}).get('sent')
        if legacy:
            state.setdefault('market_sent', {}).setdefault(o['identity'], {
                'at': legacy['at'], 'price': legacy['price'], 'offer': o['key'], 'episode': 0,
                'message_id': legacy.get('message_id')})
        item = history.setdefault(o['key'], {'samples': [], 'episode': 0})
        if item.get('identity') and item['identity'] != o['identity']:
            item.clear(); item.update(samples=[], episode=0)
        prev = item.get('available')
        if o['available'] is False:
            if prev is not False:
                item['out_since'] = now
            item.pop('restocked_at', None)
        elif prev is False:
            if now - item.get('out_since', now) >= policy.get('restock_min_hours', 6) * 3600 and now - item.get('last_seen', 0) <= 2 * 3600:
                item['episode'] += 1
                item['restocked_at'] = now
        item.update(identity=o['identity'], retailer=o['retailer'], shop=o['shop_name'], url=o['url'],
                    available=o['available'], last_seen=now, price=o['price'], reference=o.get('reference'))
        if o['available']:
            item['in_stock_price'] = o['price']; item['in_stock_at'] = now
        samples = item['samples']
        sample = {'at': now, 'price': o['price'], 'available': o['available']}
        if not samples or any(samples[-1][k] != sample[k] for k in ('price', 'available')) or now - samples[-1]['at'] >= 86400:
            samples.append(sample)
        item['samples'] = [x for x in samples if now - x['at'] <= ttl][-180:]


def price_rating(price, normal, market_median, policy):
    """Rate against the more conservative verified baseline and current market."""
    baseline = min(Decimal(normal), Decimal(market_median))
    price = Decimal(price)
    delta = (price / baseline - 1) * 100
    premium = policy.get('max_premium_eur')
    limit = Decimal(normal) + Decimal(str(premium)) if premium is not None else baseline * (1 + Decimal(str(policy.get('near_retail_tolerance_pct', 15))) / 100)
    if price > limit:
        code, label = 'expensive', '🔴 Über deinem Preisrahmen'
    elif price <= baseline * Decimal('0.85') and baseline - price >= Decimal(str(policy.get('min_saving_eur', 8))):
        code, label = 'very_good', '🔥 Sehr guter Preis'
    elif price <= baseline:
        code, label = 'fair', '🟢 Guter / fairer Preis'
    elif price <= baseline * (1 + Decimal(str(policy.get('near_retail_tolerance_pct', 15))) / 100):
        code, label = 'acceptable', '🟡 Noch okay'
    elif premium is not None:
        code, label = 'elevated', '🟠 Erhöhter Preis – kein Schnäppchen'
    else:
        code, label = 'expensive', '🔴 Zu teuer'
    direction = 'über' if delta > 0 else 'unter' if delta < 0 else 'auf'
    explanation = (f"Vergleichsbasis {baseline:.2f} € (kleinerer Wert aus geprüftem Normalpreis und Marktmedian). "
                   + (f"{abs(delta):.1f} % {direction} dieser Basis." if delta else 'Entspricht dieser Basis.'))
    if code == 'acceptable':
        explanation += ' Noch akzeptabel; kein Schnäppchen.'
    if code == 'elevated':
        explanation += ' Teuer im Vergleich zum Normalpreis, aber innerhalb deines gewünschten Preisrahmens.'
    explanation += f' Abstand zum geprüften Normalpreis: {price - Decimal(normal):+.2f} €. Höchstpreis: {limit:.2f} €.'
    return {'code': code, 'label': label, 'baseline_eur': str(baseline),
            'difference_pct': str(delta.quantize(Decimal('0.1'))), 'premium_eur': str(price - Decimal(normal)), 'limit_eur': str(limit), 'explanation': explanation}


def unknown_rating(reason):
    return {'code': 'unknown', 'label': '⚪ Nicht sicher bewertbar',
            'explanation': 'Keine ausreichend sichere Preisbewertung; nur Prüfbericht.', 'reason': reason}


def delivery_key(offer):
    return offer['identity'] + '|' + offer['retailer']


def migrate_offer_deliveries(state, rows):
    """Transfer confirmed deliveries only to the actual sending retailer."""
    delivered = state.setdefault('market_offer_sent', {})
    for row in rows:
        candidates = [state.get('market_sent', {}).get(row['identity']),
                      state.get('offers', {}).get(row['key'], {}).get('sent')]
        for old in candidates:
            if not old or not old.get('message_id'):
                continue
            if old.get('offer', row['key']) != row['key']:
                continue
            key = delivery_key(row)
            if key not in delivered or old['at'] > delivered[key]['at']:
                delivered[key] = dict(old, offer=row['key'])


def assess_market(o, state, cfg, now, assessment=None):
    policy = cfg['market']
    if not o['available']:
        return None, 'out_of_stock'
    item = state['market_history'][o['key']]
    peers = {}
    for h in state['market_history'].values():
        if h.get('identity') != o['identity'] or h['retailer'] == o['retailer']:
            continue
        # Historical prices support restocks only for 24h, never indefinitely.
        if now - h.get('in_stock_at', 0) > policy.get('comparison_max_hours', 24) * 3600:
            continue
        p = Decimal(h['in_stock_price'])
        if h['retailer'] not in peers or p < Decimal(peers[h['retailer']]['in_stock_price']):
            peers[h['retailer']] = h
    values = sorted(Decimal(h['in_stock_price']) for h in peers.values())
    minimum = policy.get('min_comparisons', 3)
    if len(values) < minimum:
        return None, 'insufficient_independent_prices'
    center = median(values)
    # A loose robust fence removes isolated scalpers and obvious parser errors.
    keep = {k: h for k, h in peers.items() if center * Decimal('0.60') <= Decimal(h['in_stock_price']) <= center * Decimal('1.50')}
    if len(keep) < minimum:
        return None, 'insufficient_prices_after_outliers'
    values = sorted(Decimal(h['in_stock_price']) for h in keep.values())
    center = median(values)
    price = Decimal(o['price'])
    # With five or more peers, judge spread on the central majority.
    # A single clearance price or expensive shop must not veto a coherent market.
    trim = len(values) // 5 if len(values) >= 5 else 0
    core = values[trim:len(values)-trim] if trim else values
    if core[-1] / core[0] > Decimal('1.65'):
        return None, 'market_inconsistent'
    if price < center * Decimal('0.50'):
        return None, 'suspicious_low_price'
    anchors = []
    anchor_labels = []
    today = date.fromtimestamp(now)
    # A reviewed reference transfers only to exactly normalized sibling offers.
    configured_refs = {r['id']: r for r in cfg['references']}
    references = [o.get('reference')] + [configured_refs.get((h.get('reference') or {}).get('id')) for h in state['market_history'].values()
                   if h['identity'] == o['identity'] and now - h['last_seen'] <= 86400]
    for ref in references:
        if ref and date.fromisoformat(ref['verified_on']) <= today <= date.fromisoformat(ref['valid_until']) and (today - date.fromisoformat(ref['verified_on'])).days <= policy.get('anchor_max_days', 30):
            anchors.append(Decimal(ref['retail_eur']))
            anchor_labels.append({'kind': ref['kind'], 'price': ref['retail_eur'], 'url': next((e['url'] for e in ref['evidence'] if ref['retail_eur'] in e.get('note', '')), ref['evidence'][0]['url'])})
    # Optional reviewed reference: exact identity + dated evidence, never search snippets.
    for r in policy.get('price_references', []):
        if r['identity'] == o['identity'] and r['kind'] in ('msrp', 'observed_retail') and date.fromisoformat(r['verified_on']) <= today <= date.fromisoformat(r['valid_until']) and (today - date.fromisoformat(r['verified_on'])).days <= policy.get('anchor_max_days', 30):
            anchors.append(Decimal(r['price_eur']))
            anchor_labels.append({'kind': r['kind'], 'price': r['price_eur'], 'url': r['evidence_url']})
    if not anchors and policy.get('automatic_comparison', False):
        # A current market comparison is not evidence of MSRP or normal retail.
        # Require three independent, currently orderable retailers; use the lower
        # cluster and no absolute premium allowance for this weaker evidence.
        fresh_rows = [h for h in state['market_history'].values()
                      if h['identity'] == o['identity'] and h['available']
                      and h['last_seen'] == now]
        independent = {}
        for h in fresh_rows:
            if h['retailer'] not in independent or Decimal(h['price']) < Decimal(independent[h['retailer']]['price']):
                independent[h['retailer']] = h
        cluster = sorted(independent.values(), key=lambda h: Decimal(h['price']))
        if len(cluster) >= 3 and Decimal(cluster[2]['price']) / Decimal(cluster[0]['price']) <= Decimal('1.25'):
            baseline = Decimal(cluster[0]['price'])
            anchors.append(baseline)
            anchor_labels.append({'kind': 'automatic_market', 'price': str(baseline), 'url': cluster[0]['url']})
    if not anchors:
        return None, 'no_verified_normal_retail_anchor'
    # Stable history can cap an inflated contemporary market; never raises an anchor.
    old = [Decimal(s['price']) for h in state['market_history'].values() if h['identity'] == o['identity']
           for s in h['samples'] if s['available'] and 7 * 86400 <= now - s['at'] <= 30 * 86400]
    if len(old) >= 7:
        anchors.append(median(old))
    ceiling = min(anchors) if anchors else center
    fresh = sum(now - h['in_stock_at'] <= 7200 for h in keep.values())
    confidence = round(min(0.98, 0.80 + min(len(keep), 5) * 0.025 + (0.04 if fresh >= minimum else 0) + (0.02 if anchors else 0)), 3)
    if confidence < policy.get('min_confidence', 0.90):
        return None, 'low_confidence'
    automatic = all(a['kind'] == 'automatic_market' for a in anchor_labels)
    rating_policy = dict(policy)
    if automatic:
        rating_policy.pop('max_premium_eur', None)
        rating_policy['near_retail_tolerance_pct'] = 10
    rating = price_rating(price, ceiling, center, rating_policy)
    if automatic:
        rating['explanation'] = rating['explanation'].replace('geprüftem Normalpreis', 'aktuell beobachtetem Vergleichspreis').replace('geprüften Normalpreis', 'aktuellen Vergleichspreis')
        rating['label'] = '🔎 Preis im unteren Marktbereich' if rating['code'] != 'expensive' else '🔴 Über dem Vergleichspreisrahmen'
        rating['explanation'] += ' Normalpreis/UVP unbekannt; auch mehrere Händler können über UVP liegen.'
    if assessment is not None:
        assessment.update(rating)
    if rating['code'] == 'expensive':
        return None, 'over_normal_retail'
    savings = center - price
    discount = savings / center * 100
    bargain = rating['code'] in ('very_good', 'fair') and price <= ceiling and discount >= Decimal(str(policy.get('discount_pct', 15))) and savings >= Decimal(str(policy.get('min_saving_eur', 8))) and price <= values[0]
    available_shops = {h['retailer'] for h in state['market_history'].values()
                       if h['identity'] == o['identity'] and h['available'] and now - h['last_seen'] <= 7200}
    restock = bool(item.get('restocked_at') and now - item['restocked_at'] <= 86400
                   and len(available_shops) <= policy.get('restock_max_live_shops', 2)
                   and rating['code'] in ('very_good', 'fair', 'acceptable', 'elevated')
                   and not any(h['available'] and now - h['last_seen'] <= 7200
                               and Decimal(h['in_stock_price']) < price for h in peers.values()))
    if not bargain and not restock and not policy.get('notify_within_price_range', False):
        return None, 'normal_price_no_deal'
    reason = 'Preisdeal' if bargain else 'Relevanter Restock' if restock else 'Neues Angebot in deinem Preisrahmen'
    if o.get('preorder'):
        reason = 'Bestellbare Vorbestellung – ' + reason
    sent = (state.setdefault('market_offer_sent', {}).get(delivery_key(o))
            if policy.get('notify_all_shops', False)
            else state.setdefault('market_sent', {}).get(o['identity']))
    if sent:
        age = now - sent['at']
        improved = Decimal(sent['price']) - price >= Decimal(str(cfg['price_drop_eur'])) and price <= Decimal(sent['price']) * (1 - Decimal(str(cfg['price_drop_pct'])) / 100)
        new_episode = restock and (sent.get('offer') != o['key'] or sent.get('episode', 0) < item['episode'])
        # Meaningful price drops bypass the restock cooldown; unchanged offers stay silent.
        if not improved and (age < policy.get('alert_cooldown_hours', 24) * 3600 or not new_episode):
            return None, 'duplicate_or_cooldown'
    return dict(o, reason=reason, rating=rating, confidence=confidence, median=str(center), savings=str(savings),
                discount=str(discount.quantize(Decimal('0.1'))), ceiling=str(ceiling),
                anchor=min(anchor_labels, key=lambda a: Decimal(a['price'])), comparisons=[{'shop': h['shop'], 'price': h['in_stock_price'], 'url': h['url'], 'at': h['in_stock_at']} for h in keep.values()],
                episode=item['episode']), 'eligible'


def market_payload(d):
    availability = ('Vorbestellung bestellbar' if d.get('preorder') else 'laut Händler lieferbar')
    if d.get('preorder'):
        availability += (' · Händlertermin: ' + d['release_date']) if d.get('release_date') else ' · Liefertermin nicht angegeben'
    comparisons = '\n'.join(f"{h['shop']}: {Decimal(h['price']):.2f} € [Quelle]({h['url']})" for h in d['comparisons'][:5])
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': (d['rating']['label'] + ': ' + d['title'])[:250], 'url': d['url'], 'color': {'acceptable': 0xE5A50A, 'elevated': 0xE66100}.get(d['rating']['code'], 0x26A269),
        'description': f"**{Decimal(d['price']):.2f} €** · {d['language']} · {d['shop_name']}\n{d['packs']} Booster · Edition {d['edition'] if d['edition'] != 'unspecified' else 'nicht angegeben'} · {availability}\n"
                       f"Marktmedian **{Decimal(d['median']):.2f} €**; **{abs(Decimal(d['discount'])):.1f} %** {'darunter' if Decimal(d['discount']) >= 0 else 'darüber'}.\n"
                       f"{len(d['comparisons'])} unabhängige Vergleichshändler; Confidence **{d['confidence']:.0%}**.\n"
                       '**Produktpreise inkl. MwSt.; Versand zusätzlich, im Checkout prüfen.**',
        'fields': [{'name': 'Hersteller-UVP' if d['anchor']['kind'] == 'msrp' else 'Aktueller Marktvergleich (Normalpreis/UVP unbekannt)' if d['anchor']['kind'] == 'automatic_market' else 'Geprüfter Normalpreis (keine UVP)', 'value': f"{Decimal(d['anchor']['price']):.2f} € · [Beleg]({d['anchor']['url']})"}, {'name': 'Preisbewertung', 'value': d['rating']['explanation']}, {'name': 'Warum qualifiziert?', 'value': d['reason'] + '; identisches Set, Sprache, Edition und Packformat. Keine UVP-Ableitung aus hohen Marktpreisen.'},
                   {'name': 'Vergleichsmarkt (höchstens 24 Stunden alt)', 'value': comparisons[:1024]}],
        'footer': {'text': 'Confidence ist ein Regelwert, keine statistische Wahrscheinlichkeit. Bestand kann sich ändern.'}
    }]}


def migrate_alias_identities(state, policy):
    """Carry delivery history across reviewed naming fixes, not across editions."""
    def canonical(identity):
        parts = identity.split('|')
        if len(parts) != 6 or not parts[1].startswith('name:'):
            return identity
        family = parts[0].split(':')[0]
        hits = [a for a in policy.get('set_aliases', [])
                if a['franchise'] == family and re.search(a['pattern'], folded(parts[1][5:]), re.I)]
        if len(hits) != 1:
            return identity
        alias = hits[0]
        if alias.get('system'):
            if parts[0] not in (family + ':unspecified', alias['system']):
                return identity
            parts[0] = alias['system']
        parts[1] = alias['set']
        return '|'.join(parts)
    for item in state.get('market_history', {}).values():
        item['identity'] = canonical(item['identity'])
    sent = state.setdefault('market_sent', {})
    for identity in list(sent):
        target = canonical(identity)
        if target != identity:
            old = sent.pop(identity)
            if target not in sent or old['at'] > sent[target]['at']:
                sent[target] = old


def evaluate(offers, cfg, state, now):
    migrate_alias_identities(state, cfg['market'])
    rows, skipped, candidates = [], Counter(), []
    # Repeated catalog/watch URLs do not create multiple observations or votes.
    for o in {o['key']: o for o in offers}.values():
        normalized, reason = normalize(o, cfg)
        if normalized:
            rows.append(normalized)
        else:
            skipped[reason] += 1
            if reason != 'irrelevant':
                candidates.append({'shop': o['shop'], 'title': o['title'], 'price': o['price'], 'url': o['url'], 'reason': reason, 'rating': unknown_rating(reason)})
    update_history(state, rows, now, cfg['market'])
    if cfg['market'].get('notify_all_shops', False):
        migrate_offer_deliveries(state, rows)
    eligible = []
    for o in rows:
        assessment = {}
        deal, reason = assess_market(o, state, cfg, now, assessment)
        skipped[reason] += 1
        if deal:
            eligible.append(deal)
        elif o['available']:
            candidates.append({'shop': o['shop'], 'title': o['title'], 'price': o['price'], 'url': o['url'], 'identity': o['identity'], 'reason': reason, 'rating': assessment or unknown_rating(reason)})
    german = {d['group'] for d in eligible if d['language'] == 'DE'}
    best = {}
    for d in sorted(eligible, key=lambda d: (d['language'] != 'DE', Decimal(d['price']), d['key'])):
        if not cfg['market'].get('notify_all_shops', False) and d['language'] == 'EN' and d['group'] in german:
            continue
        key = delivery_key(d) if cfg['market'].get('notify_all_shops', False) else d['identity']
        best.setdefault(key, d)
    return list(best.values()), dict(skipped), candidates
