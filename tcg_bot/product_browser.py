"""Read a JS-initialized product form. No clicks, cart writes, or queue bypass."""
import time
from .browser_runtime import launch_browser
from urllib.parse import urlsplit
from .http import FetchError


class ProductRenderer:
    def __init__(self):
        self.runtime = self.browser = None

    def read(self, url, variant_id, deadline):
        context = None
        try:
            if deadline - time.monotonic() < 3:
                raise FetchError('Browser request budget exhausted')
            if self.runtime is None:
                from playwright.sync_api import sync_playwright
                self.runtime = sync_playwright().start()
                self.browser = launch_browser(self.runtime)
            context = self.browser.new_context(locale='de-DE', service_workers='block')
            # Read-only browsing: stop explicit cart/checkout mutations and assets
            # which do not affect form initialization.
            def route(request_route):
                request = request_route.request
                if request.method not in ('GET', 'HEAD') or request.resource_type in ('image', 'media', 'font'):
                    request_route.abort()
                elif request.is_navigation_request() and urlsplit(request.url).hostname != urlsplit(url).hostname:
                    request_route.abort()
                else:
                    request_route.continue_()
            context.route('**/*', route)
            page = context.new_page()
            def remaining():
                left = min(15, deadline - time.monotonic())
                if left <= 0:
                    raise FetchError('Browser request budget exhausted')
                return max(1, int(left * 1000))
            response = page.goto(url, wait_until='domcontentloaded', timeout=remaining())
            if not response or response.status != 200 or urlsplit(page.url).hostname != urlsplit(url).hostname:
                raise FetchError('Browser product unavailable')
            if any(word in page.title().lower() for word in ('access denied', 'just a moment', 'captcha', 'queue', 'warteschlange')):
                raise FetchError('Browser challenge or queue; no purchase validation')
            page.wait_for_function('''vid => [...document.forms].some(f =>
                new URL(f.action).pathname.endsWith('/cart/add') &&
                [...f.elements].some(e => e.name === 'id' && e.value === vid && !e.disabled) &&
                [...f.elements].some(e => e.type === 'submit' && !e.disabled))''',
                arg=str(variant_id), timeout=remaining())
            body = page.content()
            if len(body) > 12_000_000:
                raise FetchError('Browser response too large')
            return body
        except FetchError:
            raise
        except Exception:
            raise FetchError('Browser variant not confirmed') from None
        finally:
            if context:
                context.close()

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.runtime:
                self.runtime.stop()
            self.browser = self.runtime = None
