"""Shared public queue trigger; only first-party DE confirmation may alert."""
from datetime import datetime
import math
from urllib.parse import urljoin

from .http import FetchError
from .pokemon_center_access import FreeAccessProbe, free_usage
from .pokemon_center_queue import public_queue_url, snapshot, visible_tree
from .web_sources import Document

STATUS_URL = 'https://stock-watch.co.uk/api/pokemon-queue/status'
HOME = 'https://www.pokemoncenter.com/de-de/'
CREDIT_COST = 125


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d.timestamp() if d.tzinfo else None
    except (ValueError, OverflowError):
        return None


def public_signal(data, now):
    """StockWatch `open` means shop accessible, not an active queue."""
    unknown = {'state': 'unknown', 'trigger': False, 'germany_confirmed': False}
    if not isinstance(data, dict) or data.get('success') is not True:
        return {**unknown, 'reason': 'INVALID_PUBLIC_SIGNAL'}
    value = data.get('data')
    if not isinstance(value, dict):
        return {**unknown, 'reason': 'INVALID_PUBLIC_SIGNAL'}
    checked = timestamp(value.get('lastChecked'))
    age_ms = value.get('ageMs')
    if (checked is None or not -30 <= now-checked <= 120 or
            type(age_ms) not in (int, float) or not math.isfinite(age_ms) or not 0 <= age_ms <= 120000):
        return {**unknown, 'reason': 'STALE_PUBLIC_SIGNAL'}
    state = value.get('state')
    if state not in ('open', 'live', 'opening', 'gated'):
        return {**unknown, 'reason': 'UNKNOWN_PUBLIC_STATE'}
    return {'state': state, 'trigger': state == 'live', 'germany_confirmed': False,
            'checked_at': checked, 'age_seconds': round(max(0, now-checked), 2)}


def provider_snapshot(data, now):
    """Reuse the official-frame parser; never retain cookies/XHR/query metadata."""
    if not isinstance(data, dict) or data.get('status_code') != 200:
        raise FetchError('PC_PROVIDER_TARGET_NOT_HTTP_200')
    body = data.get('html')
    if not isinstance(body, str) or len(body.encode('utf-8')) > 8_000_000:
        raise FetchError('PC_PROVIDER_HTML_MISSING')
    pages = {HOME: body}
    frames = [n for n in visible_tree(Document(body).root)
              if n.tag == 'iframe' and n.attrs.get('id') == 'main-iframe']
    if len(frames) == 1:
        expected = urljoin(HOME, frames[0].attrs.get('src', ''))
        if public_queue_url(expected):
            matches = [f for f in data.get('iframes', []) if isinstance(f, dict)
                       and urljoin(HOME, str(f.get('src', ''))) == expected
                       and isinstance(f.get('html'), str)]
            if len(matches) == 1 and len(matches[0]['html'].encode('utf-8')) <= 8_000_000:
                pages[expected] = matches[0]['html']
    class Pages:
        def text(self, url):
            if url not in pages:
                raise FetchError('PC_PROVIDER_FRAME_UNREADABLE')
            return pages[url]
    return snapshot(Pages(), HOME, now)


class QueueProbe(FreeAccessProbe):
    def check(self, now):
        self.policy_client.check_allowed(HOME)
        usage, _ = self.request_json('usage')
        remaining = free_usage(usage, CREDIT_COST)['remaining_credits']
        if self.reserved + CREDIT_COST > self.max_credits:
            raise FetchError('PC_PROVIDER_TEST_BUDGET_EXHAUSTED')
        self.reserved += CREDIT_COST
        # A real queue/security page may have no `main`; do not wait for one.
        data, cost = self.request_json('extended', {
            'url': HOME, 'proxy_type': 'residential', 'proxy_country': 'DE',
            'browser': 'true', 'timeout': 25,
        })
        if cost is not None and (not math.isfinite(cost) or not 0 <= cost <= CREDIT_COST):
            raise FetchError('PC_PROVIDER_COST_CHANGED_STOPPED')
        return {**provider_snapshot(data, now), 'reserved_credits': CREDIT_COST,
                'reported_credits': cost, 'remaining_before': remaining}
