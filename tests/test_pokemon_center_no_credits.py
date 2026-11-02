"""Free sources still deliver with no provider balance; never send real Discord."""
from datetime import datetime, timezone
from email.utils import formatdate
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock
from xml.sax.saxutils import escape

from tcg_bot.__main__ import load_state, save_state
from tcg_bot.http import Client, FetchError
from tcg_bot.pokemon_center_gate import run_gate, STATUS_URL
from tcg_bot.pokemon_center_watch import parse_xml, qualify, run
from tcg_bot.scanning import collect

NOW = 1793647560
CLAIM = 'Pokemon Center Queue is for Germany only.'
SOURCE = dict(id='pokehunt-public', name='PokeHunt', kind='x_rss',
              handle='pokehuntdotfun', url='https://teapawt.net/pokehuntdotfun/rss',
              interval_seconds=60)


def feed(text=CLAIM, author='pokehuntdotfun', age=30):
    return ('<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>'
            '<title>'+escape(text)+'</title><dc:creator>@'+author+'</dc:creator>'
            '<link>https://teapawt.net/'+author+'/status/123</link><pubDate>'+
            formatdate(NOW-age, usegmt=True)+'</pubDate><description>'+
            escape('<p>'+text+'</p>')+'</description></item></channel></rss>')


class CreditIndependentTests(unittest.TestCase):
    def test_missing_key_exhausted_budget_and_provider_error_keep_free_delivery(self):
        for mode in ('no_key', 'monthly_cap', 'provider_empty'):
            with self.subTest(mode=mode):
                state = {'version': 1, 'offers': {}}
                probe = Mock(side_effect=FetchError('PC_PROVIDER_FREE_CREDITS_EXHAUSTED'))
                if mode == 'monthly_cap':
                    state['pc_queue_gate'] = {'reservations': [NOW-86400]*48}
                client = Mock(spec=['text'])
                data = {'success': True, 'data': dict(state='live', ageMs=0,
                    lastChecked=datetime.fromtimestamp(NOW, timezone.utc).isoformat())}
                client.text.side_effect = lambda url: json.dumps(data) if url == STATUS_URL else feed()
                gate, observation = run_gate({'enabled': True}, state, client, NOW,
                                             None if mode == 'no_key' else probe)
                self.assertFalse(gate['germany_confirmed'])
                self.assertIsNone(observation)
                send = Mock(return_value='synthetic-receipt')
                report = run({'sources': [SOURCE]}, state, client, NOW, send, queue_observation=observation)
                self.assertEqual(report['sent'], 1)
                payload = send.call_args.args[0]['embeds'][0]
                self.assertIn('QUEUE GEMELDET', payload['title'])
                self.assertIn('vom Shop nicht bestätigt', payload['description'])
                if mode == 'provider_empty':
                    probe.assert_called_once()
                else:
                    probe.assert_not_called()
                    self.assertEqual(gate['credits_reserved_this_run'], 0)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'state.json'
                    save_state(path, state)
                    restored = load_state(path)
                self.assertEqual(run({'sources': [SOURCE]}, restored, client, NOW+60, send)['sent'], 0)
                send.assert_called_once()

    def test_present_tense_report_is_not_a_direct_shop_confirmation(self):
        rows = parse_xml(feed(), SOURCE)
        event, reason = qualify(rows[0], NOW, {})
        self.assertIsNone(reason)
        self.assertEqual(event['kind'], 'queue_report')
        self.assertEqual(event['evidence'], 'community_report')
        self.assertFalse(event['inventory_confirmed'])
        self.assertEqual(event['url'], 'https://x.com/pokehuntdotfun/status/123')

    def test_foreign_historical_speculative_quoted_or_old_claims_never_alert(self):
        for text in (
            'Pokemon Center Queue is for UK only.',
            'Pokemon Center Queue was for Germany only.',
            'Yesterday Pokemon Center Queue is for Germany only.',
            'Pokemon Center Queue will be for Germany only.',
            'Maybe Pokemon Center Queue is for Germany only.',
            'Pokemon Center Queue is for Germany only?',
            'Pokemon Center Queue is not for Germany.',
            'Guide: Pokemon Center Queue is for Germany only.',
            'Pokemon Center Queue is for Germany only but it is closed.',
            CLAIM+' It is closed now.',
            CLAIM+' That was yesterday.',
            CLAIM+' Maybe tomorrow.',
            'Hello UK. <blockquote>'+CLAIM+'</blockquote>',
        ):
            with self.subTest(text=text):
                row = parse_xml(feed(text), SOURCE)[0]
                self.assertIsNone(qualify(row, NOW, {})[0])
        self.assertEqual(parse_xml(feed(author='other_author'), SOURCE), [])
        self.assertIsNone(qualify(parse_xml(feed(age=901), SOURCE)[0], NOW, {})[0])

    def test_global_queue_without_any_germany_report_never_sends(self):
        client = Mock(spec=['text'])
        client.text.return_value = feed('Pokemon Center queue is live!')
        send = Mock()
        report = run({'sources': [SOURCE]}, {}, client, NOW, send)
        self.assertEqual(report['sent'], 0)
        send.assert_not_called()

    def test_free_message_delivered_while_another_host_is_still_blocked(self):
        started, delivered, finished = Event(), Event(), Event()
        slow_saw_delivery = []

        class Transport(Client):
            def text(self, url):
                if 'slow.test' in url:
                    started.set()
                    slow_saw_delivery.append(delivered.wait(3))
                    finished.set()
                    raise FetchError('HTTP 503')
                if not started.wait(3):
                    raise AssertionError('Other host did not start')
                return feed()

        def send(message):
            self.assertFalse(finished.is_set())
            delivered.set()
            return 'synthetic-receipt'

        slow = dict(id='slow', name='Slow source', kind='atom', url='https://slow.test/feed')
        client = Transport()
        report = run({'sources': [slow, SOURCE]}, {}, client, NOW, send)
        self.assertEqual(report['sent'], 1)
        self.assertEqual(slow_saw_delivery, [True])
        self.assertEqual(report['sources'][0]['id'], SOURCE['id'])
        self.assertEqual(report['sources'][1]['status'], 'unavailable')

    def test_existing_retailer_collector_keeps_priority_order_and_host_serialization(self):
        seen, clients = [], []
        def adapter(shop, client):
            seen.append(shop['id'])
            clients.append(client)
            return [shop['id']], []
        shops = [dict(id=str(i), adapter='test', base_url='https://same.test/'+str(i)) for i in range(3)]
        rows = collect(shops, Client(), {'test': adapter}, workers=3)
        self.assertEqual(seen, ['0', '1', '2'])
        self.assertEqual([r[0]['id'] for r in rows], ['0', '1', '2'])
        self.assertIs(clients[0], clients[1])
        self.assertIs(clients[1], clients[2])


if __name__ == '__main__':
    unittest.main()
