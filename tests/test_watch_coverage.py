import threading
import time
import unittest
from unittest.mock import Mock
from tcg_bot import drop_watch, fast_watch
from tcg_bot.http import Client
from test_drop_watch import QUEUE, NOW
import test_preorders as fixtures


class WatchCoverage(unittest.TestCase):
    setUp = fixtures.Preorders.setUp

    def test_failed_fetch_never_claims_complete_live_coverage(self):
        fast_watch.remember([self.offer], self.cfg, self.state, NOW)
        key = self.offer['key']
        failed = fast_watch.coverage(self.cfg, self.state, [self.offer], {key: (None, 'HTTP_403')})
        self.assertTrue(failed['all_attempted'])
        self.assertFalse(failed['all_confirmed'])
        self.assertEqual(failed['failed'], 1)
        missing = fast_watch.coverage(self.cfg, self.state, [self.offer], {})
        self.assertEqual(missing['not_attempted'], 1)
        self.assertFalse(missing['all_attempted'])
        success = fast_watch.coverage(self.cfg, self.state, [self.offer], {key: ({'live_validated': True}, None)})
        self.assertTrue(success['all_confirmed'])

    def test_disabled_shops_not_claimed_as_active_coverage(self):
        fast_watch.remember([self.offer], self.cfg, self.state, NOW)
        self.cfg['shops'][0]['enabled'] = False
        self.assertEqual(fast_watch.coverage(self.cfg, self.state, [], {})['eligible'], 0)

    def test_critical_queue_rechecked_even_before_interval_without_spam(self):
        source = {'id':'pc', 'name':'PC', 'url':'https://example.test', 'every_run':True, 'interval_seconds':300}
        cfg = {'shops':[], 'drop_watch':{'enabled':True,'sources':[source]}}
        client = Mock(spec=['text']);client.text.return_value = QUEUE
        send = Mock(return_value='id');state = {}
        drop_watch.run(cfg, state, client, NOW, send)
        drop_watch.run(cfg, state, client, NOW+240, send)
        self.assertEqual(client.text.call_count, 2)
        self.assertEqual(send.call_count, 1)

    def test_exhausted_budget_does_not_mark_queue_source_checked(self):
        source = {'id':'pc','name':'PC','url':'https://example.test','every_run':True}
        cfg = {'shops':[], 'drop_watch':{'enabled':True,'sources':[source]}}
        client = Mock(spec=['text','deadline']);client.deadline = time.monotonic()-1
        state = {};report = drop_watch.run(cfg, state, client, NOW)
        client.text.assert_not_called()
        self.assertNotIn('pc',state['drop_watch_sources'])
        self.assertEqual(report['critical_not_checked'], ['pc'])

    def test_slow_host_does_not_block_queue_on_other_host(self):
        fast_read = threading.Event()
        class Transport(Client):
            def text(self, url):
                if 'slow.test' in url:
                    if not fast_read.wait(1):
                        raise AssertionError('other host never started independently')
                    raise TimeoutError('slow source')
                fast_read.set()
                return QUEUE
        cfg = {'shops':[], 'drop_watch':{'enabled':True, 'workers':2, 'sources':[
            {'id':host,'name':host,'url':'https://'+host,'every_run':True}
            for host in ['slow.test','fast.test']]}}
        state = {};send = Mock(return_value='id')
        report = drop_watch.run(cfg,state,Transport(),NOW,send)
        self.assertTrue(fast_read.is_set())
        self.assertEqual(report['sent'],1)
        self.assertEqual(report['critical_not_checked'],[])
        self.assertTrue(state['drop_watch_sources']['slow.test']['status'].startswith('unavailable:'))
        self.assertEqual(state['drop_watch_sources']['fast.test']['status'],'queue_open')
