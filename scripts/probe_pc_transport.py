"""One-off public DE transport comparison; never sends Discord or stores sessions.

Runs only on explicit diagnostic dispatch/push, not on the minute timer. A normal
Chrome loads the site's own JavaScript. No CAPTCHA clicks, solver, proxies,
checkout, account login, HAR, cookie export, or third-party bot code.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit

from tcg_bot.pokemon_center_queue import QueueClient, public_queue_url, snapshot
from tcg_bot.web_sources import Document

HOME = 'https://www.pokemoncenter.com/de-de/'


def summarize(pages):
    """Classify only the current public document and its observed main iframe."""
    class Pages:
        def text(self, url):
            if url not in pages:
                raise ValueError('FRAME_UNREADABLE')
            return pages[url]
    result = snapshot(Pages(), HOME, time.time())
    result.pop('banner', None)
    result['page_bytes'] = len(pages[HOME].encode('utf-8'))
    result['next_data_present'] = 'id="__NEXT_DATA__"' in pages[HOME]
    return result


def http_probe():
    from curl_cffi import requests
    with requests.Session(impersonate='chrome') as session:
        class Transport:
            def text(self, url):
                if not (public_queue_url(url, home=True) or public_queue_url(url)):
                    raise ValueError('UNSUPPORTED_PUBLIC_URL')
                response = session.get(url, timeout=20, allow_redirects=False,
                                       headers={'Cache-Control': 'no-cache', 'Accept-Language': 'de-DE,de;q=0.9'})
                if response.status_code != 200:
                    raise ValueError('HTTP_' + str(response.status_code))
                if len(response.content) > 8_000_000:
                    raise ValueError('RESPONSE_SIZE_LIMIT')
                return response.text
        result = snapshot(Transport(), HOME, time.time())
        result.pop('banner', None)
        return result


def browser_probe(headed):
    from playwright.sync_api import sync_playwright
    observations = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel='chrome', headless=not headed)
        context = browser.new_context(locale='de-DE', timezone_id='Europe/Berlin',
                                      accept_downloads=False)
        page = context.new_page()
        # The diagnostic never navigates to an account/cart or clicks anything.
        # Ordinary automatic browser requests can run, including public JS checks.
        def guard(route):
            request = route.request
            p = urlsplit(request.url)
            sensitive = re.search(r'/(?:checkout|intl-checkout|account|orders|cart|carts|extcarts|wishlist|auth/login)(?:/|$)', p.path, re.I)
            foreign_navigation = request.is_navigation_request() and p.hostname != 'www.pokemoncenter.com'
            if sensitive or foreign_navigation or request.method in ('PUT', 'PATCH', 'DELETE'):
                route.abort()
            else:
                route.continue_()
        page.route('**/*', guard)
        try:
            response = page.goto(HOME, wait_until='domcontentloaded', timeout=30000)
            for delay in (3000, 12000, 15000):
                page.wait_for_timeout(delay)
                if not public_queue_url(page.url, home=True):
                    observations.append({'status': 'REGION_OR_REDIRECT_UNCONFIRMED'})
                    break
                body = page.content()
                pages = {HOME: body}
                frames = [n for n in Document(body).root.walk()
                          if n.tag == 'iframe' and n.attrs.get('id') == 'main-iframe']
                if len(frames) == 1:
                    target = urljoin(HOME, frames[0].attrs.get('src', ''))
                    if public_queue_url(target):
                        element = page.query_selector('iframe#main-iframe')
                        frame = element.content_frame() if element else None
                        if frame and public_queue_url(frame.url):
                            pages[target] = frame.content()
                try:
                    observation = summarize(pages)
                except ValueError:
                    observation = {'status': 'FRAME_UNREADABLE'}
                observation['http_status'] = response.status if response else None
                observations.append(observation)
            return {'status': observations[-1]['status'], 'observations': observations}
        finally:
            context.close()
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headed', action='store_true')
    args = parser.parse_args()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'discord_sent': 0,
              'inventory_confirmed': False, 'results': []}
    try:
        QueueClient().check_allowed(HOME)
    except Exception:
        report['status'] = 'POLICY_CHECK_UNAVAILABLE'
    else:
        for name, run in (('chrome_http', http_probe), ('normal_chrome', lambda: browser_probe(args.headed))):
            try:
                result = run()
            except Exception as error:
                # Exceptions can contain challenge URLs, tokens and cookies.
                result = {'status': 'ERROR', 'error_type': type(error).__name__}
            report['results'].append({'transport': name, **result})
            print('PC_TRANSPORT ' + json.dumps(report['results'][-1]), flush=True)
        report['status'] = 'COMPLETE'
    Path('pc-transport-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PC_TRANSPORT_REPORT ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
