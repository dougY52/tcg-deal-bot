import unittest
from unittest.mock import Mock

from tcg_bot.browser import pokemon_queue_document
from tcg_bot.drop_watch import inspect, run
from tcg_bot.http import FetchError

URL = 'https://www.pokemoncenter.com/de-de/'
QUEUE = '<title>Virtual Queue</title><h1>You are now in line</h1><p>Estimated wait time: <span id="ttw">00:04:00</span>. Keep this window open.</p>'
CHALLENGE = '<title>[Error Title]</title><h1>www.pokemoncenter.com</h1><p>Additional security check is required. Click the checkbox above to pass the security check.</p>'


class PokemonQueueFrameTests(unittest.TestCase):
    def setUp(self):
        self.frame = Mock()
        self.frame.url = 'https://www.pokemoncenter.com/_Incapsula_Resource?observed=1'
        self.frame.content.return_value = QUEUE
        self.frame.title.return_value = 'Virtual Queue'
        self.frame.frame_element.return_value.is_visible.return_value = True
        self.page = Mock(url=URL, frames=[self.frame])
        self.statuses = {self.frame: 200}
        self.allowed = Mock()

    def read(self, url=URL):
        return pokemon_queue_document(self.page, url, self.statuses, self.allowed)

    def test_visible_successful_same_origin_frame(self):
        self.assertEqual(self.read(), (QUEUE, 'Virtual Queue'))
        self.allowed.assert_called_once_with(self.frame.url)

    def test_security_page_is_unknown_not_queue_or_closed(self):
        for body in (CHALLENGE, CHALLENGE + '<p>' + ' filler' * 600 + '</p>',
                     '<iframe src="/_Incapsula_Resource"></iframe>',
                     '<title>Virtual Queue</title><p>Additional security check is required. Estimated wait time: 2 minutes.</p>'):
            self.frame.content.return_value = body
            self.assertIsNone(self.read())
            self.assertEqual(inspect(body, {}, 0), ('blocked_or_unreadable', []))

    def test_foreign_origin_http_and_other_endpoint_rejected(self):
        for url in ('https://evil.test/_Incapsula_Resource',
                    'https://www.pokemoncenter.com.evil.test/_Incapsula_Resource',
                    'http://www.pokemoncenter.com/_Incapsula_Resource',
                    'https://www.pokemoncenter.com/other',
                    'https://user:pass@www.pokemoncenter.com/_Incapsula_Resource'):
            self.frame.url = url
            self.assertIsNone(self.read())
        self.frame.content.assert_not_called()

    def test_product_pages_and_other_regions_not_replaced_by_queue(self):
        for suffix in ('/en-gb', '/en-us', '/de-de/product/123', '/de-de/category/tcg'):
            self.assertIsNone(self.read('https://www.pokemoncenter.com' + suffix))
        self.page.url = 'https://www.pokemoncenter.com/en-us'
        self.assertIsNone(self.read())
        self.frame.content.assert_not_called()

    def test_hidden_failed_unobserved_navigation_and_robots_denied(self):
        for status in (None, 403, 429, 503):
            self.statuses[self.frame] = status
            self.assertIsNone(self.read())
        self.statuses[self.frame] = 200
        self.frame.frame_element.return_value.is_visible.return_value = False
        self.assertIsNone(self.read())
        self.frame.frame_element.return_value.is_visible.return_value = True
        self.allowed.side_effect = FetchError('robots denied')
        self.assertIsNone(self.read())
        self.frame.content.assert_not_called()

    def test_detached_frame_does_not_fail_entire_scan(self):
        self.frame.content.side_effect = RuntimeError('Frame detached')
        self.assertIsNone(self.read())

    def test_queue_uses_existing_dedupe_and_never_claims_inventory(self):
        source = {'id': 'pokemon-center-de', 'name': 'Pokémon Center', 'url': URL, 'every_run': True}
        cfg = {'shops': [], 'drop_watch': {'enabled': True, 'sources': [source]}}
        client = Mock(spec=['text'])
        client.text.return_value = self.read()[0]
        send, state = Mock(return_value='ok'), {}
        run(cfg, state, client, 1000, send)
        run(cfg, state, client, 1300, send)
        client.text.return_value = CHALLENGE
        run(cfg, state, client, 1600, send)
        client.text.return_value = QUEUE
        run(cfg, state, client, 1900, send)
        self.assertEqual(send.call_count, 1)
        embed = send.call_args.args[0]['embeds'][0]
        self.assertIn('WARTESCHLANGE', embed['title'])
        self.assertIn('Kein bestätigter Drop', embed['description'])

    def test_duplicate_run_summary_does_not_claim_empty_watchlist(self):
        from tcg_bot.fast_watch import run as fast_run
        from tcg_bot.__main__ import summary
        state = {'fast_last_run': 1000, 'fast_targets': {'saved': {}}}
        report = fast_run({'fast_watch': {'min_run_gap_seconds': 240}}, state, Mock(), {}, now=1100)
        self.assertEqual(report['fast_watch']['targets'], 1)
        self.assertEqual(report['fast_watch']['retry_after_seconds'], 140)
        self.assertIn('Doppelstart übersprungen', summary(report))


if __name__ == '__main__':
    unittest.main()
