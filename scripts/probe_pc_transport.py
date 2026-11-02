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
from urllib.parse import urlsplit

from tcg_bot.pokemon_center_queue import QueueClient, public_queue_url, snapshot
from tcg_bot.pokemon_center_gate import provider_snapshot

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


def observation_times(seconds):
    if type(seconds) is not int or not 30 <= seconds <= 300:
        raise ValueError('Duration must be 30..300 seconds')
    return sorted(set([3, 15, 30, *range(60, seconds+1, 30), seconds]))


def rendered_observation(body, status, now):
    # An error response cannot become a positive queue result through its text.
    if status != 200:
        return {'status': 'blocked' if status in (401, 403, 429) else 'unknown',
                'region': None, 'inventory_confirmed': False}
    try:
        result = provider_snapshot({'status_code': status, 'html': body}, now,
                                   require_rendered=True)
        result.pop('banner', None)
        return result
    except Exception:
        return {'status': 'unknown', 'reason': 'VISIBLE_CAPTURE_UNREADABLE',
                'region': None, 'inventory_confirmed': False}


def browser_probe(headed, seconds=30):
    from playwright.sync_api import sync_playwright
    samples = observation_times(seconds)
    capture_js = Path('tcg_bot/pc_queue_dom.js').read_text()
    observations = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel='chrome', headless=not headed)
        context = browser.new_context(locale='de-DE', timezone_id='Europe/Berlin',
                                      accept_downloads=False)
        page = context.new_page()
        navigation = {'count': 0, 'status': None}
        def on_response(response):
            request = response.request
            if request.is_navigation_request() and response.frame == page.main_frame:
                navigation['count'] += 1
                navigation['status'] = response.status
        page.on('response', on_response)
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
            page.goto(HOME, wait_until='domcontentloaded', timeout=30000)
            started = time.monotonic()
            for offset in samples:
                page.wait_for_timeout(max(0, started+offset-time.monotonic())*1000)
                if not public_queue_url(page.url, home=True):
                    observations.append({'status': 'REGION_OR_REDIRECT_UNCONFIRMED'})
                    break
                try:
                    # Same context/tab throughout; this only copies visible DOM.
                    # No page reload, clicks, cookie export or network call here.
                    page.evaluate('async () => {'+capture_js+'}')
                    body = page.content()
                    observation = rendered_observation(body, navigation['status'], time.time())
                    observation['page_bytes'] = len(body.encode('utf-8'))
                except Exception:
                    observation = {'status': 'unknown', 'reason': 'VISIBLE_CAPTURE_UNREADABLE'}
                observation.update(http_status=navigation['status'],
                                   elapsed_seconds=round(time.monotonic()-started, 2))
                observations.append(observation)
                print('PC_BROWSER_SAMPLE '+json.dumps(observation), flush=True)
            return {'status': observations[-1]['status'], 'observations': observations,
                    'requested_duration_seconds': seconds,
                    'elapsed_seconds': round(time.monotonic()-started, 2),
                    'browser_contexts': 1, 'tabs': 1, 'manual_navigations': 1,
                    'manual_reloads': 0, 'observed_main_responses': navigation['count'],
                    'live_german_queue_observed': any(o['status'] == 'queue_open_de' for o in observations)}
        finally:
            context.close()
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--browser-only', action='store_true')
    parser.add_argument('--seconds', type=int, choices=range(30, 301), default=30)
    args = parser.parse_args()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'discord_sent': 0,
              'credits_consumed': 0, 'provider_requests': 0,
              'inventory_confirmed': False, 'results': []}
    try:
        QueueClient().check_allowed(HOME)
    except Exception:
        report['status'] = 'POLICY_CHECK_UNAVAILABLE'
    else:
        probes = [('normal_chrome', lambda: browser_probe(args.headed, args.seconds))]
        if not args.browser_only:
            probes.insert(0, ('chrome_http', http_probe))
        for name, run in probes:
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
