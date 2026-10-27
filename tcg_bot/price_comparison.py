"""Keep reviewed retail separate from unfiltered Cardmarket resale snapshots."""
import copy
from datetime import datetime, timezone
from decimal import Decimal
import re

from . import cardmarket
from .product_types import product_kind, single_pack_variant
from .rules import franchise, language


def match_product(o, cfg, state=None):
    reviewed = reviewed_match_product(o,cfg)
    if reviewed or state is None:
        return reviewed
    from .cardmarket_catalog import match_offer
    return match_offer(o,cfg,state)


def reviewed_pack_counts(o, cfg):
    """Packaging from exact reviewed SKU bindings/EANs, never from a set code alone."""
    from .preorders import reference_matches
    return {r['packs'] for r in cfg.get('references', [])
            if r.get('packs') and reference_matches(o, r)}


def reviewed_match_product(o, cfg):
    settings = cfg.get('price_comparison', {})
    if not settings.get('enabled') or o.get('currency') != 'EUR':
        return None
    title = o['title']+' '+o.get('variant', '')
    from .product_types import NON_SEALED
    if re.search(NON_SEALED,title,re.I):
        return None
    if (single_pack_variant(o.get('variant','')) or
            re.search(r'\b(?:case|repack|opened|unsealed|resealed|b-ware|non-english|asia|japanisch|japanese|korean|chinesisch|enhanced|reprint|unlimited|collector|1st|2nd|first edition|second edition)\b', title, re.I) or
            re.search(r'\b\d+\s*[x×]\s*(?:display|box|bundle|etb)',title,re.I)):
        return None
    family = o.get('franchise') or franchise(dict(o, description=''), cfg)
    lang = o.get('language') or language(o)
    kind = product_kind(title)
    if kind == 'display' and re.search(r'\b(?:special|premium|anniversary)\b', title, re.I):
        return None
    codes = {prefix.upper()+f'{int(number):02d}' for prefix,number in re.findall(r'\b(FB|BT|OP|EB|PRB)[ -]?(\d+)\b',title,re.I)}
    text = title+' '+o.get('description','')
    counts = {int(n) for n in re.findall(r'\b(\d{1,3})\s*(?:[x×]\s*)?(?:boosters?|boosterpacks?|packs?)\b', text, re.I)}
    counts.update(int(n) for n in re.findall(r'\b(\d{1,2})er[ -]*(?:booster[ -]*)?display',title,re.I))
    counts.discard(1)
    if o.get('packs'):
        counts.add(int(o['packs']))
    counts.update(reviewed_pack_counts(o, cfg))
    pc = bool(re.search(r'pok[eé]mon[ -]*cent(?:er|re)|\bPC\s*(?:ETB|exclusive)', title,re.I))
    matches = []
    for m in settings.get('products', []):
        if m.get('gtins'):
            from .rules import gtin_key
            if gtin_key(o.get('gtin')) not in {gtin_key(g) for g in m['gtins']}:
                continue
        if (family != cardmarket.GAMES[m['game_id']] or lang != m['language'] or kind != m['product_type'] or
                pc != m.get('pokemon_center',False) or not re.search(m['pattern'],title,re.I)):
            continue
        if m.get('packs') and counts != {m['packs']}:
            continue
        if codes and m.get('set_code') and codes != {m['set_code']}:
            continue
        matches.append(m)
    return matches[0] if len(matches)==1 else None


def retail_reference(o, cfg, now, mapping=None):
    """Only explicit, dated EUR retail evidence; NEVER Cardmarket/history/median."""
    if not cfg.get('price_comparison',{}).get('enabled'):
        return None
    today = datetime.fromtimestamp(now, timezone.utc).date()
    def fresh(r):
        try:
            verified = datetime.strptime(r['verified_on'],'%Y-%m-%d').date()
            until = datetime.strptime(r['valid_until'],'%Y-%m-%d').date()
            return verified <= today <= until and (today-verified).days <= 30
        except (KeyError, ValueError):
            return False
    references = []
    from .retail_research import reference_for
    automatic = reference_for(o, cfg, now)
    if automatic:
        references.append(automatic)
    mapping = mapping or match_product(o,cfg)
    if mapping:
        r = mapping.get('retail')
        if r and fresh(r):
            references.append(r)
    from .preorders import reference_matches
    for r in cfg.get('references',[]):
        if fresh(r) and r['kind'] in ('msrp','observed_retail') and reference_matches(o,r):
            references.append(dict(price_eur=r['retail_eur'],kind=r['kind'],url=r['evidence'][0]['url'],verified_on=r['verified_on']))
    for r in cfg.get('preorder_watch',{}).get('price_references',[]):
        if fresh(r) and r['kind'] in ('msrp','observed_retail') and r.get('comparison_key')==o.get('comparison_key') and o.get('comparison_key'):
            references.append(dict(price_eur=r['price_eur'],kind=r['kind'],url=r['evidence_url'],verified_on=r['verified_on']))
    # Existing market evidence is keyed by exact normalized product identity.
    if o.get('identity'):
        for r in cfg.get('market',{}).get('price_references',[]):
            if fresh(r) and r['kind'] in ('msrp','observed_retail') and r['identity']==o['identity']:
                references.append(dict(price_eur=r['price_eur'],kind=r['kind'],url=r['evidence_url'],verified_on=r['verified_on']))
    references = [r for r in references if cardmarket.positive(r.get('price_eur'))]
    return min(references,key=lambda r:Decimal(r['price_eur'])) if references else None


