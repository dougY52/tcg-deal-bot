import unittest
from unittest.mock import patch
from test_market import cfg,offers,state,NOW
from tcg_bot.market import evaluate,normalize,delivery_key
from tcg_bot.__main__ import run

class AllShopAlerts(unittest.TestCase):
    def config(self):
        c=cfg();c['market']['notify_all_shops']=True
        c['market']['notify_within_price_range']=True
        c['market']['max_premium_eur']=30
        c['max_alerts_per_run']=20
        return c

    def test_all_retailers_in_price_range(self):
        deals,_,_=evaluate(offers(('70','75','79','85')),self.config(),state(),NOW)
        self.assertEqual(len(deals),4)

    def test_expensive_and_unavailable_stay_excluded(self):
        rows=offers(('70','75','79','200','75'))
        rows[4]['available']=False
        deals,_,_=evaluate(rows,self.config(),state(),NOW)
        self.assertNotIn('3:b15',[d['key'] for d in deals])
        self.assertNotIn('4:b15',[d['key'] for d in deals])

    def test_legacy_delivery_only_suppresses_its_own_shop(self):
        c=self.config();rows=offers(('70','75','79','85'));s=state()
        identity=normalize(rows[0],c)[0]['identity']
        s['market_sent']={identity:dict(at=NOW-60,price='70',offer='0:b15',message_id='confirmed')}
        deals,_,_=evaluate(rows,c,s,NOW)
        self.assertEqual({d['shop'] for d in deals},{'1','2','3'})

    def test_same_retailer_alias_not_sent_twice(self):
        c=self.config();c['shops'][1]['retailer_group']='same'
        c['shops'][2]['retailer_group']='same';c['market']['min_comparisons']=2
        deals,_,_=evaluate(offers(('70','75','79','85')),c,state(),NOW)
        self.assertEqual(len([d for d in deals if d['shop'] in ('1','2')]),1)

    def test_batch_cap_does_not_lose_other_shops(self):
        c=self.config();c['max_alerts_per_run']=2;rows=offers(('70','75','79','85'));s=state()
        def adapter(shop,client):return ([rows[int(shop['id'])]] if int(shop['id'])<4 else []),[]
        with patch('tcg_bot.__main__.ADAPTERS',{'shopify':adapter}):
            first=run(c,s,None,send=lambda p:'id',now=NOW)
            second=run(c,s,None,send=lambda p:'id',now=NOW+60)
            third=run(c,s,None,send=lambda p:self.fail('repeat'),now=NOW+120)
        self.assertEqual((first['sent'],first['pending_alerts'],second['sent'],third['sent']),(2,2,2,0))

    def test_failed_send_is_retryable(self):
        c=self.config();rows=offers(('70','75','79','85'));s=state()
        def adapter(shop,client):return ([rows[int(shop['id'])]] if int(shop['id'])<4 else []),[]
        with patch('tcg_bot.__main__.ADAPTERS',{'shopify':adapter}):
            r=run(c,s,None,send=lambda p:(_ for _ in ()).throw(RuntimeError()),now=NOW)
        self.assertEqual(r['sent'],0)
        self.assertFalse(s['market_offer_sent'])
