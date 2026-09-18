"""Isolated public-page browser for the two verified MMS retailer hosts."""
from urllib.parse import urlsplit
from .http import Client, FetchError

HOSTS = frozenset({'www.mediamarkt.de', 'www.saturn.de'})


def validate_page(url, final_url, status, title, body):
    if urlsplit(final_url).hostname != urlsplit(url).hostname:
        raise FetchError('Unexpected browser redirect host')
    if status != 200:
        raise FetchError('Browser HTTP ' + str(status))
    if any(x in title.casefold() for x in ('nur einen moment', 'just a moment', 'access denied', 'client challenge')):
        raise FetchError('Browser challenge; no product data')
    if len(body) > 12_000_000:
        raise FetchError('Browser response too large')
    if 'window.__PRELOADED_STATE__' not in body:
        raise FetchError('Missing retailer page state')
    return body


class BrowserClient(Client):
    def __init__(self):
        super().__init__()
        self.runtime = self.browser = None
        self.contexts = {}

    def text(self, url):
        host = urlsplit(url).hostname
        if host not in HOSTS:
            return super().text(url)
        self.check_allowed(url)
        if self.runtime is None:
            from playwright.sync_api import sync_playwright
            self.runtime = sync_playwright().start()
            self.browser = self.runtime.chromium.launch(channel='chromium', headless=True)
        if host not in self.contexts:
            self.contexts[host] = self.browser.new_context(locale='de-DE', service_workers='block')
        page = self.contexts[host].new_page()
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=35000)
            if not response or response.status != 200:
                raise FetchError('Browser HTTP ' + str(response.status if response else 'missing'))
            page.wait_for_function('Boolean(window.__PRELOADED_STATE__)', timeout=10000)
            return validate_page(url, page.url, response.status, page.title(), page.content())
        except FetchError:
            raise
        except Exception:
            # Never log browser exception text (URLs/response bodies may be present).
            raise FetchError('Browser navigation or page-state error') from None
        finally:
            page.close()

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.runtime:
                self.runtime.stop()
            self.browser = self.runtime = None
            self.contexts.clear()
