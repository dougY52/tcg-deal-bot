"""Sealed product formats; never compare a tin with a display or empty storage."""
import re
import unicodedata
from .rules import gtin_key

LABELS = {'display': 'Booster-Display', 'etb': 'Top-Trainer-Box', 'tin': 'Tin',
          'mini_tin': 'Mini-Tin', 'bundle': 'Booster-Bundle', 'collection': 'Kollektion / Box',
          'blister': 'Blister', 'box': 'Sammelbox'}
EXCLUDED = r'\b(?:acryl\w*|acrylic\w*|sleeves?|binder|leere?s?|empty|opened|geöffnet|unsealed|repack|proxy|fake|break|live[ -]?stream|rip(?:pen)?|decks?|deckbox|storage|aufbewahrung\w*|storagebox|boxbreak|case|hülle\w*|schutz\w*|beschädigt|damaged|einzelkarte\w*|single cards?|gebraucht|refurbished|b-ware|sticker|mystery|überraschung)\b'


def product_kind(title):
    if re.search(EXCLUDED, title, re.I):
        return None
    # Bulk assortments must not masquerade as a single tin/ETB.
    container = r'tins?|top[ -]?trainer|elite[ -]?trainer|\betb\b|\bttb\b|blister|bundle|kollektion|collection'
    if re.search(r'display', title, re.I) and re.search(container, title, re.I):
        return None
    for kind, pattern in [('etb', r'top[ -]?trainer|elite[ -]?trainer|\betb\b|\bttb\b'),
                          ('mini_tin', r'mini[ -]?tin'), ('tin', r'\btin(?:s|[ -]?box)?\b'),
                          ('bundle', r'booster[ -]?(?:bundle|bündel)|boosterpaket'),
                          ('blister', r'blister'), ('collection', r'kollektion|collection|premium[ -]?box'),
                          ('display', r'display|booster[ -]?box'), ('box', r'\bbox\b|sammelbox')]:
        if re.search(pattern, title, re.I):
            return kind
    return None


def product_token(offer, kind):
    code = gtin_key(offer.get('gtin'))
    # Include selected variant even for duplicated supplier barcodes.
    title = offer['title'] + ' ' + offer.get('variant', '')
    title = ''.join(c for c in unicodedata.normalize('NFKD', title.casefold()) if not unicodedata.combining(c))
    title = re.sub(r'\b(?:default title|vorbestellung|pre[ -]?order|deutsch|german|englisch|english|eng|ger|de|en|sealed|ovp)\b', ' ', title)
    title = re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}', ' ', title)
    title = re.sub(r'[^a-z0-9]+', ' ', title).strip()
    # Assorted tins/ETBs may reuse an EAN for different artwork. Preserve the
    # named motif, normalizing format words/order, rather than pooling variants.
    motif = re.sub(r'\b(?:pokemon|tin|tins|mini|box|top|trainer|elite|etb|ttb|tcg)\b', ' ', title)
    motif = ' '.join(sorted(motif.split())) if kind in ('tin', 'mini_tin', 'etb') else ''
    # Full named product stays conservative when a barcode is absent.
    variant = offer.get('variant', '')
    variant = '' if variant in ('', 'Default Title') else re.sub(r'[^a-z0-9]+', ' ', variant.casefold()).strip()
    return kind + ':' + ('gtin:' + code + (':' + motif if motif else '') + (':' + variant if variant else '') if code else 'name:' + title)
