"""Browser replay of public notice wording, not a live queue/Discord test.

The notice was visually checked against a user's historical screenshot:
https://www.reddit.com/r/PokemonTCG/comments/1tvshzm/
HTML structure and styles below are synthetic parser regressions.
All browser requests are intercepted; no Pokémon Center request is made.
"""
import os
from pathlib import Path
import unittest

from tcg_bot.pokemon_center_gate import HOME, provider_snapshot
from tcg_bot.http import FetchError

NOTICE = ("Please note: We will be launching German-language TCG merchandise exclusively on "
          "the Pokémon Center Germany store today. English TCGs will not be launching in any of our stores.")
QUEUE = '<h1>Hi, Trainer! You’re in the virtual queue.</h1><p>Please keep this window open. Estimated wait time: 00:15:00.</p>'
FRAME = '<iframe id="main-iframe" src="/_Incapsula_Resource?fixture=1"></iframe>'
BLOCK = '<h1>Additional security check is required</h1><p>Verify you are human.</p>'
SCRIPT = Path(__file__).resolve().parents[1].joinpath('tcg_bot/pc_queue_dom.js').read_text()


@unittest.skipUnless(os.environ.get('TCG_TEST_PC_DOM') == '1', 'Cloud browser replay is opt-in')
class RenderedQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(channel='chrome', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def capture(self, home, frame=QUEUE):
        page = self.browser.new_page()
        def route(request):
            if request.request.url == HOME:
                request.fulfill(status=200, content_type='text/html', body='<html><body>'+home+'</body></html>')
            elif request.request.url == 'https://www.pokemoncenter.com/_Incapsula_Resource?fixture=1':
                request.fulfill(status=200, content_type='text/html', body='<html><body>'+frame+'</body></html>')
            else:
                request.abort()
        page.route('**/*', route)
        try:
            page.goto(HOME)
            page.evaluate('async () => {'+SCRIPT+'}')
            return page.content()
        finally:
            page.close()

    def parse(self, home, frame=QUEUE):
        return provider_snapshot({'status_code': 200, 'html': self.capture(home, frame)}, 1793647560, require_rendered=True)

    def test_historical_notice_wording_confirms_visible_de_queue(self):
        result = self.parse('<div>'+NOTICE+'</div>'+QUEUE)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertTrue(result['rendered_visibility'])
        self.assertFalse(result['inventory_confirmed'])

    def test_css_hidden_notice_never_confirms(self):
        for rule in ('display:none', 'visibility:hidden', 'opacity:0'):
            result = self.parse('<style>.notice{'+rule+'}</style><div class="notice"><strong>'+NOTICE+'</strong></div>'+QUEUE)
            self.assertEqual(result['status'], 'queue_open_region_unknown')

    def test_notice_outside_primary_frame_is_retained(self):
        result = self.parse('<div>'+NOTICE+'</div>'+FRAME)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertEqual(result['banner_location'], 'page_outside_primary_frame')

    def test_notice_inside_primary_frame_is_retained(self):
        result = self.parse(FRAME, '<div>'+NOTICE+'</div>'+QUEUE)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertEqual(result['banner_location'], 'primary_frame')

    def test_security_frame_remains_blocked_despite_notice(self):
        self.assertEqual(self.parse('<div>'+NOTICE+'</div>'+FRAME, BLOCK)['status'], 'blocked')

    def test_hidden_frames_footer_and_unrelated_regions_cannot_donate_proof(self):
        result = self.parse('<div hidden>'+FRAME+'</div><footer>'+NOTICE+'</footer>'+QUEUE)
        self.assertEqual(result['status'], 'queue_open_region_unknown')

    def test_unreadable_foreign_frame_fails_closed(self):
        with self.assertRaises(FetchError):
            self.parse('<div>'+NOTICE+'</div>'+FRAME.replace('/_Incapsula_Resource?fixture=1', 'https://example.test/frame'))


if __name__ == '__main__':
    unittest.main()
