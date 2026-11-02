import unittest
from unittest.mock import Mock, patch

from tcg_bot.http import Client, FetchError
from tcg_bot.pokemon_center_queue import QueueClient, snapshot
from tcg_bot import pokemon_center_watch as watch
from scripts.watch_pokemon_center_de import relay_health

URL = 'https://www.pokemoncenter.com/de-de/'
FRAME = '<iframe id="main-iframe" src="/_Incapsula_Resource?observed=1&amp;event=2"></iframe>'
QUEUE = '<h1>Virtual Queue</h1><p>You are now in line. Keep this window open.</p>'
BANNER = '<div><strong>Today’s launch of German-language TCG merchandise is exclusive to the Pokémon Center Germany store.</strong></div>'
BLOCK = '<h1>Additional security check is required</h1><p>Click the checkbox to pass the security check.</p>'
STORE = '<h1>Pokémon Center Deutschland</h1><p>Willkommen in unserem offiziellen deutschen Shop.</p>'
SOURCE = dict(id='pc-de-store', name='Pokémon Center Deutschland', kind='store', url=URL)
NOW = 1793646000


class PokemonCenterQueueTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=['text'])

    def test_reads_only_observed_primary_frame_and_german_banner(self):
        self.client.text.side_effect = [FRAME, QUEUE+BANNER]
        result = snapshot(self.client, URL, NOW)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertTrue(result['frame_checked'])
        self.assertFalse(result['inventory_confirmed'])
        self.assertEqual(self.client.text.call_args.args[0], 'https://www.pokemoncenter.com/_Incapsula_Resource?observed=1&event=2')
        self.assertNotIn('observed=', str(result))

    def test_frame_challenge_is_unknown_never_open_or_closed(self):
        self.client.text.side_effect = [FRAME, BLOCK]
        self.assertEqual(snapshot(self.client, URL, NOW)['status'], 'blocked')

    def test_unconfirmed_shared_queue_is_not_germany(self):
        self.client.text.side_effect = [FRAME, QUEUE]
        self.assertEqual(snapshot(self.client, URL, NOW)['status'], 'queue_open_region_unknown')

    def test_no_region_from_hidden_content_footer_or_country_selector(self):
        for extra in ('<footer><p>Queue Germany</p></footer>',
                      '<div hidden>'+BANNER+'</div>', '<div style="display:none">'+BANNER+'</div>',
                      '<nav>'+BANNER+'</nav>', '<select><option>Queue Germany</option></select>',
                      '<p>The queue is for the UK, not Germany.</p>'):
            with self.subTest(extra=extra):
                self.client.text.side_effect = None
                self.client.text.return_value = QUEUE+extra
                self.assertEqual(snapshot(self.client, URL, NOW)['status'], 'queue_open_region_unknown')

    def test_no_arbitrary_frame_requests(self):
        for src in ('https://evil.test/_Incapsula_Resource?x=1',
                    'https://user:pass@www.pokemoncenter.com/_Incapsula_Resource?x=1',
                    '/_Incapsula_Resource', '/account', '/en-gb', '/_Incapsula_Resource?x=1#fragment'):
            with self.subTest(src=src):
                self.client.reset_mock()
                self.client.text.return_value = FRAME.replace('/_Incapsula_Resource?observed=1&amp;event=2', src)
                self.assertFalse(snapshot(self.client, URL, NOW)['frame_checked'])
                self.assertEqual(self.client.text.call_count, 1)

    def test_hidden_ambiguous_or_unrelated_frame_is_not_followed(self):
        for body in ('<div hidden>'+FRAME+'</div>', FRAME+FRAME,
                     FRAME.replace('main-iframe', 'advertisement')):
            self.client.reset_mock()
            self.client.text.return_value = body
            self.assertFalse(snapshot(self.client, URL, NOW)['frame_checked'])
            self.assertEqual(self.client.text.call_count, 1)

    def test_bad_page_is_not_a_closed_queue(self):
        for body in ('<h1>Error 15</h1><p>Pokémon Center shop is temporarily unavailable.</p>',
                     '<h1>Maintenance</h1><p>Please come back later to the Pokémon Center shop.</p>',
                     '<h1>Welcome</h1><p>This is some unrelated page with enough visible text.</p>'):
            self.client.text.return_value = body
            self.assertEqual(snapshot(self.client, URL, NOW)['status'], 'unknown')

    def test_fresh_transport_refuses_foreign_region_redirect(self):
        client = QueueClient()
        with patch.object(Client, 'raw', return_value=STORE) as raw:
            client.raw(URL)
            self.assertEqual(raw.call_args.args[2]['Cache-Control'], 'no-cache')
            with self.assertRaises(FetchError):
                client.raw('https://www.pokemoncenter.com/en-gb')
            raw.assert_called_once()

    def test_frame_failures_propagate_as_unknown(self):
        self.client.text.side_effect = [FRAME, FetchError('HTTP 429')]
        with self.assertRaises(FetchError):
            snapshot(self.client, URL, NOW)

    def test_challenge_rechecks_next_run_including_old_hour_pause(self):
        state = {'pc_de': {'sources': {'pc-de-store': dict(status='blocked', checked_at=NOW-300,
                 failures=6, retry_at=NOW+3300)}, 'events': {}, 'delivered': {}}}
        self.client.text.return_value = BLOCK
        report = watch.run({'sources': [SOURCE]}, state, self.client, NOW)
        self.assertEqual(report['sources'][0]['status'], 'blocked')
        self.assertEqual(state['pc_de']['sources']['pc-de-store']['retry_at'], NOW+240)
        self.client.text.assert_called_once()

    def test_network_backoff_is_not_shortened(self):
        state = {'pc_de': {'sources': {'pc-de-store': dict(status='unavailable', checked_at=NOW-300,
                 failures=6, retry_at=NOW+3300)}, 'events': {}, 'delivered': {}}}
        self.assertEqual(watch.run({'sources': [SOURCE]}, state, self.client, NOW)['sources'][0]['status'], 'backoff')
        self.client.text.assert_not_called()

    def test_open_block_open_duplicate_then_verified_close_reopen(self):
        state, send = {}, Mock(return_value='confirmed')
        bodies = [QUEUE+BANNER, BLOCK, QUEUE+BANNER, STORE, BLOCK, STORE, QUEUE+BANNER, STORE, STORE, QUEUE+BANNER]
        for i, body in enumerate(bodies):
            self.client.text.return_value = body
            watch.run({'sources': [SOURCE]}, state, self.client, NOW+i*300, send)
        self.assertEqual(send.call_count, 2)
        self.assertIn('DE-WARTESCHLANGE', send.call_args.args[0]['embeds'][0]['title'])
        self.assertIn('garantiert keinen Drop', send.call_args.args[0]['embeds'][0]['description'])

    def test_health_is_read_only_freshness_checked_and_no_latency_promise(self):
        read = Mock(return_value=dict(status='stream_connected', last_stream_at=NOW*1000-20000))
        result = relay_health(NOW, read)
        read.assert_called_once_with('/cardpal/status')
        self.assertTrue(result['connection_fresh'])
        self.assertFalse(result['shop_drop_latency_verified'])
        read.return_value['last_stream_at'] = (NOW-1000)*1000
        self.assertFalse(relay_health(NOW, read)['connection_fresh'])
        read.side_effect = RuntimeError('secret text must not leave boundary')
        self.assertNotIn('secret', str(relay_health(NOW, read)))


if __name__ == '__main__':
    unittest.main()
