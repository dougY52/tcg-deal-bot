import copy
from datetime import date, timedelta
import json
import unittest

from tcg_bot.rules import assess, gtin_key, observe
from tcg_bot.web_sources import parse_mms, parse_otto, parse_structured, identifier
from test_bot import config, offer


def shop(market=False):
    return {'id': 'shop', 'name': 'Example', 'base_url': 'https://example.org', 'marketplace': market, 'allowed_sellers': ['Example']}


def mms_body(market=False, stock='AVAILABLE', store=None, regional=False):
    data = {'productAggregate': {'product': {'id': '42', 'title': 'Pokémon Test Booster Display DE', 'ean': '0196214107908'}},
            'cofrProductAggregate': {
                'cofrPriceFeature': {'isProductOfTypeMarketplace': market, 'currency': 'EUR',
                                    'price': {'amount': 139.99}, 'marketplaceSeller': {'sellerName': 'Unknown Seller'} if market else None},
                'cofrDeliveryFeature': {'delivery': {'deliveryStatus': stock, 'isZipCodeCheckNeeded': regional}},
                'cofrPickupFeature': {'storeId': store, 'isProductPickable': True, 'pickupStatus': 'NO_STORE_SELECTED'},
                'cofrOnlineStatusFeature': {}}}
    return '<script>window.__PRELOADED_STATE__ = ' + json.dumps({'routerHydrationData': {'loaderData': {'route': {'data': data}}}}) + ';</script>'


