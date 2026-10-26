"""Daily full sealed catalogue; deterministic identities, never fuzzy price matching."""
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import re
import time
import unicodedata

CATEGORIES = {6: {53,1014,1015,1016,1083}, 13: {1052,1053,1054,1055,1061}, 18: {1624,1625,1628}}
# This excludes foreign-market releases and multi-unit cases, not expensive prices.
EXCLUDED = re.compile(r'\b(?:case|cases|non[ -]english|asia|japanese|japanisch|korean|chinese|chinesisch|indonesian|thai|french|francaise|italian|spanish|portuguese|s-ch|t-ch|jp|kr|cn|repack|mystery|empty|opened|unsealed|sleeves?|playmat|deckbox|coin set|coins? frame|card display|pendant|figure set|jigsaw|complete set)\b|\b(?:CSV|CSM|CBB|CSN|CSH)\w*:',re.I)
SOURCES = {
    'fw': 'https://www.dbs-cardgame.com/fw/en/products/',
    'masters': 'https://www.dbs-cardgame.com/us-en/product/',
    'op': 'https://en.onepiece-cardgame.com/products/?subcategory=boosters&page=1',
}
CODE = re.compile(r'\b(FB|BT|OP|EB|PRB|SB|FS|ST|TB|MB|EX|B)[ -]?(\d{1,3})\b',re.I)


def fold(text):
    text = unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode().lower()
    text = text.replace("'",'').replace('&',' and ')
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9.]+',' ',text)).strip()


def form(name, game):
    n=fold(name)
    if 'booster bundle' in n or 'booster bundel' in n or 'boosterpaket' in n:return 'bundle'
    if re.search(r'elite trainer|top trainer|\betb\b|\bttb\b',n):return 'etb'
    if re.search(r'\bmini tin\b',n):return 'mini_tin'
    if re.search(r'\btins?\b',n):return 'tin'
    if re.search(r'build and battle',n):return 'box'
    if re.search(r'booster box|booster display|\bdisplay\b',n):return 'display'
    if re.search(r'\bdeck\b',n):return 'deck'
    if re.search(r'collection|kollektion|premium|poster|binder',n):return 'collection'
    if re.search(r'\bbox\b|\bset\b|calendar|kalender',n):return 'box'
    return None


def catalogue(products, game):
    """No ID whitelist or price cutoff. Keep variants, even ones without a quote."""
    rows={}
    ids=Counter(p.get('idProduct') for p in products)
    for p in products:
        name=p.get('name','');pid=p.get('idProduct');category=p.get('idCategory')
        if (type(pid) is not int or pid<=0 or ids[pid]!=1 or category not in CATEGORIES[game]
                or not isinstance(name,str) or len(name)>300 or EXCLUDED.search(name) or EXCLUDED.search(fold(name))
                or re.search(r'\b\d+\s*[x×]\s*(?:booster box|display|tin|box|bundle)',name,re.I)):
            continue
        kind=form(name,game)
        if not kind:continue
        # A display of boxes/tins is not a single collection.
        if kind!='display' and re.search(r'\bdisplay\b',name,re.I):continue
        explicit=re.search(r'\((\d+) Boosters?\)',name,re.I)
        packs=int(explicit[1]) if explicit else 6 if kind=='bundle' else None
        # Standard boxes have known formats. Special formats retain unknown count;
        # exact full names and qualifiers still have to match.
        if kind=='display' and packs is None:
            if game==6:packs=36
            elif not re.search(r'manga|story|the best|collector',name,re.I):packs=24
        rows[str(pid)]={'game_id':game,'product_id':pid,'catalog_name':name,'category_id':category,
                       'product_type':kind,'packs':packs,'language':'DE' if game==6 else 'EN',
                       'pokemon_center':'pokemon center' in fold(name),'automatic':True}
    return rows


def pokemon_aliases(en,de):
    def valid(rows):
        if not isinstance(rows,list) or not rows or len(rows)>5000:raise ValueError('Invalid set catalogue')
        result={}
        for r in rows:
            if not isinstance(r,dict) or not isinstance(r.get('id'),str) or not isinstance(r.get('name'),str):continue
            if r['id'] in result:raise ValueError('Duplicate set ID')
            # Uppercase A/B sets are the digital Pocket game, not physical sealed.
            if re.fullmatch(r'[A-Z]\d[a-z]?',r['id']) or 'tcgp/' in r.get('logo',''):continue
            result[r['id']]=r['name']
        return result
    a,b=valid(en),valid(de)
    result = {fold(b[k]):fold(a[k]) for k in a.keys() & b.keys() if fold(a[k]) and fold(b[k])}
    for k in a.keys() & b.keys():
        if re.fullmatch(r'(sv|swsh|sm|xy|me)\d+(?:\.\d+)?',k):
            result[k]=fold(a[k])
            result[re.sub(r'(?<=[a-z])0+(?=\d)','',k)]=fold(a[k])
    return result


