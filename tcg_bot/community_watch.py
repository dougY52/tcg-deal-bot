"""Fresh, explicitly German PC community reports, never verified stock alerts.

Only public feeds, Telegram previews and original MyDealz articles are read. No accounts,
private Discord messages, redirect trackers or paid scraping are used.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
import time
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from .web_sources import Document, walk_json
from .drop_watch import visible, visible_nodes
from .scanning import collect
from . import telegram_sources

SOURCES = (
    ('mydealz-pokemon', 'https://www.mydealz.de/rss/gruppe/pokemon', 'rss'),
    ('mydealz-new', 'https://www.mydealz.de/rss/new', 'rss'),
    ('restockradar', 'https://restockradar.de/de/feed', 'radar'),
)
CENTER = re.compile(r'pok[eé]mon\s*cent(?:er|re)', re.I)
GERMANY = re.compile(r'pok[eé]mon\s*cent(?:er|re)\s*(?:[-–:|]\s*)?(?:deutschland|germany|german\b|de\b)', re.I)
PRODUCT = re.compile(r'booster|display|trainer[ -]?box|\betb\b|kollektion|collection|\btin\b|\bbundle\b', re.I)
QUEUE = re.compile(r'warteschlange|warteraum|\bqueue\b', re.I)
NEGATIVE = re.compile(r'ausverkauft|sold\s*out|abgelaufen|nicht (?:mehr )?(?:verfügbar|lieferbar)|geschlossen|\bclosed\b|waitlist|notify me|benachrichtigen|coming soon|einladung|invitation', re.I)
FOREIGN = re.compile(r'\b(?:uk|us|usa|gb|japan|japanisch|japanese|englisch|english)\b|großbritannien', re.I)


def clean(text):
    return re.sub(r'\s+', ' ', visible(Document(text).root)).strip()


def article_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'www.mydealz.de' or not re.fullmatch(r'/(?:deals|diskussionen)/[a-z0-9-]+-\d+', p.path):
        return None
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def pc_de_url(url):
    p = urlsplit(url)
    return not re.search(r'[\s<>()[\]\\]', url) and p.scheme == 'https' and p.netloc in ('www.pokemoncenter.com', 'pokemoncenter.com') and bool(re.match(r'^/(?:de-de|en-de)(?:/|$)', p.path))


def stamp(value):
    try:
        date = parsedate_to_datetime(value)
        return date.timestamp() if date.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def rss(body):
    if re.search(r'<!DOCTYPE|<!ENTITY', body, re.I):
        raise ValueError('Unsupported RSS entities')
    root = ET.fromstring(body)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Not an RSS feed')
    return [dict(url=i.findtext('link', ''), title=clean(i.findtext('title', '')),
                 published=stamp(i.findtext('pubDate')), body=i.findtext('description', ''))
            for i in root.findall('channel/item')[:100]]


def radar(body, now):
    doc = Document(body)
    if 'Community-Deals' not in clean(body):
        raise ValueError('Community feed layout changed')
    rows = []
    for node in doc.root.walk():
        if node.tag != 'div' or 'deal' not in node.attrs.get('class', '').split():
            continue
        link = next((n for n in node.walk() if n.tag == 'a' and article_url(n.attrs.get('href', ''))), None)
        if link is None:
            continue
        age = re.search(r'vor\s+(\d+)\s*(Minuten?|Sekunden?)', clean(node.text()), re.I)
        # Unknown/hour/day ages cannot qualify for a <=30 minute alert.
        published = now - (int(age[1])+1) * (60 if age[2].lower().startswith('min') else 1) if age else None
        rows.append(dict(url=link.attrs['href'], title=link.text(), body='', published=published))
    return rows


def original(body, url):
    """Read JSON serialization, never execute JS or match another article/comments."""
    thread_id = url.rsplit('-', 1)[-1]
    for node in Document(body).root.walk():
        if node.tag != 'script':
            continue
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*', node.text())
        if not match:
            continue
        try:
            data, _ = json.JSONDecoder().raw_decode(node.text()[match.end():])
        except ValueError:
            continue
        for obj in walk_json(data):
            if str(obj.get('threadId')) == thread_id and 'isExpired' in obj and 'descriptionPurified' in obj:
                return obj
    raise ValueError('Original article unavailable or parser changed')


def qualify(obj, now, settings):
    title = clean(obj.get('title', ''))
    body = obj.get('descriptionPurified') or ''
    if not isinstance(body, str):
        return None, 'UNKNOWN_CONTENT'
    text = clean(body)
    if obj.get('isExpired') is not False or obj.get('deletedAt') or obj.get('status') != 'Activated':
        return None, 'EXPIRED_OR_INACTIVE'
    if not CENTER.search(title):
        return None, 'NOT_POKEMON_CENTER'
    if FOREIGN.search(title):
        return None, 'WRONG_REGION_OR_LANGUAGE'
    links = [n.attrs.get('href', '') for n in visible_nodes(Document(body).root) if n.tag == 'a']
    if obj.get('link'):
        links.append(obj['link'])
    targets = [u for u in links if isinstance(u, str) and pc_de_url(u)]
    # German-language websites, EUR prices and the feed's locale are NOT DE proof.
    if not GERMANY.search(title + ' ' + text) and not targets:
        return None, 'GERMANY_NOT_EXPLICIT'
    is_queue = bool(QUEUE.search(title))
    if not is_queue and not PRODUCT.search(title):
        return None, 'NOT_SEALED_OR_QUEUE'
    if '?' in title or NEGATIVE.search(title) or re.search(r'\bmorgen\b|vielleicht|gerücht|vermutlich|bald|\bsoon\b', title, re.I):
        return None, 'NOT_CURRENT_REPORT'
    if is_queue and not re.search(r'\blive\b|\baktiv\b|\boffen\b|\bopen\b|geöffnet|online|gestartet', title, re.I):
        return None, 'QUEUE_NOT_OPEN_REPORT'
    # Explicit closure of this queue in the author's body defeats the title.
    if is_queue and re.search(r'(?:queue|warteschlange|warteraum).{0,35}(?:geschlossen|closed|nicht mehr|vorbei)', text, re.I):
        return None, 'NOT_CURRENT_REPORT'
    published = obj.get('publishedAt')
    age_limit = settings.get('queue_max_age_seconds', 900) if is_queue else settings.get('max_age_seconds', 1800)
    if not isinstance(published, (int, float)) or not math.isfinite(published) or not 0 <= now-published <= age_limit:
        return None, 'STALE_OR_UNDATED'
    price = obj.get('price')
    if price is not None:
        try:
            price = float(price)
        except (ValueError, TypeError):
            return None, 'INVALID_PRICE'
        if not math.isfinite(price) or price < 0 or price > settings.get('max_price_eur', 200):
            return None, 'PRICE_TOO_HIGH_OR_INVALID'
    return dict(title=title, published=published, kind='queue' if is_queue else 'product',
                price=price, target=targets[0] if targets else None), None


def payload(event, url, source_name='MyDealz'):
    title = re.sub(r'[@*_`<>\[\]\\]', '', event['title'])[:230]
    reported = datetime.fromtimestamp(event['published'], timezone.utc).isoformat()
    description = ('**' + title + '**\n🇩🇪 Pokémon Center Deutschland laut Originalbeitrag\n'
                   + ('🚦 Community meldet eine offene Warteschlange.' if event['kind'] == 'queue' else '📦 Community meldet ein Angebot / eine Vorbestellung.')
                   + (f"\n💶 Im Beitrag genannt: {event['price']:.2f} € (Versand siehe Quelle)." if event.get('price') else '')
                   + '\n\n**Community-Hinweis – vom Bot nicht live bestätigt.**\n'
                     'Bestand, Checkout, Produktsprache und Preis können inzwischen abweichen. '
                     'Keine UVP-/Dealbewertung.'
                   + (f"\n[Deutscher Shoplink]({event['target']})" if event.get('target') else ''))
    return {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': '📣 COMMUNITY · POKÉMON CENTER DE', 'url': url, 'color': 0x3498DB,
        'description': description, 'timestamp': reported,
        'footer': {'text': 'Quelle: '+source_name+' · Zeit = Veröffentlichung des Originalbeitrags'}}]}


def run(cfg, state, client, now, send=None, checkpoint=None):
    settings = cfg.get('community_watch', {})
    result = dict(sources=[], rejected={}, alerts=[], sent=0, errors=[])
    if not settings.get('enabled'):
        return result
    table = state.setdefault('community_watch', {'sources': {}, 'delivered': {}})
    old_deadline = getattr(client, 'deadline', None)
    if old_deadline is not None:
        client.deadline = min(old_deadline, time.monotonic()+settings.get('budget_seconds', 20))
    candidates = {}
    try:
        def fetch(source, transport):
            body = transport.text(source['url'])
            if source['kind'] == 'telegram':
                return telegram_sources.parse(body, source['channel']), []
            return (rss(body) if source['kind'] == 'rss' else radar(body, now)), []
        due = [dict(id=source_id, url=url, base_url=url, kind=kind, adapter='community')
               for source_id, url, kind in SOURCES
               if now-table['sources'].get(source_id, {}).get('checked_at', 0) >= settings.get('interval_seconds', 240)]
        for channel in settings.get('telegram_channels', []):
            if not telegram_sources.valid_channel(channel):
                result['errors'].append('Invalid Telegram channel configuration')
                continue
            source_id = 'telegram:'+channel.lower()
            url = 'https://t.me/s/'+channel
            if now-table['sources'].get(source_id, {}).get('checked_at', 0) >= settings.get('interval_seconds', 240):
                due.append(dict(id=source_id, url=url, base_url=url, kind='telegram',
                                channel=channel, adapter='community'))
        # Separate hosts have separate bounded transports; a timeout at MyDealz
        # cannot stop the Radar fetch. Reserve half the budget for original pages.
        for source, rows, _, error, _ in collect(due, client, {'community':fetch}, workers=2,
                                                source_seconds=settings.get('budget_seconds', 20)/2):
            source_id = source['id']
            if error:
                result['sources'].append(dict(id=source_id, status='unavailable', error=error))
                continue
            result['sources'].append(dict(id=source_id, status='ok', items=len(rows)))
            table['sources'][source_id] = dict(checked_at=now, status='ok')
            for row in rows:
                is_telegram = source['kind'] == 'telegram'
                target = row['url'] if is_telegram else article_url(row['url'])
                if not target or not CENTER.search(row['title']):
                    continue
                published = row['published']
                if published is None or not 0 <= now-published <= settings.get('max_age_seconds', 1800):
                    result['rejected']['STALE_OR_UNDATED'] = result['rejected'].get('STALE_OR_UNDATED', 0)+1
                    continue
                key = 'telegram:'+target.split('t.me/', 1)[1].lower() if is_telegram else 'mydealz:'+target.rsplit('-', 1)[-1]
                if is_telegram:
                    # A Telegram mirror linking MyDealz shares its original ID
                    # and must pass original-article validation, including age.
                    origin = next((article_url(u) for u in row['links'] if article_url(u)), None)
                    if origin:
                        target = origin
                        key = 'mydealz:'+origin.rsplit('-', 1)[-1]
                        row = {k:v for k,v in row.items() if k not in ('object', 'source_name')}
                candidates.setdefault(key, row | {'url': target})
        attempted = 0
        for key, row in sorted(candidates.items(), key=lambda pair: pair[1]['published'], reverse=True):
            if key in table['delivered']:
                result['rejected']['DUPLICATE'] = result['rejected'].get('DUPLICATE', 0)+1
                continue
            if attempted >= settings.get('max_article_checks', 5) or len(result['alerts']) >= settings.get('max_alerts_per_run', 3):
                break
            attempted += 1
            try:
                obj = row.get('object') or original(client.text(row['url']), row['url'])
                if row.get('object') and not telegram_sources.current_claim(row['title']):
                    event, reason = None, 'NOT_CURRENT_REPORT'
                else:
                    event, reason = qualify(obj, now, settings)
            except Exception as exc:
                result['errors'].append('Community article: '+type(exc).__name__)
                continue
            if reason:
                result['rejected'][reason] = result['rejected'].get(reason, 0)+1
                continue
            message = payload(event, row['url'], row.get('source_name', 'MyDealz'))
            result['alerts'].append(dict(key=key, reason='community_report_de', payload=message))
            if send:
                try:
                    message_id = send(message)
                except Exception as exc:
                    result['errors'].append('Community Discord: '+type(exc).__name__)
                    break
                table['delivered'][key] = dict(at=now, published=event['published'], message_id=message_id)
                result['sent'] += 1
                if checkpoint:
                    checkpoint(state)
        table['delivered'] = {k:v for k,v in table['delivered'].items() if now-v['at'] <= 30*86400}
    finally:
        if old_deadline is not None:
            client.deadline = old_deadline
    return result
