import copy
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from tcg_bot import fast_watch, preorders, stock_watch
from tcg_bot.sources import shopify
from tcg_bot.__main__ import load_config
import test_preorders as fixtures
NOW = fixtures.NOW


def product(n=1, available=True):
    return dict(handle='fb11-' + str(n), title='Dragon Ball FB11 Display EN',
                variants=[dict(id=n, title='Default Title', price='109.99', available=available)])


class CatalogClient:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def get(self, url):
        self.urls.append(url)
        page = int(parse_qs(urlsplit(url).query)['page'][0])
        result = self.pages[page - 1]
        if isinstance(result, Exception):
            raise result
        return {'products': copy.deepcopy(result)}


class StockCatalogTests(unittest.TestCase):
    def setUp(self):
        self.shop = dict(id='test', name='Test', base_url='https://test.invalid',
                         currency='EUR', adapter='shopify', max_pages=40, _stock_scan=True)

    def test_complete_catalog_restarts_page_one_each_run_including_closed_variants(self):
        client = CatalogClient([[product(n, n % 2 == 0) for n in range(250)], [product(250, False)]])
        self.shop.update(_catalog_pages={'https://test.invalid/products.json': 8},
                         rotate_collections=True, catalog_collections=['wrong'], watch_handles=['old'])
        for _ in range(2):
            rows, warnings = shopify(self.shop, client)
            self.assertEqual(len(rows), 251)
            self.assertTrue(any(not row['available'] for row in rows))
            self.assertEqual(warnings, [])
            self.assertTrue(self.shop['_catalog_coverage']['complete'])
        self.assertEqual([parse_qs(urlsplit(u).query)['page'][0] for u in client.urls], ['1','2','1','2'])
        self.assertFalse(any('/collections/' in url or '/old.js' in url for url in client.urls))

    def test_all_feenturm_tcg_collections_each_run_without_toy_catalog(self):
        self.shop['stock_collections'] = ['dragon-ball', 'one-piece-tcg-1', 'pokemon-gesamtes-sortiment']
        client = CatalogClient([[product()]])
        rows, warnings = shopify(self.shop, client)
        self.assertEqual(len(client.urls), 3)
        self.assertTrue(all('/collections/' in u for u in client.urls))
        self.assertTrue(self.shop['_catalog_coverage']['complete'])

    def test_cap_and_error_do_not_claim_complete_inventory(self):
        for second in (TimeoutError(), [product(n + 250) for n in range(250)]):
            self.shop['max_pages'] = 2
            rows, warnings = shopify(self.shop, CatalogClient([[product(n) for n in range(250)], second]))
            self.assertGreaterEqual(len(rows), 250)
            self.assertFalse(self.shop['_catalog_coverage']['complete'])
            self.assertTrue(warnings)

    def test_shipped_shops_and_scope(self):
        cfg = load_config('config/config.json')
        shops = {s['id']: s for s in cfg['shops'] if s.get('stock_watch_each_run')}
        self.assertEqual(set(shops), {'kofuku','feenturm','tcgviert','herbtcg','manaquelle','yonkai-berlin'})
        self.assertEqual(shops['kofuku']['base_url'], 'https://kofuku.de')
        self.assertEqual(len(shops['feenturm']['stock_collections']), 3)
        for sid in ('kofuku','tcgviert','herbtcg'):
            self.assertFalse(shops[sid].get('stock_collections'))

    def test_one_broken_shop_does_not_skip_other_shops(self):
        cfg = load_config('config/config.json')
        def adapter(shop, client):
            if shop['id'] == 'kofuku':
                raise TimeoutError()
            shop['_catalog_coverage'] = dict(complete=True, products=0, endpoints=[])
            return [], []
        _, report = stock_watch.scan(cfg, {}, object(), {'shopify': adapter, 'yonkai': adapter}, NOW)
        self.assertEqual(len(report), 6)
        self.assertEqual(sum(s['complete'] for s in report), 5)
        self.assertEqual(next(s['error'] for s in report if s['shop']=='kofuku'), 'TimeoutError')