def assess(o, cfg, state, now):
    mapping = match_product(o,cfg,state)
    retail = retail_reference(o,cfg,now,mapping)
    cm = cardmarket.lookup(mapping,state,now) if mapping else None
    price = Decimal(str(o['price']))
    under_cm = bool(cm and price < Decimal(cm['trend']))
    if retail:
        base = Decimal(retail['price_eur'])
        delta = (price/base-1)*100
        if price <= base:
            code, label = 'retail_deal', '🟢 Guter Retailpreis'
            explanation = f'Artikelpreis {delta:+.1f} % zum belegten Retailwert. Versand separat prüfen; kein garantierter Bestpreis.'
        elif price <= (base*Decimal('1.05')).quantize(Decimal('0.01')):
            code, label = 'near_retail', '🟡 Nahe Retail – kein Schnäppchen'
            explanation = f'Artikelpreis {delta:+.1f} % über dem belegten Retailwert.'
        else:
            code = 'resale_only' if under_cm else 'above_retail'
            label = '🟠 Nur unter CM-Trend – kein Retail-Deal' if under_cm else '🔴 Über Retail – kein guter Retail-Deal'
            explanation = f'Artikelpreis {delta:+.1f} % über dem belegten Retailwert. Ein höherer Wiederverkaufsmarkt rechtfertigt diesen Aufschlag nicht.'
    else:
        code = 'resale_unverified' if under_cm else 'unknown'
        label = '🟠 Unter CM-Trend – Retail ungeprüft' if under_cm else '⚪ Retail ungeprüft – kein bestätigter Deal'
        explanation = 'Kein gültiger produktspezifischer Retail-/UVP-Beleg vorhanden. Händlervergleich oder Cardmarket-Trend allein bestätigen keinen guten Retail-Deal.'
    return {'code':code,'label':label,'explanation':explanation,'retail':retail,'cardmarket':cm,
            'mapping':mapping,'under_cardmarket_trend':under_cm}


def decorate(message, o, cfg, state, now):
    if not cfg.get('price_comparison',{}).get('enabled'):
        return message
    result = assess(o,cfg,state,now)
    msg = copy.deepcopy(message)
    e = msg['embeds'][0]
    event = ('FILIALBESTAND' if o.get('channel')=='pickup' else 'PREORDER' if o.get('preorder_status') or o.get('preorder') else 'RESTOCK' if o.get('episode',0)>0 else 'ANGEBOT')
    e['title'] = (result['label']+' · '+event+' · '+o['title'])[:250]
    e['color'] = {'retail_deal':0x26A269,'near_retail':0xE5A50A,'resale_only':0xE66100,'above_retail':0xC01C28,'resale_unverified':0xE66100,'unknown':0x777777}[result['code']]
    # Replace old market-median-based praise instead of displaying contradictions.
    e['description'] = re.sub(r'\n?💡[^\n]*','',e.get('description',''))
    removed = {'Einordnung','Vergleichsbasis','Preisquellen und Zeitpunkt','Hersteller-UVP','Geprüfter Normalpreis (keine UVP)','Aktueller Marktvergleich (Normalpreis/UVP unbekannt)','Preisbewertung','Warum qualifiziert?'}
    e['fields'] = [f for f in e.get('fields',[]) if f['name'] not in removed]
    r = result['retail']
    labels = {'msrp':'Hersteller-UVP','observed_retail':'Belegter Händler-Retailpreis','retailer_msrp':'UVP laut Händler (kein eigener Herstellerbeleg)'}
    retail = (f"{labels[r['kind']]}: **{Decimal(r['price_eur']):.2f} €**\nStand {r['verified_on']} · [Beleg]({r['url']})" if r else 'Unbekannt / Beleg abgelaufen. Cardmarket ersetzt keinen Retailpreis.')
    cm = result['cardmarket']
    if cm:
        delta = (Decimal(str(o['price']))/Decimal(cm['trend'])-1)*100
        stamp = datetime.fromtimestamp(cm['at'],timezone.utc).strftime('%d.%m.%Y %H:%M UTC')
        cm_text = f"Trend **{Decimal(cm['trend']):.2f} €** · Artikelpreis dazu {delta:+.1f} %\nStand {stamp} · Produkt-ID {cm['product_id']} · [Tagesdatei]({cm['source_url']})\nUngefilterter Marktwert: keine Sprach-/DE-Verkäuferfilter, kein Versand, kein Liveangebot. Keine UVP."
    else:
        cm_text = ('Keine eindeutige Produktzuordnung.' if not result['mapping'] else 'Kein aktueller gültiger Cardmarket-Datensatz; wird automatisch erneut geprüft.')+' Kein bestätigter Preisvergleich.'
    e['fields'] += [{'name':'Retail / UVP – getrennte Referenz','value':retail},
                    {'name':'Cardmarket – Wiederverkaufsmarkt','value':cm_text},
                    {'name':'Dealbewertung','value':result['explanation']}]
    return msg


