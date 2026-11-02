"""Read the public DE storefront and its observed waiting-room frame, once each.

No invented queue endpoint, session replay, CAPTCHA solving, or queue entry.
The shared queue needs an explicit German regional banner before an alert.
"""
import re
from urllib.parse import urljoin, urlsplit

from .drop_watch import inspect, visible
from .http import Client, FetchError
from .web_sources import Document

HOST = 'www.pokemoncenter.com'
HOMES = ('/de-de', '/de-de/', '/en-de', '/en-de/')
QUEUE = re.compile(r'warteschlange|warteraum|\bqueue\b|waiting room', re.I)
GERMANY = re.compile(r'\bGermany\b|\bDeutschland\b|\bGerman (?:store|site|shop)\b|\bdeutsche[nrms]? (?:Shop|Seite)\b', re.I)
NEGATIVE = re.compile(r'\b(?:not|no|nicht|kein\w*)\s+(?:(?:for|in|für)\s+)?(?:germany|german|deutsch\w*)', re.I)
NEGATED_CLAIM = re.compile(r'\b(?:not|no|never|none|nicht|kein\w*|keinerlei|cancelled|canceled|abgesagt)\b', re.I)
DROP = re.compile(r'launch|\bdrop\b|verkaufsstart|veröffentlich|veroeffentlich|erscheinen|\brelease\b', re.I)
PRODUCT = re.compile(r'\bTCG\b|sammelkart|products?|produkte?|merchandise', re.I)
CURRENT = re.compile(r'\btoday\b|\bheute\b|\bnow\b|\bjetzt\b', re.I)


def public_queue_url(url, *, home=False):
    try:
        p = urlsplit(url)
        return (p.scheme == 'https' and p.netloc == HOST and not p.fragment
                and (p.path in HOMES and not p.query if home else
                     p.path == '/_Incapsula_Resource' and bool(p.query) and len(p.query) <= 4096))
    except ValueError:
        return False


class QueueClient(Client):
    """Ordinary anonymous HTTP, fresh reads and no foreign-region redirects."""
    def raw(self, url, _redirects=0, _headers=None):
        p = urlsplit(url)
        if p.hostname == HOST:
            if not (public_queue_url(url, home=True) or public_queue_url(url)
                    or url == 'https://'+HOST+'/robots.txt'):
                raise FetchError('PC_QUEUE_UNSUPPORTED_REDIRECT')
            _headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
                        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.7'}
        return super().raw(url, _redirects, _headers)


def visible_tree(node):
    # Do not let hidden/ancestor footer/navigation content donate region proof.
    if node.tag in ('script', 'style', 'template', 'noscript', 'nav', 'footer', 'select'):
        return
    if 'hidden' in node.attrs or node.attrs.get('aria-hidden') == 'true' or re.search(
            r'display\s*:\s*none|visibility\s*:\s*hidden', node.attrs.get('style', ''), re.I):
        return
    yield node
    for child in node.children:
        if hasattr(child, 'tag'):
            yield from visible_tree(child)


def regional_banner(body):
    doc = Document(body)
    for n in doc.root.walk():
        if n.tag in ('nav', 'footer', 'select', 'script', 'style', 'template', 'noscript'):
            n.children = []
    for n in visible_tree(doc.root):
        if n.tag not in ('title', 'h1', 'h2', 'p', 'div', 'span', 'strong', 'section'):
            continue
        # Do not stitch a queue heading to an unrelated country-selector block.
        if any(getattr(c, 'tag', '') in ('p', 'div', 'section', 'h1', 'h2', 'h3') for c in n.children):
            continue
        text = re.sub(r'\s+', ' ', visible(n)).strip()
        if not 1 <= len(text) <= 650:
            continue
        # A separate country selector or footer is not the regional announcement.
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            if GERMANY.search(sentence) and not (NEGATIVE.search(sentence) or NEGATED_CLAIM.search(sentence)) and (
                    QUEUE.search(sentence) or DROP.search(sentence) and PRODUCT.search(sentence) and CURRENT.search(sentence)):
                return sentence
    return None


def classify(body, now, *, frame_checked=False):
    status, _ = inspect(body, {}, now)
    banner = regional_banner(body) if status == 'queue_open' else None
    if status == 'queue_open':
        state = 'queue_open_de' if banner else 'queue_open_region_unknown'
    elif status == 'blocked_or_unreadable':
        state = 'blocked'
    else:
        doc = Document(body)
        text = re.sub(r'\s+', ' ', visible(doc.root))
        # Errors, maintenance and empty HTTP 200 pages never close an episode.
        shop = (re.search(r'Pok[eé]mon Center', text, re.I) and
                re.search(r'willkommen|welcome|shop|sammelkart|trading.card', text, re.I) and
                not re.search(r'error|fehler|maintenance|wartungsarbeiten|unavailable|not found', text, re.I))
        state = 'store_readable' if shop else 'unknown'
    return dict(status=state, frame_checked=frame_checked, region='DE' if banner else None,
                banner=banner, inventory_confirmed=False)


def classify_documents(home, frame, now):
    result = classify(frame if frame is not None else home, now, frame_checked=frame is not None)
    location = 'primary_frame' if frame is not None else 'page'
    # Both documents are from the same live response. The actual waiting room
    # still has to be readable; a security frame plus an old banner cannot alert.
    if frame is not None and result['status'] == 'queue_open_region_unknown':
        outer_status, _ = inspect(home, {}, now)
        banner = regional_banner(home) if outer_status != 'blocked_or_unreadable' else None
        if banner:
            result.update(status='queue_open_de', region='DE', banner=banner)
            location = 'page_outside_primary_frame'
    result['banner_location'] = location if result['banner'] else None
    return result


def snapshot(client, url, now):
    if not public_queue_url(url, home=True):
        raise FetchError('PC_QUEUE_GERMAN_HOME_REQUIRED')
    body = client.text(url)
    # Follow only the primary frame actually embedded in this response. Never
    # persist/replay its challenge query, execute its scripts, or follow forms.
    frames = [n for n in visible_tree(Document(body).root)
              if n.tag == 'iframe' and n.attrs.get('id') == 'main-iframe']
    frame = None
    if len(frames) == 1:
        frame_url = urljoin(url, frames[0].attrs.get('src', ''))
        if public_queue_url(frame_url):
            frame = client.text(frame_url)
    return classify_documents(body, frame, now)
