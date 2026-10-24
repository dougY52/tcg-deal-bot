import copy
from datetime import datetime
import unittest
from unittest.mock import Mock
from tcg_bot import drop_watch as d

NOW = datetime(2026, 10, 24, 12, tzinfo=d.BERLIN).timestamp()
QUEUE = '<title>Virtual Queue</title><h1>You are now in line</h1><p>Estimated wait time: 10 minutes. Keep this window open.</p>'
NORMAL = '<title>TCG Händler</title><h1>Willkommen im Kartenshop</h1><p>Hier findest du unser Sammelkartensortiment und Zubehör.</p>'
EVENT = '<article>Pokémon Booster Display Deutsch – Verkaufsstart: 25.10.2026 um 12:00 Uhr.</article>'


class DropWatchTests(unittest.TestCase):
    def setUp(self):
        self.source = {'id': 'test', 'name': 'Test Shop', 'url': 'https://example.test', 'interval_seconds': 300}
        self.cfg = {'shops': [], 'drop_watch': {'enabled': True, 'sources': [self.source]}}
        self.state = {}
        self.client = Mock(spec=['text'])
        self.client.text.return_value = QUEUE
        self.send = Mock(return_value='discord-confirmed')

    def run_at(self, at):
        return d.run(self.cfg, self.state, self.client, at, self.send)

    def test_queue_is_information_not_preorder(self):
        report = self.run_at(NOW)
        self.assertEqual(report['sent'], 1)
        msg = self.send.call_args.args[0]['embeds'][0]
        self.assertIn('WARTESCHLANGE', msg['title'])
        self.assertIn('Kein bestätigter Drop', msg['description'])
        self.assertNotIn('PREORDER LIVE', msg['title'])

    def test_unchanged_queue_and_unknown_do_not_realert(self):
        self.run_at(NOW)
        self.run_at(NOW+300)
        self.client.text.side_effect = TimeoutError()
        self.run_at(NOW+600)
        self.client.text.side_effect = None
        self.run_at(NOW+900)
        self.assertEqual(self.send.call_count, 1)

    def test_confirmed_queue_reopening(self):
        self.run_at(NOW)
        self.client.text.return_value = NORMAL
        self.run_at(NOW+300)
        self.run_at(NOW+600)
        self.client.text.return_value = QUEUE
        self.run_at(NOW+900)
        self.assertEqual(self.send.call_count, 2)

    def test_challenge_and_waitlist_are_not_queue_signals(self):
        for page in ['<title>Access denied</title><p>Request unsuccessful. Incapsula incident ID 123</p>',
                     '<h1>Pokémon Vorbestellung</h1><button>Notify me</button><p>Coming soon, Waitlist</p>']:
            self.client.text.return_value = page
            self.run_at(NOW)
            self.assertFalse(self.send.called)
            self.state = {}

    def test_future_sale_with_exact_date_language_and_time(self):
        self.client.text.return_value = EVENT
        self.run_at(NOW)
        self.run_at(NOW+300)
        self.assertEqual(self.send.call_count, 1)
        self.assertIn('DROP ANGEKÜNDIGT', self.send.call_args.args[0]['embeds'][0]['title'])

    def test_old_wrong_language_undated_release_only_or_hidden(self):
        for page in [EVENT.replace('25.10.2026','20.10.2026'), EVENT.replace('Deutsch','English'),
                     EVENT.replace('12:00 Uhr','bald'), EVENT.replace('Verkaufsstart','Release'),
                     EVENT.replace('<article>','<article hidden>'), '<script>'+EVENT+'</script>',
                     NORMAL+'<div hidden>'+EVENT+'</div>']:
            status, events = d.inspect(page, self.source, NOW)
            self.assertEqual(events, [], page)

    def test_failed_send_is_retryable_and_dryrun_never_marks_delivered(self):
        dry = d.run(self.cfg, {}, self.client, NOW)
        self.assertEqual(dry['sent'], 0)
        self.send.side_effect = RuntimeError()
        self.assertTrue(self.run_at(NOW)['errors'])
        self.send.side_effect = None
        self.assertEqual(self.run_at(NOW+300)['sent'], 1)

    def test_one_broken_source_does_not_stop_next(self):
        self.cfg['drop_watch']['sources'].append(dict(self.source, id='second'))
        self.client.text.side_effect = [TimeoutError(), EVENT]
        self.assertEqual(self.run_at(NOW)['sent'], 1)

    def test_script_word_and_queue_faq_do_not_create_queue(self):
        for page in [NORMAL+'<script src="queue-it.js"></script>',
                     NORMAL+'<p>Our virtual queue: keep this window open when you are in line.</p>']:
            self.assertEqual(d.inspect(page, self.source, NOW)[1], [])
