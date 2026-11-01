import copy
from datetime import datetime, timezone
from email.utils import formatdate
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from xml.sax.saxutils import escape

from tcg_bot import pokemon_center_watch as w
from tcg_bot.__main__ import load_state, save_state

NOW = datetime(2026, 11, 1, 20, tzinfo=timezone.utc).timestamp()
CLAIM = 'The 30th Celebration ETBs are loaded on Pokémon Center, but only for Germany, not the UK.'
SOURCE = dict(id='galar', name='Galar', kind='communityone', url='https://communityone.io/en/servers/123/test/updates/')


def row(text=CLAIM, age=30, id='a'):
    return dict(id=id, text=text, published=NOW-age, url=SOURCE['url']+'#msg-'+id)


def html(text=CLAIM, id='123', age=30):
    date = datetime.fromtimestamp(NOW-age, timezone.utc).isoformat()
    return '<div id="announcementsSSR"><article id="msg-'+id+'"><div class="announcement-content"><p>'+escape(text)+'</p></div><time datetime="'+date+'"></time></article></div>'


class PokemonCenterWatchTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'sources': [SOURCE]}
        self.state = {'version': 1, 'offers': {}}
        self.client = Mock(spec=['text'])
        self.client.text.return_value = html()
        self.send = Mock(return_value='discord-confirmed-id')

    def run_at(self, now=NOW):
        return w.run(self.cfg, self.state, self.client, now, self.send)

    def test_german_backend_lead_is_early_warning_never_live_stock(self):
        event, reason = w.qualify(row(), NOW, {})
        self.assertIsNone(reason)
        self.assertEqual(event['kind'], 'early_warning')
        self.assertFalse(event['inventory_confirmed'])
        self.assertEqual(self.run_at()['sent'], 1)
        message = self.send.call_args.args[0]
        self.assertIn('VORWARNUNG', message['embeds'][0]['title'])
        self.assertIn('vom Shop nicht bestätigt', message['embeds'][0]['description'])
        self.assertEqual(message['allowed_mentions'], {'parse': []})

    def test_uk_product_does_not_borrow_germany_from_other_sentence(self):
        text = 'Pokemon Center UK has loaded the Ditto Collection. Hello Germany!'
        self.assertIsNone(w.qualify(row(text), NOW, {})[0])

    def test_negative_germany_and_foreign_only_rejected(self):
        for text in ('Pokemon Center ETBs loaded for UK, not Germany.', 'Pokemon Center ETB loaded for US.',
                     'Pokemon Center Deutschland ist unser Thema. UK ETB in stock.'):
            with self.subTest(text=text):
                self.assertIsNone(w.qualify(row(text), NOW, {})[0])

    def test_other_retailer_cannot_borrow_pokemon_center_context(self):
        text = 'Pokemon Center UK is quiet. Smyths Germany ETB loaded on backend.'
        self.assertIsNone(w.qualify(row(text), NOW, {})[0])

    def test_german_sku_lead_without_product_type_is_allowed(self):
        event, reason = w.qualify(row('Pokemon Center Germany SKU 10-10438-110 loaded on backend.'), NOW, {})
        self.assertIsNone(reason)
        self.assertEqual(event['skus'], ['10-10438-110'])

    def test_precise_30_year_lead_with_foreign_headline(self):
        text = '30th Ditto Collection UK. Only Ditto is for the UK. '+CLAIM
        event, _ = w.qualify(row(text), NOW, {})
        self.assertEqual(event['identity'], '30-years-etb-de')
        self.assertNotIn('Ditto', event['claim'])

    def test_early_not_yet_live_is_accepted_but_not_stock(self):
        text = 'Pokemon Center Germany ETBs loaded on backend, not live yet.'
        self.assertEqual(w.qualify(row(text), NOW, {})[0]['kind'], 'early_warning')

    def test_speculation_retraction_and_old_reports_rejected(self):
        for text in ('Maybe Pokemon Center Germany ETBs loaded on backend.',
                     'Pokemon Center Germany ETBs not loaded on backend.',
                     'Pokemon Center Germany ETBs sold out.',
                     'Pokemon Center Germany queue open?'):
            self.assertIsNone(w.qualify(row(text), NOW, {})[0])
        self.assertIsNone(w.qualify(row(age=172801), NOW, {})[0])
        self.assertIsNone(w.qualify(row(age=-30), NOW, {})[0])

    def test_fresh_queue_report_15_minutes_max(self):
        event, _ = w.qualify(row('Pokemon Center Germany queue is live!'), NOW, {})
        self.assertEqual(event['kind'], 'queue_report')
        self.assertIsNone(w.qualify(row('Pokemon Center Germany queue is live!', age=901), NOW, {})[0])

    def test_repeated_message_is_deduped_after_restart(self):
        self.assertEqual(self.run_at()['sent'], 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'state.json'
            save_state(path, self.state)
            self.state = load_state(path)
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.send.assert_called_once()

    def test_cross_source_duplicate_and_new_wave(self):
        self.assertEqual(self.run_at()['sent'], 1)
        self.client.text.return_value = html('Pokémon Center Deutschland: 30 Jahre TTB im Backend hinterlegt.', id='999')
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.client.text.return_value = html('Pokémon Center Deutschland: 30 Jahre TTB jetzt verfügbar.', id='998', age=-600)
        self.assertEqual(self.run_at(NOW+600)['sent'], 1)

    def test_send_failure_does_not_consume_alert(self):
        self.send.side_effect = RuntimeError('failed')
        self.assertEqual(self.run_at()['sent'], 0)
        self.assertEqual(self.state['pc_de']['delivered'], {})
        self.send.side_effect = None
        self.assertEqual(self.run_at(NOW+300)['sent'], 1)

    def test_bad_source_does_not_stop_good_source(self):
        self.cfg['sources'].insert(0, dict(SOURCE, id='bad', url='https://example.com/'))
        self.client.text.side_effect = [ValueError('layout changed'), html()]
        self.assertEqual(self.run_at()['sent'], 1)
        self.assertEqual(self.state['pc_de']['sources']['bad']['status'], 'unavailable')

    def test_dry_run_does_not_mark_delivered(self):
        result = w.run(self.cfg, self.state, self.client, NOW)
        self.assertEqual(len(result['alerts']), 1)
        self.assertEqual(self.state['pc_de']['delivered'], {})

    def test_bot_challenge_http_200_never_queue(self):
        source = dict(SOURCE, id='store', kind='store', url='https://www.pokemoncenter.com/de-de/')
        self.client.text.return_value = '<html><iframe src="/_Incapsula_Resource"></iframe></html>'
        rows, notes = w.fetch_source(source, self.client, NOW)
        self.assertEqual(rows, [])
        self.assertEqual(notes, ['BLOCKED_NOT_STOCK'])

    def test_global_queue_on_german_url_is_not_german_confirmation(self):
        source = dict(SOURCE, kind='store', url='https://www.pokemoncenter.com/de-de/')
        self.client.text.return_value = '<h1>Virtual Queue</h1><p>You are now in line. Please keep this window open.</p>'
        self.assertEqual(w.fetch_source(source, self.client, NOW)[0], [])

    def test_region_in_footer_is_not_queue_evidence(self):
        source = dict(SOURCE, kind='store', url='https://www.pokemoncenter.com/de-de/')
        self.client.text.return_value = '<h1>Virtual Queue</h1><p>You are now in line. Please keep this window open.</p><footer>Germany</footer>'
        self.assertEqual(w.fetch_source(source, self.client, NOW)[0], [])

    def test_direct_queue_reopens_only_after_two_readable_clear_observations(self):
        self.cfg['sources'] = [dict(SOURCE, kind='store', url='https://www.pokemoncenter.com/de-de/')]
        active = '<h1>Virtual Queue Germany</h1><p>You are now in line. Please keep this window open.</p>'
        self.client.text.return_value = active
        self.assertEqual(self.run_at()['sent'], 1)
        self.client.text.return_value = '<html><iframe src="/_Incapsula_Resource"></iframe></html>'
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.client.text.return_value = active
        self.assertEqual(self.run_at(NOW+600)['sent'], 0)
        self.client.text.return_value = '<h1>Pokémon Center Deutschland</h1><p>Willkommen in unserem offiziellen deutschen Shop.</p>'
        self.run_at(NOW+900)
        self.run_at(NOW+1200)
        self.client.text.return_value = active
        self.assertEqual(self.run_at(NOW+1500)['sent'], 1)

    def test_rss_author_retweets_quotes_dates_and_canonical_link(self):
        source = dict(kind='x_rss', handle='dropalertsuk')
        def feed(author='dropalertsuk', body=CLAIM):
            return '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>Update</title><dc:creator>@'+author+'</dc:creator><link>https://teapawt.net/'+author+'/status/123</link><pubDate>'+formatdate(NOW-30, usegmt=True)+'</pubDate><description>'+escape('<p>'+body+'</p>')+'</description></item></channel></rss>'
        rows = w.parse_xml(feed(), source)
        self.assertEqual(rows[0]['url'], 'https://x.com/dropalertsuk/status/123')
        self.assertEqual(rows[0]['published'], NOW-30)
        self.assertEqual(w.parse_xml(feed('another'), source), [])
        rows = w.parse_xml(feed(body='UK ETB live <blockquote>'+CLAIM+'</blockquote>'), source)
        self.assertIsNone(w.qualify(rows[0], NOW, {})[0])

    def test_invalid_xml_or_layout_rejected(self):
        with self.assertRaises(ValueError):
            w.parse_xml('<!DOCTYPE rss><rss/>', {'kind':'x_rss'})
        with self.assertRaises(ValueError):
            w.parse_communityone('<h1>Check your browser</h1>', SOURCE)

    def test_no_alert_no_discord_message(self):
        self.client.text.return_value = html('Pokemon Center UK queue is open')
        self.assertEqual(self.run_at()['sent'], 0)
        self.send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
