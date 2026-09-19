import unittest
from pathlib import Path
from tcg_bot.__main__ import load_config, watch_only_config
from tcg_bot.rules import observe, assess, alert_reason
from test_bot import config, offer

class FastWatchTests(unittest.TestCase):
    def test_shipped_config_has_no_extra_delay_or_batch_limit(self):
        c = load_config('config/config.json')
        self.assertEqual(c['restock_cooldown_hours'], 0)
        self.assertEqual(c['max_alerts_per_run'], 20)

    def test_restock_in_next_check_alerts_without_wait(self):
        c=config(); c['restock_cooldown_hours']=0
        o=offer(); s={'offers':{}}; observe(s,[o])
        s['offers'][o['key']]['sent']={'at':1000,'episode':0,'price':o['price']}
        observe(s,[o|{'available':False}]); observe(s,[o])
        self.assertEqual(alert_reason(assess(o,c)[0],s,1300,c),'Restock')
        s['offers'][o['key']]['sent']['episode']=1
        self.assertIsNone(alert_reason(assess(o,c)[0],s,1301,c))

    def test_fast_config_keeps_all_exact_targets(self):
        c=load_config('config/config.json'); fast=watch_only_config(c)
        expected={s['id'] for s in c['shops'] if s.get('watch_handles') or s.get('watch_urls')}
        self.assertEqual({s['id'] for s in fast['shops']},expected)
        for s in fast['shops']:
            original=next(x for x in c['shops'] if x['id']==s['id'])
            self.assertEqual(s['watch_handles'],original['watch_handles'])
            self.assertEqual(s['watch_urls'],original['watch_urls'])
            self.assertEqual(s['catalog_urls'],[])
            self.assertEqual(s['max_pages'],0)
        self.assertTrue(all(s['max_pages']>0 for s in c['shops']))
