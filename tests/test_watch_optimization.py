import copy
import unittest
from tcg_bot import fast_watch as f, preorders as p, price_comparison as pc
from tcg_bot.__main__ import load_config
import test_preorders as fixtures
from test_cardmarket_prices import offer

TODAY=1793001600
NOW=fixtures.NOW


class WatchOptimization(unittest.TestCase):
    setUp=fixtures.Preorders.setUp

    def test_broken_url_backoff_and_retry(self):
        f.remember([self.offer],self.cfg,self.state,NOW)
        f.record_fetch(self.state,{self.offer['key']:(None,'LIVE_CHECK_FAILED_HTTP_404')},NOW)
        self.assertFalse(f.select(self.cfg,self.state,NOW+300))
        self.assertEqual(len(f.select(self.cfg,self.state,NOW+900)),1)
        f.record_fetch(self.state,{self.offer['key']:(None,'LIVE_CHECK_FAILED_HTTP_404')},NOW+900)
        self.assertEqual(self.state['fast_targets'][self.offer['key']]['retry_after'],NOW+2700)

    def test_unchanged_catalog_does_not_cancel_backoff(self):
        f.remember([self.offer],self.cfg,self.state,NOW)
        f.record_fetch(self.state,{self.offer['key']:(None,'LIVE_CHECK_FAILED_HTTP_404')},NOW)
        f.remember([self.offer],self.cfg,self.state,NOW+300)
        self.assertFalse(f.select(self.cfg,self.state,NOW+300))

    def test_changed_catalog_retries_immediately(self):
        f.remember([self.offer],self.cfg,self.state,NOW)
        f.record_fetch(self.state,{self.offer['key']:(None,'LIVE_CHECK_FAILED_HTTP_404')},NOW)
        f.remember([self.offer|{'price':'99'}],self.cfg,self.state,NOW+300)
        self.assertEqual(len(f.select(self.cfg,self.state,NOW+300)),1)

    def test_stock_waitlist_and_budget_do_not_arm_backoff(self):
        for row,error in [({'available':False},'OUT_OF_STOCK'),({'available':False},'WAITLIST'),
                          (None,'LIVE_CHECK_FAILED_Run_request_budget_exhausted'),(None,'LIVE_CHECK_FAILED_TimeoutError')]:
            with self.subTest(error=error):
                f.remember([self.offer],self.cfg,self.state,NOW)
                f.record_fetch(self.state,{self.offer['key']:(row,error)},NOW)
                self.assertEqual(len(f.select(self.cfg,self.state,NOW+300)),1)

    def test_success_clears_error_without_changing_alert_state(self):
        f.remember([self.offer],self.cfg,self.state,NOW)
        self.state['preorder_products']={'existing':{'episode':7,'last_alert':{'at':NOW}}}
        old=copy.deepcopy(self.state['preorder_products'])
        f.record_fetch(self.state,{self.offer['key']:(None,'LIVE_CHECK_FAILED_HTTP_404')},NOW)
        f.record_fetch(self.state,{self.offer['key']:({'available':True},None)},NOW+900)
        self.assertNotIn('retry_after',self.state['fast_targets'][self.offer['key']])
        self.assertEqual(self.state['preorder_products'],old)

    def test_livebreak_and_loose_contents_rejected(self):
        for title,variant in [('Pokémon 30 Jahre Poster Kollektion DE','Livebreak'),
                              ('Pokemon Mega Kräfte Tin DE','Stream Opening'),
                              ('45 Pokémon Energie-Karten aus ETB/TTB DE','Default Title'),
                              ('50 Pokémon Karten Common/Uncommon deutsch in Mini Tin','Default Title'),
                              ('Pokemon 151 Poster beidseitig DE','Default Title')]:
            with self.subTest(title=title):
                o=self.offer|dict(title=title,variant=variant)
                self.assertEqual(p.identity(o,self.cfg)[1],'UNSUPPORTED_PRODUCT')
                self.assertIsNone(pc.match_product(o,self.cfg))
                self.state['fast_targets']={o['key']:{'offer':o}}
                self.assertFalse(f.select(self.cfg,self.state,NOW))

    def test_real_sealed_products_remain_eligible(self):
        for title in ['Pokémon 30 Jahre Poster Kollektion DE','Pokémon Mega Kräfte Tin DE']:
            self.assertIsNone(p.identity(self.offer|{'title':title},self.cfg)[1])

    def test_new_retail_evidence_qualifies_real_box(self):
        o=offer('Pokémon Mega Quajutsu ex Premium Kollektion DE',price='42.99',packs=8)
        o.update(gtin='0196214141971')
        row,reason=p.identity(o,self.cfg)
        self.assertIsNone(reason)
        self.assertEqual(pc.assess(row,self.cfg,{},TODAY)['code'],'retail_deal')
        self.assertIsNotNone(p.price_check(row,[],self.cfg,TODAY))
        # Higher observations must not authorize a price above verified retail.
        history=[{'retail_observation':dict(at=TODAY,price='60',comparison_key=row['comparison_key'])}]
        self.assertIsNone(p.price_check(row|{'price':'60'},[],self.cfg,TODAY,history))

    def test_new_reference_cannot_cross_barcode_language_or_variant(self):
        o=offer('Pokémon Mega Quajutsu ex Premium Kollektion DE',price='42.99',packs=8)|{'gtin':'0196214141971'}
        for changed in [{'gtin':'196214141803'},{'variant':'Livebreak'}, {'title':o['title'].replace('DE','EN')}]:
            self.assertIsNone(pc.retail_reference(o|changed,self.cfg,TODAY))

    def test_exact_catalogue_identity_joins_shop_names_but_not_languages(self):
        a=offer('Pokémon Mega Quajutsu ex Premium Kollektion DE',price='42.99',packs=8)|{'gtin':'0196214141971'}
        b=a|{'title':'Pokemon Mega-Quajutsu Premium-Kollektion Deutsch','shop':'other'}
        self.assertEqual(pc.match_product(a,self.cfg),pc.match_product(b,self.cfg))
        self.assertIsNone(pc.match_product(b|{'title':b['title'].replace('Deutsch','English')},self.cfg))

    def test_exact_peer_identity_needs_three_independent_fresh_shops(self):
        cfg=copy.deepcopy(self.cfg)
        cfg['references']=[];cfg['preorder_watch']['price_references']=[];cfg['preorder_watch']['user_price_guides']=[]
        row,_=p.identity(self.offer,cfg)
        row.update(price='90')
        peers=[row|dict(price=str(90+i),retailer_group=str(i),validated_at=NOW)
               for i in range(3)]
        self.assertIsNotNone(p.price_check(row,peers,cfg,NOW))
        self.assertIsNone(p.price_check(row,peers[:2],cfg,NOW))
        self.assertIsNone(p.price_check(row,[r|{'validated_at':NOW-1801} for r in peers],cfg,NOW))
        self.assertIsNone(p.price_check(row,[r|{'retailer_group':'same-owner'} for r in peers],cfg,NOW))
        self.assertIsNone(p.price_check(row,[r|{'comparison_key':'other-language'} for r in peers],cfg,NOW))
