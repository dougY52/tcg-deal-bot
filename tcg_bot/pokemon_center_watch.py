"""Independent German Pokémon Center signals; no login or stock inference.

Public community statements are attributed leads, never checkout confirmation.
The store, source region, observation time and evidence class stay separate.
"""
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
import time
from math import isfinite
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .drop_watch import visible
from .pokemon_center_queue import snapshot as queue_snapshot
from .pc_schedule import due as check_due
from .scanning import collect
from .telegram_sources import parse as telegram_parse
from .web_sources import Document

CENTER = re.compile(r'pok[eé]mon\s*cent(?:er|re)|\bPKC\b', re.I)
DE = re.compile(r'\b(?:deutschland|germany|german|deutsch(?:e[nmrs]?)?)\b|Pok[eé]mon Center\s+DE\b', re.I)
NEG_DE = re.compile(r'\b(?:not|no|nicht|kein\w*)\s+(?:(?:for|in|für)\s+)?(?:germany|german|deutsch\w*|DE\b)', re.I)
PRODUCT = re.compile(r'booster|display|trainer[ -]?box|\betbs?\b|\bttbs?\b|kollektion|collection|\btins?\b|\bbundles?\b|\bupcs?\b', re.I)
EARLY = re.compile(r'back[ -]?end|(?:loaded|added|listed|hinterlegt|eingepflegt|gelistet).{0,80}(?:product|produkt|SKU)|(?:products?|produkte?|SKUs?).{0,80}(?:loaded|added|listed|hinterlegt|eingepflegt|gelistet)', re.I)
QUEUE = re.compile(r'warteschlange|warteraum|\bqueue\b', re.I)
LIVE = re.compile(r'\blive\b|\bopen\b|\bup\b|aktiv|geöffnet|offen|gestartet', re.I)
STOCK = re.compile(r'auf lager|vorrätig|lieferbar|verfügbar|erhältlich|bestellbar|vorbestellen|pre.?orders? (?:open|live)|in stock|available|add to cart', re.I)
NEGATIVE = re.compile(r'ausverkauft|sold out|out of stock|abgelaufen|closed|geschlossen|not (?:live|available|open)|nicht (?:mehr )?(?:lieferbar|verfügbar|offen)|waitlist|notify me|benachrichtigen|coming soon|invitation|einladung', re.I)
SPECULATIVE = re.compile(r'\?|vielleicht|vermutlich|gerücht|rumou?r|maybe|might|possibly|could be|expected|expecting|hopefully|likely|\bsoon\b|\bbald\b|\bmorgen\b|tomorrow', re.I)
SKU = re.compile(r'\b\d{2,3}-\d{4,6}-\d{3}\b')
OTHER_SHOP = re.compile(r'\b(?:smyths|target|walmart|amazon|otto|kaufland|mediamarkt|saturn|müller|rossmann|costco|best\s*buy)\b', re.I)


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def content(body):
    """Only the author's prose. Quoted posts/previews must not donate DE proof."""
    doc = Document(body)
    for n in doc.root.walk():
        if n.tag in ('blockquote', 'img') or 'quote' in n.attrs.get('class', '').split():
            n.children = []
        if n.tag == 'br':
            n.children = ['\n']
    return clean(visible(doc.root))


def timestamp(value):
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        try:
            d = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return d.timestamp() if d.tzinfo else None


def parse_xml(body, source):
    if re.search(r'<!DOCTYPE|<!ENTITY', body, re.I):
        raise ValueError('XML entities unsupported')
    root = ET.fromstring(body)
    rows = []
    if root.tag == 'rss' and root.find('channel') is not None:
        for node in root.findall('channel/item')[:100]:
            url = node.findtext('link', '')
            title = node.findtext('title', '')
            if source['kind'] == 'x_rss':
                handle = source['handle']
                match = re.fullmatch(r'https://teapawt\.net/'+re.escape(handle)+r'/status/(\d+)', url, re.I)
                creator = node.findtext('{http://purl.org/dc/elements/1.1/}creator', '')
                if not match or creator.lower() != '@'+handle.lower() or title.startswith('RT '):
                    continue
                url = 'https://x.com/'+handle+'/status/'+match[1]
            rows.append(dict(id=url, url=url, text=content(node.findtext('description') or title),
                             published=timestamp(node.findtext('pubDate', ''))))
    elif root.tag == '{http://www.w3.org/2005/Atom}feed':
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for node in root.findall('a:entry', ns)[:100]:
            link = node.find('a:link', ns)
            url = link.get('href', '') if link is not None else ''
            # Reddit's new-post feed, not comments or arbitrarily embedded links.
            if not re.fullmatch(r'https://www\.reddit\.com/r/[A-Za-z0-9_]+/comments/[a-z0-9]+/[^?#]*/?', url):
                continue
            title = node.findtext('a:title', '', ns)
            # Use title only: Atom content includes crossposts and unrelated previews.
            rows.append(dict(id=node.findtext('a:id', url, ns), url=url, text=title,
                             published=timestamp(node.findtext('a:published', '', ns))))
    else:
        raise ValueError('Feed layout unavailable')
    return rows


