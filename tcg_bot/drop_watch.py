"""Official public announcements and visible queues; never purchase/stock proof."""
from datetime import datetime
from hashlib import sha256
import re
import time
from urllib.parse import urlsplit, urljoin
from zoneinfo import ZoneInfo
from .web_sources import Document, Node
from .rules import excluded_franchise

BERLIN = ZoneInfo('Europe/Berlin')
EVENT = re.compile(r'\bdrop\b|verkaufsstart|vorverkaufsstart|vorbestellstart|pre.?orders? (?:open|start)|sale (?:starts|opens)', re.I)
FAMILY = re.compile(r'pok[eé]mon|dragon\s*ball|one\s*piece|naruto', re.I)
PRODUCT = re.compile(r'\btcg\b|sammelkarten|booster|display|trainer.box|collection|\betb\b', re.I)


def visible(node):
    if node.tag in ('script', 'style', 'template', 'noscript', 'nav', 'footer') or 'hidden' in node.attrs or node.attrs.get('aria-hidden') == 'true':
        return ''
    if re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', node.attrs.get('style', ''), re.I):
        return ''
    return ' '.join(visible(c) if isinstance(c, Node) else c for c in node.children)


def visible_nodes(node):
    if not visible(node).strip():
        return
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from visible_nodes(child)


def inspect(page, source, now):
    doc = Document(page)
    text = re.sub(r'\s+', ' ', visible(doc.root)).strip()
    title = ' '.join(n.text() for n in doc.root.walk() if n.tag in ('title', 'h1'))
    # HTTP 200 challenges are not normal pages, closed queues, or stock evidence.
    if len(text) < 30 or (len(text) < 3000 and re.search(r'incapsula|access denied|verify you are human|captcha|request unsuccessful|just a moment|client challenge', text + ' ' + title, re.I)):
        return 'blocked_or_unreadable', []
    queue_title = re.search(r'virtual queue|waiting room|warteschlange|warteraum|you are (?:now )?in line', title, re.I)
    queue_body = re.search(r'wartezeit|position in|dein(?:e)? (?:platz|position)|estimated wait|you are (?:now )?in line|keep (?:this|the|your).*?(?:window|page) open|bitte.*warten', text, re.I)
    closed = re.search(r'queue (?:is )?closed|warteschlange (?:ist )?geschlossen|waiting room (?:is )?closed', title, re.I)
    if queue_title and queue_body and not closed:
        return 'queue_open', [{'kind': 'queue', 'key': 'queue', 'title': 'Warteschlange sichtbar',
                               'detail': 'Die Händlerseite zeigt aktuell einen Warteraum. Kein bestätigter Drop, Bestand oder Kaufzugang. Produktsprache noch unbestätigt.'}]
    events = {}
    for node in visible_nodes(doc.root):
        if node.tag not in ('article', 'section', 'p', 'div'):
            continue
        block = re.sub(r'\s+', ' ', visible(node)).strip()
        if not 25 <= len(block) <= 800 or not EVENT.search(block) or not FAMILY.search(block) or not PRODUCT.search(block):
            continue
        if re.search(r'abgesagt|verschoben|cancelled|canceled|sold out|ausverkauft', block, re.I):
            continue
        family = FAMILY.search(block)[0].lower()
        if re.search('pok[eé]mon', family) and not re.search(r'deutsch|german|\bDE\b', block, re.I):
            continue
        if re.search('dragon|one', family) and not re.search(r'englisch|english|\bEN\b', block, re.I):
            continue
        if re.search('naruto', family) and not re.search(r'deutsch|german|englisch|english|\b(?:DE|EN)\b', block, re.I):
            continue
        # A precise date AND time are mandatory; release dates alone do not count.
        date_match = re.search(r'\b(20\d{2})-(\d{2})-(\d{2})\b|\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b', block)
        clock = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\s*(?:Uhr|CET|CEST|MEZ|MESZ)?', block)
        if not date_match or not clock:
            continue
        try:
            y, m, d = (date_match.group(1, 2, 3) if date_match[1] else date_match.group(6, 5, 4))
            start = datetime(int(y), int(m), int(d), int(clock[1]), int(clock[2]), tzinfo=BERLIN)
            if not -300 <= start.timestamp() - now <= 7 * 86400:
                continue
        except ValueError:
            continue
        key = family + ':' + str(int(start.timestamp()))
        event = {'kind': 'announcement', 'key': key, 'title': 'Verkaufsstart angekündigt',
                 'start': start.isoformat(), 'detail': block[:650]}
        if key not in events or len(event['detail']) < len(events[key]['detail']):
            events[key] = event
    return 'readable', list(events.values())


