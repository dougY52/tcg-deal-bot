import unittest
from unittest.mock import Mock
from test_market import cfg, offers, state, NOW
from tcg_bot.market import evaluate, normalize, market_payload
from tcg_bot.comparison import enrich
from tcg_bot.__main__ import load_config

class ComparisonTests(unittest.TestCase):
    def config(self):
        c = cfg()
        c['market'].update(automatic_comparison=True, min_comparisons=2, notify_all_shops=True, notify_within_price_range=True)
        c['market']['price_references'] = []
        return c

    def test_preorder_is_orderable_and_labeled(self):
        c=self.config()
        rows=[o | {'preorder': True, 'release_date': '2026-12-01'} for o in offers(('75','79','80'))]
        deals,_,_=evaluate(rows,c,state(),NOW)
        self.assertEqual(len(deals),3)
        embed=market_payload(deals[0])['embeds'][0]
        self.assertIn('Vorbestellung bestellbar',embed['description'])
        self.assertIn('2026-12-01',embed['description'])
        self.assertIn('Normalpreis/UVP unbekannt',embed['fields'][0]['name'])

    def test_unavailable_and_unknown_preorder_never_sent(self):
        for availability in (False,None):
            rows=offers(('75','79','80'))
            rows[0].update(available=availability,preorder=True)
            deals,_,_=evaluate(rows,self.config(),state(),NOW)
            self.assertNotIn(rows[0]['key'],[d['key'] for d in deals])

    def test_auto_reference_does_not_allow_thirty_euro_premium(self):
        deals,_,_=evaluate(offers(('75','79','80','100')),self.config(),state(),NOW)
        self.assertNotIn('3:b15',[d['key'] for d in deals])

    def test_verified_lower_normal_price_wins(self):
        c=self.config(); c['market']['price_references']=cfg()['market']['price_references']
        deals,_,_=evaluate(offers(('140','150','155')),c,state(),NOW)
        self.assertFalse(deals)

    def test_same_owner_and_old_observations_cannot_make_auto_anchor(self):
        c=self.config();s=state();evaluate(offers(('75','79','80')),c,s,NOW)
        self.assertFalse(evaluate(offers(('75',)),c,s,NOW+3600)[0])
        c['shops'][1]['retailer_group']='shop0.example'
        self.assertFalse(evaluate(offers(('75','79','80')),c,state(),NOW)[0])

    def test_search_fetches_details_in_same_run_and_caches_failures(self):
        c=self.config();c['market']['research_max_requests']=2
        rows=offers(('75',));client=Mock();client.deadline=float('inf')
        client.get.side_effect=[{'resources':{'results':{'products':[{'handle':'b15'}]}}},
                               {'handle':'b15','title':rows[0]['title'],'description':'24 Booster original versiegelt',
                                'variants':[{'id':'new','title':'Default Title','price':7900,'available':True}]}]
        s=state(); report=enrich(rows,c,s,client,NOW)
        self.assertEqual(report['requests'],2);self.assertEqual(report['added'],1)
        self.assertEqual(rows[-1]['price'],'79')
        self.assertIn('shop1.example',rows[-1]['url'])
        client.get.side_effect=ValueError('blocked')
        enrich(rows,c,s,client,NOW+1)
        self.assertTrue(s['comparison_searches'])

    def test_watch_handles_survive_loading(self):
        c=load_config('config/config.json')
        lake=next(s for s in c['shops'] if s['id']=='lakecards')
        self.assertTrue(any('attack-on-titan' in h for h in lake['watch_handles']))

    def test_preorder_title_does_not_change_identity(self):
        o=offers()[0];c=self.config()
        self.assertEqual(normalize(o,c)[0]['identity'],normalize(o|{'title':o['title']+' Vorbestellung'},c)[0]['identity'])

    def test_known_normal_price_rechecked_without_raising_it(self):
        c=self.config();c['market']['price_references']=cfg()['market']['price_references']
        c['market']['research_max_requests']=0
        client=Mock();client.deadline=float('inf')
        report=enrich(offers(('75','79','80')),c,state(),client,NOW)
        self.assertEqual(report['normal_prices_rechecked'],1)
        self.assertEqual(c['market']['price_references'][-1]['price_eur'],'75')
        c=self.config();c['market']['price_references']=cfg()['market']['price_references']
        c['market']['research_max_requests']=0
        self.assertEqual(enrich(offers(('140','150','155')),c,state(),client,NOW)['normal_prices_rechecked'],0)

    def test_preorder_notice_in_description_is_not_marked_in_stock(self):
        row,_=normalize(offers()[0]|{'description':'24 Booster. Vorbestellhinweis: Dies ist ein Vorbestellungsprodukt.'},self.config())
        self.assertTrue(row['preorder'])

    def test_dunkelnacht_code_matches_named_preorder(self):
        c=load_config('config/config.json');base=offers()[0]
        a=base|{'title':'Pokémon Dunkelnacht Display DE','description':'36 Booster'}
        b=base|{'title':'Pokémon Mega-Entwicklung Dunkelnacht ME05 Display DE Vorbestellung','description':'36 Booster'}
        self.assertEqual(normalize(a,c)[0]['identity'],normalize(b,c)[0]['identity'])
