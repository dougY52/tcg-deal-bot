"""Public directory discovery only. New domains require evidence before activation."""
import re
import time
from urllib.parse import urlsplit


def discover(cfg, state, client, now):
    result = {'new_shops': 0, 'errors': [], 'cardmarket': 'not_due'}
    if now - state.get('retailer_discovery_at', 0) < 10800:
        return result
    state['retailer_discovery_at'] = now
    deadline = getattr(client, 'deadline', None)
    if deadline is not None:
        client.deadline = time.monotonic()+20
    try:
        from .web_sources import Document
        index = client.text('https://cardwatch.eu/de/stores/germany')
        slugs = list(dict.fromkeys(re.findall(r'href="/de/stores/([a-z0-9-]+)"', index)))
        visited = state.setdefault('retailer_directory_checked', {})
        queue = state.setdefault('retailer_candidates', {})
        known = {urlsplit(s['base_url']).hostname for s in cfg['shops']}
        for slug in sorted(slugs, key=lambda s: visited.get(s, 0))[:4]:
            url = 'https://cardwatch.eu/de/stores/'+slug
            visited[slug] = now
            page = Document(client.text(url))
            for node in page.root.walk():
                if node.tag != 'a' or 'besuchen' not in node.text().lower():
                    continue
                target = urlsplit(node.attrs.get('href', ''))
                if target.scheme != 'https' or not target.hostname or target.hostname in known or target.hostname.endswith('cardwatch.eu'):
                    continue
                if target.hostname not in queue:
                    result['new_shops'] += 1
                # Never crawl or trust an arbitrary new host solely on directory evidence.
                queue[target.hostname] = {'url': 'https://'+target.hostname, 'discovered_at': now,
                                          'source': url, 'status': 'needs_legal_payment_reputation_check'}
    except Exception as exc:
        result['errors'].append('directory: '+type(exc).__name__)
    finally:
        if deadline is not None:
            client.deadline = time.monotonic()+10
    try:
        client.text('https://www.cardmarket.com/de/DragonBallSuper/Products/Booster-Boxes')
        result['cardmarket'] = 'page_received_seller_variant_validation_not_supported'
    except Exception as exc:
        result['cardmarket'] = 'unavailable_'+type(exc).__name__
    finally:
        if deadline is not None:
            client.deadline = deadline
    state['retailer_discovery_report'] = result
    return result