def parse_communityone(body, source):
    rows = []
    doc = Document(body)
    container = next((n for n in doc.root.walk() if n.attrs.get('id') == 'announcementsSSR'), None)
    if container is None:
        raise ValueError('Announcements unavailable')
    for node in container.walk():
        if node.tag != 'article' or not re.fullmatch(r'msg-\d+', node.attrs.get('id', '')):
            continue
        prose = next((n for n in node.walk() if 'announcement-content' in n.attrs.get('class', '').split()), None)
        date = next((n for n in node.walk() if n.tag == 'time'), None)
        if prose is None or date is None:
            continue
        # A headline can concern UK, while a separate sentence explicitly concerns DE.
        text = clean(visible(prose))
        rows.append(dict(id=source['id']+':'+node.attrs['id'], url=source['url']+'#'+node.attrs['id'],
                         text=text, published=timestamp(date.attrs.get('datetime', ''))))
    return rows


def qualify(row, now, cfg):
    text = row['text']
    if not CENTER.search(text):
        return None, 'NOT_POKEMON_CENTER'
    # Region must occur in the same statement as the signal. Do not infer it
    # from the account name, feed language, EUR price or a different UK product.
    sentences = re.split(r'(?<=[.!?])\s+|[\r\n]+', text)
    parts = [s for s in sentences if DE.search(s) and not NEG_DE.search(s) and not OTHER_SHOP.search(s)]
    if not parts:
        return None, 'GERMANY_NOT_EXPLICIT'
    claim = clean(' '.join(parts))
    if SPECULATIVE.search(claim):
        return None, 'SPECULATION'
    if QUEUE.search(claim) and LIVE.search(claim) and not NEGATIVE.search(claim):
        kind = 'queue_report'
    elif (PRODUCT.search(claim) or SKU.search(claim)) and (EARLY.search(claim) or re.search(r'\bloaded\b|hinterlegt|eingepflegt', claim, re.I)):
        # "Not live yet" is expected in a backend lead, but a retraction is not.
        if re.search(r'not.{0,15}(?:loaded|listed)|nicht.{0,15}(?:hinterlegt|gelistet)|fake|falsch|widerrufen|cancelled', claim, re.I):
            return None, 'RETRACTED'
        kind = 'early_warning'
    elif PRODUCT.search(claim) and STOCK.search(claim) and not NEGATIVE.search(claim):
        kind = 'stock_report'
    else:
        return None, 'NO_ACTIONABLE_SIGNAL'
    age = now-row['published'] if isinstance(row.get('published'), (int, float)) else float('inf')
    limit = cfg.get('early_max_age_seconds', 172800) if kind == 'early_warning' else cfg.get('live_max_age_seconds', 900)
    if not 0 <= age <= limit:
        return None, 'STALE_OR_UNDATED'
    skus = sorted(set(SKU.findall(claim)))
    if kind == 'queue_report':
        identity = 'queue-de'
    elif skus:
        identity = ','.join(skus)
    elif re.search(r'30(?:th|\s*jahre)|30.?(?:anniversary|celebration)', claim, re.I) and re.search(r'\betbs?\b|\bttbs?\b|trainer[ -]?box', claim, re.I):
        identity = '30-years-etb-de'
    else:
        identity = clean(re.sub(r'[^a-z0-9äöüß ]', '', claim.casefold()))
    return dict(row, claim=claim, kind=kind, identity=identity, skus=skus,
                evidence='community_report', inventory_confirmed=False), None


