"""Documented foreign MSRP is context, never an implicit European deal ceiling."""
from datetime import date
from decimal import Decimal
import re


def orientation(offer, cfg, lang):
    if lang != 'EN':
        return ''
    text = offer['title'] + ' ' + offer['variant']
    matched = [g for g in cfg.get('price_guides', [])
               if date.fromisoformat(g['verified_on']) <= date.today() <= date.fromisoformat(g['valid_until'])
               and re.search(g['title_pattern'], text, re.I)]
    if len(matched) != 1:
        return ''
    guide = matched[0]
    amount = Decimal(guide['usd_per_pack'])
    result = f"US-UVP zur Orientierung: {amount:.2f} USD je Booster"
    if guide.get('packs'):
        result += f"; {guide['packs']} × {amount:.2f} = {amount * guide['packs']:.2f} USD (hochgerechnet, keine Display-UVP)"
    return result + f". Kein EU-Endpreis; Steuern/Versand nicht eingerechnet. [Herstellerbeleg]({guide['url']})"
