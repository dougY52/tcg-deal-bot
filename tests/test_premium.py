import unittest
from unittest.mock import patch
from test_market import cfg, offers, state, NOW
from tcg_bot.market import evaluate, price_rating, market_payload
from tcg_bot.__main__ import run, load_config

def premium_cfg():
    c=cfg();c['market'].update(max_premium_eur=30,notify_within_price_range=True)
    c['market']['price_references'][0]['price_eur']='70'
    return c

class PremiumTests(unittest.TestCase):
    def test_active_configuration(self):
        p=load_config('config/config.json')['market']
        self.assertEqual(p['max_premium_eur'],30)
        self.assertTrue(p['notify_within_price_range'])

    def test_twenty_and_thirty_euros_extra_are_rated_not_hidden(self):
        for price in ['90','100']:
            deals,_,_=evaluate(offers((price,'105','106','108')),premium_cfg(),state(),NOW)
            self.assertEqual(len(deals),1)
            d=deals[0]
            self.assertEqual(d['price'],price)
            self.assertEqual(d['rating']['code'],'elevated')
            self.assertNotEqual(d['reason'],'Preisdeal')
            self.assertIn('kein Schnäppchen',market_payload(d)['embeds'][0]['title'])
            self.assertEqual(d['rating']['premium_eur'],str(int(price)-70))

    def test_cap_exactly_thirty_and_not_percentage(self):
        p=premium_cfg()['market']
        self.assertEqual(price_rating('100','70','70',p)['code'],'elevated')
        self.assertEqual(price_rating('100.01','70','70',p)['code'],'expensive')
        self.assertEqual(price_rating('1100','1000','1000',p)['code'],'expensive')

    def test_no_anchor_still_no_notification(self):
        c=premium_cfg();c['market']['price_references']=[]
        self.assertFalse(evaluate(offers(('90','105','106','108')),c,state(),NOW)[0])

    def test_only_cheapest_variant_of_product(self):
        deals,_,_=evaluate(offers(('90','95','99','100')),premium_cfg(),state(),NOW)
        self.assertEqual([d['price'] for d in deals],['90'])

    def test_repeated_run_does_not_resend_normal_offer(self):
        c=premium_cfg();s=state();rows=offers(('90','105','106','108'))
        def adapter(shop,_):return ([rows[int(shop['id'])]] if int(shop['id'])<4 else []),[]
        with patch('tcg_bot.__main__.ADAPTERS',{'shopify':adapter}):
            first=run(c,s,None,send=lambda _:'id',now=NOW)
            second=run(c,s,None,send=lambda _:self.fail('duplicate'),now=NOW+600)
        self.assertEqual(first['sent'],1)
        self.assertEqual(second['sent'],0)
