import copy
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import test_preorders as fixtures
from tcg_bot import fast_watch as f

NOW = fixtures.NOW


class Client(fixtures.Client):
    def text(self, url):
        self.form_id = parse_qs(urlsplit(url).query).get('variant', ['123'])[0]
        return super().text(url)


class FastDiscoveryTests(unittest.TestCase):
    setUp = fixtures.Preorders.setUp

    def run_bot(self, rows=None, now=NOW, send=None):
        self.state.update(fast_bootstrapped=True, retailer_discovery_at=now)
        rows = [self.offer] if rows is None else rows
        with patch('tcg_bot.retailer_coverage.check_sources', return_value={}), patch('tcg_bot.retailer_discovery.discover', return_value={}):
            return f.run(self.cfg, self.state, self.client,
                         {'shopify': lambda *_: (rows, [])}, send=send, now=now)

    def test_new_product_alerts_in_discovery_run(self):
        sent = []
        report = self.run_bot(send=lambda m: sent.append(m) or 'message')
        self.assertEqual(report['sent'], 1)
        self.assertEqual(report['fresh_watch']['checked'], 1)
        self.assertEqual(report['fast_watch']['checked'], 0)
        self.assertIn('PREORDER', sent[0]['embeds'][0]['title'])

    def test_new_catalog_waitlist_is_silent(self):
        self.client.button = '<button>Notify me</button>'
        report = self.run_bot(send=lambda _: self.fail('waitlist alert'))
        self.assertEqual(report['sent'], 0)
        self.assertEqual(report['fresh_watch']['rejected']['WAITLIST'], 1)

    def test_new_catalog_stale_price_never_alerts(self):
        self.client.product['variants'][0]['price'] = 18000
        report = self.run_bot(send=lambda _: self.fail('stale price'))
        self.assertEqual(report['fresh_watch']['rejected']['PRICE_TOO_HIGH'], 1)

    def test_second_run_does_not_repeat_fresh_alert(self):
        self.run_bot(send=lambda _: 'message')
        report = self.run_bot(now=NOW+300, send=lambda _: self.fail('duplicate'))
        self.assertEqual(report['sent'], 0)

    def test_new_target_live_failure_not_stock_outage(self):
        self.client.fail = True
        report = self.run_bot(send=lambda _: self.fail('failed validation'))
        self.assertEqual(report['sent'], 0)
        self.assertEqual(self.state.get('preorder_products'), {})

    def test_alert_limit_shared_across_both_lanes(self):
        self.client = Client()
        self.client.product['variants'].append(dict(self.client.product['variants'][0], id=456))
        other = dict(self.offer, key='example:456', variant_id='456',
                     url='https://example.test/products/fb11?variant=456')
        self.cfg['max_alerts_per_run'] = 1
        f.remember([self.offer], self.cfg, self.state, NOW-300)
        report = self.run_bot([other], send=lambda _: 'message')
        self.assertEqual(report['sent'], 1)
        self.assertEqual(len(report['alerts']), 1)
        self.assertEqual(report['pending_alerts'], 1)
        records = list(self.state['preorder_products'].values())
        self.assertEqual(sum('last_alert' in r for r in records), 1)

    def test_json_shared_but_variant_forms_both_fresh(self):
        self.client = Client()
        self.client.product['variants'].append(dict(self.client.product['variants'][0], id=456))
        other = dict(self.offer, key='example:456', variant_id='456',
                     url='https://example.test/products/fb11?variant=456')
        self.run_bot([self.offer, other], send=lambda _: 'message')
        self.assertEqual(sum('.js?' in u for u in self.client.urls), 1)
        self.assertEqual(sum('?variant=' in u for u in self.client.urls), 2)
        self.client.product['variants'][0]['price'] = 9500
        self.run_bot(now=NOW+300, send=lambda _: 'next-message')
        self.assertEqual(sum('.js?' in u for u in self.client.urls), 2)

    def test_many_variants_do_not_starve_other_hosts(self):
        self.cfg['fast_watch']['quotas'][0] = 6
        rows = []
        for shop_index in range(6):
            shop = dict(self.shop, id='s'+str(shop_index),
                        base_url='https://s'+str(shop_index)+'.test')
            self.cfg['shops'].append(shop)
            for variant in range(12):
                rows.append(dict(self.offer, shop=shop['id'],
                                 key=shop['id']+':'+str(variant), variant_id=str(variant),
                                 title='Dragon Ball Fusion World FB04 Display EN'))
        f.remember(rows, self.cfg, self.state, NOW)
        self.assertEqual(len({o['shop'] for o in f.select(self.cfg, self.state)}), 6)

    def test_product_cache_never_caches_html_or_failures(self):
        client = fixtures.Client()
        cache = f.ProductCache(client)
        client.fail = True
        with self.assertRaises(TimeoutError):
            cache.get('https://example.test/products/fb11.js?check=1')
        client.fail = False
        first = cache.get('https://example.test/products/fb11.js?check=1')
        first['title'] = 'mutation'
        self.assertNotEqual(cache.get('https://example.test/products/fb11.js?check=1')['title'], 'mutation')
        cache.text('https://example.test/products/fb11?variant=123')
        cache.text('https://example.test/products/fb11?variant=123')
        self.assertEqual(len(client.urls), 4)

    def test_available_targets_and_closed_windows_both_get_slots(self):
        self.cfg['fast_watch']['quotas'][0] = 6
        rows = [dict(self.offer, key='example:'+str(i), variant_id=str(i),
                     title='Dragon Ball Fusion World FB04 Display EN', available=i>=12)
                for i in range(24)]
        f.remember(rows, self.cfg, self.state, NOW)
        chosen = f.select(self.cfg, self.state)
        self.assertEqual(sum(o['available'] is True for o in chosen), 4)
        self.assertEqual(sum(o['available'] is False for o in chosen), 2)