def payload(event, source):
    titles = {'early_warning': '👀 VORWARNUNG · POKÉMON CENTER DE',
              'queue_report': '🚦 QUEUE GEMELDET · POKÉMON CENTER DE',
              'stock_report': '📣 BESTAND GEMELDET · POKÉMON CENTER DE',
              'queue_confirmed': '🚦 DE-WARTESCHLANGE SICHTBAR'}
    excerpt = re.sub(r'[@*_`<>\[\]\\]', '', event['claim'])[:600]
    description = '🇩🇪 **Deutschland ausdrücklich genannt**\n'+excerpt
    if event['evidence'] == 'community_report':
        description += '\n\n**Community-Hinweis, vom Shop nicht bestätigt.**'
    if event['kind'] == 'early_warning':
        description += '\nProdukt laut Quelle hinterlegt. Noch kein bestätigter Verkaufsstart, Bestand oder Termin.'
    elif event['kind'] in ('queue_report', 'queue_confirmed'):
        description += '\nEine Warteschlange garantiert keinen Drop oder Bestand.'
    else:
        description += '\nKaufbarkeit und Preis bitte im Shop prüfen.'
    description += '\n[Pokémon Center Deutschland öffnen](https://www.pokemoncenter.com/de-de/)'
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': titles[event['kind']], 'url': event['url'], 'description': description,
        'color': 0x3498DB if event['kind'] == 'early_warning' else 0xF1C40F,
        'timestamp': datetime.fromtimestamp(event['published'], timezone.utc).isoformat(),
        'footer': {'text': 'Quelle: '+source['name']+' · Datum = Originalmeldung'}}]}


def fetch_source(source, client, now, queue_observation=None):
    kind = source['kind']
    if kind == 'store':
        result = queue_observation or queue_snapshot(client, source['url'], now)
        note = {'blocked': 'BLOCKED_NOT_STOCK', 'unknown': 'QUEUE_STATUS_UNKNOWN',
                'queue_open_region_unknown': 'QUEUE_REGION_UNCONFIRMED',
                'queue_open_de': 'QUEUE_DE_CONFIRMED', 'store_readable': 'STORE_READABLE'}[result['status']]
        rows = []
        if result['status'] == 'queue_open_de':
            rows.append(dict(id='official-queue', url=source['url'], claim=result['banner'],
                             published=now, kind='queue_confirmed', identity='queue-de',
                             evidence='store_page', inventory_confirmed=False))
        return rows, [note] + (['QUEUE_FRAME_READ'] if result['frame_checked'] else [])
    body = client.text(source['url'])
    if kind == 'communityone':
        return parse_communityone(body, source), []
    if kind in ('x_rss', 'atom'):
        return parse_xml(body, source), []
    if kind == 'telegram':
        return [dict(id=r['url'], url=r['url'], text=r['title'], published=r['published'])
                for r in telegram_parse(body, source['channel'])], []
    raise ValueError('Unsupported source kind')


