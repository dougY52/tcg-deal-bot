import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tcg_bot import preorders as p
from tcg_bot.__main__ import load_config, run, load_state, save_state

NOW = 1791021600  # 2026-10-03 UTC


class Client:
    def __init__(self):
        self.product = {'handle': 'fb11', 'title': 'Dragon Ball Fusion World FB11 Brightness of Hope Display EN Preorder',
                        'description': 'Release: 2026-10-16', 'variants': [
                            {'id': 123, 'title': 'Default Title', 'price': 10499, 'available': True, 'barcode': '1234567890123'}]}
        self.button = '<button type="submit">Vorbestellen</button>'
        self.form_id = '123'
        self.fail = False
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        if self.fail:
            raise TimeoutError()
        if '/cart.js?' in url:
            return {'currency': 'EUR'}
        return copy.deepcopy(self.product)

    def text(self, url):
        self.urls.append(url)
        return '<script>Shopify.currency = {"active":"EUR"};</script><form action="/cart/add" method="post"><input name="id" value="' + self.form_id + '">' + self.button + '</form>'


class Preorders(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config('config/config.json')
        self.shop = {'id': 'example', 'name': 'Example Cards', 'base_url': 'https://example.test', 'adapter': 'shopify', 'currency': 'EUR', 'max_pages': 1}
        self.cfg['shops'] = [self.shop]
        self.cfg['preorder_watch']['trusted_shop_ids'] = ['example']
        self.cfg['market']['automatic_comparison'] = False
        self.client = Client()
        self.offer = {'key': 'example:123', 'shop': 'example', 'shop_name': 'Example Cards', 'seller': 'Example Cards',
                      'seller_verified': True, 'title': self.client.product['title'], 'description': '', 'variant': 'Default Title',
                      'price': '104.99', 'available': True, 'currency': 'EUR', 'handle': 'fb11', 'variant_id': '123',
                      'url': 'https://example.test/products/fb11?variant=123', 'gtin': '1234567890123'}
        self.state = {'version': 1, 'offers': {}}

    def scan(self, now=NOW):
        return p.scan([self.offer], self.cfg, self.state, self.client, now)

    def sent(self):
        d = self.scan()[1][0]
        p.delivered(self.state, d, NOW, 'message')
        return d

    def rejected(self, reason):
        ordinary, deals, report = self.scan()
        self.assertEqual(ordinary, [])
        self.assertEqual(deals, [])
        self.assertEqual(report['rejected'].get(reason), 1, report)

    def test_preorder_cart_alert(self):
        d = self.scan()[1][0]
        self.assertEqual(d['language'], 'EN')
        self.assertTrue(d['add_to_cart_available'])
        self.assertEqual(d['release_date'], '2026-10-16')
        self.assertIn('PREORDER LIVE', p.payload(d)['embeds'][0]['title'])
        self.assertTrue(all('_preorder_check=' in u for u in self.client.urls))

    def test_waitlist(self):
        self.client.button = '<button>Waitlist</button>'
        self.rejected('WAITLIST')

    def test_notify_me(self):
        self.client.button = '<button>Notify me</button>'
        self.rejected('WAITLIST')

    def test_search_stock_but_live_soldout(self):
        self.client.product['variants'][0]['available'] = False
        self.rejected('OUT_OF_STOCK')

    def test_wrong_language(self):
        self.client.product['title'] = self.client.product['title'].replace(' EN ', ' DE ')
        self.rejected('WRONG_LANGUAGE')

    def test_duplicate(self):
        self.sent()
        self.rejected('DUPLICATE')

    def test_price_drop(self):
        self.sent()
        self.client.product['variants'][0]['price'] = 9900
        self.assertEqual(len(self.scan(NOW+60)[1]), 1)

    def test_price_increase_or_tiny_drop_not_new(self):
        self.sent()
        for price in (10400, 11000):
            self.client.product['variants'][0]['price'] = price
            self.rejected('DUPLICATE')

    def test_out_of_stock_reopens(self):
        self.sent()
        self.client.product['variants'][0]['available'] = False
        self.scan(NOW+60)
        self.client.product['variants'][0]['available'] = True
        d = self.scan(NOW+120)[1][0]
        self.assertEqual(d['episode'], 1)
        self.assertEqual([x['status'] for x in self.state['preorder_products'][d['product_key']]['history']], ['preorder', 'out_of_stock', 'preorder'])

    def test_unknown_scam(self):
        self.cfg['preorder_watch']['seller_evidence']['Example Cards'] = {'red_flags': ['serious_scam_signal']}
        self.rejected('SELLER_RISK')

    def test_marketplace_reputable_seller(self):
        self.offer['seller'] = 'Reviewed Marketplace Seller'
        self.cfg['preorder_watch']['seller_evidence'][self.offer['seller']] = {
            'legal_entity_verified': True, 'buyer_protection': True, 'review_count': 300,
            'rating': 4.8, 'evidence_url': 'https://example.test/seller/history'}
        self.assertIsNotNone(p.seller_confidence(self.offer, self.shop, self.cfg['preorder_watch']))

    def test_unknown_without_evidence(self):
        self.cfg['preorder_watch']['trusted_shop_ids'] = []
        self.rejected('SELLER_RISK')

    def test_sapphire_ambiguous_variant(self):
        self.shop['id'] = self.offer['shop'] = 'sapphire-cards'
        self.cfg['preorder_watch']['trusted_shop_ids'] = ['sapphire-cards']
        self.client.form_id = '456'
        self.rejected('AMBIGUOUS_VARIANT')

    def test_galeria_visible_button_no_cart_confirmation(self):
        self.shop['id'] = self.offer['shop'] = 'galeria'
        self.cfg['preorder_watch']['trusted_shop_ids'] = ['galeria']
        self.rejected('NO_CHECKOUT')

    def test_disabled_button(self):
        self.client.button = '<button disabled>Vorbestellen</button>'
        self.rejected('NO_CHECKOUT')

    def test_timeout_not_restock(self):
        self.sent()
        self.client.fail = True
        self.scan(NOW+60)
        self.client.fail = False
        self.rejected('DUPLICATE')

    def test_expensive_unverified_rejected(self):
        self.client.product['variants'][0]['price'] = 15000
        self.rejected('PRICE_TOO_HIGH')

    def test_tins_preorders_allowed_without_changing_deals(self):
        self.client.product['title'] = 'Pokémon Premium Tin Deutsch Vorbestellung'
        row, _ = p.live(self.offer, self.shop, self.client, NOW)
        obj, error = p.identity(row, self.cfg)
        self.assertIsNone(error)
        self.assertEqual(obj['product_type'], 'tin')
        self.assertNotIn('tin', self.cfg['market']['allowed_product_types'])

    def test_pokemon_english_rejected(self):
        self.client.product['title'] = 'Pokémon ETB English Preorder'
        self.rejected('WRONG_LANGUAGE')

    def test_heroes_excluded(self):
        self.client.product['title'] += ' Super Dragon Ball Heroes'
        self.rejected('CONTENT_EXCLUDED')

    def test_send_failure_retry_and_persistence(self):
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.offer], [])}):
            failed = run(self.cfg, self.state, self.client, send=lambda _: (_ for _ in ()).throw(RuntimeError()), now=NOW)
            self.assertEqual(failed['sent'], 0)
            sent = run(self.cfg, self.state, self.client, send=lambda _: 'discord-id', now=NOW+60)
            self.assertEqual(sent['preorder_watch']['sent'], 1)
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                file = Path(d) / 'state.json'
                save_state(file, self.state)
                self.state = load_state(file)
            repeat = run(self.cfg, self.state, self.client, send=lambda _: self.fail('duplicate'), now=NOW+120)
            self.assertEqual(repeat['sent'], 0)

    def test_dry_run_does_not_mark_sent(self):
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.offer], [])}):
            preview = run(self.cfg, self.state, self.client, now=NOW)
            self.assertEqual(len(preview['alerts']), 1)
            self.assertEqual(len(self.scan()[1]), 1)

    def test_rejected_preorder_does_not_bypass_via_deal_lane(self):
        self.client.product['variants'][0]['available'] = False
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.offer], [])}):
            r = run(self.cfg, self.state, self.client, send=lambda _: self.fail('invalid alert'), now=NOW)
            self.assertEqual(r['alerts'], [])

    def test_alert_budget_keeps_pending(self):
        self.cfg['max_alerts_per_run'] = 1
        other = dict(self.offer, key='example:456', variant_id='456')
        other_deal = dict(self.scan()[1][0], key=other['key'], product_key='second')
        first_deal = self.scan()[1][0]
        self.state['preorder_products']['second'] = {'history': [], 'episode': 0}
        with patch('tcg_bot.__main__.ADAPTERS', {'shopify': lambda *_: ([self.offer], [])}), patch('tcg_bot.preorders.scan', return_value=([], [first_deal, other_deal], {'sent': 0})):
            r = run(self.cfg, self.state, self.client, send=lambda _: 'id', now=NOW)
        self.assertEqual(r['pending_alerts'], 1)
        self.assertNotIn('last_alert', self.state['preorder_products']['second'])

    def test_title_change_does_not_duplicate(self):
        self.sent()
        self.client.product['title'] += ' jetzt neu'
        self.rejected('DUPLICATE')

    def test_waitlist_becomes_real_checkout(self):
        self.client.button = '<button>Notify me</button>'
        self.scan()
        self.client.button = '<button>Vorbestellen</button>'
        self.assertEqual(len(self.scan(NOW+60)[1]), 1)

    def test_variant_id_available_but_other_form_selected(self):
        self.client.form_id = '987'
        self.rejected('AMBIGUOUS_VARIANT')

    def test_disabled_soldout_overrides_catalog(self):
        self.client.button = '<button disabled>Sold out</button>'
        self.rejected('OUT_OF_STOCK')

    def test_three_price_peers_exact_identity(self):
        obj = self.scan()[1][0]
        obj['price'] = '125'
        peers = [dict(obj, price=str(x), retailer_group=str(i)) for i,x in enumerate((125,130,140))]
        self.assertIsNotNone(p.price_check(obj, peers, self.cfg, NOW))
        peers[2]['comparison_key'] = 'other-product'
        self.assertIsNone(p.price_check(obj, peers, self.cfg, NOW))

    def test_no_double_vote_same_retailer(self):
        obj = self.scan()[1][0]
        obj['price'] = '125'
        peers = [dict(obj, price='130', retailer_group='same') for _ in range(3)]
        self.assertIsNone(p.price_check(obj, peers, self.cfg, NOW))

    def test_previous_deal_delivery_migrated(self):
        self.state['market_offer_sent'] = {'legacy': {'at': NOW-100, 'offer': self.offer['key'], 'price': '104.99', 'episode': 0}}
        self.rejected('DUPLICATE')

    def test_price_cap_still_applies_with_high_reference(self):
        self.cfg['preorder_watch']['user_price_guides'][2]['ceiling_eur'] = '400'
        self.client.product['variants'][0]['price'] = 35000
        self.rejected('PRICE_TOO_HIGH')

    def test_quote_expires(self):
        self.scan()
        self.client.fail = True
        self.scan(NOW+1801)
        self.assertEqual(self.state['preorder_quotes'], {})

    def test_unsupported_non_shopify_is_silent(self):
        self.shop['adapter'] = 'html_catalog'
        self.rejected('UNSUPPORTED_LIVE_CHECK')

    def test_live_stock_returns_to_ordinary_lane(self):
        self.client.product['title'] = self.client.product['title'].replace(' Preorder', '')
        self.client.product['description'] = ''
        self.client.button = '<button>Add to cart</button>'
        ordinary, deals, _ = self.scan()
        self.assertEqual(len(ordinary), 1)
        self.assertFalse(p.candidate(ordinary[0]))
        self.assertEqual(deals, [])

    def test_unrelated_ordinary_offer_preserved(self):
        ordinary = dict(self.offer, title='Dragon Ball BT15 Display EN', key='ordinary:1')
        rows, deals, _ = p.scan([ordinary], self.cfg, self.state, self.client, NOW)
        self.assertEqual(rows, [ordinary])
        self.assertEqual(deals, [])

    def test_non_eur_storefront_rejected(self):
        original = self.client.text
        self.client.text = lambda u: original(u).replace('EUR', 'USD')
        self.rejected('CURRENCY_UNCONFIRMED')

    def test_bare_button_without_variant_is_not_enough(self):
        original = self.client.text
        self.client.text = lambda u: original(u).replace('name="id"', 'name="other"')
        self.rejected('AMBIGUOUS_VARIANT')

    def test_one_piece_deck_sets(self):
        self.client.product['title'] = 'One Piece Deck Set EN Preorder'
        obj, error = p.identity(dict(self.offer, title=self.client.product['title']), self.cfg)
        self.assertIsNone(error)
        self.assertEqual(obj['product_type'], 'deck_set')


if __name__ == '__main__':
    unittest.main()
