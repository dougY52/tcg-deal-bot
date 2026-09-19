"""Bounded requests; never print URLs containing credentials."""
from email.utils import parsedate_to_datetime
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.robotparser import RobotFileParser

UA = 'TCGRetailWatch/1.0'

class FetchError(RuntimeError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Client:
    def __init__(self, delay=1.0):
        self.delay = delay
        self.last = {}
        self.robots = {}
        self.host_delay = {}
        self.blocked = set()
        self.cooldowns = {}
        self.deadline = time.monotonic() + 600

    def raw(self, url):
        if time.monotonic() >= self.deadline:
            raise FetchError('Run request budget exhausted')
        host = urllib.parse.urlsplit(url).netloc
        if host in self.blocked or time.time() < self.cooldowns.get(host, 0):
            raise FetchError('Host backed off until next run')
        delay = max(self.delay, self.host_delay.get(host, 0))
        wait = max(0, delay - (time.monotonic() - self.last.get(host, 0)))
        if time.monotonic() + wait >= self.deadline:
            raise FetchError('Run request budget exhausted')
        time.sleep(wait)
        self.last[host] = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=max(1, min(25, self.deadline - time.monotonic()))) as response:
                if urllib.parse.urlsplit(response.url).hostname != urllib.parse.urlsplit(url).hostname:
                    raise FetchError('Unexpected redirect host')
                data = response.read(12_000_001)
                if len(data) > 12_000_000:
                    raise FetchError('Response too large')
                return data.decode('utf-8')
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                self.blocked.add(host)
                retry = exc.headers.get('Retry-After', '') if exc.headers else ''
                try:
                    until = time.time() + max(0, float(retry))
                except ValueError:
                    try:
                        until = parsedate_to_datetime(retry).timestamp()
                    except (ValueError, TypeError, OverflowError):
                        until = time.time() + 3600
                self.cooldowns[host] = max(time.time() + 60, until)
            raise FetchError(f'HTTP {exc.code}') from None
        except (urllib.error.URLError, TimeoutError, UnicodeError):
            raise FetchError('Network or encoding error') from None

    def check_allowed(self, url):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != 'https' or parts.username or parts.password:
            raise FetchError('Only public HTTPS sources allowed')
        origin = f'https://{parts.netloc}'
        if origin not in self.robots:
            try:
                body = self.raw(origin + '/robots.txt')
            except FetchError as exc:
                if str(exc) != 'HTTP 404':
                    raise
                body = 'User-agent: *\nAllow: /'
            # Match robots wildcards and end anchors as used by Shopify.
            self.robots[origin] = body
            parser = RobotFileParser()
            parser.parse(body.splitlines())
            crawl = parser.crawl_delay(UA) or 0
            rate = parser.request_rate(UA)
            if rate and rate.requests:
                crawl = max(crawl, rate.seconds / rate.requests)
            for value in re.findall(r'^Crawl-delay:\s*([0-9.]+)', body, re.I | re.M):
                try:
                    crawl = max(crawl, float(value))
                except ValueError:
                    pass
            if crawl > 60:
                self.blocked.add(parts.netloc)
                raise FetchError('Required crawl delay exceeds run budget')
            self.host_delay[parts.netloc] = crawl
        if not robots_allowed(self.robots[origin], url):
            raise FetchError('robots.txt disallows this endpoint')

    def text(self, url):
        self.check_allowed(url)
        return self.raw(url)

    def close(self):
        pass

    def get(self, url):
        return json.loads(self.text(url))


def robots_allowed(body, url):
    # RobotFileParser handles group selection; expand wildcards for each selected rule.
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    entry = next((e for e in parser.entries if e.applies_to(UA)), parser.default_entry)
    if entry is None:
        return not parser.disallow_all
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    query = urllib.parse.urlsplit(url).query
    if query:
        path += '?' + urllib.parse.unquote(query)
    matches = []
    for rule in entry.rulelines:
        pattern = urllib.parse.unquote(rule.path)
        regex = re.escape(pattern).replace(r'\*', '.*')
        if pattern.endswith('$'):
            regex = regex[:-2] + '$'
        if re.match('^' + regex, path):
            matches.append((len(pattern.replace('*', '').rstrip('$')), rule.allowance))
    return max(matches)[1] if matches else True


def webhook_url(value):
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'https' or p.netloc != 'discord.com' or
            not re.fullmatch(r'/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9_-]+', p.path)
            or p.fragment or p.query):
        raise ValueError('DISCORD_WEBHOOK_URL fehlt oder ist keine gültige Discord-Webhook-URL.')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, 'wait=true', ''))


def send_discord(secret, payload):
    url = webhook_url(secret)
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(3):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST',
                                     headers={'Content-Type': 'application/json', 'User-Agent': UA})
        try:
            with opener.open(req, timeout=25) as response:
                result = json.load(response)
                if not result.get('id'):
                    raise FetchError('Discord did not confirm message')
                return str(result['id'])
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                try:
                    delay = float(json.load(exc).get('retry_after', 1))
                except (ValueError, TypeError):
                    raise FetchError('Discord invalid rate-limit response') from None
                if not 0 <= delay <= 60:
                    raise FetchError('Discord rate limit too long') from None
                time.sleep(delay + 0.25)
                continue
            raise FetchError(f'Discord HTTP {exc.code}') from None
        except (urllib.error.URLError, TimeoutError, ValueError):
            # No immediate retry: server may have accepted the message already.
            raise FetchError('Discord response uncertain; no automatic immediate retry') from None
    raise FetchError('Discord rate limit')
