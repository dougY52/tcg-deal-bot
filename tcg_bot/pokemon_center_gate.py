"""Shared public queue trigger; only first-party DE confirmation may alert."""
from datetime import datetime, timezone
import base64
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urljoin

from .http import FetchError
from .pokemon_center_access import FreeAccessProbe, free_usage
from .pokemon_center_queue import HOMES, classify_documents, public_queue_url, snapshot, visible_tree
from .web_sources import Document
from .pc_schedule import due

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


def provider_snapshot(data, now, *, require_rendered=False):
    """Reuse the official-frame parser; never retain cookies/XHR/query metadata."""
    if not isinstance(data, dict) or data.get('status_code') != 200:
        raise FetchError('PC_PROVIDER_TARGET_NOT_HTTP_200')
    body = data.get('html')
    if not isinstance(body, str) or len(body.encode('utf-8')) > 8_000_000:
        raise FetchError('PC_PROVIDER_HTML_MISSING')
    doc = Document(body)
    markers = [n for n in doc.root.walk() if n.tag == 'script' and n.attrs.get('id') == 'tcg-queue-visible-v1']
    rendered = None
    if markers:
        try:
            if len(markers) != 1 or len(markers[0].text()) > 1_000_000:
                raise ValueError()
            capture = json.loads(markers[0].text())
            if (capture.get('version') != 1 or capture.get('home_path') not in HOMES or
                    capture.get('primary_frames') not in (0, 1)):
                raise ValueError()
            documents = capture['documents']
            if not isinstance(documents, list) or len(documents) != 1+capture['primary_frames']:
                raise ValueError()
            rendered = {d['kind']: d['html'] for d in documents}
            if (set(rendered) != ({'home', 'primary_frame'} if capture['primary_frames'] else {'home'}) or
                    any(not isinstance(v, str) or len(v) > 700000 for v in rendered.values())):
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise FetchError('PC_PROVIDER_VISIBLE_CAPTURE_INCOMPLETE') from None
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
    result = (classify_documents(rendered['home'], rendered.get('primary_frame'), now)
              if rendered is not None else snapshot(Pages(), HOME, now))
    result['rendered_visibility'] = rendered is not None
    if require_rendered and rendered is None:
        # Raw HTML can contain CSS-hidden announcements for other regions.
        if result['status'] == 'queue_open_de':
            result.update(status='queue_open_region_unknown', region=None, banner=None, banner_location=None)
        result['reason'] = 'PC_PROVIDER_VISIBLE_CAPTURE_MISSING'
    # Public page diagnostics only. Never export cookies, XHRs or frame URLs.
    doc = Document(body)
    result['page_bytes'] = len(body.encode('utf-8'))
    result['headings'] = [re.sub(r'https?://\S+', '[URL]', n.text()).strip()[:160]
                          for n in visible_tree(doc.root) if n.tag in ('title', 'h1')][:3]
    result['embedded_frames'] = len(frames)
    result['next_data_present'] = 'id="__NEXT_DATA__"' in body
    return result


class QueueProbe(FreeAccessProbe):
    def check(self, now):
        self.policy_client.check_allowed(HOME)
        usage, _ = self.request_json('usage')
        remaining = free_usage(usage, CREDIT_COST + 1000)['remaining_credits']
        if self.reserved + CREDIT_COST > self.max_credits:
            raise FetchError('PC_PROVIDER_TEST_BUDGET_EXHAUSTED')
        self.reserved += CREDIT_COST
        # A real queue/security page may have no `main`; do not wait for one.
        data, cost = self.request_json('extended', {
            'url': HOME, 'proxy_type': 'residential', 'proxy_country': 'DE',
            'browser': 'true', 'timeout': 25,
            'js_snippet': base64.b64encode(Path(__file__).with_name('pc_queue_dom.js').read_bytes()).decode(),
        })
        if cost is not None and (not math.isfinite(cost) or not 0 <= cost <= CREDIT_COST):
            raise FetchError('PC_PROVIDER_COST_CHANGED_STOPPED')
        observed_at = time.time()
        return {**provider_snapshot(data, observed_at, require_rendered=True), 'observed_at': observed_at,
                'reserved_credits': CREDIT_COST,
                'reported_credits': cost, 'remaining_before': remaining}