def bandai_aliases(body, source):
    from .web_sources import Document
    rows={};conflicts=set()
    for n in Document(body).root.walk():
        if n.tag not in ('a','h3','h4'):continue
        text=' '.join(n.text().replace('\u200b','').split())
        text=re.sub(r'^NEW\s+(?=[-～])','',text)
        if re.search(r'pre[ -]?release set|release event',text,re.I):continue
        # Only bracketed official product codes, never navigation pagination.
        m=re.search(r'[\[【](?:DBS-)?(FB|B|BT|OP|EB|PRB|SB|TB|MB|EX)[- ]?(\d+)[\]】]',text,re.I)
        if not m:continue
        before=text[:m.start()].strip(' -～')
        if '-' in before and re.search(r'BOOSTER|PACK',before,re.I):before=before.split('-',1)[1].strip(' -')
        before=before.strip(' -～')
        before=re.sub(r'^.*～','',before).strip()
        prefix=m[1].upper();prefix='BT' if prefix=='B' else prefix
        key=prefix+f'{int(m[2]):02d}'
        value=fold(before)
        value=re.sub(r'^one piece (?:card )?','',value)
        if not value or len(value)>100:continue
        if key in rows and rows[key]!=value:conflicts.add(key)
        rows[key]=value
    for k in conflicts:rows.pop(k,None)
    if not rows:raise ValueError('No official set names')
    return rows


def refresh_names(cfg,state,client,now):
    """One daily pass; separate source failures never suppress catalogue/alerts."""
    if not cfg.get('price_comparison',{}).get('automatic_catalog'):return {}
    if not callable(getattr(client,'public_set_json',None)):return {'status':'unavailable'}
    day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
    saved=state.setdefault('cardmarket_names',{})
    report={};deadline=client.deadline;client.deadline=min(deadline,time.monotonic()+25)
    try:
        for source in ('pokemon','fw','masters','op'):
            old=saved.get(source,{})
            if old.get('day')==day or now<old.get('retry_after',0):continue
            try:
                if source=='pokemon':
                    data=pokemon_aliases(client.public_set_json('en'),client.public_set_json('de'))
                else:
                    data=bandai_aliases(client.text(SOURCES[source]),source)
                    if source in ('op','fw'):
                        # Bounded public pagination. New sets appear on page one;
                        # old mappings remain cached as the archive grows.
                        for page in range(2,5 if source=='op' else 6):
                            url=SOURCES[source].replace('page=1',f'page={page}') if source=='op' else SOURCES[source]+f'?page={page}'
                            try:data.update(bandai_aliases(client.text(url),source))
                            except Exception:break
                saved[source]={'day':day,'at':now,'aliases':dict(old.get('aliases',{}),**data)}
                report[source]={'status':'updated','aliases':len(data)}
            except Exception as exc:
                saved.setdefault(source,{})['retry_after']=now+3600
                report[source]={'status':'unavailable','error':type(exc).__name__}
    finally:client.deadline=deadline
    return report


# Exact reviewed spelling fixes, not approximate matching.
SPELLINGS={'brigtness of hope':'brightness of hope','beyond generations':'beyond generation',
           'legend of the dragon balls':'legends of the dragon balls',
           'impact beyond dimensions':'impact beyond dimension',
           '500 years in the future':'500 years into the future'}
DESCRIPTORS=[(r'ultra premium (?:kollektion|collection|box)|\bupc\b','ultra premium collection'),
             (r'elite trainer box|top trainer box|\betb\b|\bttb\b',''),
             (r'booster bundle|booster bundel|boosterpaket',''),
             (r'booster box|booster display|\bdisplay\b',''),
             (r'\bkollektion\b','collection'),(r'\bfigur\b','figure'),
             (r'\bordner\b','binder'),(r'\bkalender\b','calendar'),
             (r'\bund\b','and'),(r'\bglurak\b','charizard'),(r'\bmewtu\b','mewtwo'),
             (r'\bquajutsu\b','greninja'),(r'\bfeelinara\b','sylveon'),
             (r'\bnachtara\b','umbreon'),(r'\bpsiana\b','espeon')]


