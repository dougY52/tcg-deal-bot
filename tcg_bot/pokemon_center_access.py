"""Bounded public DE access diagnostics. Readability is never stock proof.

The optional provider is test-only: free subscription required, no retries,
no cookies/account endpoints, no alert sender, no automatic paid upgrade.
"""
import json
import math
import re
from urllib.parse import urljoin, urlsplit, urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from .http import FetchError, NoRedirect, UA
from .drop_watch import inspect, visible
from .web_sources import Document, structured_products

ORIGIN = 'https://www.pokemoncenter.com'
TARGETS = (ORIGIN + '/de-de/', ORIGIN + '/en-de', ORIGIN + '/sitemap.xml')
MODES = (('datacenter', False, 1), ('datacenter', True, 10),
         ('residential', False, 25), ('residential', True, 125))
MAX_TEST_CREDITS = sum(mode[2] for mode in MODES)
API = 'https://api.scrapingant.com/v2/'


def public_de_url(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and p.netloc == 'www.pokemoncenter.com'
            and not p.query and not p.fragment and '%' not in p.path and '..' not in p.path
            and bool(re.fullmatch(r'/(?:de-de|en-de)(?:/)?|/(?:de-de|en-de)/(?:product|category)/[a-zA-Z0-9_/-]+', p.path)))


def page_result(body, url, now):
    """Store only public metadata, never provider cookies, raw XHR or HTML."""
    status, _ = inspect(body, {}, now)
    if re.search(r'_Incapsula_Resource|incapsula incident|geo\.captcha-delivery\.com', body, re.I):
        status = 'blocked_or_unreadable'
    if status == 'blocked_or_unreadable':
        return {'status': status, 'bytes': len(body), 'inventory_confirmed': False}
    doc = Document(body)
    candidates = []
    for node in doc.root.walk():
        if node.tag != 'a':
            continue
        target = urljoin(url, node.attrs.get('href', ''))
        title = re.sub(r'\s+', ' ', visible(node)).strip()
        if (public_de_url(target) and '/product/' in target
                and re.search(r'booster|trainer.?box|collection|kollektion|bundle|\betb\b|premium', title, re.I)
                and target not in [x['url'] for x in candidates]):
            candidates.append({'url': target, 'name': title[:200]})
    products = structured_products(doc)
    return {'status': 'readable_discovery_only', 'bytes': len(body),
            'headings': [n.text().strip()[:180] for n in doc.root.walk() if n.tag in ('title', 'h1')][:3],
            'structured_product_count': len(products), 'candidate_links': candidates[:12],
            'inventory_confirmed': False}


def free_usage(data, reserve):
    """Fail closed on paid/trial/unknown plans and incomplete usage responses."""
    if not isinstance(data, dict) or str(data.get('plan_name', '')).strip().lower() not in ('free', 'free plan'):
        raise FetchError('PC_PROVIDER_FREE_PLAN_REQUIRED')
    total, remaining = data.get('plan_total_credits'), data.get('remained_credits')
    if (type(total) not in (int, float) or type(remaining) not in (int, float)
            or not math.isfinite(total) or not math.isfinite(remaining)
            or not 0 < total <= 10000 or not reserve <= remaining <= total):
        raise FetchError('PC_PROVIDER_FREE_CREDITS_UNCONFIRMED')
    return {'plan': 'free', 'remaining_credits': remaining}


class FreeAccessProbe:
    def __init__(self, key, policy_client):
        if not key or len(key) > 512 or any(c.isspace() for c in key):
            raise FetchError('PC_PROVIDER_KEY_INVALID')
        self.key = key
        self.policy_client = policy_client
        self.reserved = 0
        self.attempted = set()

    def request_json(self, endpoint, params=None):
        if endpoint not in ('usage', 'extended'):
            raise FetchError('PC_PROVIDER_UNSUPPORTED_ENDPOINT')
        url = API + endpoint + ('?' + urlencode(params) if params else '')
        request = Request(url, headers={'x-api-key': self.key, 'User-Agent': UA, 'Accept': 'application/json'})
        try:
            with build_opener(NoRedirect()).open(request, timeout=35) as response:
                raw = response.read(12000001)
                if len(raw) > 12000000:
                    raise FetchError('PC_PROVIDER_RESPONSE_TOO_LARGE')
                data = json.loads(raw)
                cost = response.headers.get('Ant-credits-cost')
                if cost is not None:
                    try: cost = float(cost)
                    except (TypeError, ValueError): cost = None
                return data, cost
        except HTTPError as exc:
            # Never log provider response text or request URLs containing secrets.
            raise FetchError('PC_PROVIDER_HTTP_' + str(exc.code)) from None
        except (URLError, TimeoutError, UnicodeError, ValueError):
            raise FetchError('PC_PROVIDER_UNAVAILABLE_OR_INVALID') from None

    def fetch(self, url, mode):
        if not public_de_url(url) or mode not in MODES:
            raise FetchError('PC_PROVIDER_UNSUPPORTED_TARGET')
        if mode in self.attempted or self.reserved + mode[2] > MAX_TEST_CREDITS:
            raise FetchError('PC_PROVIDER_TEST_BUDGET_EXHAUSTED')
        self.policy_client.check_allowed(url)
        usage, _ = self.request_json('usage')
        free_usage(usage, mode[2])
        # Reserve before the request, including failures. No automatic retries.
        self.reserved += mode[2]
        self.attempted.add(mode)
        params = {'url': url, 'proxy_type': mode[0], 'browser': str(mode[1]).lower(), 'timeout': 25}
        data, cost = self.request_json('extended', params)
        if cost is not None and (not math.isfinite(cost) or cost < 0 or cost > mode[2]):
            self.reserved = MAX_TEST_CREDITS
            raise FetchError('PC_PROVIDER_COST_CHANGED_STOPPED')
        if not isinstance(data, dict) or type(data.get('status_code')) is not int or data['status_code'] != 200:
            raise FetchError('PC_PROVIDER_TARGET_NOT_HTTP_200')
        body = data.get('html')
        if not isinstance(body, str) or len(body.encode('utf-8')) > 12000000:
            raise FetchError('PC_PROVIDER_HTML_MISSING')
        # No account or checkout navigation. Only observed first-party GET paths
        # are retained as research metadata, never as availability evidence.
        endpoints = []
        for item in data.get('xhrs', []) if isinstance(data.get('xhrs', []), list) else []:
            if not isinstance(item, dict) or item.get('method') != 'GET':
                continue
            p = urlsplit(str(item.get('url', '')))
            if public_de_url(p._replace(query='', fragment='').geturl()):
                endpoints.append({'path': p.path[:250], 'status': item.get('status')})
        return body, {'reserved_credits': mode[2], 'reported_credits': cost,
                      'public_get_paths': endpoints[:12]}
