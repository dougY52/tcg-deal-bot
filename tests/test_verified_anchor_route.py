import unittest
from test_market import cfg, offers, state, NOW
from tcg_bot.market import evaluate, market_payload, complete_pack_counts

class VerifiedAnchorTests(unittest.TestCase):
    def config(self):
        c=cfg(); c['market'].update(allow_verified_without_comparisons=True,notify_within_price_range=True)
        return c
    def test_single_offer_with_valid_reference_qualifies(self):
        deals,_,_=evaluate(offers(('79.99',)),self.config(),state(),NOW)
        self.assertEqual(len(deals),1)
        embed=market_payload(deals[0])['embeds'][0]
        self.assertIn('Belegter Normalpreis',embed['description'])
        self.assertNotIn('Marktmedian',embed['description'])
        self.assertIn('Keine weiteren',embed['fields'][-1]['value'])
    def test_expired_missing_and_expensive_still_blocked(self):
        c=self.config();c['market']['price_references'][0]['valid_until']='2026-09-17'
        self.assertFalse(evaluate(offers(('79.99',)),c,state(),NOW)[0])
        self.assertFalse(evaluate(offers(('150',)),self.config(),state(),NOW)[0])
    def test_expensive_peer_cannot_hide_normal_price(self):
        deals,_,_=evaluate(offers(('79.99','300')),self.config(),state(),NOW)
        self.assertEqual([d['key'] for d in deals],['0:b15'])
    def test_pack_facts_require_exact_valid_gtin_and_language(self):
        rows=offers(('79','80'))
        for r in rows:r['gtin']='4006381333931'
        rows[0]['description']='Original versiegelt'
        self.assertEqual(complete_pack_counts(rows,self.config())[0]['pack_count_evidence'],'matching_gtin')
        rows[1]['gtin']='4006381333932'
        self.assertNotIn('pack_count_evidence',complete_pack_counts(rows,self.config())[0])
    def test_conflicting_pack_counts_not_overridden(self):
        rows=offers(('79','80'))
        for r in rows:r['gtin']='4006381333931'
        rows[0]['description']='18 Booster oder 24 Booster'
        self.assertNotIn('pack_count_evidence',complete_pack_counts(rows,self.config())[0])
