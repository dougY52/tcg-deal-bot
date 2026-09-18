import copy
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from tcg_bot.__main__ import load_config, load_state, run, save_state
from tcg_bot.http import FetchError, robots_allowed, send_discord, webhook_url
from tcg_bot.rules import assess, prefer_german, observe, alert_reason, payload
from tcg_bot.sources import parse_product, shopify


def config():
    return {'franchises': {'Pokemon': 'Pokémon'}, 'max_alerts_per_run': 6,
            'restock_cooldown_hours': 6, 'price_drop_eur': 5, 'price_drop_pct': 5,
            'shops': [{'id': 'shop', 'name': 'Shop', 'base_url': 'https://example.org', 'adapter': 'shopify', 'currency': 'EUR', 'max_pages': 1}],
            'references': [{'id': 'test', 'group': 'set-36', 'language': 'DE', 'packs': 36, 'sealed': True,
                            'kind': 'observed_retail', 'retail_eur': '140.00', 'tolerance_pct': 0,
                            'verified_on': '2026-01-01', 'valid_until': '2099-01-01',
                            'title_pattern': '^Pokémon Test Booster Display DE$',
                            'bindings': [{'shop': 'shop', 'handle': 'test', 'variant_id': '42', 'variant_pattern': '^Default Title$'}],
                            'evidence': [{'url': 'https://example.org/products/test', 'note': 'Synthetic fixture'}]}]}


def product():
    return {'handle': 'test', 'title': 'Pokémon Test Booster Display DE', 'body_html': '36 Booster, original versiegelt.',
            'variants': [{'id': 42, 'title': 'Default Title', 'price': '139.99', 'available': True}]}


def offer():
    return parse_product(config()['shops'][0], product())[0]


class RulesTests(unittest.TestCase):
    def test_exact_retail_accepted(self):
        self.assertIsNotNone(assess(offer(), config(), date(2026, 9, 18))[0])

    def test_scalper_excluded(self):
        o = offer(); o['price'] = '140.01'
        self.assertEqual(assess(o, config())[1], 'over_retail')

    def test_no_reference_no_alert(self):
        o = offer(); o['variant_id'] = '43'
        self.assertEqual(assess(o, config())[1], 'missing_reference')

    def test_no_reference_inflation(self):
        c = config(); o = offer(); o['price'] = '500'
        assess(o, c)
        self.assertEqual(c['references'][0]['retail_eur'], '140.00')

    def test_wrong_currency(self):
        o = offer(); o['currency'] = 'USD'
        self.assertEqual(assess(o, config())[1], 'invalid_price')

    def test_expired(self):
        self.assertEqual(assess(offer(), config(), date(2100, 1, 1))[1], 'reference_expired')

    def test_out_of_stock(self):
        o = offer(); o['available'] = False
        self.assertEqual(assess(o, config())[1], 'out_of_stock')

    def test_preorder_description_despite_available(self):
        o = offer(); o['description'] = 'Vorbestellungsprodukt; Versand ab morgen'
        self.assertEqual(assess(o, config())[1], 'preorder_or_uncertain_release')

    def test_japanese_rejected(self):
        o = offer(); o['title'] = 'Pokémon Test Booster Display JP'
        self.assertEqual(assess(o, config())[1], 'language')

    def test_language_conflict(self):
        o = offer(); o['title'] = 'Pokémon Test Booster Display EN'
        self.assertEqual(assess(o, config())[1], 'language_conflict')

    def test_accessories_cases_and_non_booster_displays(self):
        for title in ('Pokémon Acryl Display', 'Pokémon Mini Tin Display DE', 'Pokémon Booster Bundle Display', 'Pokémon Display B-Ware'):
            o = offer(); o['title'] = title
            self.assertEqual(assess(o, config())[1], 'not_sealed_display', title)

    def test_identity_changes(self):
        for field, value in [('title', 'Pokémon Different Booster Display DE'), ('variant', '1 Booster')]:
            o = offer(); o[field] = value
            self.assertEqual(assess(o, config())[1], 'identity_changed')

    def test_variant_price_not_product_minimum(self):
        p = product(); p['variants'].append({'id': 43, 'title': 'Einzelbooster', 'price': '3.50', 'available': True})
        rows = parse_product(config()['shops'][0], p)
        self.assertEqual(rows[0]['price'], '139.99')
        self.assertEqual(assess(rows[1], config())[1], 'missing_reference')

    def test_de_preferred_only_for_same_group(self):
        de = assess(offer(), config())[0]
        en = copy.deepcopy(de); en['language'] = 'EN'; en['key'] = 'other'
        self.assertEqual(prefer_german([en, de]), [de])
        en['reference']['group'] = 'different-set'
        self.assertEqual(len(prefer_german([en, de])), 2)
        self.assertEqual(prefer_german([en]), [en])

    def test_payload_no_ping(self):
        p = payload(assess(offer(), config())[0], 'Neu')
        self.assertEqual(p['allowed_mentions'], {'parse': []})
        self.assertIn('keine UVP', p['embeds'][0]['fields'][0]['name'])


