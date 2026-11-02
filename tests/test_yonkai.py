"""Public product API + page + exact storefront identity must agree."""
import copy
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from tcg_bot import yonkai, preorders, fast_watch
from tcg_bot.__main__ import load_config

SHOP = dict(id='yonkai-berlin', name='Yonkai Berlin', base_url='https://yonkaiberlin.de',
            adapter='yonkai', currency='EUR', max_pages=40,
            shipping_eur='6.99', free_shipping_from_eur='60.00')
URL = SHOP['base_url'] + '/produkt/fb11/'
NOW = 1793659800


class Client:
    def __init__(self):
        self.api = dict(id=123, name='Dragon Ball FB11 Display EN', type='simple', sku='FB11-EN', permalink=URL,
                        description='24 Booster', short_description='', has_options=False, variations=[],
                        is_password_protected=False, is_purchasable=True, is_in_stock=True, is_on_backorder=False,
                        prices=dict(price='10499', currency_code='EUR', currency_minor_unit=2, price_range=None),
                        add_to_cart=dict(text='In den Warenkorb', url='/?add-to-cart=123', minimum=1, maximum=3))
        self.product = dict(name=self.api['name'], sku=self.api['sku'], url=URL, description='24 Booster',
                            **{'@type':'Product'}, offers=dict(price='104.99', priceCurrency='EUR',
                            availability='https://schema.org/InStock', url=URL))
        self.item = dict(id=123, g='Dragon Ball', n='FB11 Display EN', p=10499, s=1, buy=True, q=3, u=URL, d='24 Booster')
        self.page_id = 123
        self.extra_script = ''
        self.protected_form = ''
        self.calls = []
        self.products = [self.api]

    def text(self, url):
        self.calls.append(url)
        if 'yk_ykp=' in url:
            return 'window.YKP=' + json.dumps([self.item]) + ';' + self.extra_script
        return ('<script type="application/ld+json">' + json.dumps(self.product) + '</script>'
                '<script>window.YKPID=' + str(self.page_id) + ';</script>'
                '<script src="/?yk_ykp=abc123def0"></script>' + self.protected_form)

    def get(self, url):
        self.calls.append(url)
        if '/products?' in url:
            page = int(parse_qs(urlsplit(url).query)['page'][0])
            return copy.deepcopy(self.products[(page-1)*100:page*100])
        return copy.deepcopy(self.api)


class YonkaiTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.offer = yonkai.offer(self.client.api, SHOP)
        self.cfg = load_config('config/config.json')
        self.cfg['shops'] = [SHOP]
        self.cfg['daily_prices']['enabled'] = False
        self.state = {}

    def live(self):
        return preorders.live(self.offer, SHOP, self.client, NOW)

    def scan(self, now=NOW):
        cfg = copy.deepcopy(self.cfg)
        cfg['_fast_lane'] = True
        cfg['_fast_keys'] = [self.offer['key']]
        cfg['_fast_groups'] = {self.offer['key']: 0}
        return preorders.scan([self.offer], cfg, self.state, self.client, now)

    def test_live_stock_and_price_with_read_only_requests(self):
        row, error = self.live()
        self.assertIsNone(error)
        self.assertEqual(row['price'], '104.99')
        self.assertTrue(row['add_to_cart_available'])
        self.assertEqual(row['shipping_cost'], '0.00')
        self.assertFalse(row['cart_validated'])
        self.assertTrue(all('add-to-cart=' not in u for u in self.client.calls))

    def test_reserved_offer_not_alerted_without_orderability(self):
        self.client.item['d'] = 'Unverbindlich reservieren'
        self.assertEqual(self.live()[1], 'WAITLIST')
        self.assertEqual(self.scan()[1], [])

    def test_full_preorder_contingent_is_waitlist(self):
        self.client.item.update(pre='2026-11-20', cap=24, booked=24)
        self.assertEqual(self.live()[1], 'WAITLIST')
        self.assertEqual(self.scan()[1], [])

    def test_preorder_without_full_capacity_data_fails_closed(self):
        self.client.item.update(pre='2026-11-20', cap=24)
        self.assertEqual(self.live()[1], 'NO_CHECKOUT')

    def test_waitlist_to_real_preorder_then_duplicate(self):
        self.client.item.update(pre='2026-11-20', cap=24, booked=24)
        self.assertEqual(self.scan()[1], [])
        self.client.item['booked'] = 23
        deals = self.scan(NOW+300)[1]
        self.assertEqual(len(deals), 1)
        self.assertTrue(deals[0]['preorder_status'])
        preorders.delivered(self.state, deals[0], NOW+300, 'test-receipt')
        self.assertEqual(self.scan(NOW+600)[1], [])

    def test_real_restock_then_duplicate(self):
        deals = self.scan()[1]
        self.assertEqual(len(deals), 1)
        preorders.delivered(self.state, deals[0], NOW, 'test-receipt')
        self.assertEqual(self.scan(NOW+300)[1], [])
        self.client.product['offers']['availability'] = 'https://schema.org/OutOfStock'
        self.assertEqual(self.scan(NOW+600)[1], [])
        self.client.product['offers']['availability'] = 'https://schema.org/InStock'
        self.assertEqual(len(self.scan(NOW+900)[1]), 1)

    def test_page_sold_out_overrides_positive_api_and_storefront(self):
        self.client.product['offers']['availability'] = 'https://schema.org/OutOfStock'
        self.assertEqual(self.live()[1], 'OUT_OF_STOCK')
        self.assertEqual(self.scan()[1], [])

    def test_either_api_or_storefront_sold_out_blocks(self):
        self.client.api['is_in_stock'] = False
        self.assertEqual(self.live()[1], 'OUT_OF_STOCK')
        self.client.api['is_in_stock'] = True
        self.client.item['s'] = 0
        self.assertEqual(self.live()[1], 'OUT_OF_STOCK')

    def test_live_price_replaces_discovery_price(self):
        self.offer['price'] = '69.99'
        self.assertEqual(self.live()[0]['price'], '104.99')

    def test_inconsistent_prices_do_not_alert(self):
        self.client.product['offers']['price'] = '99.99'
        self.assertEqual(self.live()[1], 'STALE_PRICE')
        self.client.product['offers']['price'] = '104.99'
        self.client.item['p'] = 9999
        self.assertEqual(self.live()[1], 'STALE_PRICE')

    def test_wrong_product_page_and_wrong_cart_id_fail(self):
        self.client.page_id = 999
        self.assertEqual(self.live()[1], 'AMBIGUOUS_VARIANT')
        self.client.page_id = 123
        self.client.api['add_to_cart']['url'] = '/?add-to-cart=999'
        self.assertEqual(self.live()[1], 'NO_CHECKOUT')

    def test_html_encoded_cart_query_preserves_exact_product_id(self):
        self.client.api['add_to_cart']['url'] = '/?check=1&#038;add-to-cart=123'
        self.assertIsNone(self.live()[1])
        self.client.api['add_to_cart']['url'] = 'https://other.test/?add-to-cart=123'
        self.assertEqual(self.live()[1], 'NO_CHECKOUT')

    def test_wrong_language_live_page_cannot_alert(self):
        self.client.api['name'] = self.client.product['name'] = 'Dragon Ball FB11 Display JP'
        self.client.item['n'] = 'FB11 Display JP'
        self.assertEqual(self.scan()[1], [])

    def test_non_purchasable_protected_or_variable_product_fails(self):
        for field,value in [('is_purchasable',False),('has_options',True),('is_password_protected',True),('type','variable')]:
            with self.subTest(field=field):
                old = self.client.api[field]
                self.client.api[field] = value
                self.assertIsNotNone(self.live()[1])
                self.client.api[field] = old
        self.client.item['buy'] = False
        self.assertEqual(self.live()[1], 'NO_CHECKOUT')

    def test_public_script_is_only_json_never_executed(self):
        self.client.extra_script = ';fetch("https://example.test/")'
        with self.assertRaises(ValueError):
            self.live()

    def test_inventory_cache_is_per_batch_but_product_pages_are_fresh(self):
        cache = fast_watch.ProductCache(self.client)
        for _ in range(2):
            self.assertIsNone(yonkai.live(self.offer, SHOP, cache, NOW)[1])
        self.assertEqual(sum('yk_ykp=' in url for url in self.client.calls), 1)
        self.assertEqual(sum(url.startswith(URL) for url in self.client.calls), 2)
        self.assertIsNone(yonkai.live(self.offer, SHOP, fast_watch.ProductCache(self.client), NOW+300)[1])
        self.assertEqual(sum('yk_ykp=' in url for url in self.client.calls), 2)

    def test_catalog_checks_every_page_and_closed_stock_each_time(self):
        self.client.products = [dict(self.client.api, id=i, permalink=SHOP['base_url']+'/produkt/p'+str(i)+'/', is_in_stock=i%2==0) for i in range(1,102)]
        shop = dict(SHOP)
        for _ in range(2):
            rows, warnings = yonkai.scan(shop, self.client)
            self.assertEqual(len(rows), 101)
            self.assertEqual(warnings, [])
            self.assertTrue(shop['_catalog_coverage']['complete'])
            self.assertTrue(any(not r['available'] for r in rows))
        self.assertEqual(len(self.client.calls), 4)

    def test_truncated_or_failed_catalog_is_not_complete(self):
        self.client.products = [dict(self.client.api, id=i, permalink=SHOP['base_url']+'/produkt/p'+str(i)+'/') for i in range(1,101)]
        shop = dict(SHOP, max_pages=1)
        rows, notes = yonkai.scan(shop, self.client)
        self.assertEqual(len(rows), 100)
        self.assertFalse(shop['_catalog_coverage']['complete'])
        self.assertTrue(notes)
        with patch.object(self.client, 'get', side_effect=TimeoutError()):
            self.assertTrue(yonkai.scan(shop, self.client)[1])
            self.assertFalse(shop['_catalog_coverage']['complete'])
