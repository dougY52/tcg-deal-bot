"""Independent, fail-closed preorder lane. Catalogs discover; live variants confirm.

No cart mutation, checkout, external search API or dependency is used. Unsupported
shop checkout mechanisms are rejected rather than guessed from a visible button.
"""
from collections import Counter
from datetime import datetime, timezone, date
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import logging
import re
from statistics import median
import time
from urllib.parse import quote, urlsplit

from .rules import language
from .sources import plain
from .product_types import product_kind, product_token, EXCLUDED, single_pack_variant

PREORDER = re.compile(r'vorbestell|pre[ -]?order|vorverkauf|coming soon|waitlist|notify me|benachrichtigen|lieferbar ab|versand ab', re.I)
BLOCK = re.compile(r'waitlist|warteliste|notify me|benachrichtigen|einladungskauf|invitation only|coming soon|backorder|nachbestellung', re.I)
SHOP_RULES = {'sapphire-cards': {'strict_variant_check': True, 'require_live_stock_validation': True},
              'galeria': {'strict_cart_check': True},
              'keepseven': {'strict_variant_check': True, 'require_live_stock_validation': True}}
LOG = logging.getLogger(__name__)


def token(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')


def release_day(text):
    match = re.search(r'(?:release(?:datum)?|erschein\w*|lieferbar ab|versand ab|vorverkauf)\s*(?:ist der|am|ab|:)?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})', text, re.I)
    if not match:
        return None
    try:
        return datetime.strptime(match[1], '%Y-%m-%d' if '-' in match[1] else '%d.%m.%Y').date()
    except ValueError:
        return None


def candidate(o):
    if o.get('live_validated') and o.get('availability_status') == 'in_stock' and not o.get('preorder_status'):
        return False
    text = o.get('title', '') + ' ' + o.get('description', '')
    released = release_day(text)
    if o.get('release_date'):
        try:
            released = date.fromisoformat(str(o['release_date'])[:10])
        except ValueError:
            pass
    return bool(o.get('preorder') or PREORDER.search(text) or (released and released > datetime.now(timezone.utc).date()))


def reference_matches(o, ref):
    """Share reviewed display references only across proven equivalent SKUs."""
    if ref['language'] != language(o) or not re.search(ref['title_pattern'], o['title'], re.I):
        return False
    bound = any(b['shop'] == o['shop'] and str(b['variant_id']) == str(o['variant_id'])
                for b in ref['bindings'])
    if bound:
        return True
    from .rules import gtin_key
    gtin = gtin_key(o.get('gtin'))
    if not gtin or gtin not in {gtin_key(g) for g in ref.get('gtins', [])}:
        return False
    # Barcodes can be reused across selectable packaging. Explicitly constrain
    # the selected display variant and reject quantities contradicting the ref.
    if ref.get('product_type') != 'display' or product_kind(o['title']) != 'display':
        return False
    variant = o.get('variant', '')
    if not re.fullmatch(ref.get('cross_shop_variant_pattern', r'Default Title'), variant, re.I):
        return False
    text = o['title'] + ' ' + variant
    if re.search(r'\b(?:[2-9]|[1-9]\d+)\s*[x×]\s*(?:display|box)|\b(?:case|bundle|set of)\b', text, re.I):
        return False
    counts = re.findall(r'\b(\d+)\s*(?:booster(?:packs?)?|packs?)\b', text, re.I)
    return all(int(n) == ref['packs'] for n in counts)


def identity(o, cfg):
    """Use only variant-specific title/language; a set code alone is not a SKU."""
    text = o['title'] + ' ' + o.get('variant', '')
    family = next((f for f, p in cfg['franchises'].items() if re.search(p, o['title'], re.I)), None)
    if not family:
        return None, 'UNSUPPORTED_PRODUCT'
    lang = language(dict(o, variant=o.get('variant', ''), description=o.get('description', '')))
    allowed = {'Pokémon': ['DE'], 'Dragon Ball': ['EN'], 'One Piece': ['EN'], 'Naruto': ['DE', 'EN']}
    if lang not in allowed.get(family, []):
        return None, 'WRONG_LANGUAGE'
    if re.search(r'\b(repack|mystery|funko|blindbox|ichiban|history.box|logo.display|figurine|proxy|fake|opened|geöffnet|empty|leer|stapel|konvolut|case|acrylic|acryl|sleeves?|binder|einzelkarte)\b', text, re.I):
        return None, 'UNSUPPORTED_PRODUCT'
    if family == 'Dragon Ball' and re.search(r'heroes|xeno|time patrol|what.if|alternative.timeline', text, re.I):
        return None, 'CONTENT_EXCLUDED'
    if family == 'Naruto' and not re.search(r'mythos', text, re.I) and not any(re.search(pattern, text, re.I) for pattern in cfg.get('preorder_watch', {}).get('official_naruto_patterns', [])):
        return None, 'UNVERIFIED_LICENSE'
    exclusion_text = re.sub(r'deck.?sets?', '', text, flags=re.I) if family == 'One Piece' else text
    if re.search(EXCLUDED, exclusion_text, re.I) or re.search(r'selbst zusammengestellt|von uns zusammengestellt|händler.bundle|\bstacks?\b', text + ' ' + o.get('description', ''), re.I):
        return None, 'UNSUPPORTED_PRODUCT'
    if single_pack_variant(o.get('variant', '')):
        return None, 'AMBIGUOUS_VARIANT'
    kind = product_kind(text)
    if family == 'One Piece' and re.search(r'deck.?set', text, re.I):
        kind = 'deck_set'
    if not kind and re.search(r'premium|anniversary|collector|collection|kollektion|poster', text, re.I):
        kind = 'collection'
    if kind not in ('display', 'bundle', 'etb', 'box', 'collection', 'tin', 'mini_tin', 'deck_set'):
        return None, 'UNSUPPORTED_PRODUCT'
    code = re.search(r'\b(FB|BT|OP|EB|PRB|SV|SWSH|ME)[ -]?(\d{1,3})\b', text, re.I)
    code = code[1].upper() + code[2].zfill(2) if code else ''
    edition = 'second' if re.search(r'\b(?:2nd|second|2\.?\s*edition)\b', text, re.I) else 'first' if re.search(r'\b(?:1st|first\s+edition|1\.?\s*edition)\b', text, re.I) else 'unspecified'
    # Cross-shop comparisons require a barcode or an explicitly reviewed product mapping.
    mapped = next((r['id'] for r in cfg.get('references', []) if reference_matches(o, r)), None)
    sku = mapped or product_token(dict(o, variant=o.get('variant', '')), kind)
    comparison_key = '|'.join((family, code, kind, lang, edition, sku))
    # Keep distinct art/pack quantities and seller variants separate, even with the same set.
    key = sha256(('|'.join((family, kind, lang, edition, o['shop'], o.get('seller') or '', str(o['variant_id'])))).encode()).hexdigest()[:32]
    return dict(o, product_name=o['title'], franchise=family, set_code=code, language=lang,
                edition=edition, product_type=kind, product_key=key, comparison_key=comparison_key), None


class Forms(HTMLParser):
    """Only an enabled submit control in the exact variant's cart form counts."""
    def __init__(self):
        super().__init__()
        self.forms = []
        self.form = None
        self.button = None
        self.select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.form = {'action': a.get('action', ''), 'method': a.get('method', '').lower(), 'ids': [], 'buttons': [], 'text': '', 'hidden': 'hidden' in a or a.get('aria-hidden') == 'true'}
        if self.form is None:
            return
        if tag == 'select' and a.get('name') == 'id' and 'disabled' not in a and 'multiple' not in a:
            self.select = []
        if tag == 'option' and self.select is not None and 'disabled' not in a:
            self.select.append((a.get('value', ''), 'selected' in a))
        if tag == 'input' and a.get('name') == 'id' and 'disabled' not in a:
            self.form['ids'].append(a.get('value', ''))
        if tag in ('button', 'input') and a.get('type', 'submit' if tag == 'button' else '').lower() == 'submit':
            self.button = {'enabled': 'disabled' not in a and 'hidden' not in a and a.get('aria-disabled') != 'true' and a.get('aria-hidden') != 'true', 'text': a.get('value', '')}
            self.form['buttons'].append(self.button)
        if tag == 'input':
            self.button = None

    def handle_data(self, data):
        if self.form is not None:
            self.form['text'] += ' ' + data
        if self.button is not None:
            self.button['text'] += ' ' + data

    def handle_endtag(self, tag):
        if tag == 'select' and self.select is not None:
            chosen = [value for value, selected in self.select if selected]
            if not chosen and len(self.select) == 1:
                chosen = [self.select[0][0]]
            if self.form is not None:
                self.form['ids'].extend(chosen if len(chosen) == 1 else [''])
            self.select = None
        if tag == 'button':
            self.button = None
        if tag == 'form' and self.form is not None:
            self.forms.append(self.form)
            self.form = None


def live(o, shop, client, now):
    """Fresh Shopify product endpoint plus exact product form; never use snippets."""
    if shop['id'] == 'mueller':
        from .retailers import mueller_product
        return mueller_product(shop, client.text(o['url']), o['url'], str(o['variant_id']))
    if shop['adapter'] == 'mms':
        from .web_sources import parse_mms, same_site
        if not same_site(o['url'], shop['base_url']):
            return None, 'AMBIGUOUS_VARIANT'
        rows = parse_mms(shop, client.text(o['url']), o['url'])
        selected = [r for r in rows if str(r['variant_id']) == str(o['variant_id'])]
        if len(selected) != 1:
            return None, 'AMBIGUOUS_VARIANT'
        row = selected[0]
        if row.get('seller') != o.get('seller'):
            return None, 'SELLER_RISK'
        if row['available'] is False:
            return row, 'OUT_OF_STOCK'
        if row.get('add_to_cart_available') is not True:
            return row, 'NO_CHECKOUT'
        if row.get('preorder_status'):
            row['availability_status'] = 'preorder'
        return row, None
    if shop['adapter'] in ('woocommerce', 'jtl') and not shop.get('marketplace'):
        from .web_sources import parse_woocommerce
        if urlsplit(o['url']).netloc != urlsplit(shop['base_url']).netloc:
            return None, 'AMBIGUOUS_VARIANT'
        url = o['url'] + ('&' if '?' in o['url'] else '?') + '_preorder_check=' + str(int(now))
        from .checkout import single_product
        parse = single_product if shop['adapter'] == 'jtl' else parse_woocommerce
        rows = parse(shop, client.text(url), o['url'])
        selected = [r for r in rows if r['variant_id'] == str(o['variant_id'])]
        if len(selected) != 1:
            return None, 'AMBIGUOUS_VARIANT'
        row = selected[0]
        return row, 'WAITLIST' if row.get('availability_status') == 'waitlist' else 'OUT_OF_STOCK' if row['available'] is False else None if row.get('add_to_cart_available') is True else 'NO_CHECKOUT'
    if shop['adapter'] != 'shopify' or shop.get('marketplace'):
        return None, 'UNSUPPORTED_LIVE_CHECK'
    handle, vid = o.get('handle', ''), str(o.get('variant_id', ''))
    if not re.fullmatch(r'[a-z0-9_-]+', handle) or not vid.isdigit():
        return None, 'AMBIGUOUS_VARIANT'
    base = shop['base_url']
    product = client.get(base + '/products/' + quote(handle) + '.js?_preorder_check=' + str(int(now)))
    if product.get('handle') != handle:
        return None, 'AMBIGUOUS_VARIANT'
    variants = [v for v in product.get('variants', []) if str(v.get('id')) == vid]
    if len(variants) != 1:
        return None, 'AMBIGUOUS_VARIANT'
    v = variants[0]
    # Rebuild all identity/price/stock data from the live product, not stale discovery.
    row = dict(o, title=plain(product['title']), variant=plain(v.get('title', '')),
               description=plain(product.get('description', '')), gtin=str(v.get('barcode') or ''),
               available=v.get('available'), preorder=False, live_validated=True,
               variant_validated=True, cart_validated=False, add_to_cart_available=False,
               stock_text='', release_date=None, shipping_cost=None, product_url=o['url'],
               seller=shop['name'], seller_verified=True)
    if isinstance(v.get('price'), bool) or not isinstance(v.get('price'), int) or v['price'] <= 0:
        return None, 'INVALID_PRICE'
    row['price'] = row['current_price'] = str(Decimal(v['price']) / 100)
    if v.get('available') is False:
        return dict(row, availability_status='out_of_stock', preorder_status=False), 'OUT_OF_STOCK'
    if v.get('available') is not True:
        return None, 'AMBIGUOUS_VARIANT'
    page = client.text(base + '/products/' + quote(handle) + '?variant=' + vid + '&_preorder_check=' + str(int(now)))
    active_currency = re.search(r'Shopify\.currency\s*=\s*\{[^}]*[\"\']active[\"\']\s*:\s*[\"\']([A-Z]{3})[\"\']', page)
    if not active_currency or active_currency[1] != shop['currency']:
        return None, 'CURRENCY_UNCONFIRMED'
    row['currency'] = active_currency[1]
    from .checkout import BLOCK as RESTRICTED
    restricted_pattern = shop.get('checkout_exclude_pattern')
    if RESTRICTED.search(row['description']) or (restricted_pattern and re.search(restricted_pattern, row['title'] + ' ' + row['description'], re.I)):
        return dict(row, availability_status='waitlist', preorder_status=False), 'WAITLIST'
    parser = Forms()
    parser.feed(page)
    matching = [f for f in parser.forms if not f['hidden'] and f['ids'] == [vid] and f['method'] == 'post' and
                urlsplit(f['action']).path.rstrip('/').endswith('/cart/add') and
                (not urlsplit(f['action']).netloc or urlsplit(f['action']).netloc == urlsplit(base).netloc)]
    if not matching:
        return dict(row, availability_status='unknown', preorder_status=False), 'AMBIGUOUS_VARIANT'
    buttons = [b for f in matching for b in f['buttons']]
    order = [b for b in buttons if b['enabled'] and re.search(r'add to (?:cart|bag)|in den warenkorb|zum warenkorb|vorbestell|pre.?order|jetzt kaufen', b['text'], re.I) and not BLOCK.search(b['text'])]
    row['stock_text'] = ' '.join(b['text'].strip() for b in buttons)[:300]
    if not order:
        reason = 'WAITLIST' if BLOCK.search(row['stock_text']) else 'OUT_OF_STOCK' if re.search(r'sold out|ausverkauft|nicht lieferbar|out of stock', row['stock_text'], re.I) else 'NO_CHECKOUT'
        return dict(row, availability_status='out_of_stock' if reason == 'OUT_OF_STOCK' else 'waitlist' if reason == 'WAITLIST' else 'unknown', preorder_status=False), reason
    row['add_to_cart_available'] = True
    # Notify widgets elsewhere on the page do not override an exact active cart form.
    text = row['title'] + ' ' + row['description'] + ' ' + row['stock_text']
    preorder = bool(re.search(r'vorbestell|pre[ -]?order|vorverkauf|lieferbar ab|versand ab', text, re.I))
    released = release_day(text)
    if released:
        row['release_date'] = released.isoformat()
        today = datetime.fromtimestamp(now, timezone.utc).date()
        if released > today:
            preorder = True
        elif not re.search(r'\b(?:vorbestell(?:bar|en|ung)|pre[ -]?order)\b', row['stock_text'] + ' ' + row['description'], re.I):
            # Old release labels in a title must not quarantine normal stock forever.
            preorder = False
    row.update(preorder=preorder, preorder_status=preorder, availability_status='preorder' if preorder else 'in_stock')
    return row, None


def seller_confidence(o, shop, settings):
    actual = o.get('seller', '')
    evidence = settings.get('seller_evidence', {}).get(actual, {})
    if 'serious_scam_signal' in evidence.get('red_flags', []) or evidence.get('payment_only') in ('crypto', 'bank_transfer'):
        return None
    known = shop['id'] in settings.get('trusted_shop_ids', []) and actual in shop.get('allowed_sellers', [shop['name']]) and o.get('seller_verified') is True
    reviewed = evidence.get('legal_entity_verified') is True and evidence.get('buyer_protection') is True and evidence.get('evidence_url', '').startswith('https://') and evidence.get('review_count', 0) >= 20 and evidence.get('rating', 0) >= 4
    if not known and not reviewed:
        return None
    return {'score': shop.get('seller_score', 90) if known else 80, 'known_retailer': known,
            'buyer_protection': evidence.get('buyer_protection'), 'review_count': evidence.get('review_count'),
            'rating': evidence.get('rating'), 'red_flags': evidence.get('red_flags', []),
            'note': (shop.get('trust_note') or 'Händler-Basisprüfung: Impressum und Kontakt geprüft.' if shop.get('trust_evidence') else 'Händler auf der konfigurierten Vertrauensliste.') if known else 'Geprüfte Firmendaten, Käuferschutz und Händlerhistorie laut hinterlegtem Nachweis.'}


def price_check(o, peers, cfg, now, history=(), diagnostics=None):
    settings = cfg['preorder_watch']
    if diagnostics is not None:
        diagnostics['reason'] = 'PRICE_TOO_HIGH'
    price = Decimal(o['price'])
    if not price.is_finite() or price <= 0 or o['currency'] != 'EUR' or price > Decimal(str(settings.get('max_price_eur', 200))):
        return None
    today = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    anchors = []
    for ref in cfg.get('references', []):
        if ref['verified_on'] <= today <= ref['valid_until'] and reference_matches(o, ref):
            anchors.append((Decimal(ref['retail_eur']), ref['kind'], 'Geprüfter Retail-Referenzpreis'))
    for ref in settings.get('price_references', []):
        if ref['verified_on'] <= today <= ref['valid_until'] and ref['comparison_key'] == o['comparison_key']:
            anchors.append((Decimal(ref['price_eur']), ref['kind'], ref['note']))
    if cfg.get('_fast_lane'):
        from .market import normalize
        normalized, _ = normalize(o, cfg)
        if normalized:
            for ref in cfg.get('market', {}).get('price_references', []):
                if ref['identity'] == normalized['identity'] and ref['kind'] in ('msrp', 'observed_retail') and ref['verified_on'] <= today <= ref['valid_until']:
                    anchors.append((Decimal(ref['price_eur']), ref['kind'], 'Geprüfte bestehende Retail-Referenz'))
    for guide in settings.get('user_price_guides', []):
        if (guide['valid_until'] >= today >= guide['verified_on'] and o['franchise'] == guide['franchise'] and
            o['set_code'] == guide['set_code'] and o['product_type'] == 'display' and o['language'] == guide['language']):
            anchors.append((Decimal(guide['ceiling_eur']), 'user_reference', 'Innerhalb deiner Preisorientierung; keine Hersteller-UVP'))
    for record in history:
        observed = record.get('retail_observation')
        if observed and observed['comparison_key'] == o['comparison_key'] and 0 <= now - observed['at'] <= 14 * 86400:
            anchors.append((Decimal(observed['price']), 'observed_retail', 'Zuletzt qualifizierter Retailpreis (höchstens 14 Tage alt)'))
    for anchor, kind, note in sorted(anchors):
        if price <= anchor * (Decimal('1.05') if kind == 'msrp' else Decimal('1')):
            return {'baseline': str(anchor), 'why': note + f': {anchor:.2f} €.', 'strong': price <= anchor * Decimal('.9')}
    if diagnostics is not None and not anchors:
        diagnostics['reason'] = 'MISSING_PRICE_REFERENCE'
    # Use at most one live price per independently configured retailer group.
    groups = {}
    for p in peers:
        if p['comparison_key'] == o['comparison_key'] and p['currency'] == 'EUR':
            group = p['retailer_group']
            groups[group] = min(groups.get(group, Decimal('Infinity')), Decimal(p['price']))
    if len(groups) >= 3:
        anchor = median(sorted(groups.values())[:10])
        # A reviewed retail ceiling also prevents a uniformly scalped market median.
        ceilings = [a * Decimal('1.05') if k == 'msrp' else a * Decimal('1.20') for a, k, _ in anchors if k != 'user_reference']
        if price <= anchor and (not cfg.get('_fast_lane') or bool(anchors)) and (not ceilings or price <= min(ceilings)):
            return {'baseline': str(anchor), 'why': f'Nicht über dem Median von {min(len(groups), 10)} innerhalb von 30 Minuten live geprüften Händlern ({anchor:.2f} €).', 'strong': price <= anchor * Decimal('.9')}
    return None


def payload(o):
    money = lambda x: f'{Decimal(x):.2f}'.replace('.', ',') + ' €'
    shipping = money(o['shipping_cost']) if o.get('shipping_cost') is not None else 'nicht bestätigt'
    return {'allowed_mentions': {'parse': []}, 'embeds': [{'title': '🔥 PREORDER LIVE', 'url': o['url'],
        'color': 0x2ECC71 if o['pricing']['strong'] else 0xF1C40F,
        'description': (f"**{o['title'][:200]}**\n🌍 {o['language']} · 🏪 {o['seller']}\n"
                        f"💶 {money(o['price'])} · 📦 Versand: {shipping}\n"
                        f"📅 Release: {o.get('release_date') or 'nicht bestätigt'}\n✅ Direkt vorbestellbar\n\n"
                        f"💡 {o['pricing']['why']}\n🛡️ {o['seller_confidence']['note']}")}]}


def scan(offers, cfg, state, client, now):
    settings = cfg.get('preorder_watch', {})
    report = {'checked': 0, 'deferred': 0, 'rejected': {}, 'candidates': [], 'sent': 0}
    if not settings.get('enabled'):
        return offers, [], report
    table = state.setdefault('preorder_products', {})
    tracked = state.setdefault('preorder_tracking', {})
    quotes = state.setdefault('preorder_quotes', {})
    for key in list(quotes):
        if now - quotes[key]['validated_at'] > 1800:
            del quotes[key]
    shops = {s['id']: s for s in cfg['shops'] if s.get('enabled', True)}
    ordinary, pending = [], {}
    for o in offers:
        if cfg.get('_fast_lane') or candidate(o) or o['key'] in tracked:
            if any(re.search(pattern, o['title'], re.I) for pattern in cfg['franchises'].values()):
                pending[o['key']] = o
        else:
            ordinary.append(o)
    for key, old in list(tracked.items()):
        if now - old['last_discovered'] > 14 * 86400:
            del tracked[key]
        elif not cfg.get('_fast_lane') and old['offer']['shop'] in shops:
            pending.setdefault(key, old['offer'])
    # Catalog hints affect scheduling only; every alert still needs live proof.
    oldest = sorted(pending.values(), key=lambda o: tracked.get(o['key'], {}).get('checked_at', 0))
    def promising(o):
        obj, _ = identity(o, cfg)
        old = tracked.get(o['key'], {})
        changed = old.get('offer', {}).get('available') != o.get('available')
        return (not (o.get('available') is True and obj is not None), not changed,
                old.get('checked_at', 0))
    ranked = sorted(oldest, key=promising)
    urgent = [o for o in ranked if re.search(r'\bFB[ -]?11\b', o['title'], re.I)][:2]
    # Reserve background checks so cached OOS/wrong-language listings can recover.
    audit = [o for o in oldest if o not in urgent][:min(4, settings.get('max_live_checks', 24) // 4)]
    selected = urgent + audit + [o for o in ranked if o not in urgent and o not in audit]
    if cfg.get('_fast_lane'):
        by_key = {o['key']: o for o in pending.values()}
        selected = [by_key[k] for k in cfg['_fast_keys'] if k in by_key]
    rejected = Counter()
    valid = []
    observed_keys = {o['key'] for o in offers}
    deadline = time.monotonic() + settings.get('validation_seconds', 90)
    original_deadline = getattr(client, 'deadline', None)
    if original_deadline is not None:
        client.deadline = min(original_deadline + settings.get('validation_seconds', 90), deadline)
    def reject(o, reason):
        rejected[reason] += 1
        report['candidates'].append({'key': o['key'], 'reason': 'REJECTED - ' + reason,
                                     'title': o.get('title', ''), 'shop': o.get('shop', ''),
                                     'price': o.get('price'), 'live_validated': o.get('live_validated') is True})
        LOG.info('REJECTED - %s (%s)', reason, o['key'])
    phase = None
    phase_deadline = deadline
    try:
        for o in selected:
            if cfg.get('_fast_lane'):
                group = cfg['_fast_groups'][o['key']]
                if group != phase:
                    phase = group
                    phase_deadline = min(deadline, time.monotonic() + (40, 25, 25, 20, 20, 10)[group])
                    if original_deadline is not None:
                        client.deadline = phase_deadline
                if time.monotonic() >= phase_deadline:
                    report['deferred'] += 1
                    continue
            old = tracked.get(o['key'], {})
            tracked[o['key']] = dict(old, offer=o, last_discovered=now if o['key'] in observed_keys else old.get('last_discovered', now))
            if report['checked'] >= settings.get('max_live_checks', 24) or time.monotonic() >= deadline:
                report['deferred'] += 1
                continue
            if '_fast_preloaded' in cfg and o['key'] not in cfg['_fast_preloaded']:
                report['deferred'] += 1
                continue
            report['checked'] += 1
            cfg.setdefault('_fast_attempted', []).append(o['key'])
            tracked[o['key']]['checked_at'] = now
            shop = shops[o['shop']]
            try:
                if '_fast_preloaded' in cfg:
                    row, error = cfg['_fast_preloaded'][o['key']]
                else:
                    row, error = live(o, shop, client, now)
            except Exception as exc:
                reject(o, 'LIVE_CHECK_FAILED_' + type(exc).__name__)
                continue  # A timeout is NOT an observed outage.
            if row is None:
                reject(o, error)
                continue
            if cfg.get('_fast_lane'):
                cfg.setdefault('_fast_observed', []).append(row)
            normalized, identity_error = identity(row, cfg)
            if cfg.get('_fast_lane') and normalized:
                before, _ = identity(o, cfg)
                if before and any(before[k] != normalized[k] for k in ('language', 'edition', 'product_type', 'set_code')):
                    identity_error = 'WRONG_VARIANT'
            key = normalized['product_key'] if normalized else old.get('product_key')
            if key and key not in table and normalized and normalized['edition'] == 'second':
                # Repair the former "First Set ... 2nd Edition" classification
                # without re-alerting the same already delivered seller variant.
                old_title = old.get('offer', {}).get('title', '')
                legacy_key = sha256(('|'.join((normalized['franchise'], normalized['product_type'],
                    normalized['language'], 'first', row['shop'], row.get('seller') or '',
                    str(row['variant_id'])))).encode()).hexdigest()[:32]
                if (old.get('product_key') == legacy_key and legacy_key in table and
                    re.search(r'first\s+set', old_title, re.I) and
                    re.search(r'2nd|second|2\.?\s*edition', old_title, re.I)):
                    table[key] = table.pop(legacy_key)
                    quotes.pop(legacy_key, None)
            if key:
                record = table.setdefault(key, {'history': [], 'episode': 0})
                status = row['availability_status'] if not identity_error else 'invalid_variant'
                # Only observed loss of orderability arms another availability episode.
                previous = record.get('status')
                if not record.get('history') and not record.get('last_alert'):
                    old_alerts = [a for name in ('market_offer_sent', 'market_sent') for a in state.get(name, {}).values() if a.get('offer') == o['key']]
                    if old_alerts:
                        sent = max(old_alerts, key=lambda a: a['at'])
                        record['last_alert'] = dict(sent, episode=record['episode'])
                if status in ('preorder', 'in_stock') and previous in ('out_of_stock', 'waitlist', 'invalid_variant'):
                    record['episode'] += 1
                if previous != status or record.get('price') != row['price']:
                    record['history'].append({'timestamp': now, 'price': row['price'], 'status': status})
                    record['history'] = record['history'][-100:]
                record.update(status=status, price=row['price'], last_seen=now, seller=row.get('seller'))
                tracked[o['key']]['product_key'] = key
            if error or identity_error:
                if key:
                    quotes.pop(key, None)
                reject(o, error or identity_error)
                continue
            if not row['preorder_status'] and not cfg.get('_fast_lane'):
                # Finished preorders return to the unchanged deal lane after live validation.
                ordinary.append(row)
                tracked.pop(o['key'], None)
                quotes.pop(key, None)
                continue
            rules = dict(SHOP_RULES.get(shop['id'], {}), **settings.get('shop_rules', {}).get(shop['id'], {}))
            if (rules.get('strict_variant_check') and not row.get('variant_validated')) or (rules.get('require_live_stock_validation') and not row.get('live_validated')):
                reject(o, 'AMBIGUOUS_VARIANT')
                continue
            if rules.get('strict_cart_check') and not row.get('cart_validated'):
                reject(o, 'NO_CHECKOUT')
                continue
            if row['availability_status'] not in ('in_stock', 'preorder') or row.get('add_to_cart_available') is not True:
                reject(o, 'NO_CHECKOUT')
                continue
            confidence = seller_confidence(row, shop, settings)
            if confidence is None:
                quotes.pop(key, None)
                reject(o, 'SELLER_RISK')
                continue
            normalized.update(seller_confidence=confidence, retailer_group=shop.get('retailer_group', urlsplit(shop['base_url']).hostname))
            valid.append(normalized)
            quotes[key] = dict(normalized, validated_at=now)
    finally:
        if original_deadline is not None:
            client.deadline = original_deadline
    deals = []
    for o in valid:
        diagnostic = {}
        pricing = price_check(o, list(quotes.values()), cfg, now, table.values(), diagnostic)
        if pricing and cfg.get('_fast_lane') and re.search(r'wachsendes chaos|optimale ordnung|ME[ -]?0[34]\b', o['title'], re.I) and o['franchise'] == 'Pokémon':
            if Decimal(o['price']) > Decimal(pricing['baseline']) * Decimal('.80'):
                pricing = None
        if not pricing:
            reject(o, diagnostic.get('reason', 'PRICE_TOO_HIGH'))
            continue
        record = table[o['product_key']]
        # Do not perpetually renew a historical anchor from its own derived verdict.
        if not pricing['why'].startswith('Zuletzt qualifizierter'):
            record['retail_observation'] = {'at': now, 'price': o['price'], 'comparison_key': o['comparison_key']}
        sent = record.get('last_alert')
        drop = Decimal(str(settings.get('price_drop_pct', 5))) / 100
        if sent and sent['episode'] == record['episode'] and Decimal(o['price']) > Decimal(sent['price']) * (1 - drop):
            reject(o, 'DUPLICATE')
            continue
        o.update(pricing=pricing, episode=record['episode'])
        o['priority_score'] = (100 if o['set_code'] == 'FB11' else 0) + (30 if o['product_type'] == 'display' else 10) + (20 if o['edition'] == 'first' else -10 if o['edition'] == 'second' else 0) + (30 if pricing['strong'] else 0) + o['seller_confidence']['score'] // 10
        deals.append(o)
    report['rejected'] = dict(rejected)
    unique = {o['product_key']: o for o in deals}
    return ordinary, sorted(unique.values(), key=lambda o: (-o['priority_score'], Decimal(o['price']))), report


def delivered(state, deal, now, message_id):
    state['preorder_products'][deal['product_key']]['last_alert'] = {
        'at': now, 'price': deal['price'], 'episode': deal['episode'], 'message_id': message_id}
