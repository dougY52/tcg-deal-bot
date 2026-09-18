import unittest
from unittest.mock import patch
from tcg_bot.browser import BrowserClient, validate_page
from tcg_bot.http import Client, FetchError

class BrowserTests(unittest.TestCase):
    def test_challenge_redirect_and_missing_state_rejected(self):
        url = 'https://www.mediamarkt.de/de/product/test.html'
        valid = '<script>window.__PRELOADED_STATE__={}</script>'
        self.assertEqual(validate_page(url, url, 200, 'Product', valid), valid)
        for final, status, title, body in [(url,403,'Product',valid),('https://example.org',200,'Product',valid),(url,200,'Nur einen Moment…',valid),(url,200,'Product','<p>Loading</p>')]:
            with self.assertRaises(FetchError): validate_page(url,final,status,title,body)

    def test_other_shops_keep_http_and_browser_not_started(self):
        with patch.object(Client, 'text', return_value='http') as get:
            c=BrowserClient()
            self.assertEqual(c.text('https://cardbuddys.de/products.json'), 'http')
            self.assertIsNone(c.runtime)
            get.assert_called_once()
            c.close()

    def test_robots_denial_before_browser_start(self):
        c=BrowserClient()
        with patch.object(c,'check_allowed',side_effect=FetchError('disallowed')):
            with self.assertRaises(FetchError): c.text('https://www.saturn.de/test')
        self.assertIsNone(c.runtime)