class StockPipelineTests(unittest.TestCase):
    setUp = fixtures.Preorders.setUp

    def test_deferred_inventory_variants_move_ahead_of_recent_checks(self):
        first = dict(self.offer, key='example:first')
        second = dict(self.offer, key='example:second')
        self.state['fast_targets'] = {first['key']: {'checked_at': NOW}, second['key']: {'checked_at': NOW-300}}
        chosen = stock_watch.live_targets([first, second], self.cfg, self.state)
        self.assertEqual([o['key'] for o in chosen], [second['key'], first['key']])

    def tick(self, now=NOW, rows=None):
        self.shop['stock_watch_each_run'] = True
        # Discovery is not due and ordinary live quotas are deliberately zero.
        self.cfg['fast_watch']['quotas'] = [0]*6
        self.state.update(fast_bootstrapped=True, fast_catalog_checks={'example': now}, retailer_discovery_at=now)
        offers = [dict(self.offer, available=self.client.product['variants'][0]['available'])] if rows is None else rows
        def adapter(shop, client):
            self.assertTrue(shop['_stock_scan'])
            shop['_catalog_coverage'] = dict(complete=True, endpoints=[], products=len(offers))
            return offers, []
        sent = []
        with patch('tcg_bot.retailer_coverage.check_sources', return_value={}), patch('tcg_bot.retailer_discovery.discover', return_value={}):
            report = fast_watch.run(self.cfg, self.state, self.client, {'shopify': adapter},
                                   send=lambda msg: sent.append(msg) or 'message', now=now)
        return report, sent

    def test_every_run_independent_of_rotation_and_daily_dedupe(self):
        report, sent = self.tick()
        self.assertEqual(len(sent), 1)
        self.assertEqual(report['stock_watch'][0]['live_attempted'], 1)
        self.assertEqual(self.tick(NOW+300)[1], [])
        self.assertTrue(self.tick(NOW+600)[0]['stock_watch'][0]['complete'])

    def test_observed_sold_out_then_restock_gets_one_new_alert(self):
        self.assertEqual(len(self.tick()[1]), 1)
        self.client.product['variants'][0]['available'] = False
        report, sent = self.tick(NOW+300)
        self.assertEqual(sent, [])
        self.assertEqual(report['stock_watch'][0]['live_attempted'], 1)
        self.client.product['variants'][0]['available'] = True
        self.assertEqual(len(self.tick(NOW+600)[1]), 1)
        self.assertEqual(self.tick(NOW+900)[1], [])
        history = next(iter(self.state['preorder_products'].values()))['history']
        self.assertEqual([h['status'] for h in history], ['preorder','out_of_stock','preorder'])

    def test_waitlist_to_checkout(self):
        self.client.button = '<button>Notify me</button>'
        self.assertEqual(self.tick()[1], [])
        self.client.button = '<button>Vorbestellen</button>'
        self.assertEqual(len(self.tick(NOW+300)[1]), 1)
        self.assertEqual(self.tick(NOW+600)[1], [])

    def test_failed_live_negative_never_arms_restock(self):
        self.tick()
        self.client.product['variants'][0]['available'] = False
        self.client.fail = True
        self.assertEqual(self.tick(NOW+300)[1], [])
        self.client.fail = False
        self.client.product['variants'][0]['available'] = True
        self.assertEqual(self.tick(NOW+600)[1], [])

    def test_missing_catalog_row_never_arms_restock(self):
        self.tick()
        self.assertEqual(self.tick(NOW+300, rows=[])[1], [])
        self.assertEqual(self.tick(NOW+600)[1], [])

    def test_catalog_price_never_overrides_live_page(self):
        self.offer['price'] = '69.99'
        report, sent = self.tick()
        self.assertEqual(len(sent), 1)
        self.assertIn('104,99', sent[0]['embeds'][0]['description'])
        self.client.product['variants'][0]['price'] = 19999
        self.assertEqual(self.tick(NOW+300)[1], [])
        self.offer['price'] = '299.99'
        self.client.product['variants'][0]['price'] = 29999
        report, sent = self.tick(NOW+600)
        self.assertEqual(sent, [])
        self.assertEqual(report['stock_watch'][0]['live_attempted'], 1)

    def test_mixed_riftbound_bundle_and_wall_poster_rejected_but_sealed_poster_allowed(self):
        for title in ('Pokemon X CHI Riftbound Bundle: Partner Kollektion DE',
                      'Abysse Pokemon Johto Maxi Poster EN',
                      'One Piece Film Red Collectors Box Panini EN'):
            self.assertIsNone(preorders.identity(dict(self.offer, title=title), self.cfg)[0])
        self.assertIsNotNone(preorders.identity(dict(self.offer, title='Pokémon 30 Jahre Poster Kollektion DE'), self.cfg)[0])

    def test_herb_raffle_cannot_alert_with_visible_cart(self):
        cfg = load_config('config/config.json')
        self.shop['checkout_exclude_pattern'] = next(s['checkout_exclude_pattern'] for s in cfg['shops'] if s['id']=='herbtcg')
        self.client.product['description'] = 'Raffle: Teilnahme an der Verlosung'
        self.assertEqual(self.tick()[1], [])