def run(cfg, state, client, now=None, send=None, checkpoint=None, queue_observation=None):
    now = time.time() if now is None else now
    # The independent provider has already fetched the page. A transport pause
    # on the direct route must not suppress fresh evidence from that read.
    observed = queue_observation.get('observed_at') if isinstance(queue_observation, dict) else None
    confirmed = (type(observed) in (int, float) and isfinite(observed)
                 and 0 <= now-observed <= 120
                 and queue_observation.get('status') == 'queue_open_de'
                 and queue_observation.get('region') == 'DE'
                 and bool(queue_observation.get('banner')))
    if not confirmed:
        queue_observation = None
    state.setdefault('pc_de', {'sources': {}, 'delivered': {}, 'events': {}})
    table = state['pc_de']
    report = dict(checked_at=datetime.fromtimestamp(now, timezone.utc).isoformat(),
                  sources=[], rejected={}, alerts=[], sent=0, errors=[], inventory_confirmed=False)
    rejects = Counter()
    due, immediate = [], []
    for source in cfg['sources']:
        old = table['sources'].get(source['id'], {})
        ready = check_due(old.get('checked_at', 0), now, source.get('interval_seconds', 240), source.get('minute_slots', False))
        # Migrate old one-hour pauses for HTML challenge pages. Network/429/503
        # backoff remains unchanged; a normal 200 challenge gets one next-run read.
        recheck_blocked = (source['kind'] == 'store' and old.get('status') == 'blocked'
                           and ready)
        if source['id'] == 'pc-de-store' and source['kind'] == 'store' and confirmed:
            immediate.append(dict(source, adapter='pc', base_url=source['url']))
        elif now < old.get('retry_at', 0) and not recheck_blocked:
            report['sources'].append(dict(id=source['id'], status='backoff', retry_at=old['retry_at']))
        elif ready:
            due.append(dict(source, adapter='pc', base_url=source['url']))
        else:
            report['sources'].append(dict(id=source['id'], status='not_due'))
    def fetch(source, transport):
        observation = queue_observation if source['id'] == 'pc-de-store' else None
        return fetch_source(source, transport, now, observation)
    def results():
        # Yield before starting other network requests: collect() waits for all
        # its futures. Confirmed queues must not wait for slow community feeds.
        for source in immediate:
            rows, notes = fetch(source, client)
            yield source, rows, notes, None, 0
        yield from collect(due, client, {'pc': fetch}, workers=4, source_seconds=30)
    for source, rows, notes, error, elapsed in results():
        old = table['sources'].setdefault(source['id'], {})
        direct_retry = old.get('retry_at', 0) if confirmed and source['id'] == 'pc-de-store' else 0
        old['checked_at'] = now
        blocked = 'BLOCKED_NOT_STOCK' in notes
        status = 'unavailable' if error else 'blocked' if blocked else 'ok'
        old['status'] = status
        if error or blocked:
            old['failures'] = min(6, old.get('failures', 0)+1)
            # A failed source is visible; it is never stored as "no stock".
            old['retry_at'] = max(now+min(3600, 300*2**(old['failures']-1)),
                                  getattr(client, 'cooldowns', {}).get(urlsplit(source['url']).netloc, 0))
            if blocked and source['kind'] == 'store':
                old['retry_at'] = max(now+source.get('interval_seconds', 240),
                                      getattr(client, 'cooldowns', {}).get(urlsplit(source['url']).netloc, 0))
        else:
            # Reading already-confirmed evidence does not lift the direct
            # route's Retry-After/network backoff for the next HTTP request.
            old.update(failures=0, retry_at=direct_retry, last_success=now)
        if source['kind'] == 'store' and not error and not blocked:
            if 'STORE_READABLE' in notes and not rows:
                old['clear_count'] = old.get('clear_count', 0)+1
                if old['clear_count'] >= 2:
                    old['queue_active'] = False
            elif rows:
                old['clear_count'] = 0
                # A new shared-queue wave needs two fresh clear samples AND a
                # new official DE page confirmation. A generic signal is never
                # sufficient. A direct DE observation in this wave already counts.
                wave = queue_observation if source['id'] == 'pc-de-store' else None
                new_wave = (wave and wave.get('gate_wave') != old.get('gate_wave') and
                            old.get('last_queue_seen_at', 0) < wave.get('wave_started_at', 0))
                if not old.get('queue_active') or new_wave:
                    old['queue_episode'] = old.get('queue_episode', 0)+1
                old['last_queue_seen_at'] = now
                if wave:
                    old['gate_wave'] = wave.get('gate_wave')
                old['queue_active'] = True
                rows[0]['id'] += ':'+str(old['queue_episode'])
            else:
                old['clear_count'] = 0
        elif source['kind'] == 'store':
            old['clear_count'] = 0
        report['sources'].append(dict(id=source['id'], status=status, items=len(rows), notes=notes,
                                      error=error, seconds=elapsed))
        for row in rows:
            if row.get('evidence') == 'store_page':
                event, reason = row, None
            else:
                event, reason = qualify(row, now, cfg)
            if reason:
                rejects[reason] += 1
                continue
            key = sha256(event['id'].encode()).hexdigest()[:32]
            fingerprint = sha256((event['kind']+':'+event['identity']).encode()).hexdigest()[:32]
            shared_duplicate = (event['evidence'] != 'store_page' and
                now-table['events'].get(fingerprint, {}).get('at', 0) < cfg.get('cross_source_cooldown_seconds', 21600))
            if key in table['delivered'] or shared_duplicate:
                rejects['DUPLICATE'] += 1
                continue
            if len(report['alerts']) >= cfg.get('max_alerts_per_run', 4):
                rejects['ALERT_BUDGET'] += 1
                continue
            message = payload(event, source)
            report['alerts'].append(dict(source=source['id'], kind=event['kind'], url=event['url'], payload=message))
            if send:
                try:
                    message_id = send(message)
                except Exception as exc:
                    report['errors'].append('Discord: '+type(exc).__name__)
                    # Do not mark delivered if Discord did not acknowledge it.
                    report['rejected'] = dict(rejects)
                    return report
                table['delivered'][key] = dict(at=now, message_id=message_id, source=source['id'], url=event['url'])
                table['events'][fingerprint] = dict(at=now, kind=event['kind'])
                report['sent'] += 1
                if checkpoint:
                    checkpoint(state)
    for key in ('delivered', 'events'):
        table[key] = {k:v for k,v in table[key].items() if now-v['at'] <= 30*86400}
    report['rejected'] = dict(rejects)
    report['readable_sources'] = sum(r['status'] == 'ok' for r in report['sources'])
    return report
