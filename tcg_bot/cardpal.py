"""Read the owner's CardPal inbox without exposing credentials or unrelated alerts.

The transport follows CardPal's public web client. It is not an official external
API contract. A working stream proves transport only, not timely shop detection.
"""
from datetime import datetime, timezone
from hashlib import sha256
from http.cookiejar import CookieJar
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

ORIGIN = 'https://www.mycardpal.com'
PREFIX = 'broadcast:pokecenter-drop'
MAX_JSON = 1_000_000
DE = re.compile(r'\b(?:Deutschland|Germany)\b|Pok[eé]mon\s*Center\s+DE\b', re.I)
OTHER_REGION = re.compile(r'\b(?:UK|US|USA|United Kingdom|United States|Großbritannien)\b', re.I)
NEG_DE = re.compile(r'\b(?:not|nicht|kein\w*)\s+(?:(?:for|für|in)\s+)?(?:Deutschland|Germany|DE)\b', re.I)


class CardPalError(Exception):
    """A static safe code, never a response body, cookie, token or request URL."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CardPalError('REDIRECT_REJECTED')


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except ValueError:
        return None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def germany_url(value):
    """Return only a canonical public German shop link, without tracking tokens."""
    if not isinstance(value, str) or len(value) > 2000:
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.hostname != 'www.pokemoncenter.com'
                or u.username or u.password or u.port or '%' in u.path
                or not re.fullmatch(r'/(?:de-de|en-de)(?:/[A-Za-z0-9_/-]*)?', u.path)
                or '..' in u.path):
            return None
        return 'https://www.pokemoncenter.com'+u.path
    except ValueError:
        return None


def drop_record(row, observed_at):
    """Select PC broadcasts only; never export the rest of the private inbox."""
    if not isinstance(row, dict):
        return None
    key = row.get('dedupe_key')
    if not isinstance(key, str) or not re.match(re.escape(PREFIX)+r'(?:$|[:|_-])', key):
        return None
    title = row.get('article_name') or row.get('template')
    if not isinstance(title, str):
        title = ''
    link = germany_url(row.get('url'))
    if NEG_DE.search(title) or OTHER_REGION.search(title):
        region = 'ambiguous_or_other'
    elif link or DE.search(title):
        region = 'DE'
    else:
        region = 'unconfirmed'
    created = stamp(row.get('created_at'))
    # An old inbox entry's age is NOT delivery latency. Only a live observation
    # after a clean baseline can estimate publication -> receipt latency.
    return {
        'event_key': sha256(key.encode()).hexdigest()[:32],
        'region': region,
        'published_at': iso(created) if created is not None else None,
        'observed_at': iso(observed_at),
        'age_at_observation_seconds': round(observed_at-created, 3) if created is not None else None,
        'product_url': link,
        'shop_stock_confirmed': False,
        'shop_drop_to_cardpal_seconds': None,
    }


def read_sse(lines, max_bytes=262144, max_events=200):
    """Bounded SSE framing; ignore comments and never return raw token-bearing text."""
    event, data, size, emitted = 'message', [], 0, 0
    for raw in lines:
        size += len(raw)
        if size > max_bytes or len(raw) > 16384:
            raise CardPalError('STREAM_TOO_LARGE')
        try:
            line = raw.decode('utf-8').rstrip('\r\n')
        except (AttributeError, UnicodeDecodeError):
            raise CardPalError('STREAM_INVALID_ENCODING') from None
        if not line:
            if data:
                emitted += 1
                if emitted > max_events:
                    raise CardPalError('STREAM_TOO_MANY_EVENTS')
                try:
                    parsed = json.loads('\n'.join(data))
                except (ValueError, RecursionError):
                    raise CardPalError('STREAM_INVALID_JSON') from None
                yield event, parsed
            event, data = 'message', []
        elif line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].lstrip(' '))


class CardPalClient:
    def __init__(self, opener=None, clock=time.time, timeout=15):
        self.opener = opener or build_opener(NoRedirects(), HTTPCookieProcessor(CookieJar()))
        self.clock = clock
        self.timeout = timeout
        self.token = None

    def _open(self, path, data=None, stream=False):
        allowed = ('/auth/login', '/users/me', '/auth/stream-token')
        if not (path in allowed or re.fullmatch(r'/notifications/\?limit=50&offset=\d{1,4}', path)
                or (stream and path.startswith('/notifications/stream?token='))):
            raise CardPalError('UNSUPPORTED_ENDPOINT')
        headers = {'User-Agent': 'TCGDealWatch/1.0', 'Cache-Control': 'no-cache',
                   'Accept': 'text/event-stream' if stream else 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer '+self.token
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = Request(ORIGIN+'/api'+path, data=data, headers=headers)
        try:
            response = self.opener.open(req, timeout=self.timeout)
            if response.status != 200:
                response.close()
                raise CardPalError('UNEXPECTED_HTTP_STATUS')
            return response
        except HTTPError as e:
            code = e.code
            e.close()
            raise CardPalError('HTTP_'+str(code)) from None
        except (URLError, TimeoutError, OSError):
            raise CardPalError('NETWORK_UNAVAILABLE') from None

    def _json(self, path, data=None):
        with self._open(path, data) as response:
            if response.headers.get_content_type() != 'application/json':
                raise CardPalError('NOT_JSON')
            try:
                raw = response.read(MAX_JSON+1)
            except (TimeoutError, OSError):
                raise CardPalError('NETWORK_UNAVAILABLE') from None
        if len(raw) > MAX_JSON:
            raise CardPalError('RESPONSE_TOO_LARGE')
        try:
            value = json.loads(raw)
        except (ValueError, RecursionError):
            raise CardPalError('INVALID_JSON') from None
        if not isinstance(value, dict):
            raise CardPalError('INVALID_RESPONSE_SCHEMA')
        return value

    def login(self, email, password):
        if not email or not password:
            raise CardPalError('CREDENTIALS_REQUIRED')
        value = self._json('/auth/login', urlencode({'username': email, 'password': password}).encode())
        token = value.get('access_token')
        if not isinstance(token, str) or not 10 <= len(token) <= 20000 or re.search(r'\s', token):
            raise CardPalError('INVALID_ACCESS_TOKEN')
        self.token = token

    def settings(self):
        value = self._json('/users/me')
        return {k: value.get(k) for k in ('notification_enabled', 'allow_drop_notifications')
                if isinstance(value.get(k), bool)}

    def inbox(self, pages=5):
        rows, total = [], None
        for page in range(min(5, pages)):
            value = self._json('/notifications/?limit=50&offset='+str(page*50))
            items = value.get('items')
            if not isinstance(items, list) or len(items) > 50 or not all(isinstance(x, dict) for x in items):
                raise CardPalError('INVALID_INBOX_SCHEMA')
            rows.extend(items)
            n = value.get('total')
            if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                total = n
            if len(items) < 50 or (total is not None and len(rows) >= total):
                break
        return rows, total

    def probe_stream(self, baseline, seconds=30):
        value = self._json('/auth/stream-token')
        token = value.get('token')
        if not isinstance(token, str) or not 10 <= len(token) <= 20000:
            raise CardPalError('INVALID_STREAM_TOKEN')
        started = self.clock()
        result = {'connected': False, 'notification_events': 0, 'new_de_broadcasts': [],
                  'publication_to_receipt_seconds': [], 'shop_drop_to_cardpal_seconds': None}
        baseline_keys = {r['event_key'] for row in baseline if (r := drop_record(row, started))}
        old_timeout = self.timeout
        self.timeout = min(15, max(1, seconds))
        try:
            with self._open('/notifications/stream?'+urlencode({'token': token}), stream=True) as response:
                if response.headers.get_content_type() != 'text/event-stream':
                    raise CardPalError('NOT_EVENT_STREAM')
                result['connected'] = True

                def lines():
                    while self.clock()-started < seconds:
                        try:
                            line = response.readline(16385)
                        except (TimeoutError, OSError):
                            return
                        if not line:
                            return
                        yield line

                for event, value in read_sse(lines()):
                    if event != 'notification':
                        continue
                    if not isinstance(value, dict):
                        raise CardPalError('INVALID_EVENT_SCHEMA')
                    result['notification_events'] += 1
                    rows, _ = self.inbox()
                    received = self.clock()
                    for row in rows:
                        record = drop_record(row, received)
                        if not record or record['event_key'] in baseline_keys:
                            continue
                        baseline_keys.add(record['event_key'])
                        created = stamp(record['published_at'])
                        if record['region'] == 'DE' and created is not None and started <= created <= received:
                            result['new_de_broadcasts'].append(record)
                            result['publication_to_receipt_seconds'].append(round(received-created, 3))
                    if self.clock()-started >= seconds:
                        break
        finally:
            self.timeout = old_timeout
        result['observed_seconds'] = round(max(0, self.clock()-started), 2)
        return result


def audit(client, email, password, stream_seconds=30):
    report = {'status': 'not_checked', 'checked_at': iso(client.clock()),
              'discord_sent': 0, 'instant_shop_detection_verified': False}
    try:
        client.login(email, password)
        report['login'] = 'verified'
        report['settings'] = client.settings()
        rows, total = client.inbox()
        now = client.clock()
        records = [r for row in rows if (r := drop_record(row, now))]
        report.update(inbox_items_checked=len(rows), inbox_total=total,
                      pokemon_center_broadcasts=records,
                      de_broadcasts=sum(r['region'] == 'DE' for r in records))
        report['stream'] = client.probe_stream(rows, seconds=stream_seconds)
        report['status'] = 'transport_verified' if report['stream']['connected'] else 'stream_unverified'
        report['latency_verdict'] = ('publication_to_receipt_sample_only'
                                    if report['stream']['publication_to_receipt_seconds']
                                    else 'no_live_drop_sample')
    except CardPalError as e:
        report['status'] = 'requires_credentials' if e.args[0] == 'CREDENTIALS_REQUIRED' else 'failed'
        report['error'] = e.args[0]
    finally:
        client.token = None
    return report
