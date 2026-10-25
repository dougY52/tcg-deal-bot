"""Optional authenticated free Worker transport; existing validators remain authoritative."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from .http import FetchError, NoRedirect


def target_allowed(url):
    p = urllib.parse.urlsplit(url)
    return (p.scheme == 'https' and p.netloc in ('www.mediamarkt.de', 'www.saturn.de')
            and not p.query and not p.fragment and '%' not in p.path and '..' not in p.path
            and (p.path == '/robots.txt' or bool(re.fullmatch(
                r'/de/(product|category|brand)/[a-zA-Z0-9_/-]+(?:\.html)?', p.path))))


def settings():
    endpoint = os.environ.get('TCG_CLOUD_READER_URL', '').strip()
    token = os.environ.get('TCG_CLOUD_READER_TOKEN', '')
    if not endpoint and not token:
        return None
    p = urllib.parse.urlsplit(endpoint)
    if (p.scheme != 'https' or not re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev', p.netloc)
            or p.path != '/read' or p.query or p.fragment or len(token) < 32
            or '\r' in token or '\n' in token):
        raise FetchError('Cloud reader configuration invalid')
    return endpoint, token


def enabled_for(url):
    # Do not let optional configuration affect other retailers.
    return target_allowed(url) and settings() is not None


def read(url, timeout):
    config = settings()
    if not target_allowed(url) or config is None:
        raise FetchError('Unsupported cloud reader target')
    endpoint, token = config
    request = urllib.request.Request(endpoint + '?' + urllib.parse.urlencode({'url': url}),
        headers={'Authorization': 'Bearer ' + token, 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise FetchError('Cloud reader transport unavailable')
            raw = response.read(24_000_001)
            if len(raw) > 24_000_000:
                raise FetchError('Cloud reader response too large')
            data = json.loads(raw)
        stamp = data.get('fetched_at')
        if (data.get('url') != url or type(stamp) not in (int, float)
                or not -5 <= time.time() - stamp <= 60):
            raise FetchError('Cloud reader stale or mismatched response')
        status = data.get('status')
        if type(status) is not int or not 100 <= status <= 599:
            raise FetchError('Cloud reader invalid status')
        if status != 200:
            # Existing Client handles 429/503 backoff and robots 404.
            raise urllib.error.HTTPError(url, status, 'Upstream unavailable', {}, None)
        body = data.get('body')
        if not isinstance(body, str) or len(body.encode('utf-8')) > 12_000_000:
            raise FetchError('Cloud reader invalid body')
        return body
    except urllib.error.HTTPError as exc:
        if exc.url == url:
            raise
        raise FetchError('Cloud reader transport HTTP ' + str(exc.code)) from None
    except (ValueError, TypeError, AttributeError, urllib.error.URLError, TimeoutError):
        raise FetchError('Cloud reader response unavailable or invalid') from None
