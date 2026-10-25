"""Normal read-only Chromium pages; no proxy, stealth, login, or queue bypass."""
import time
from .browser_runtime import launch_browser
from urllib.parse import urlsplit
from .http import Client, FetchError

MMS_HOSTS = frozenset({'www.mediamarkt.de', 'www.saturn.de'})
HOSTS = MMS_HOSTS | {'www.mueller.de', 'www.pokemoncenter.com'}


def pokemon_queue_document(page, url, statuses, check_allowed):
    """Read an already loaded, visible same-origin queue frame; never solve it.

    An Incapsula iframe alone is NOT queue evidence: the same container is
    used for CAPTCHA/error pages. Only positive queue text may leave here.
    No additional navigation, guessed endpoint, cookies, or paid API calls.
    """
    from .drop_watch import inspect
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.netloc != 'www.pokemoncenter.com'
            or parts.path.rstrip('/') not in ('/de-de', '/en-de')):
        return None
    final = urlsplit(page.url)
    if final.netloc != parts.netloc or final.path.rstrip('/') not in ('/de-de', '/en-de'):
        return None
    # Inspect only the small number of frames already present in this page.
    for frame in page.frames[:8]:
        target = urlsplit(frame.url)
        if (frame == page.main_frame or target.scheme != 'https'
                or target.netloc != parts.netloc or target.path != '/_Incapsula_Resource'
                or statuses.get(frame) != 200):
            continue
        try:
            check_allowed(frame.url)
            if not frame.frame_element().is_visible():
                continue
            body = frame.content()
            if len(body) > 1_000_000:
                continue
            if inspect(body, {}, time.time())[0] == 'queue_open':
                return body, frame.title()
        except Exception:
            # Detached, blocked or inaccessible frames are unknown, never a
            # closed queue. The parent page still undergoes normal validation.
            continue
    return None


def validate_page(url, final_url, status, title, body):
    if urlsplit(final_url).hostname != urlsplit(url).hostname:
        raise FetchError('Unexpected browser redirect host')
    if status != 200:
        raise FetchError('Browser HTTP ' + str(status))
    if any(x in title.casefold() for x in ('nur einen moment', 'just a moment', 'access denied', 'client challenge')):
        raise FetchError('Browser challenge; no product data')
    if len(body) > 12_000_000:
        raise FetchError('Browser response too large')
    from .drop_watch import inspect
    if urlsplit(url).hostname in MMS_HOSTS and 'window.__PRELOADED_STATE__' not in body:
        # A real homepage queue has no catalogue state. Permit it only as a
        # public signal; product pages still require retailer product data.
        home_queue = urlsplit(url).path in ('', '/', '/de', '/de/') and inspect(body, {}, time.time())[0] == 'queue_open'
        if not home_queue:
            raise FetchError('Missing retailer page state')
    if inspect(body, {}, time.time())[0] == 'blocked_or_unreadable' and urlsplit(url).hostname not in MMS_HOSTS:
        raise FetchError('Browser challenge or empty page')
    return body


class BrowserClient(Client):
    def __init__(self, delay=1.0):
        super().__init__(delay)
        self.runtime = self.browser = None

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise FetchError('Run request budget exhausted')
        return max(1, int(min(20, left) * 1000))

    def back_off_browser(self, host, status):
        # A direct browser access denial does not describe the separately
        # validated Cloudflare reader. Rate limits / overload remain host-wide.
        if status in (403, 429, 503):
            key = 'browser:' + host if status == 403 else host
            self.blocked.add(key)
            self.cooldowns[key] = time.time() + 1800

    def text(self, url):
        from . import cloud_reader
        if cloud_reader.enabled_for(url):
            body = super().text(url)
            if urlsplit(url).path == '/robots.txt':
                return body
            return validate_page(url, url, 200, '', body)
        host = urlsplit(url).hostname
        if host not in HOSTS or urlsplit(url).path.endswith(('.xml', '.txt')):
            return super().text(url)
        self.check_allowed(url)
        if any(key in self.blocked or time.time() < self.cooldowns.get(key, 0)
               for key in (host, 'browser:' + host)):
            raise FetchError('Host backed off until next run')
        wait = max(0, max(self.delay, self.host_delay.get(host, 0)) -
                   (time.monotonic() - self.last.get(host, 0)))
        if time.monotonic() + wait >= self.deadline:
            raise FetchError('Run request budget exhausted')
        time.sleep(wait)
        self.remaining()
        context = None
        try:
            if self.runtime is None:
                from playwright.sync_api import sync_playwright
                self.runtime = sync_playwright().start()
                self.browser = launch_browser(self.runtime)
            context = self.browser.new_context(locale='de-DE', service_workers='block')
            def route(r):
                request = r.request
                if request.method not in ('GET', 'HEAD') or request.resource_type in ('image', 'media', 'font'):
                    r.abort()
                elif request.is_navigation_request() and urlsplit(request.url).hostname != host:
                    r.abort()
                else:
                    r.continue_()
            context.route('**/*', route)
            page = context.new_page()
            frame_statuses = {}
            def record_navigation(response):
                if response.request.is_navigation_request():
                    frame_statuses[response.frame] = response.status
            page.on('response', record_navigation)
            self.last[host] = time.monotonic()
            response = page.goto(url, wait_until='domcontentloaded', timeout=self.remaining())
            status = response.status if response else None
            if status != 200:
                self.back_off_browser(host, status)
                raise FetchError('Browser HTTP ' + str(status))
            # Read current DOM after hydration. Never click cart/consent/queue controls.
            predicate = ('Boolean(window.__PRELOADED_STATE__)' if host in MMS_HOSTS else
                         "document.querySelector('main,h1') && document.body.innerText.trim().length > 30")
            try:
                page.wait_for_function(predicate, timeout=min(4000, self.remaining()))
            except Exception:
                pass  # Validation below distinguishes empty/challenge from readable pages.
            queue = pokemon_queue_document(page, url, frame_statuses, self.check_allowed)
            body, title = queue if queue else (page.content(), page.title())
            return validate_page(url, page.url, status, title, body)
        except FetchError:
            raise
        except Exception:
            raise FetchError('Browser navigation or page-state error') from None
        finally:
            if context:
                context.close()

    def close(self):
        super().close()
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.runtime:
                self.runtime.stop()
            self.browser = self.runtime = None
