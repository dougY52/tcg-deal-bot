"""Free sources still deliver with no provider balance; never send real Discord."""
from datetime import datetime, timezone
from contextlib import redirect_stdout
from email.utils import formatdate
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch
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
    def test_disabled_or_missing_opt_in_never_invokes_provider_on_live_trigger(self):
        for opt_in in ({}, {'allow_credit_provider': False}, {'allow_credit_provider': 'true'}):
            with self.subTest(opt_in=opt_in):
                client = Mock(spec=['text'])
                client.text.return_value = json.dumps({'success': True, 'data': dict(
                    state='live', ageMs=0, lastChecked=datetime.fromtimestamp(NOW, timezone.utc).isoformat())})
                probe = Mock(side_effect=AssertionError('Credit provider must never run'))
                state = {}
                report, observation = run_gate({'enabled': True, **opt_in}, state, client, NOW, probe)
                self.assertFalse(report['credit_provider_enabled'])
                self.assertEqual(report['status'], 'confirmation_not_enabled')
                self.assertEqual(report['credits_reserved_this_run'], 0)
                self.assertIsNone(observation)
                self.assertEqual(state['pc_queue_gate'].get('reservations', []), [])
                probe.assert_not_called()

    def test_real_entrypoint_keeps_direct_de_delivery_without_spending_existing_key(self):
        from scripts import watch_pokemon_center_de as script
        source = dict(id='pc-de-store', name='Pokemon Center DE', kind='store',
                      url='https://www.pokemoncenter.com/de-de/')
        queue = '<h1>Virtual Queue</h1><p>You are now in line.</p><p>The queue is for the Germany store.</p>'
        signal = json.dumps({'success': True, 'data': dict(state='live', ageMs=0,
            lastChecked=datetime.fromtimestamp(NOW, timezone.utc).isoformat())})
        for direct_body, expected_sent in ((queue, 1), ('<h1>Additional security check is required</h1>', 0)):
            with self.subTest(expected_sent=expected_sent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cfg = dict(sources=[source], queue_gate=dict(enabled=True, allow_credit_provider=False),
                           community_watch=dict(enabled=False))
                (root/'config.json').write_text(json.dumps(cfg))
                transport = Mock(spec=['text', 'close', 'deadline'])
                transport.text.side_effect = lambda url: signal if url == STATUS_URL else direct_body
                argv = ['watch', '--config', str(root/'config.json'), '--state', str(root/'state.json'),
                        '--report', str(root/'report.json'), '--send']
                with patch.object(sys, 'argv', argv), patch.dict(os.environ, {
                        'SCRAPINGANT_API_KEY': 'test-existing-key', 'DISCORD_WEBHOOK_URL': 'test-hook',
                        'GITHUB_STEP_SUMMARY': ''}), patch.object(script.time, 'time', return_value=NOW), \
                        patch.object(script, 'QueueClient', return_value=transport), \
                        patch.object(script, 'QueueProbe') as provider, \
                        patch.object(script, 'webhook_url'), \
                        patch.object(script, 'send_discord', return_value='synthetic-receipt') as send, \
                        patch.object(script, 'relay_health', return_value={'status':'not_checked'}), \
                        redirect_stdout(io.StringIO()):
                    report = script.main()
                self.assertEqual(report['sent'], expected_sent)
                self.assertEqual(send.call_count, expected_sent)
                self.assertEqual(report['queue_gate']['credits_reserved_this_run'], 0)
                provider.assert_not_called()
                saved = load_state(root/'state.json')
                self.assertEqual(saved['pc_queue_gate'].get('reservations', []), [])
                self.assertNotIn('test-existing-key', (root/'report.json').read_text())

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
                gate, observation = run_gate({'enabled': True, 'allow_credit_provider': True}, state, client, NOW,
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