def canonical(title,game,aliases):
    n=fold(title)
    if game==6:
        n=re.sub(r'\b(sv|swsh|sm|xy|me)[ -]+(\d+(?:\.\d+)?)\b',r'\1\2',n)
        # Longest alias first; no guessing or substring similarity.
        for de,en in sorted(aliases.get('pokemon',{}).items(),key=lambda x:-len(x[0])):
            n=re.sub(r'(?<!\w)'+re.escape(de)+r'(?!\w)',lambda _:en,n)
    if game==6 and form(title,game) in ('display','bundle','etb'):
        eras={'scarlet and violet','sword and shield','sun and moon','mega evolution','black and white','diamond and pearl','xy'}
        named={v for v in aliases.get('pokemon',{}).values() if v not in eras and len(v)>3 and re.search(r'(?<!\w)'+re.escape(v)+r'(?!\w)',n)}
        if named:
            for era in eras:n=re.sub(r'(?<!\w)'+re.escape(era)+r'(?!\w)',' ',n)
        # Some titles carry both the set code and the written name. Both must agree.
        for name in sorted(named,key=len,reverse=True):
            n=re.sub(r'('+re.escape(name)+r')\s+\1\b',r'\1',n)
    for old,new in SPELLINGS.items():n=n.replace(old,new)
    n=re.sub(r'\bcollector(?: s|s)?\b','collector',n)
    n=re.sub(r'(?<![\w.])\d+\s*(?:x\s*)?(?:boosters?|boosterpacks?|packs?)\b(?![ -]*(?:box|display)\b)',' ',n)
    n=re.sub(r'\b\d+er\b',' ',n)
    for pattern,replacement in DESCRIPTORS:n=re.sub(pattern,replacement,n)
    n=re.sub(r'\b(?:pokemon|dragon ball|super|fusion world|masters|one piece|trading card game|card game|tcg|default title|englisch|english|german|deutsch|eng|ger|de|en|neu|ovp|sealed|original|vorbestellung|vorbestellbar|preorder|pre order)\b',' ',n)
    n=re.sub(r'\b\d{4} \d{2} \d{2}\b|\b\d{2}\.\d{2}\.\d{4}\b',' ',n)
    n=re.sub(r'\bvol\.?\s*(\d+)',r'vol \1',n)
    return ' '.join(n.split()).strip(' .')


@lru_cache(maxsize=32)
def prepared(game, entries_key, names_key):
    """Build name index once per daily catalogue, not for every live candidate."""
    import json
    entries=json.loads(entries_key);aliases=json.loads(names_key);index={};code_names={}
    for source in ('fw','masters','op'):
        for code,name in aliases.get(source,{}).items():
            if (game==13 and source!='op') or (game==18 and source=='op'):
                code_names[code]=canonical(name,game,{})
    for row in entries:
        name=canonical(row['catalog_name'],game,aliases)
        index.setdefault((row['product_type'],name),[]).append(row)
    return index,code_names,aliases


def match_offer(o,cfg,state):
    if not cfg.get('price_comparison',{}).get('enabled') or not cfg.get('price_comparison',{}).get('automatic_catalog'):return None
    from .rules import franchise,language
    from .cardmarket import GAMES
    from .product_types import single_pack_variant, NON_SEALED
    game=next((g for g,f in GAMES.items() if f==(o.get('franchise') or franchise(dict(o,description=''),cfg))),None)
    detected=language(o)
    lang=o.get('language') or detected
    if game is None or lang!=('DE' if game==6 else 'EN') or o.get('currency')!='EUR':return None
    if detected not in ('UNKNOWN',lang):return None
    title=o['title']+' '+o.get('variant','')
    if re.search(NON_SEALED,title,re.I):return None
    if (EXCLUDED.search(title) or EXCLUDED.search(fold(title)) or single_pack_variant(o.get('variant','')) or
            re.search(r'\b\d+\s*[x×]\s*(?:display|box|tin|bundle|etb)',title,re.I)):return None
    kind=form(title,game)
    if kind!='display' and re.search(r'\bdisplay\b',title,re.I):return None
    cache=state.get('cardmarket_daily',{}).get(str(game),{})
    entries=cache.get('catalogue',{})
    if not entries:return None
    import json
    # Config seed keeps known spellings usable during a source outage.
    aliases={k:dict(v) for k,v in cfg['price_comparison'].get('name_aliases',{}).items()}
    for source,row in state.get('cardmarket_names',{}).items():aliases.setdefault(source,{}).update(row.get('aliases',{}))
    index,code_names,aliases=prepared(game,json.dumps(list(entries.values()),sort_keys=True),json.dumps(aliases,sort_keys=True))
    codes={m[0].upper()+f'{int(m[1]):02d}' for m in CODE.findall(title)}
    clean=title
    if codes:
        if len(codes)!=1:return None
        code=next(iter(codes))
        if game==13 and re.fullmatch(r'B\d+',code):code='BT'+code[1:]
        name=code_names.get(code)
        if name:
            clean=CODE.sub('',title)
            core=canonical(clean,game,aliases)
            # Code-only is allowed only with an official name. A conflicting name fails.
            if core and core!=name and not core.startswith(name+' '):return None
            clean=core or name
        # A future catalogue entry literally named OP19 is also an exact identity.
    identity=canonical(clean,game,aliases)
    rows=index.get((kind,identity),[])
    counts={int(n) for n in re.findall(r'(?<![\w.])(\d{1,3})\s*(?:[x×]\s*)?(?:boosters?|boosterpacks?|packs?)\b(?![ -]*(?:box|display)\b)',title+' '+o.get('description',''),re.I)}
    counts.update(int(n) for n in re.findall(r'\b(\d{1,2})er[ -]*(?:booster[ -]*)?display',title,re.I));counts.discard(1)
    if o.get('packs'):counts.add(int(o['packs']))
    from .price_comparison import reviewed_pack_counts
    counts.update(reviewed_pack_counts(o,cfg))
    if kind in ('display','bundle'):
        if len(counts)!=1:return None
        rows=[r for r in rows if r['packs'] is None or counts=={r['packs']}]
    # Distinct art/edition/version/PC/collector qualifiers remain in the identity.
    return rows[0] if len(rows)==1 else None
