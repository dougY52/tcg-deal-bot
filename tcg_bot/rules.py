from datetime import date
from decimal import Decimal
import re

# Restricted to the offer title/variant: descriptions often mention accessories as cross-sales.
BAD = r'\b(acryl|acrylic|sleeves?|binder|leere?s?|empty|opened|geöffnet|unsealed|repack|proxy|fake|break|live[ -]?stream|rip(?:pen)?|starter[ -]?deck|theme[ -]?deck|case|hülle|schutz|beschädigt|damaged|einzelkarte|single card|gebraucht|refurbished|b-ware|mini tin|booster bundle|sticker)\b'
PREORDER = r'vorbestell|pre[ -]?order|vorverkauf|erscheint am|release[: ]|lieferbar ab|versand (?:ab|ca)' 
FOREIGN = r'\b(japanisch|japanese|jpn|jp|cn|chinesisch|chinese|chn|kor|kr|korean|koreanisch|französisch|french|italienisch|italian|spanisch|spanish)\b'


def language(offer):
    text = offer['title'] + ' ' + offer['variant']
    if re.search(FOREIGN, text, re.I):
        return 'OTHER'
    de = bool(re.search(r'\b(de|ger|deutsch|german)\b', text, re.I))
    en = bool(re.search(r'\b(en|eng|englisch|english)\b', text, re.I))
    if de != en:
        return 'DE' if de else 'EN'
    # Explicit labelled language only; never infer language from German shop prose.
    match = re.search(r'(?:karten)?sprache\s*:?\s*(deutsch|german|englisch|english)', offer['description'], re.I)
    if match and not (de and en):
        return 'DE' if match[1].lower() in ('deutsch', 'german') else 'EN'
    return 'UNKNOWN'


def franchise(offer, config):
    text = offer['title'] + ' ' + offer.get('description', '')[:500]
    return next((name for name, pattern in config['franchises'].items() if re.search(pattern, text, re.I)), None)


def gtin_key(value):
    text = str(value or '')
    if not text.isdigit() or len(text) not in (8, 12, 13, 14):
        return None
    digits = [int(n) for n in text]
    check = (10 - sum(n * (3 if i % 2 == 0 else 1) for i, n in enumerate(reversed(digits[:-1]))) % 10) % 10
    return text.zfill(14) if check == digits[-1] else None


def reference_matches(offer, config):
    found = []
    for ref in config['references']:
        binding = next((b for b in ref['bindings'] if b['shop'] == offer['shop'] and b['handle'] == offer['handle'] and b['variant_id'] == offer['variant_id']), None)
        exact_gtin = gtin_key(offer.get('gtin'))
        if binding or (exact_gtin and exact_gtin in [gtin_key(g) for g in ref.get('gtins', [])]):
            found.append((ref, binding))
    return found


