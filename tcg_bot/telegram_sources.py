"""Read public Telegram previews without an account, token or private-channel access."""
from datetime import datetime
from html import escape
import re

from .web_sources import Document
from .drop_watch import visible, visible_nodes


def valid_channel(channel):
    return isinstance(channel, str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', channel))


def parse(body, channel):
    if not valid_channel(channel):
        raise ValueError('Invalid public Telegram channel')
    rows = []
    found = False
    for node in Document(body).root.walk():
        post = node.attrs.get('data-post', '')
        if not re.fullmatch(re.escape(channel) + r'/\d+', post, re.I):
            continue
        found = True
        nodes = list(visible_nodes(node))
        # Reposted messages must not acquire a fresh original publication time.
        if any('tgme_widget_message_forwarded_from' in n.attrs.get('class', '').split() for n in nodes):
            continue
        message = next((n for n in nodes if 'tgme_widget_message_text' in n.attrs.get('class', '').split()), None)
        date = next((n for n in nodes if n.tag == 'a' and 'tgme_widget_message_date' in n.attrs.get('class', '').split()), None)
        if message is None or date is None or date.attrs.get('href') != 'https://t.me/'+post:
            continue
        # Quotes and previews are not the channel author's own claim.
        if any(n.tag == 'blockquote' for n in message.walk()):
            continue
        at = next((n.attrs.get('datetime', '') for n in date.walk() if n.tag == 'time'), '')
        try:
            timestamp = datetime.fromisoformat(at.replace('Z', '+00:00'))
            published = timestamp.timestamp() if timestamp.tzinfo else None
        except (ValueError, OverflowError):
            published = None
        text = re.sub(r'\s+', ' ', visible(message)).strip()
        links = [n.attrs.get('href', '') for n in visible_nodes(message) if n.tag == 'a']
        # Normalize to the community validator's input; do not include previews,
        # sidebars, other messages, view counts or edited-at timestamps.
        obj = dict(title=text, descriptionPurified=escape(text)+' '.join(
            '<a href="'+escape(link, quote=True)+'">Link</a>' for link in links),
            publishedAt=published, isExpired=False, status='Activated', deletedAt=None, price=None)
        prices = re.findall(r'(?<![\d.,])(\d+(?:[.,]\d{3})*[.,]\d{2}|\d+)\s*(?:€|EUR\b)', text, re.I)
        if prices:
            def amount(value):
                return float(value.replace('.', '').replace(',', '.')) if ',' in value else float(value)
            obj['price'] = max(amount(p) for p in prices)
        rows.append(dict(url='https://t.me/'+post, title=text, published=published,
                         body='', object=obj, links=links, source_name='Telegram · '+channel))
    if not found:
        raise ValueError('Telegram public message preview unavailable')
    return rows


def current_claim(text):
    """News, speculation and reseller mentions alone are not drop reports."""
    return bool(re.search(r'verfügbar|lieferbar|vorrätig|erhältlich|bestellbar|vorbestellen|restock|auf lager|\blive\b|\boffen\b|geöffnet|add to cart', text, re.I)) and not re.search(
        r'\bmorgen\b|\bbald\b|\bsoon\b|angekündigt|voraussichtlich|vermutlich|\bkein(?:e|en)?\b|\bnicht\b|ausverkauft|sold out|geschlossen|waitlist|notify me|coming soon|benachrichtigen|\bwar(?:en)?\b|\bgestern\b', text, re.I)
