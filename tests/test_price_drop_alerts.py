import unittest
from test_market import cfg, offers, state, NOW
from tcg_bot.market import evaluate, normalize

class PriceDropAlerts(unittest.TestCase):
    def check(self, previous, current, elapsed=60):
        c=cfg(); s=state(); rows=offers((current,'79.99','74.99','79.99'))
        identity=normalize(rows[0],c)[0]['identity']
        s['market_sent']={identity:dict(at=NOW,price=previous,offer='0:b15',episode=0,message_id='confirmed')}
        return evaluate(rows,c,s,NOW+elapsed)[0]

    def test_price_drop_inside_cooldown_alerts(self):
        self.assertEqual(len(self.check('65','59.99')),1)

    def test_5499_to_50_alerts_immediately(self):
        self.assertEqual(len(self.check('54.99','50')),1)

    def test_unchanged_offer_stays_silent(self):
        self.assertFalse(self.check('59.99','59.99'))
        self.assertFalse(self.check('59.99','59.99',86401))

    def test_small_price_change_stays_silent(self):
        self.assertFalse(self.check('60','59.99'))

    def test_second_scan_after_delivery_stays_silent(self):
        self.assertFalse(self.check('59.99','59.99',600))

    def test_one_pack_contents_do_not_conflict_with_display_count(self):
        row=offers()[0] | {'description':'24 Booster. 1 Boosterpack enthält 12 Karten.'}
        normalized,reason=normalize(row,cfg())
        self.assertEqual(normalized['packs'],24)

    def test_conflicting_display_counts_still_rejected(self):
        row=offers()[0] | {'description':'24 Booster oder 36 Booster.'}
        self.assertIsNone(normalize(row,cfg())[0])
