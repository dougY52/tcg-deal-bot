import unittest
from tcg_bot.market import price_rating, evaluate, market_payload
from test_market import cfg, offers, state, NOW

class RatingTests(unittest.TestCase):
    def test_price_bands(self):
        for price,code in [('59','very_good'),('70','fair'),('80','acceptable'),('80.50','acceptable'),('80.51','expensive')]:
            self.assertEqual(price_rating(price,'70','70',cfg()['market'])['code'],code)

    def test_inflated_median_does_not_make_premium_a_bargain(self):
        self.assertEqual(price_rating('80','70','120',cfg()['market'])['code'],'acceptable')
        self.assertEqual(price_rating('100','70','120',cfg()['market'])['code'],'expensive')

    def test_missing_anchor_unknown_report_no_alert(self):
        c=cfg();c['market']['price_references']=[]
        deals,_,candidates=evaluate(offers(),c,state(),NOW)
        self.assertFalse(deals)
        self.assertTrue(all(x['rating']['code']=='unknown' for x in candidates))

    def test_normal_price_rated_but_not_sent(self):
        c=cfg();c['market']['price_references'][0]['price_eur']='70'
        deals,_,candidates=evaluate(offers(('80','70','70','70')),c,state(),NOW)
        self.assertFalse(deals)
        self.assertEqual(next(x for x in candidates if x['shop']=='0')['rating']['code'],'acceptable')

    def restock(self, price='80', cheaper_live=False):
        c=cfg();c['market']['price_references'][0]['price_eur']='70'
        s=state();rows=offers(('70',)*5)
        evaluate(rows,c,s,NOW)
        unavailable=[o|{'available':False} for o in rows]
        evaluate(unavailable,c,s,NOW+60)
        for hour in range(1,8):evaluate(unavailable,c,s,NOW+hour*3600)
        current=[rows[0]|{'price':price}]+unavailable[1:]
        if cheaper_live:current[1]=rows[1]
        return evaluate(current,c,s,NOW+8*3600)

    def test_80_instead_of_70_restock_yellow(self):
        deals,_,_=self.restock()
        self.assertEqual(len(deals),1)
        self.assertEqual(deals[0]['rating']['code'],'acceptable')
        message=market_payload(deals[0])['embeds'][0]
        self.assertIn('Noch okay',message['title'])
        self.assertIn('darüber',message['description'])
        self.assertIn('kein Schnäppchen',str(message))

    def test_too_expensive_restock_stays_silent(self):
        deals,_,candidates=self.restock('81')
        self.assertFalse(deals)
        self.assertEqual(candidates[0]['rating']['code'],'expensive')

    def test_premium_restock_with_cheaper_live_offer_not_sent(self):
        deals,_,_=self.restock(cheaper_live=True)
        self.assertNotIn('0:b15',[d['key'] for d in deals])