class WebSourceTests(unittest.TestCase):
    def test_mms_own_sale_stock(self):
        row = parse_mms(shop(True), mms_body(), 'https://example.org/item')[0]
        self.assertTrue(row['available'])
        self.assertTrue(row['seller_verified'])
        self.assertEqual(row['seller'], 'Example')

    def test_marketplace_seller_not_retailer(self):
        row = parse_mms(shop(True), mms_body(market=True), 'https://example.org/item')[0]
        self.assertEqual(row['seller'], 'Unknown Seller')
        self.assertFalse(row['seller_verified'])

    def test_no_selected_store_is_not_local_stock(self):
        row = parse_mms(shop(True), mms_body(stock='NOT_AVAILABLE'), 'https://example.org/item?storeId=123')[0]
        self.assertFalse(row['available'])
        self.assertIsNone(row['store_id'])
        self.assertEqual(row['store_status'], 'selection_required')
        self.assertEqual(row['channel'], 'online')

    def test_region_dependent_or_unknown_status_is_unknown(self):
        for body in (mms_body(regional=True), mms_body(stock='NEW_UNKNOWN_STATUS')):
            self.assertIsNone(parse_mms(shop(True), body, 'https://example.org/item')[0]['available'])

    def test_mms_never_evaluates_javascript(self):
        with self.assertRaises(ValueError):
            parse_mms(shop(), '<script>window.__PRELOADED_STATE__ = alert(1);</script>', 'https://example.org/item')

    def test_microdata_explicit_stock(self):
        body = '''<div itemscope itemtype="https://schema.org/Product">
        <span itemprop="name">Pokémon Display DE</span><meta itemprop="sku" content="42">
        <meta itemprop="url" content="https://example.org/item"><meta itemprop="price" content="100.00">
        <meta itemprop="priceCurrency" content="EUR"><link itemprop="availability" href="https://schema.org/InStock"></div>'''
        rows, _ = parse_structured(shop(), body, 'https://example.org/item')
        self.assertTrue(rows[0]['available'])
        self.assertEqual(rows[0]['price'], '100.00')
        self.assertEqual(rows[0]['variant_id'], '42')

    def test_jsonld_aggregate_low_price_is_not_offer(self):
        p = {'@type': 'Product', 'name': 'Pokemon Display', 'offers': {'@type': 'AggregateOffer', 'lowPrice': 5, 'priceCurrency': 'EUR'}}
        rows, _ = parse_structured(shop(), '<script type="application/ld+json">'+json.dumps(p)+'</script>', 'https://example.org/item')
        self.assertFalse(rows)

    def test_jsonld_unknown_stock_never_means_out_of_stock(self):
        p = {'@type': 'Product', 'name': 'Pokemon Display', 'offers': {'price': 100, 'priceCurrency': 'EUR'}}
        rows, _ = parse_structured(shop(), '<script type="application/ld+json">'+json.dumps(p)+'</script>', 'https://example.org/item')
        self.assertIsNone(rows[0]['available'])
        state = {'offers': {rows[0]['key']: {'episode': 0, 'available': True}}}
        observe(state, rows)
        self.assertTrue(state['offers'][rows[0]['key']]['available'])

    def test_physical_offer_never_claims_online_stock(self):
        p = {'@type': 'Product', 'name': 'Pokemon Display', 'offers': {'price': 100, 'priceCurrency': 'EUR',
            'availability': 'https://schema.org/InStock', 'availableAtOrFrom': {'@type': 'Place', 'name': 'Store A'}}}
        rows, _ = parse_structured(shop(), '<script type="application/ld+json">'+json.dumps(p)+'</script>', 'https://example.org/item')
        self.assertIsNone(rows[0]['available'])

    def test_preorder_schema(self):
        p = {'@type': 'Product', 'name': 'Pokemon Display', 'offers': {'price': 100, 'priceCurrency': 'EUR', 'availability': 'https://schema.org/PreOrder'}}
        rows, _ = parse_structured(shop(), '<script type="application/ld+json">'+json.dumps(p)+'</script>', 'https://example.org/item')
        self.assertTrue(rows[0]['preorder'])
        self.assertTrue(rows[0]['available'])

    def test_otto_instalments_and_starting_prices(self):
        exact = {'price': {'retailPrice': '119,90', 'isStartingPrice': False, 'installmentPlan': {'amount': 10.95}},
                 'availability': {'state': 'AVAILABLE'}, 'title': {'full': 'Pokemon Display DE'},
                 'variationId': 'S123', 'detailPageLink': '/p/item/?variationId=S123'}
        starting = copy.deepcopy(exact); starting['price']['isStartingPrice'] = True
        raw = {'tileListItems': [{'variations': [exact, starting]}]}
        rows = parse_otto(shop(True), '<main id="reptile-content">'+json.dumps(raw)+'</main>')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['price'], '119.90')
        self.assertTrue(rows[0]['discovery_only'])
        self.assertFalse(rows[0]['seller_verified'])

    def test_variant_urls_have_distinct_identity(self):
        self.assertNotEqual(identifier('https://example.org/item?v=1'), identifier('https://example.org/item?v=2'))

    def test_gtin_checksum_and_zero_padding(self):
        self.assertEqual(gtin_key('0196214107908'), gtin_key('196214107908'))
        self.assertIsNone(gtin_key('0196214107909'))
        self.assertIsNone(gtin_key('123'))

    def test_gtin_exact_cross_shop_match(self):
        cfg = config(); cfg['references'][0]['gtins'] = ['0196214107908']
        o = offer(); o.update(shop='new-shop', handle='other', variant_id='55', gtin='196214107908', seller_verified=True)
        self.assertIsNotNone(assess(o, cfg)[0])
        o['gtin'] = '0196214107909'
        self.assertEqual(assess(o, cfg)[1], 'missing_reference')

    def test_marketplace_and_unknown_stock_fail_closed(self):
        for overrides, reason in [({'seller_verified': False}, 'seller_unverified'), ({'available': None}, 'availability_unknown'), ({'discovery_only': True}, 'discovery_only')]:
            self.assertEqual(assess(offer() | overrides, config())[1], reason)

    def test_explicit_etb_reference(self):
        o = offer(); o['title'] = 'Pokémon Test Top-Trainer-Box DE'
        cfg = config(); cfg['references'][0].update(product_kind='etb', title_pattern='Top-Trainer-Box')
        self.assertIsNotNone(assess(o, cfg)[0])

if __name__ == '__main__': unittest.main()
