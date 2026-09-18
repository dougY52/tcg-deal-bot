"""Unpriced discoveries are informational, never retail recommendations."""
from decimal import Decimal, InvalidOperation
import re
from .rules import BAD, PREORDER, franchise, language, reference_matches


def discovery(offer, cfg):
    text = offer['title'] + ' ' + offer['variant']
    # Match the product itself, not unrelated cross-sales in its description.
    if not franchise(dict(offer, description=''), cfg):
        return None
    if re.search(BAD, text, re.I) or not re.search(r'display|booster[ -]?box', text, re.I):
        return None
    lang = language(offer)
    if lang not in ('DE', 'EN') or offer['currency'] != 'EUR':
        return None
    if offer.get('seller_verified') is not True or offer.get('discovery_only'):
        return None
    if offer.get('condition', '').rsplit('/', 1)[-1] in ('UsedCondition', 'RefurbishedCondition', 'DamagedCondition'):
        return None
    # Never re-label a known overpriced, expired or mismatched reference as a discovery.
    if reference_matches(offer, cfg):
        return None
    try:
        price = Decimal(offer['price'])
        if not price.is_finite() or price <= 0:
            return None
    except (InvalidOperation, ValueError):
        return None
    preorder = bool(offer.get('preorder') or re.search(PREORDER, text + ' ' + offer['description'], re.I))
    if offer['available'] is not True:
        return None
    status = 'Vorbestellung laut Händler bestellbar – noch nicht sofort lieferbar' if preorder else 'Laut Händler online verfügbar'
    return dict(offer, language=lang, discovery_status=status)


def discovery_payload(offer):
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': ('Neu entdeckt – Preis noch ungeprüft: ' + offer['title'])[:250],
        'url': offer['url'], 'color': 0xE5A50A,
        'description': f"**{Decimal(offer['price']):.2f} €** · {offer['language']} · {offer['shop_name']}\n"
                       + offer['discovery_status'] + '\n**Kein bestätigtes Schnäppchen:** Normalpreis/UVP noch nicht geprüft.\nVersand zusätzlich.',
        'footer': {'text': 'Erstmals vom Bot entdeckt; kein Beleg für eine Neuveröffentlichung. Einmal je Händler und Variante.'}
    }]}
