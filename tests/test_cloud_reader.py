import io
import json
import os
import time
import unittest
import urllib.error
from unittest.mock import patch
from tcg_bot import cloud_reader
from tcg_bot.browser import BrowserClient
from tcg_bot.http import Client, FetchError
from tcg_bot.web_sources import parse_mms
from test_web_sources import mms_body, shop

URL = 'https://www.mediamarkt.de/de/product/_pokemon-2974734.html'
ENV = {'TCG_CLOUD_READER_URL':'https://reader.example.workers.dev/read',
       'TCG_CLOUD_READER_TOKEN':'test-only-' * 4}

class Reply(io.BytesIO):
    status = 200

class CloudReaderTests(unittest.TestCase):
    def response(self, **changes):
        return dict(url=URL, fetched_at=time.time(), status=200, body=mms_body(), **{}) | changes

    def call(self, data):
        with patch.dict(os.environ, ENV), patch('urllib.request.OpenerDirector.open', return_value=Reply(json.dumps(data).encode())):
            return cloud_reader.read(URL, 5)

    def test_disabled_without_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(cloud_reader.enabled_for(URL))

    def test_allowlist(self):
        self.assertTrue(cloud_reader.target_allowed(URL))
        self.assertTrue(cloud_reader.target_allowed('https://www.saturn.de/robots.txt'))
        for url in ['https://evil.test/de/product/x.html', URL+'?token=x', URL+'#x',
                    'https://www.mediamarkt.de/account', 'https://www.mediamarkt.de/api/v1/graphql',
                    'https://www.mediamarkt.de:443/de/product/x.html',
                    'https://user@www.mediamarkt.de/de/product/x.html',
                    'https://www.mediamarkt.de/de/product/../account',
                    'https://www.mediamarkt.de/de/product/%2e%2e/account']:
            self.assertFalse(cloud_reader.target_allowed(url), url)
        self.assertTrue(cloud_reader.target_allowed('https://www.pokemoncenter.com/de-de/'))
        self.assertTrue(cloud_reader.target_allowed('https://www.pokemoncenter.com/de-de/product/123/box'))
        for path in ('/availabilities','/prices','/carts','/en-us/','/de-de/?token=x','/account'):
            self.assertFalse(cloud_reader.target_allowed('https://www.pokemoncenter.com'+path))

    def test_transport_diagnostic_contains_no_raw_body_or_secret(self):
        for body,headers,reason in [(b'Reader not configured',{},'READER_NOT_CONFIGURED'),
                (b'private details: never print',{},'WORKER_TRANSPORT_FAILURE'),
                (b'Upstream unavailable',{'X-TCG-Reader':'2026-10-28'},'READER_UPSTREAM_FAILURE')]:
            error=urllib.error.HTTPError(ENV['TCG_CLOUD_READER_URL'],503,'',headers,io.BytesIO(body))
            with patch.dict(os.environ,ENV),patch('urllib.request.OpenerDirector.open',side_effect=error):
                with self.assertRaisesRegex(FetchError,reason) as caught:
                    cloud_reader.read(URL,5)
                self.assertNotIn('private details',str(caught.exception))

    def test_temporary_worker_gateway_recovers_once_not_retailer_limit(self):
        error=urllib.error.HTTPError(ENV['TCG_CLOUD_READER_URL'],503,'',{},io.BytesIO(b'gateway unavailable'))
        with patch.dict(os.environ,ENV),patch('tcg_bot.cloud_reader.time.sleep'),patch(
                'urllib.request.OpenerDirector.open',side_effect=[error,Reply(json.dumps(self.response()).encode())]) as opener:
            self.assertEqual(cloud_reader.read(URL,10),mms_body())
            self.assertEqual(opener.call_count,2)
        error=urllib.error.HTTPError(ENV['TCG_CLOUD_READER_URL'],503,'',{'Retry-After':'120'},io.BytesIO())
        with patch.dict(os.environ,ENV),patch('urllib.request.OpenerDirector.open',side_effect=error) as opener:
            with self.assertRaises(FetchError):cloud_reader.read(URL,10)
            self.assertEqual(opener.call_count,1)

    def test_invalid_configuration_fails_closed(self):
        for endpoint in ['http://reader.example.workers.dev/read', 'https://evil.test/read',
                         'https://reader.example.workers.dev/read?secret=x']:
            with patch.dict(os.environ, ENV | {'TCG_CLOUD_READER_URL':endpoint}):
                with self.assertRaises(FetchError): cloud_reader.enabled_for(URL)
        with patch.dict(os.environ, ENV | {'TCG_CLOUD_READER_TOKEN':'short'}):
            with self.assertRaises(FetchError): cloud_reader.enabled_for(URL)

    def test_unrelated_shop_unchanged_even_if_misconfigured(self):
        with patch.dict(os.environ, ENV | {'TCG_CLOUD_READER_URL':'invalid'}):
            self.assertFalse(cloud_reader.enabled_for('https://example.org/item'))

    def test_current_exact_page_returned(self):
        with patch.dict(os.environ,ENV), patch('urllib.request.OpenerDirector.open',return_value=Reply(json.dumps(self.response()).encode())) as opener:
            self.assertEqual(cloud_reader.read(URL,5),mms_body())
            self.assertEqual(opener.call_args.args[0].get_header('User-agent'),'TCGRetailWatch/1.0')

    def test_stale_wrong_url_invalid_shape_rejected(self):
        for change in [dict(fetched_at=time.time()-120),dict(fetched_at=time.time()+120),
                       dict(fetched_at=True),dict(fetched_at=float('nan')),dict(url=URL+'other'),
                       dict(body={}),dict(status=True),dict(status='200')]:
            with self.assertRaises(FetchError): self.call(self.response(**change))
        with self.assertRaises(FetchError): self.call([])

    def test_upstream_stock_errors_stay_errors(self):
        for status in [403,429,503,302]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.call(self.response(status=status))
            self.assertEqual(error.exception.code,status)

    def test_transport_auth_error_does_not_expose_secret_or_fallback(self):
        with patch.dict(os.environ, ENV), patch('urllib.request.OpenerDirector.open', side_effect=urllib.error.HTTPError(ENV['TCG_CLOUD_READER_URL'],401,'',{},None)):
            with self.assertRaisesRegex(FetchError,'transport HTTP 401') as error:
                cloud_reader.read(URL,5)
            self.assertNotIn(ENV['TCG_CLOUD_READER_TOKEN'],str(error.exception))

    def test_client_keeps_rate_limit_backoff(self):
        with patch.dict(os.environ, ENV), patch('tcg_bot.cloud_reader.read', side_effect=urllib.error.HTTPError(URL,429,'',{},None)):
            client=Client(0)
            with self.assertRaisesRegex(FetchError,'HTTP 429'): client.raw(URL)
            self.assertIn('www.mediamarkt.de',client.blocked)

    def test_browser_transport_uses_existing_robots_and_parser(self):
        def read(url, timeout):
            return 'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else mms_body(stock='NOT_AVAILABLE')
        with patch.dict(os.environ,ENV), patch('tcg_bot.cloud_reader.read', side_effect=read):
            client=BrowserClient(0)
            body=client.text(URL)
            row=parse_mms(shop(True) | {'base_url':'https://www.mediamarkt.de'},body,URL)[0]
            self.assertFalse(row['available'])
            self.assertFalse(row['add_to_cart_available'])
            self.assertIsNone(client.browser)

    def test_robots_denial_prevents_product_request(self):
        with patch.dict(os.environ,ENV), patch('tcg_bot.cloud_reader.read', return_value='User-agent: *\nDisallow: /de/') as read:
            with self.assertRaisesRegex(FetchError,'robots.txt disallows'): BrowserClient(0).text(URL)
            self.assertEqual(read.call_count,1)

    def test_challenge_html_is_not_product(self):
        def read(url, timeout):
            return 'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else '<title>Access denied</title>'
        with patch.dict(os.environ,ENV), patch('tcg_bot.cloud_reader.read', side_effect=read):
            with self.assertRaisesRegex(FetchError,'Missing retailer page state'): BrowserClient(0).text(URL)


