import unittest
from unittest.mock import patch
from test_bot import config, offer
from tcg_bot.discovery import discovery, discovery_payload
from tcg_bot.__main__ import run

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.cfg['franchises']['Dragon Ball'] = 'dragon ball'
        self.cfg['discoveries'] = {'enabled': True, 'max_per_run': 10}
        self.row = offer() | {'key': 'shop:99', 'variant_id': '99', 'handle': 'fb10', 'title': 'Dragon Ball FB10 Booster Display EN'}

    def check(self, state, rows=None, send=lambda p: 'message'):
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda s,c: (rows or [self.row], [])}):
            return run(self.cfg, state, None, send=send, now=1000)

    def test_new_available_fb10_and_repeat(self):
        state = {'version': 1, 'offers': {}}
        self.assertEqual(self.check(state)['discovery_sent'], 1)
        self.assertEqual(self.check(state)['discovery_sent'], 0)
        self.assertNotIn('sent', state['offers']['shop:99'])
        payload = discovery_payload(discovery(self.row, self.cfg))
        self.assertIn('Kein bestätigtes Schnäppchen', payload['embeds'][0]['description'])
        self.assertEqual(payload['allowed_mentions']['parse'], [])

    def test_unavailable_unknown_rejected_preorders_allowed(self):
        for change in [{'available': False}, {'available': None}]:
            self.assertIsNone(discovery(self.row | change, self.cfg))
        for change in [{'preorder': True}, {'description': 'Vorbestellung'}]:
            self.assertIn('Vorbestellung', discovery(self.row | change, self.cfg)['discovery_status'])
            self.assertIsNone(discovery(self.row | change | {'available': False}, self.cfg))
        state = {'version': 1, 'offers': {}}
        self.assertEqual(self.check(state, [self.row | {'available': False}])['discovery_sent'], 0)
        self.assertEqual(self.check(state)['discovery_sent'], 1)

    def test_safety_filters(self):
        for changes in [{'title': 'Dragon Ball FB10 Acrylic Display Case EN'}, {'title': 'Dragon Ball FB10 Display JP'}, {'title': 'Dragon Ball FB10 Display'}, {'seller_verified': False}, {'discovery_only': True}, {'price': 'NaN'}, {'currency': 'USD'}]:
            self.assertIsNone(discovery(self.row | changes, self.cfg))
        self.assertIsNone(discovery(offer() | {'price': '999'}, self.cfg))

    def test_existing_state_baseline(self):
        state = {'version': 1, 'offers': {'shop:99': {'episode': 0, 'available': True}}}
        self.assertEqual(self.check(state)['discovery_sent'], 0)

    def test_failure_preview_retry(self):
        state = {'version': 1, 'offers': {}}
        self.check(state, send=None)
        self.assertNotIn('shop:99', state['discovery_seen'])
        def fail(p): raise RuntimeError('failure')
        self.assertTrue(self.check(state, send=fail)['errors'])
        self.assertNotIn('shop:99', state['discovery_seen'])
        self.assertEqual(self.check(state)['discovery_sent'], 1)

    def test_limit_and_future_retail_alert(self):
        self.cfg['discoveries']['max_per_run'] = 1
        state = {'version': 1, 'offers': {}}
        rows = [self.row, self.row | {'key': 'shop:100', 'variant_id': '100'}]
        self.assertEqual(self.check(state, rows)['discovery_pending'], 1)
        self.assertEqual(self.check(state, rows)['discovery_sent'], 1)
        self.assertEqual(self.check(state, rows)['discovery_sent'], 0)
        ref = self.cfg['references'][0]
        ref['title_pattern'] = 'Dragon Ball FB10'; ref['language'] = 'EN'
        ref['bindings'][0].update(handle='fb10', variant_id='99')
        report = self.check(state)
        self.assertEqual(report['sent'], 1)
        self.assertEqual(report['discovery_sent'], 0)

    def test_live_opening_and_deck_displays_are_not_sealed_booster_displays(self):
        for title in ['LIVESTREAM Dragon Ball FB10 Display EN', 'Dragon Ball Rip and Ship Booster Box EN', 'Digimon Starter Deck Display EN', 'Pokemon Theme Deck Display DE']:
            self.assertIsNone(discovery(self.row | {'title': title}, self.cfg))
        self.assertIsNotNone(discovery(self.row, self.cfg))