def sources(cfg):
    explicit = list(cfg.get('drop_watch', {}).get('sources', []))
    hosts = {urlsplit(s['url']).hostname for s in explicit}
    trusted = cfg.get('preorder_watch', {}).get('trusted_shop_ids', [])
    # Known German retailers only. Never turn arbitrary discovered hosts into trusted alerts.
    return explicit + [dict(id='shop:'+s['id'], name=s['name'], url=s['base_url'], interval_seconds=1800)
                       for s in cfg['shops'] if s.get('enabled', True) and not s.get('international')
                       and s['id'] in trusted and urlsplit(s['base_url']).hostname not in hosts]


def read_source(source, old, client, now):
    body = client.text(source['url'])
    status, events = inspect(body, source, now)
    if not source.get('follow_center_articles') or status != 'readable':
        return status, events
    checks = old.setdefault('article_checks', {})
    links = []
    for n in Document(body).root.walk():
        if n.tag != 'a' or not re.search(r'pok[eé]mon center', n.text(), re.I):
            continue
        url = urljoin(source['url'], n.attrs.get('href', ''))
        if (urlsplit(url).hostname == urlsplit(source['url']).hostname
                and urlsplit(url).path.startswith('/de/') and url not in links
                and now - checks.get(url, 0) >= 86400):
            links.append(url)
    for url in links[:2]:
        try:
            article_status, found = inspect(client.text(url), source, now)
        except Exception:
            continue
        if article_status == 'readable':
            if not found:
                checks[url] = now
            else:
                checks.pop(url, None)  # Delivery failures must remain retryable.
            # Only explicit dated DE-card sales announcements pass inspect().
            events.extend(dict(event, source_url=url) for event in found if event['kind'] == 'announcement')
    old['article_checks'] = dict(sorted(checks.items(), key=lambda item:item[1], reverse=True)[:100])
    return status, events


def payload(source, event):
    clean = lambda s: re.sub(r'[@*_`<>\[\]\\]', '', s)
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': '🚦 WARTESCHLANGE SICHTBAR' if event['kind'] == 'queue' else '📅 DROP ANGEKÜNDIGT',
        'url': event.get('source_url', source['url']), 'color': 0x3498DB,
        'description': f"**{clean(source['name'])}** · Deutschland\n{clean(event['detail'])}\n\n"
                       'Hinweis zur Händlerseite; keine Bestands-, Preis- oder Kaufbestätigung.'}]}


def run(cfg, state, client, now, send=None, checkpoint=None):
    settings = cfg.get('drop_watch', {})
    result = {'sources': [], 'alerts': [], 'sent': 0, 'errors': []}
    if not settings.get('enabled'):
        return result
    table = state.setdefault('drop_watch_sources', {})
    due = [s for s in sources(cfg) if now-table.get(s['id'], {}).get('checked_at', 0) >= s.get('interval_seconds', 1800)]
    due.sort(key=lambda s: (s.get('priority', 1), table.get(s['id'], {}).get('checked_at', 0)))
    original = getattr(client, 'deadline', None)
    if original is not None:
        client.deadline = min(original, time.monotonic()+settings.get('budget_seconds', 18))
    try:
        for source in due[:settings.get('max_sources_per_run', 5)]:
            if original is not None and time.monotonic() >= client.deadline:
                break
            old = table.setdefault(source['id'], {'delivered': {}, 'queue_episode': 0})
            old['checked_at'] = now
            try:
                status, events = read_source(source, old, client, now)
            except Exception as exc:
                status, events = 'unavailable:' + type(exc).__name__, []
            old['status'] = status
            result['sources'].append({'id': source['id'], 'status': status})
            if status == 'readable':
                old['clear_count'] = old.get('clear_count', 0) + 1
                if old.get('queue_active') and old['clear_count'] >= 2:
                    old['queue_active'] = False
                    old['queue_episode'] += 1
            elif status == 'queue_open':
                old.update(clear_count=0, queue_active=True)
            # Unknown/blocked observations do not manufacture a queue reopening.
            for event in events:
                if excluded_franchise(event.get('detail', ''), cfg):
                    continue
                identity = event['key'] + (':'+str(old['queue_episode']) if event['kind'] == 'queue' else '')
                key = sha256(identity.encode()).hexdigest()[:24]
                if key in old['delivered']:
                    continue
                message = payload(source, event)
                result['alerts'].append({'key': source['id']+':'+key, 'reason': 'drop_signal', 'payload': message})
                if send:
                    try:
                        message_id = send(message)
                    except Exception as exc:
                        result['errors'].append('Drop Discord: '+type(exc).__name__)
                        return result
                    old['delivered'][key] = {'at': now, 'message_id': message_id}
                    result['sent'] += 1
                    if checkpoint:
                        checkpoint(state)
            old['delivered'] = {k:v for k,v in old['delivered'].items() if now-v['at'] < 90*86400 or k == sha256(('queue:'+str(old['queue_episode'])).encode()).hexdigest()[:24]}
    finally:
        if original is not None:
            client.deadline = original
    return result