class GitHubIdentityTests(unittest.TestCase):
    def test_oidc_request_and_cache(self):
        env={'ACTIONS_ID_TOKEN_REQUEST_URL':'https://runner.actions.githubusercontent.com/idtoken?api-version=2',
             'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'synthetic-job-token'}
        cloud_reader._token_cache=None
        with patch.dict(os.environ,env), patch('urllib.request.OpenerDirector.open',return_value=Reply(b'{"value":"test.payload.signature"}')) as opener:
            self.assertEqual(cloud_reader.github_token('https://reader.example.workers.dev',5),'test.payload.signature')
            self.assertEqual(cloud_reader.github_token('https://reader.example.workers.dev',5),'test.payload.signature')
            self.assertEqual(opener.call_count,1)
            req=opener.call_args.args[0]
            self.assertIn('audience=https%3A%2F%2Freader.example.workers.dev',req.full_url)
            self.assertEqual(req.get_header('User-agent'),'TCGRetailWatch/1.0')
        cloud_reader._token_cache=None

    def test_identity_request_never_sends_credential_offsite(self):
        for url in ['https://evil.test/idtoken','http://runner.actions.githubusercontent.com/idtoken',
                    'https://runner.actions.githubusercontent.com@evil.test/idtoken']:
            with patch.dict(os.environ,{'ACTIONS_ID_TOKEN_REQUEST_URL':url,'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'secret'}), patch('urllib.request.OpenerDirector.open') as opener:
                with self.assertRaises(FetchError): cloud_reader.github_token('audience',5)
                opener.assert_not_called()
