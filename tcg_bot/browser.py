"""Normal read-only Chromium pages; no proxy, stealth, login, or queue bypass."""
import time
from urllib.parse import urlsplit
from .http import Client, FetchError

MMS_HOSTS = frozenset({'www.mediamarkt.de', 'www.saturn.de'})
HOSTS = MMS_HOSTS | {'www.mueller.de', 'www.pokemoncenter.com'}


def validate_page(url, final_url, status, title, body):
    if urlsplit(final_url).hostname != urlsplit(url).hostname:
        raise FetchError('Unexpected browser redirect host')
    if status != 200:
        raise FetchError('Browser HTTP ' + str(status))
    if any(x in title.casefold() for x in ('nur einen moment', 'just a moment', 'access denied', 'client challenge')):
        raise FetchError('Browser challenge; no product data')
    if len(body) > 12_000_000:
        raise FetchError('Browser response too large')
    if urlsplit(url).hostname in MMS_HOSTS and 'window.__PRELOADED_STATE__' not in body:
        raise FetchError('Missing retailer page state')
    from .drop_watch import inspect
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

    def text(self, url):
        host = urlsplit(url).hostname
        if host not in HOSTS or urlsplit(url).path.endswith(('.xml', '.txt')):
            return super().text(url)
        self.check_allowed(url)
        if host in self.blocked or time.time() < self.cooldowns.get(host, 0):
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
                self.browser = self.runtime.chromium.launch(headless=True)
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
            self.last[host] = time.monotonic()
            response = page.goto(url, wait_until='domcontentloaded', timeout=self.remaining())
            status = response.status if response else None
            if status != 200:
                if status in (403, 429, 503):
                    self.blocked.add(host)
                    self.cooldowns[host] = time.time() + 1800
                raise FetchError('Browser HTTP ' + str(status))
            # Read current DOM after hydration. Never click cart/consent/queue controls.
            predicate = ('Boolean(window.__PRELOADED_STATE__)' if host in MMS_HOSTS else
                         "document.querySelector('main,h1') && document.body.innerText.trim().length > 30")
            try:
                page.wait_for_function(predicate, timeout=min(4000, self.remaining()))
            except Exception:
                pass  # Validation below distinguishes empty/challenge from readable pages.
            return validate_page(url, page.url, status, page.title(), page.content())
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