class StateTests(unittest.TestCase):
    def setUp(self):
        self.c = config(); self.o = offer(); self.s = {'version': 1, 'offers': {}}
        observe(self.s, [self.o]); self.d = assess(self.o, self.c)[0]

    def sent(self):
        self.s['offers'][self.o['key']]['sent'] = {'at': 0, 'price': '139.99', 'episode': 0}

    def test_repeat_suppressed(self):
        self.sent()
        self.assertIsNone(alert_reason(self.d, self.s, 100000, self.c))

    def test_real_restock(self):
        self.sent(); o = dict(self.o, available=False); observe(self.s, [o]); observe(self.s, [self.o])
        self.assertEqual(alert_reason(self.d, self.s, 100000, self.c), 'Restock')

    def test_missing_source_is_not_restock(self):
        self.sent(); observe(self.s, []); observe(self.s, [self.o])
        self.assertIsNone(alert_reason(self.d, self.s, 100000, self.c))

    def test_cooldown_keeps_pending_restock(self):
        self.sent(); observe(self.s, [dict(self.o, available=False)]); observe(self.s, [self.o])
        self.assertIsNone(alert_reason(self.d, self.s, 100, self.c))
        observe(self.s, [self.o])
        self.assertEqual(alert_reason(self.d, self.s, 100000, self.c), 'Restock')

    def test_meaningful_price_drop(self):
        self.sent(); self.d['price'] = '138'
        self.assertIsNone(alert_reason(self.d, self.s, 100000, self.c))
        self.d['price'] = '120'
        self.assertEqual(alert_reason(self.d, self.s, 100000, self.c), 'Preis gesunken')

    def test_corrupt_state_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'state.json'; p.write_text('{bad')
            with self.assertRaises(ValueError): load_state(p)

    def test_atomic_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'state.json'; save_state(p, self.s)
            self.assertEqual(load_state(p), self.s)

    def test_failed_send_not_marked_sent(self):
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.o], [])}):
            def fail(_): raise FetchError('test')
            r = run(self.c, self.s, None, send=fail)
        self.assertEqual(r['sent'], 0)
        self.assertNotIn('sent', self.s['offers'][self.o['key']])
        self.assertTrue(r['errors'])

    def test_dry_run_then_send_then_repeat(self):
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.o], [])}):
            r = run(self.c, self.s, None)
            self.assertEqual(len(r['alerts']), 1)
            self.assertNotIn('sent', self.s['offers'][self.o['key']])
            r = run(self.c, self.s, None, send=lambda _: 'message1')
            self.assertEqual(r['sent'], 1)
            r = run(self.c, self.s, None, send=lambda _: self.fail('Duplicate'))
            self.assertEqual(r['sent'], 0)

    def test_all_sources_failed_preserves_stock(self):
        def fail(*_): raise FetchError('offline')
        before = copy.deepcopy(self.s)
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': fail}):
            r = run(self.c, self.s, None)
        self.assertEqual(self.s, before)
        self.assertTrue(r['errors'])


class TransportTests(unittest.TestCase):
    def test_secret_url_validation(self):
        # Synthetic token, never a real secret.
        self.assertTrue(webhook_url('https://discord.com/api/webhooks/123/fake').endswith('?wait=true'))
        for s in ('', 'https://evil.example/api/webhooks/123/fake', 'https://discord.com.evil/api/webhooks/123/fake'):
            with self.assertRaises(ValueError): webhook_url(s)

    def test_robots_longest_match_and_wildcards(self):
        text = 'User-agent: *\nDisallow: /products*\nAllow: /products/good$'
        self.assertFalse(robots_allowed(text, 'https://shop.org/products.json?limit=250'))
        self.assertTrue(robots_allowed(text, 'https://shop.org/products/good'))
        self.assertFalse(robots_allowed(text, 'https://shop.org/products/good-extra'))

    def test_malformed_product_fails_closed(self):
        for price in ('NaN', '-2', 'oops'):
            p = product(); p['variants'][0]['price'] = price
            with self.assertRaises(ValueError): parse_product(config()['shops'][0], p)
        p = product(); p['variants'][0]['available'] = 'true'
        with self.assertRaises(ValueError): parse_product(config()['shops'][0], p)

    def test_pagination_and_exact_watch(self):
        shop = config()['shops'][0] | {'watch_handles': ['test'], 'max_pages': 2}
        class Fake:
            def get(self, url):
                if '/products/test.js' in url:
                    p = product(); p['variants'][0]['price'] = 13999
                    p['description'] = p.pop('body_html')
                    return p
                return {'products': []}
        rows, warnings = shopify(shop, Fake())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['price'], '139.99')
        self.assertTrue(rows[0]['available'])
        self.assertFalse(warnings)

    def test_rate_limit_retry(self):
        error = urllib.error.HTTPError('redacted', 429, '', {}, io.BytesIO(b'{"retry_after": 0}'))
        class Fake:
            calls = 0
            def open(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1: raise error
                return io.BytesIO(b'{"id":"message"}')
        f = Fake()
        with patch('urllib.request.build_opener', return_value=f), patch('time.sleep'):
            self.assertEqual(send_discord('https://discord.com/api/webhooks/123/fake', {}), 'message')
        self.assertEqual(f.calls, 2)

    def test_shipped_config_valid(self):
        load_config('config/config.json')

if __name__ == '__main__':
    unittest.main()
