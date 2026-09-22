import unittest
from tcg_bot.market import evaluate, normalize, market_payload, delivery_key
from tcg_bot.__main__ import run
from unittest.mock import patch
from test_market import cfg, offers, state, NOW

class SealedContextTests(unittest.TestCase):
    def config(self):
        c=cfg();c['market'].update(expanded_products=True,price_context_mode=True,price_context_days=14,notify_all_shops=True,restock_min_hours=0)
        c['market']['price_references']=[]
        return c
    def product(self,title='Pokémon Glurak Tin DE',**fields):
        return offers(('49.99',))[0]|{'title':title,'description':'4 Booster und eine Promokarte',**fields}
    def test_formats_accepted_without_display_pack_requirement(self):
        for title,kind in [('Pokémon Glurak Tin DE','tin'),('Pokémon Glurak Mini Tin DE','mini_tin'),('Pokémon 151 Booster Bundle DE','bundle'),('Pokémon Wachsendes Chaos Top Trainer Box DE','etb'),('Pokémon Glurak Kollektion DE','collection'),('Pokémon 151 Blister DE','blister'),('One Piece Anniversary Box EN','box')]:
            with self.subTest(title=title):
                row,reason=normalize(self.product(title),self.config())
                self.assertIsNotNone(row,reason);self.assertEqual(row['product_kind'],kind)
    def test_empty_boxes_singles_and_cases_excluded(self):
        for title in ['Pokémon leere Tin DE','Pokémon Acryl Box DE','Pokémon Aufbewahrungsbox DE','Pokémon Glurak Einzelkarte DE','Pokémon Mini Tin Display DE','Pokémon Booster Case DE','Pokémon Mystery Box DE']:
            self.assertIsNone(normalize(self.product(title),self.config())[0],title)
    def test_pokemon_english_and_unknown_still_excluded(self):
        for title in ['Pokémon Tin EN','Pokémon Tin']:
            self.assertIsNone(normalize(self.product(title),self.config())[0])
    def test_product_formats_and_tin_variants_never_share_identity(self):
        titles=['Pokémon ME04 Display DE','Pokémon ME04 Top Trainer Box DE','Pokémon ME04 Tin Pikachu DE','Pokémon ME04 Tin Glurak DE']
        ids=[normalize(self.product(t,description='36 Booster'),self.config())[0]['identity'] for t in titles]
        self.assertEqual(len(set(ids)),4)
    def test_unknown_price_is_alert_not_fake_good_deal(self):
        d=evaluate([self.product()],self.config(),state(),NOW)[0][0]
        self.assertEqual(d['rating']['code'],'unknown');self.assertIsNone(d['baseline'])
        self.assertIn('ungeprüft',market_payload(d)['embeds'][0]['title'])
        self.assertNotIn('Confidence',str(market_payload(d)))
    def test_previous_days_price_rates_expensive_without_current_peers(self):
        c=self.config();s=state();row=self.product(price='25')
        evaluate([row],c,s,NOW-2*86400)
        d=evaluate([row|{'price':'50'}],c,s,NOW)[0][0]
        self.assertEqual(d['baseline'],'25');self.assertEqual(d['rating']['code'],'expensive')
        self.assertTrue(any(e['kind']=='history' for e in d['evidence']))
        self.assertIn('Teuer',market_payload(d)['embeds'][0]['title'])
    def test_old_and_unavailable_samples_are_not_price_history(self):
        c=self.config();s=state();row=self.product(price='25')
        evaluate([row],c,s,NOW-15*86400)
        evaluate([row|{'available':False}],c,s,NOW-86400)
        d=evaluate([row|{'price':'50'}],c,s,NOW)[0][0]
        self.assertIsNone(d['baseline'])
    def test_current_offer_cannot_be_its_own_price_reference(self):
        d=evaluate([self.product()],self.config(),state(),NOW)[0][0]
        self.assertEqual(d['evidence'],[])
    def test_expensive_reviewed_offer_posts_and_keeps_reference(self):
        c=self.config();c['market']['price_references']=cfg()['market']['price_references']
        d=evaluate(offers(('200',)),c,state(),NOW)[0][0]
        self.assertEqual(d['rating']['code'],'expensive');self.assertEqual(d['baseline'],'79.99')
    def test_out_of_stock_unknown_stock_and_failed_sources_never_post(self):
        for value in (False,None):
            self.assertFalse(evaluate([self.product(available=value)],self.config(),state(),NOW)[0])
    def test_missing_pack_count_not_invented_for_tin(self):
        d=evaluate([self.product(description='Original versiegelt')],self.config(),state(),NOW)[0][0]
        self.assertIsNone(d['packs']);self.assertNotIn('None Booster',str(market_payload(d)))
    def test_same_offer_not_repeated_and_other_shop_allowed(self):
        c=self.config();s=state();row=self.product();d=evaluate([row],c,s,NOW)[0][0]
        s['market_offer_sent']={delivery_key(d):dict(at=NOW,price=d['price'],offer=d['key'],episode=0,message_id='sent')}
        self.assertFalse(evaluate([row],c,s,NOW+600)[0])
        other=row|{'key':'1:tin','shop':'1','shop_name':'Shop 1','url':'https://shop1.example/tin'}
        self.assertEqual(len(evaluate([row,other],c,s,NOW+600)[0]),1)
    def test_capped_batch_carries_over_and_persists(self):
        c=self.config();c['max_alerts_per_run']=1;s=state()
        rows=[self.product(),self.product('Pokémon Pikachu Tin DE',key='0:second')]
        def adapter(shop,client):return (rows if shop['id']=='0' else []),[]
        with patch('tcg_bot.__main__.ADAPTERS',{'shopify':adapter}):
            first=run(c,s,None,send=lambda p:'one',now=NOW)
            second=run(c,s,None,send=lambda p:'two',now=NOW+600)
        self.assertEqual((first['sent'],first['pending_alerts'],second['sent']),(1,1,1))

    def test_same_barcode_assorted_tins_keep_motifs_separate(self):
        a=normalize(self.product('Pokémon Pikachu Tin DE',gtin='4006381333931'),self.config())[0]
        b=normalize(self.product('Pokémon Glurak Tin DE',gtin='4006381333931'),self.config())[0]
        self.assertNotEqual(a['identity'],b['identity'])
    def test_dated_external_reference_is_not_mislabeled_uvp(self):
        c=self.config();ref=cfg()['market']['price_references'][0]|{'kind':'market_reference'}
        c['market']['price_references']=[ref]
        d=evaluate(offers(('120',)),c,state(),NOW)[0][0]
        self.assertEqual(d['rating']['code'],'expensive')
        self.assertIn('externer Quelle',d['comparison_basis'])
        self.assertNotIn('Hersteller-UVP:',market_payload(d)['embeds'][0]['fields'][2]['value'])