def compact(o, cfg, state, now):
    """Same judgment for batched near-retail/daily messages."""
    result = assess(o,cfg,state,now)
    r, cm = result['retail'], result['cardmarket']
    text = result['label']+'\n'
    text += (f"Retail **{Decimal(r['price_eur']):.2f} €** ({r['verified_on']}, {'UVP laut Händler' if r['kind']=='retailer_msrp' else 'Hersteller-UVP' if r['kind']=='msrp' else 'Händlerpreis'}) · [Beleg]({r['url']})" if r else 'Retail / UVP: unbekannt oder abgelaufen.')
    text += (f"\nCM-Trend **{Decimal(cm['trend']):.2f} €** · {datetime.fromtimestamp(cm['at'],timezone.utc):%d.%m.%Y} · ID {cm['product_id']} · [Quelle]({cm['source_url']})\nCM ungefiltert: Sprache/DE-Händler/Versand nicht abgegrenzt; kein Liveangebot, keine UVP." if cm else '\nCardmarket: keine eindeutige Zuordnung oder kein frischer Datensatz.')
    text += '\n'+result['explanation']
    return text


def validate_config(settings):
    assert isinstance(settings.get('enabled'),bool)
    assert isinstance(settings.get('automatic_catalog',False),bool)
    for source, aliases in settings.get('name_aliases',{}).items():
        assert source in ('pokemon','fw','masters','op') and isinstance(aliases,dict)
        assert all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in aliases.items())
    products = settings.get('products',[])
    assert isinstance(products,list) and len(products)<=500
    ids=set()
    for m in products:
        assert m['game_id'] in cardmarket.GAMES
        key=(m['game_id'],m['product_id'])
        assert key not in ids and type(m['product_id']) is int and m['product_id']>0
        ids.add(key)
        assert type(m['category_id']) is int and m['category_id']>0
        assert isinstance(m['catalog_name'],str) and m['catalog_name']
        assert not re.search(r'\b(?:Case|Non-English|Asia Region|Single)\b',m['catalog_name'])
        re.compile(m['pattern'])
        if m.get('set_code'):
            assert re.fullmatch(r'(FB|BT|OP|EB|PRB)\d{2,3}', m['set_code'])
        assert m['product_type'] in ('display','bundle','etb','collection','box','tin','mini_tin')
        assert m['language']==('DE' if m['game_id']==6 else 'EN')
        assert m.get('packs') is None or type(m['packs']) is int and 1<=m['packs']<=36
        if m.get('gtins'):
            from .rules import gtin_key
            assert all(gtin_key(g) for g in m['gtins'])
        assert m['product_type'] not in ('display','bundle') or m.get('packs')
        r=m.get('retail')
        if r:
            assert r['kind'] in ('msrp','observed_retail','retailer_msrp')
            assert cardmarket.positive(r['price_eur']) and r['url'].startswith('https://') and r['note']
            start=datetime.strptime(r['verified_on'],'%Y-%m-%d')
            end=datetime.strptime(r['valid_until'],'%Y-%m-%d')
            assert 0 <= (end-start).days <=30
