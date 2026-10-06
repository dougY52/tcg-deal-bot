import copy
from datetime import datetime, timezone
import unittest
import test_preorders as fixtures
from tcg_bot import preorders as p

NOW = datetime(2026, 10, 6, 17, 30, tzinfo=timezone.utc).timestamp()


class RetailReferences(unittest.TestCase):
    def setUp(self):
        fixtures.Preorders.setUp(self)
        self.cfg['_fast_lane'] = True
        self.cfg['_fast_keys'] = [self.offer['key']]
        self.cfg['_fast_groups'] = {self.offer['key']: 0}
        self.client.product['title'] = 'Dragon Ball Fusion World FB03 Raging Roar Display EN'
        self.client.product['description'] = '24 Booster, English sealed display'
        self.client.product['variants'][0].update(price=7999, barcode='810059786523')
        self.offer.update(title=self.client.product['title'], gtin='810059786523', price='59.99')
        self.client.button = '<button>Add to cart</button>'

    def scan(self, now=NOW):
        return p.scan([self.offer], self.cfg, self.state, self.client, now)

    def test_fresh_7999_offer_no_longer_blocked_by_soldout_5999(self):
        _, deals, report = self.scan()
        self.assertEqual(len(deals), 1, report)
        self.assertEqual(deals[0]['price'], '79.99')
        self.assertEqual(deals[0]['pricing']['baseline'], '85.00')
        self.assertIn('dragonball-fb03-raging-roar-24', deals[0]['comparison_key'])

    def test_reference_transfers_to_new_seller_only_with_matching_barcode(self):
        row, _ = p.identity(self.offer, self.cfg)
        self.assertIsNotNone(p.price_check(row | {'price': '84.99'}, [], self.cfg, NOW))
        row, _ = p.identity(self.offer | {'gtin': '810059787407'}, self.cfg)
        diagnostic = {}
        self.assertIsNone(p.price_check(row | {'price': '84.99'}, [], self.cfg, NOW, diagnostics=diagnostic))
        self.assertEqual(diagnostic['reason'], 'MISSING_PRICE_REFERENCE')

    def test_in_stock_scalper_price_still_rejected(self):
        self.client.product['variants'][0]['price'] = 15000
        _, deals, report = self.scan()
        self.assertEqual(deals, [])
        self.assertEqual(report['rejected']['PRICE_TOO_HIGH'], 1)

    def test_wrong_language_waitlist_soldout_still_rejected(self):
        for field in ('language', 'waitlist', 'soldout'):
            self.setUp()
            if field == 'language':
                self.client.product['title'] = self.client.product['title'].replace(' EN', ' JP')
            elif field == 'waitlist':
                self.client.button = '<button>Notify me</button>'
            else:
                self.client.product['variants'][0]['available'] = False
            self.assertEqual(self.scan()[1], [], field)

    def test_variant_quantity_and_set_conflicts_not_pooled(self):
        ref = next(r for r in self.cfg['references'] if r['id'] == 'dragonball-fb03-raging-roar-24')
        for changes in ({'variant': '1 Booster'}, {'variant': '2 Displays'},
                        {'title': self.offer['title'] + ' 36 Packs'},
                        {'title': self.offer['title'] + ' 2x Display'},
                        {'title': self.offer['title'].replace('FB03', 'FB04')},
                        {'title': self.offer['title'].replace(' EN', ' JP')},
                        {'gtin': ''}):
            self.assertFalse(p.reference_matches(self.offer | changes, ref), changes)

    def test_equivalent_display_variant_uses_same_comparison(self):
        a, _ = p.identity(self.offer, self.cfg)
        b, _ = p.identity(self.offer | {'variant': 'Display', 'shop': 'second'}, self.cfg)
        self.assertEqual(a['comparison_key'], b['comparison_key'])
        self.assertNotEqual(a['product_key'], b['product_key'])

    def test_mapping_does_not_reset_existing_delivery_key(self):
        before, _ = p.identity(self.offer, self.cfg | {'references': []})
        after, _ = p.identity(self.offer, self.cfg)
        self.assertEqual(before['product_key'], after['product_key'])
        _, deals, _ = self.scan()
        p.delivered(self.state, deals[0], NOW, 'message')
        self.assertEqual(self.scan(NOW+300)[1], [])

    def test_expired_reference_is_not_a_price_anchor(self):
        for r in self.cfg['references']:
            r['valid_until'] = '2026-10-05'
        _, deals, report = self.scan()
        self.assertEqual(deals, [])
        self.assertEqual(report['rejected']['MISSING_PRICE_REFERENCE'], 1)

    def test_updated_mapping_keeps_drop_and_restock(self):
        first = self.scan()[1][0]
        p.delivered(self.state, first, NOW, 'first')
        self.client.product['variants'][0]['price'] = 6999
        dropped = self.scan(NOW+300)[1][0]
        p.delivered(self.state, dropped, NOW+300, 'drop')
        self.client.product['variants'][0]['available'] = False
        self.assertEqual(self.scan(NOW+600)[1], [])
        self.client.product['variants'][0]['available'] = True
        self.assertEqual(len(self.scan(NOW+900)[1]), 1)

    def test_past_release_price_guarantee_is_not_an_open_preorder(self):
        self.client.product['description'] = 'Release: 2026-09-04. Dein Vorbestellpreis ist durch unsere Preisgarantie geschützt.'
        row, error = p.live(self.offer, self.shop, self.client, NOW)
        self.assertIsNone(error)
        self.assertFalse(row['preorder_status'])
        self.assertEqual(row['availability_status'], 'in_stock')

    def test_explicit_preorder_button_wins_over_past_release_label(self):
        self.client.product['description'] = 'Release: 2026-09-04. Neue Welle.'
        self.client.button = '<button>Vorbestellen</button>'
        row, error = p.live(self.offer, self.shop, self.client, NOW)
        self.assertIsNone(error)
        self.assertTrue(row['preorder_status'])

    def test_first_offer_is_not_labeled_a_restock(self):
        from tcg_bot.fast_watch import payload
        deal = self.scan()[1][0]
        self.assertIn('ANGEBOT', payload(deal)['embeds'][0]['title'])
        self.assertIn('RESTOCK', payload(deal | {'episode': 1})['embeds'][0]['title'])