def run_gate(cfg, state, client, now, probe=None, checkpoint=None, interval=240, minute_slots=False):
    """Persistent trigger, free-credit budget and fresh official evidence handoff.

    Reserve before requests, including errors. Only two distinct fresh `open`
    samples end an episode. `opening`, `gated`, missing/stale data never alert.
    """
    if not cfg.get('enabled'):
        return {'status': 'disabled'}, None
    gate = state.setdefault('pc_queue_gate', {})
    report = {'status': 'not_due', 'germany_confirmed': False, 'credits_reserved_this_run': 0}
    confirmed = gate.get('confirmation')
    if not due(gate.get('checked_at', 0), now, interval, minute_slots):
        fresh = confirmed and 0 <= now-confirmed.get('observed_at', 0) <= 120
        return report, confirmed if fresh and not gate.get('acknowledged') else None
    if now < gate.get('signal_retry_at', 0):
        report['status'] = 'public_signal_backoff'
        return report, None
    gate['checked_at'] = now
    try:
        signal = public_signal(json.loads(client.text(STATUS_URL)), now)
    except Exception:
        signal = {'state': 'unknown', 'trigger': False, 'reason': 'PUBLIC_SIGNAL_UNAVAILABLE'}
        gate['signal_retry_at'] = max(now+60, getattr(client, 'cooldowns', {}).get('stock-watch.co.uk', 0))
    report['signal'] = signal
    last = gate.get('signal_checked_at', 0)
    checked = signal.get('checked_at', 0)
    if signal['state'] == 'open' and checked > last:
        gate['clear_count'] = gate.get('clear_count', 0)+1
        if gate['clear_count'] >= 2:
            gate['active'] = False
            gate.pop('confirmation', None)
    elif signal['state'] != 'open':
        gate['clear_count'] = 0
    gate['signal_checked_at'] = max(last, checked)
    if not signal['trigger']:
        report['status'] = 'no_live_trigger'
        return report, None
    if not gate.get('active'):
        gate.update(active=True, wave=gate.get('wave', 0)+1, wave_started_at=now,
                    attempts=0, retry_at=0, acknowledged=False)
        gate.pop('confirmation', None)
    if gate.get('acknowledged'):
        report['status'] = 'already_confirmed_and_delivered'
        return report, None
    confirmed = gate.get('confirmation')
    if confirmed and 0 <= now-confirmed.get('observed_at', 0) <= 120:
        report.update(status='fresh_confirmation', germany_confirmed=True)
        return report, confirmed
    if probe is None:
        report['status'] = 'confirmation_not_enabled'
        return report, None
    if gate.get('provider_halted'):
        report['status'] = 'provider_halted'
        return report, None
    if now < gate.get('retry_at', 0):
        report['status'] = 'confirmation_backoff'
        return report, None
    attempts = [t for t in gate.get('reservations', []) if now-30*86400 < t <= now]
    gate['reservations'] = attempts
    day = datetime.fromtimestamp(now, timezone.utc).date()
    today = sum(datetime.fromtimestamp(t, timezone.utc).date() == day for t in attempts)
    max_30d = min(6000, max(0, int(cfg.get('max_credits_30d', 6000))))
    max_daily = min(750, max(0, int(cfg.get('max_credits_daily', 750))))
    if (gate.get('attempts', 0) >= min(3, cfg.get('max_attempts_per_wave', 3)) or
            (len(attempts)+1)*CREDIT_COST > max_30d or (today+1)*CREDIT_COST > max_daily):
        report['status'] = 'confirmation_budget_exhausted'
        return report, None
    gate['reservations'].append(now)
    gate['attempts'] = gate.get('attempts', 0)+1
    gate['retry_at'] = now+(120 if gate['attempts'] == 1 else 300)
    if checkpoint:
        checkpoint(state)
    report['credits_reserved_this_run'] = CREDIT_COST
    try:
        result = probe(now)
    except Exception as error:
        code = str(error) if isinstance(error, FetchError) else ''
        code = code if re.fullmatch(r'PC_PROVIDER_[A-Z_0-9]+', code) else 'PC_PROVIDER_UNAVAILABLE'
        report.update(status='confirmation_unavailable', reason=code)
        if code == 'PC_PROVIDER_COST_CHANGED_STOPPED':
            gate['provider_halted'] = True
        return report, None
    report['confirmation'] = {k: result[k] for k in
        ('status', 'frame_checked', 'page_bytes', 'headings', 'reported_credits', 'remaining_before',
         'rendered_visibility', 'banner_location', 'reason') if k in result}
    if result.get('status') != 'queue_open_de' or result.get('region') != 'DE' or not result.get('banner'):
        report['status'] = 'germany_not_confirmed'
        return report, None
    observation = {k: result[k] for k in ('status', 'region', 'banner', 'frame_checked', 'inventory_confirmed')}
    observation.update(observed_at=result.get('observed_at', now), gate_wave=gate['wave'], wave_started_at=gate['wave_started_at'])
    gate['confirmation'] = observation
    report.update(status='germany_confirmed', germany_confirmed=True)
    return report, observation


def acknowledge(state):
    """Acknowledge only an actual existing-watcher Discord receipt for this wave."""
    gate = state.get('pc_queue_gate', {})
    if not gate.get('confirmation'):
        return
    gate['acknowledged'] = any(r.get('source') == 'pc-de-store' and
        r.get('at', 0) >= gate.get('wave_started_at', float('inf'))
        for r in state.get('pc_de', {}).get('delivered', {}).values())