def assess(offer, config, today=None):
    today = today or date.today()
    text = offer['title'] + ' ' + offer['variant']
    if not franchise(offer, config):
        return None, 'irrelevant'
    exact = [r for r, _ in reference_matches(offer, config)]
    other_sealed = len(exact) == 1 and exact[0].get('product_kind') in ('etb', 'bundle', 'tin', 'collection', 'booster')
    if (re.search(BAD, text, re.I) and not other_sealed) or (not re.search(r'display|booster[ -]?box', text, re.I) and not other_sealed):
        return None, 'not_sealed_display'
    if offer.get('preorder'):
        return None, 'preorder_or_uncertain_release'
    if re.search(PREORDER, text + ' ' + offer['description'], re.I):
        return None, 'preorder_or_uncertain_release'
    if offer['currency'] != 'EUR' or Decimal(offer['price']) <= 0:
        return None, 'invalid_price'
    lang = language(offer)
    if lang == 'OTHER':
        return None, 'language'
    matches = reference_matches(offer, config)
    if len(matches) != 1:
        return None, 'missing_reference'
    ref, binding = matches[0]
    if binding and not re.fullmatch(binding['variant_pattern'], offer['variant']):
        return None, 'identity_changed'
    if binding is None and offer['variant'] != 'Default Title':
        return None, 'identity_changed'
    if lang not in ('UNKNOWN', ref['language']):
        return None, 'language_conflict'
    if not re.search(ref['title_pattern'], offer['title'], re.I):
        return None, 'identity_changed'
    if not date.fromisoformat(ref['verified_on']) <= today <= date.fromisoformat(ref['valid_until']):
        return None, 'reference_expired'
    if ref['language'] not in ('DE', 'EN') or not ref['sealed']:
        return None, 'language_or_condition'
    if offer.get('discovery_only'):
        return None, 'discovery_only'
    if offer.get('seller_verified') is False:
        return None, 'seller_unverified'
    if offer['available'] is None:
        return None, 'availability_unknown'
    if offer.get('condition', '').rsplit('/', 1)[-1] in ('UsedCondition', 'RefurbishedCondition', 'DamagedCondition'):
        return None, 'not_sealed_display'
    if not offer['available']:
        return None, 'out_of_stock'
    ceiling = Decimal(ref['retail_eur']) * (1 + Decimal(str(ref.get('tolerance_pct', 0))) / 100)
    if Decimal(offer['price']) > ceiling:
        return None, 'over_retail'
    return dict(offer, reference=ref, language=ref['language'], ceiling=str(ceiling)), 'eligible'


def prefer_german(deals):
    german = {d['reference']['group'] for d in deals if d['language'] == 'DE'}
    return sorted((d for d in deals if d['language'] == 'DE' or d['reference']['group'] not in german),
                  key=lambda d: (d['language'] != 'DE', Decimal(d['price']), d['key']))


def observe(state, offers):
    for offer in offers:
        if offer['available'] is None or offer.get('discovery_only'):
            continue
        item = state['offers'].setdefault(offer['key'], {'episode': 0})
        if item.get('available') is False and offer['available']:
            item['episode'] += 1
        item['available'] = offer['available']


def alert_reason(deal, state, now, config):
    item = state['offers'][deal['key']]
    sent = item.get('sent')
    if not sent:
        return 'Neuer Retail-Treffer'
    if now - sent['at'] < config['restock_cooldown_hours'] * 3600:
        return None
    if item['episode'] > sent['episode']:
        return 'Restock'
    old, new = Decimal(sent['price']), Decimal(deal['price'])
    if old - new >= Decimal(str(config['price_drop_eur'])) and new <= old * (1 - Decimal(str(config['price_drop_pct'])) / 100):
        return 'Preis gesunken'
    return None


def payload(deal, reason):
    ref = deal['reference']
    label = 'Hersteller-UVP' if ref['kind'] == 'msrp' else 'Dokumentierter Händler-Referenzpreis (keine UVP)'
    kind_label = {'etb': 'Top-Trainer-Box', 'bundle': 'Booster-Bundle', 'tin': 'Tin-Box', 'collection': 'Kollektion', 'booster': 'Booster'}.get(ref.get('product_kind'), 'sealed Display')
    seller_text = f"\nVerkäufer: {deal['seller']}" if deal.get('seller') else ''
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': (reason + ': ' + deal['title'])[:250], 'url': deal['url'], 'color': 0x26A269,
        'description': f"**{Decimal(deal['price']):.2f} €** · {deal['language']} · {deal['shop_name']}\n"
                       f"{ref['packs']} Booster · {kind_label} · laut Händler online verfügbar\n"
                       'Preis inkl. MwSt.; **Versand zusätzlich / im Checkout prüfen.**' + seller_text,
        'fields': [{'name': label, 'value': f"{ref['retail_eur']} €; geprüft {ref['verified_on']}\n[Beleg]({ref['evidence'][0]['url']})"}],
        'footer': {'text': 'Nur Produktpreis verglichen. Verfügbarkeit kann sich ändern.'}
    }]}
