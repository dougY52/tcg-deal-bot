import copy
from datetime import datetime
import unittest
from unittest.mock import patch
import test_preorders as fixtures
from tcg_bot import daily_prices as d, preorders as p, fast_watch as f


class DailyPrices(unittest.TestCase):
    def setUp(self):
        fixtures.Preorders.setUp(self)
        self.cfg['daily_prices']['enabled'] = True
        self.cfg['daily_prices']['discord_enabled'] = True
        self.cfg['daily_prices']['discord_near_retail_only'] = False  # legacy info-mode unit tests
        self.cfg['preorder_watch']['user_price_guides'] = []
        self.cfg['references'] = []
        self.client.product['title'] = 'Dragon Ball Fusion World FB03 Raging Roar Display EN Preorder'
        self.client.product['variants'][0]['price'] = 7999
        self.offer['title'] = self.client.product['title']
        self.cfg['_fast_lane'] = True

    def validate(self, now=fixtures.NOW):
        self.cfg['_fast_keys'] = [self.offer['key']]
        self.cfg['_fast_groups'] = {self.offer['key']: f.priority(self.offer)}
        return p.scan([self.offer], self.cfg, self.state, self.client, now)

    def test_missing_anchor_shown_without_claiming_uvp(self):
        _, deals, _ = self.validate()
        self.assertEqual(deals, [])
        sent = []
        report = d.run(self.cfg, self.state, fixtures.NOW, lambda m: sent.append(m) or 'id')
        self.assertEqual(report['offers_sent'], 1)
        text = sent[0]['embeds'][0]['description']
        self.assertIn('79,99', text)
        self.assertIn('Preisvergleich offen', text)
        self.assertNotIn('104,99', text)

    def test_once_per_berlin_day_and_repeat_next_day(self):
        now = datetime(2026, 10, 5, 23, 58, tzinfo=d.BERLIN).timestamp()
        self.validate(now)
        d.run(self.cfg, self.state, now, lambda _: 'id')
        self.validate(now+30)
        self.assertEqual(d.run(self.cfg, self.state, now+30, lambda _: self.fail('duplicate'))['sent'], 0)
        self.validate(now+180)
        self.assertEqual(d.run(self.cfg, self.state, now+180, lambda _: 'next')['sent'], 1)

    def test_stale_and_failed_validation_never_reuses_price(self):
        self.validate()
        self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW+300), [])
        self.client.fail = True
        self.validate(fixtures.NOW+300)
        self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW+300), [])

    def test_waitlist_soldout_wrong_language_and_scam(self):
        for mode in ('waitlist', 'soldout', 'language', 'scam'):
            with self.subTest(mode=mode):
                self.setUp()
                if mode == 'waitlist':
                    self.client.button = '<button>Notify me</button>'
                elif mode == 'soldout':
                    self.client.product['variants'][0]['available'] = False
                elif mode == 'language':
                    self.client.product['title'] = self.client.product['title'].replace(' EN ', ' JP ')
                else:
                    self.cfg['preorder_watch']['seller_evidence']['Example Cards'] = {'red_flags': ['serious_scam_signal']}
                self.validate()
                self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW), [])

    def test_cap_and_explicit_set_exclusions(self):
        self.client.product['variants'][0]['price'] = 20100
        self.validate()
        self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW), [])
        self.client.product['variants'][0]['price'] = 17999
        self.client.product['title'] = 'Pokémon Wachsendes Chaos ME04 Display DE'
        self.offer['title'] = self.client.product['title']
        self.validate(fixtures.NOW+300)
        self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW), [])

    def test_failed_send_retries_and_dry_run_does_not_mark(self):
        self.validate()
        d.run(self.cfg, self.state, fixtures.NOW)
        self.assertNotIn('daily_price_delivery', self.state)
        def fail(_):
            raise RuntimeError('private')
        report = d.run(self.cfg, self.state, fixtures.NOW, fail)
        self.assertTrue(report['errors'])
        self.assertNotIn('daily_price_delivery', self.state)
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW, lambda _: 'ok')['sent'], 1)

    def test_separate_sellers_and_partial_delivery(self):
        self.validate()
        row = next(iter(self.state['preorder_quotes'].values()))
        other = dict(row, shop='other', seller='Other', shop_name='Other', key='other:123')
        self.cfg['shops'].append(dict(self.shop, id='other', name='Other', base_url='https://other.test'))
        self.cfg['preorder_watch']['trusted_shop_ids'].append('other')
        other, _ = p.identity(other, self.cfg)
        self.state['preorder_quotes'][other['product_key']] = other
        self.cfg['daily_prices']['offers_per_message'] = 1
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW, lambda _: 'one', budget=1)['offers_sent'], 1)
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW, lambda _: 'two')['offers_sent'], 1)

    def test_daily_delivery_does_not_consume_instant_deal_state(self):
        self.validate()
        d.run(self.cfg, self.state, fixtures.NOW, lambda _: 'daily')
        self.assertTrue(all('last_alert' not in r for r in self.state['preorder_products'].values()))

    def test_same_day_instant_alert_not_repeated_as_price_info(self):
        self.validate()
        row = next(iter(self.state['preorder_quotes'].values()))
        self.state['preorder_products'][row['product_key']]['last_alert'] = {'at': fixtures.NOW}
        self.assertEqual(d.eligible(self.cfg, self.state, fixtures.NOW), [])

    def test_fast_watch_integration_sends_live_price(self):
        self.state.update(fast_bootstrapped=True, retailer_discovery_at=fixtures.NOW)
        with patch('tcg_bot.retailer_coverage.check_sources', return_value={}), patch('tcg_bot.retailer_discovery.discover', return_value={}):
            report = f.run(self.cfg, self.state, self.client,
                           {'shopify': lambda *_: ([self.offer], [])},
                           send=lambda _: 'message', now=fixtures.NOW)
        self.assertEqual(report['sent'], 1)
        self.assertEqual(report['daily_prices']['offers_sent'], 1)

    def test_central_overview_does_not_send_discord(self):
        self.cfg['daily_prices']['discord_enabled'] = False
        self.validate()
        report = d.run(self.cfg, self.state, fixtures.NOW, lambda _: self.fail('daily Discord disabled'))
        self.assertEqual(report['sent'], 0)
        self.assertEqual(report['overview_offers'], 1)
        row = next(iter(self.state['daily_price_overview']['offers'].values()))
        self.assertEqual(row['price'], '79.99')
        self.assertEqual(row['validated_at'], fixtures.NOW)

    def test_overview_removes_confirmed_soldout_or_changed_price(self):
        self.cfg['daily_prices']['discord_enabled'] = False
        self.validate()
        d.run(self.cfg, self.state, fixtures.NOW)
        self.client.product['variants'][0]['available'] = False
        self.validate(fixtures.NOW+300)
        d.run(self.cfg, self.state, fixtures.NOW+300)
        self.assertEqual(self.state['daily_price_overview']['offers'], {})

    def test_overview_contains_today_instant_alert_and_daily_reset(self):
        self.validate()
        row = next(iter(self.state['preorder_quotes'].values()))
        self.state['preorder_products'][row['product_key']]['last_alert'] = {'at': fixtures.NOW}
        self.cfg['daily_prices']['discord_enabled'] = False
        d.run(self.cfg, self.state, fixtures.NOW)
        self.assertEqual(len(self.state['daily_price_overview']['offers']), 1)
        d.run(self.cfg, self.state, fixtures.NOW+86400)
        self.assertEqual(self.state['daily_price_overview']['offers'], {})

    def test_near_retail_discord_keeps_unanchored_prices_out(self):
        self.cfg['daily_prices']['discord_near_retail_only'] = True
        self.validate()
        r = d.run(self.cfg, self.state, fixtures.NOW, lambda _: self.fail('unknown price'))
        self.assertEqual(r['sent'], 0)
        self.assertEqual(len(self.state['daily_price_overview']['offers']), 1)

    def test_near_retail_discord_sent_once_but_real_drop_realerts(self):
        self.cfg['daily_prices']['discord_near_retail_only'] = True
        self.cfg['preorder_watch']['user_price_guides'] = [{
            'franchise': 'Dragon Ball', 'set_code': 'FB03', 'language': 'EN',
            'ceiling_eur': '85', 'verified_on': '2026-10-03',
            'valid_until': '2026-11-03', 'source': 'test'
        }]
        self.validate()
        reports = []
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW, lambda x: reports.append(x) or 'one')['offers_sent'], 1)
        self.assertIn('Nahe Retail', reports[0]['embeds'][0]['title'])
        self.validate(fixtures.NOW + 86400)
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW + 86400, lambda _: self.fail('duplicate'))['sent'], 0)
        self.client.product['variants'][0]['price'] = 7000
        self.validate(fixtures.NOW + 86400 + 300)
        self.assertEqual(d.run(self.cfg, self.state, fixtures.NOW + 86400 + 300, lambda _: 'new')['offers_sent'], 1)

    def test_discord_length_and_mentions(self):
        self.validate()
        row = next(iter(self.state['preorder_quotes'].values()))
        self.assertLess(len(d.message([row]*4, fixtures.NOW)['embeds'][0]['description']), 4096)
        self.assertEqual(d.message([row], fixtures.NOW)['allowed_mentions'], {'parse': []})


if __name__ == '__main__':
    unittest.main()
