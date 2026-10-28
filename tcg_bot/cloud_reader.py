"""Optional authenticated free Worker transport; existing validators remain authoritative."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from .http import FetchError, NoRedirect, UA


def target_allowed(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.fragment or '%' in p.path or '..' in p.path:return False
    if p.netloc in ('www.mediamarkt.de','www.saturn.de'):
        return not p.query and (p.path=='/robots.txt' or bool(re.fullmatch(r'/de/(product|category|brand)/[a-zA-Z0-9_/-]+(?:\.html)?',p.path)))
    if p.netloc == 'www.pokemoncenter.com':
        return not p.query and (p.path == '/robots.txt' or bool(re.fullmatch(
            r'/(?:de-de|en-de)/?|/(?:de-de|en-de)/(?:product|category)/[a-zA-Z0-9_/-]+',p.path)))
    if p.netloc=='www.duo-shop.de':
        return not p.query and (p.path in ('/robots.txt','/produkte/spielzeug/sammelkarten/') or bool(re.fullmatch(r'/offers/[a-zA-Z0-9-]+/',p.path)))
    if p.netloc not in ('www.vedes.com','www.faix.de'):return False
    if p.path=='/robots.txt':return not p.query
    prefix='/faix-online-shop-darmstadt' if p.netloc=='www.faix.de' else ''
    if not p.path.startswith(prefix+'/'):return False
    path=p.path[len(prefix):];params=urllib.parse.parse_qsl(p.query,keep_blank_values=True);values=dict(params)
    subsidiary=len(params)==1 and params[0][0]=='subsidiary[__identity]' and bool(re.fullmatch(r'\d{9}',params[0][1]))
    if re.fullmatch(r'/(m|s|k)/[a-z0-9/-]+',path):return not p.query
    if re.fullmatch(r'/(p|status/json)/[a-z0-9-]+',path):return subsidiary
    if path=='/c/impressum' and p.netloc=='www.faix.de':return not p.query
    return (path=='/modals/showcontentpage' and len(params)==2 and
            bool(re.fullmatch(r'\d{9}',values.get('subsidiary[__identity]',''))) and
            bool(re.fullmatch(r'[a-f0-9-]{36}',values.get('contentPage[__identity]',''))))


def settings():
    endpoint = os.environ.get('TCG_CLOUD_READER_URL', '').strip()
    token = os.environ.get('TCG_CLOUD_READER_TOKEN', '')
    if not endpoint and not token:
        return None
    p = urllib.parse.urlsplit(endpoint)
    if (p.scheme != 'https' or not re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev', p.netloc)
            or p.path != '/read' or p.query or p.fragment or (token and len(token) < 32)
            or '\r' in token or '\n' in token):
        raise FetchError('Cloud reader configuration invalid')
    return endpoint, token


def enabled_for(url):
    # Do not let optional configuration affect other retailers.
    return target_allowed(url) and settings() is not None


def read(url, timeout, _retried=False):
    config = settings()
    if not target_allowed(url) or config is None:
        raise FetchError('Unsupported cloud reader target')
    endpoint, token = config
    started = time.monotonic()
    if not token:
        token = github_token(urllib.parse.urlsplit(endpoint)._replace(path='').geturl(), timeout)
    timeout -= time.monotonic() - started
    if timeout <= 0:
        raise FetchError('Run request budget exhausted')
    request = urllib.request.Request(endpoint + '?' + urllib.parse.urlencode({'url': url}),
        headers={'Authorization': 'Bearer ' + token, 'Cache-Control': 'no-cache', 'User-Agent': UA})
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
        reason = exc.headers.get('X-TCG-Auth-Error','') if exc.headers else ''
        reason = (' (' + reason + ')') if re.fullmatch(r'[A-Z_]{1,30}',reason) else ''
        marker = exc.headers.get('X-TCG-Reader','') if exc.headers else ''
        detail = ''
        if exc.code in (502, 503, 504):
            body = exc.read(4096).decode('utf-8', errors='replace') if exc.fp else ''
            if 'Reader not configured' in body:
                detail = ' READER_NOT_CONFIGURED'
            elif re.search(r'error(?: code)?\s*:?\s*1102', body, re.I):
                detail = ' WORKER_RESOURCE_LIMIT'
            else:
                detail = ' WORKER_TRANSPORT_FAILURE' if not marker else ' READER_UPSTREAM_FAILURE'
            # A transient gateway failure is distinct from retailer rate limits
            # (raised above with the retailer URL), bad auth, or exhausted quota.
            left = timeout - (time.monotonic()-started)
            retry_after = exc.headers.get('Retry-After','') if exc.headers else ''
            if (detail == ' WORKER_TRANSPORT_FAILURE' and not _retried and
                    left > 3 and retry_after in ('','0','1')):
                time.sleep(1)
                return read(url,left-1,_retried=True)
        raise FetchError('Cloud reader transport HTTP ' + str(exc.code) + reason + detail) from None
    except (ValueError, TypeError, AttributeError, urllib.error.URLError, TimeoutError):
        raise FetchError('Cloud reader response unavailable or invalid') from None


_token_cache = None


def github_token(audience, timeout):
    """Request a short-lived job identity; never persist or log either token."""
    global _token_cache
    request_url = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL', '')
    credential = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN', '')
    p = urllib.parse.urlsplit(request_url)
    if (p.scheme != 'https' or not p.hostname or not p.hostname.endswith('.actions.githubusercontent.com')
            or p.username or p.password or p.port or p.fragment or not credential):
        raise FetchError('Cloud reader requires GitHub job identity or shared token')
    cache_key = (audience, request_url)
    if _token_cache and _token_cache[0] == cache_key and _token_cache[1] > time.time():
        return _token_cache[2]
    query = urllib.parse.parse_qsl(p.query)
    query = [(k,v) for k,v in query if k != 'audience'] + [('audience', audience)]
    url = urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode(query)))
    req = urllib.request.Request(url, headers={'Authorization':'Bearer '+credential,'User-Agent':UA})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=min(10,timeout)) as response:
            raw = response.read(100001)
            if len(raw)>100000: raise ValueError('Too large')
            token = json.loads(raw).get('value')
        if not isinstance(token,str) or len(token)>20000 or token.count('.') != 2:
            raise ValueError('Invalid token')
        _token_cache = (cache_key, time.time()+180, token)
        return token
    except (ValueError, TypeError, AttributeError, urllib.error.URLError, TimeoutError):
        raise FetchError('GitHub job identity unavailable') from None
