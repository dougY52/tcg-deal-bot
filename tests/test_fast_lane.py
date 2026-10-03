import copy
import unittest
from unittest.mock import patch
import test_preorders as fixtures
NOW = fixtures.NOW
from tcg_bot import fast_watch as f
from tcg_bot import preorders as p
f_collect = f.collect


class FastLane(unittest.TestCase):
    setUp = fixtures.Preorders.setUp

    def run_fast(self, now=NOW):
        self.state['fast_bootstrapped'] = True
        self.state['retailer_discovery_at'] = now
        if not self.state.get('fast_targets'):
            f.remember([self.offer], self.cfg, self.state, now)
        sent = []
        with patch.object(f, 'collect', side_effect=lambda shops, client, adapters, *args: f_collect(shops, client, adapters, *args) if 'fast_live' in adapters else []):
            report = f.run(self.cfg, self.state, self.client, {}, lambda m: sent.append(m) or 'discord-id', now=now)
        return report, sent

    def stock(self):
        self.client.product['title'] = 'Dragon Ball Fusion World FB04 Ultra Limit Display EN'
        self.client.product['description'] = '24 Booster'
        self.client.product['variants'][0]['price'] = 7999
        self.client.button = '<button>Add to cart</button>'
        self.offer.update(title=self.client.product['title'], description='24 Booster', price='69.99')

    def test_live_price_replaces_search_price(self):
        self.stock()
        report, sent = self.run_fast()
        self.assertEqual(report['sent'], 1)
        self.assertIn('79,99', sent[0]['embeds'][0]['description'])
        self.assertNotIn('69,99', sent[0]['embeds'][0]['description'])

    def test_stale_cheap_price_does_not_qualify(self):
        self.stock()
        self.client.product['variants'][0]['price'] = 15000
        self.assertEqual(self.run_fast()[1], [])

    def test_restock_and_duplicate(self):
        self.stock()
        self.assertEqual(len(self.run_fast()[1]), 1)
        self.assertEqual(self.run_fast(NOW+300)[1], [])
        self.client.product['variants'][0]['available'] = False
        self.assertEqual(self.run_fast(NOW+600)[1], [])
        self.client.product['variants'][0]['available'] = True
        self.assertEqual(len(self.run_fast(NOW+900)[1]), 1)
        records = list(self.state['preorder_products'].values())
        self.assertEqual([h['status'] for h in records[0]['history']], ['in_stock', 'out_of_stock', 'in_stock'])
        self.assertEqual(self.run_fast(NOW+1200)[1], [])

    def test_waitlist_to_preorder(self):
        self.client.button = '<button>Notify me</button>'
        self.assertEqual(self.run_fast()[1], [])
        self.client.button = '<button>Preorder</button>'
        report, sent = self.run_fast(NOW+300)
        self.assertEqual(report['sent'], 1)
        self.assertIn('PREORDER', sent[0]['embeds'][0]['title'])
        self.assertEqual(self.run_fast(NOW+600)[1], [])

    def test_relevant_price_drop(self):
        self.stock()
        self.run_fast()
        self.client.product['variants'][0]['price'] = 7000
        self.assertEqual(len(self.run_fast(NOW+300)[1]), 1)

    def test_false_index_stock_and_wrong_language(self):
        self.client.product['variants'][0]['available'] = False
        self.assertEqual(self.run_fast()[1], [])
        self.client.product['variants'][0]['available'] = True
        self.client.product['title'] = self.client.product['title'].replace(' EN ', ' JP ')
        self.assertEqual(self.run_fast(NOW+300)[1], [])

    def test_duplicate_dispatch_is_no_request_no_alert(self):
        self.run_fast()
        before = len(self.client.urls)
        report, sent = self.run_fast(NOW+20)
        self.assertEqual(sent, [])
        self.assertTrue(report['fast_watch']['skipped_recent_run'])
        self.assertEqual(len(self.client.urls), before)

    def test_failed_delivery_retries_without_dedupe(self):
        self.state.update(fast_bootstrapped=True, retailer_discovery_at=NOW)
        f.remember([self.offer], self.cfg, self.state, NOW)
        with patch.object(f, 'collect', side_effect=lambda shops, client, adapters, *args: f_collect(shops, client, adapters, *args) if 'fast_live' in adapters else []):
            def fail(_):
                raise TimeoutError()
            r=f.run(self.cfg, self.state, self.client, {}, fail, now=NOW)
        self.assertEqual(r['sent'], 0)
        self.assertEqual(len(self.run_fast(NOW+300)[1]), 1)

    def test_future_fb_sets_and_reserved_franchise_slots(self):
        rows=[]
        for i in range(50):
            rows.append(dict(self.offer, key=f'example:{i}', variant_id=str(i), title=f'Dragon Ball Fusion World FB{i+1:02} Display EN'))
        rows.append(dict(self.offer, key='example:p', title='Pokémon Test Top Trainer Box DE'))
        f.remember(rows,self.cfg,self.state,NOW)
        chosen=f.select(self.cfg,self.state)
        self.assertEqual(f.priority(chosen[0]),0)
        self.assertTrue(any(o['key']=='example:p' for o in chosen))
        self.assertIn('example:49',self.state['fast_targets'])

    def test_missing_price_basis_is_silent(self):
        self.cfg['preorder_watch']['user_price_guides']=[]
        self.assertEqual(self.run_fast()[1], [])

    def test_excluded_pokemon_needs_twenty_percent_discount(self):
        self.client.product['title']='Pokémon Wachsendes Chaos Top Trainer Box DE Preorder'
        self.offer['title']=self.client.product['title']
        self.client.product['variants'][0]['price']=6000
        live,_=p.live(self.offer,self.shop,self.client,NOW)
        obj,_=p.identity(live,self.cfg)
        self.cfg['preorder_watch']['price_references']=[dict(comparison_key=obj['comparison_key'],price_eur='60',kind='observed_retail',verified_on='2026-10-03',valid_until='2026-11-03',note='Fixture',evidence_url='https://example.test')]
        self.assertEqual(self.run_fast()[1], [])
        self.client.product['variants'][0]['price']=4700
        self.assertEqual(len(self.run_fast(NOW+300)[1]),1)

    def test_changed_set_on_same_variant_rejected(self):
        self.stock()
        f.remember([self.offer],self.cfg,self.state,NOW)
        self.client.product['title']=self.client.product['title'].replace('FB04','FB02')
        self.assertEqual(self.run_fast()[1], [])

    def test_non_shopify_reference_bootstrap_uses_product_url(self):
        from tcg_bot.__main__ import load_config
        cfg=load_config('config/config.json')
        state={'version':1,'offers':{}}
        f.bootstrap(cfg,state,NOW)
        self.assertIn('sapphire-cards:57145',state['fast_targets'])
        self.assertEqual(f.priority(state['fast_targets']['sapphire-cards:57145']['offer']),0)

    def test_changed_parser_key_keeps_single_watch_target(self):
        f.remember([self.offer],self.cfg,self.state,NOW)
        f.remember([dict(self.offer,key='example:123:new-parser')],self.cfg,self.state,NOW+1)
        self.assertEqual(list(self.state['fast_targets']),[self.offer['key']])
        self.assertEqual(self.state['fast_targets'][self.offer['key']]['offer']['key'],self.offer['key'])

    def test_duplicate_variant_aliases_send_once_in_same_scan(self):
        cfg=copy.deepcopy(self.cfg)
        cfg['_fast_lane']=True
        cfg['_fast_keys']=[self.offer['key'],'alias']
        cfg['_fast_groups']={self.offer['key']:0,'alias':0}
        deals=p.scan([self.offer,dict(self.offer,key='alias')],cfg,self.state,self.client,NOW)[1]
        self.assertEqual(len(deals),1)
