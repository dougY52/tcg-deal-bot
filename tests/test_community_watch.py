import copy
from email.utils import formatdate
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from xml.sax.saxutils import escape

from tcg_bot import community_watch as c
from tcg_bot.__main__ import load_state, save_state

NOW = 1792954800
URL = 'https://www.mydealz.de/deals/pokemon-center-deutschland-display-123456'
DE = 'https://www.pokemoncenter.com/de-de/product/10-123/test'
TITLE = 'Pokémon Center Deutschland: Booster Display Deutsch'


def article(**changes):
    obj = dict(threadId='123456', title=TITLE, descriptionPurified='Jetzt vorbestellbar',
               publishedAt=NOW-60, isExpired=False, deletedAt=None, status='Activated', price=99.99)
    obj.update(changes)
    return obj


def page(obj):
    return '<script>window.__INITIAL_STATE__ = '+json.dumps({'thread': obj})+';</script>'


def feed(title=TITLE, url=URL, at=NOW-60):
    return '<rss><channel><item><title>'+escape(title)+'</title><link>'+escape(url)+'</link><pubDate>'+formatdate(at, usegmt=True)+'</pubDate></item></channel></rss>'


class CommunityWatchTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'community_watch': {'enabled': True}}
        self.state = {}
        self.obj = article()
        self.client = Mock(spec=['text'])
        self.client.text.side_effect = self.read
        self.send = Mock(return_value='discord-id')

    def read(self, url):
        if url == URL:
            return page(self.obj)
        if url == c.SOURCES[2][1]:
            return '<h2>Community-Deals</h2><div class="deal"><a href="'+URL+'">'+TITLE+'</a><span>vor 1 Minute</span></div>'
        return feed()

    def run_at(self, at=NOW, **kw):
        return c.run(self.cfg, self.state, self.client, at, self.send, **kw)

    def test_new_german_report_posted_once_across_all_feeds_and_restart(self):
        result = self.run_at()
        self.assertEqual(result['sent'], 1)
        with tempfile.TemporaryDirectory() as path:
            p = Path(path)/'state.json'
            self.state.update(version=1, offers={})
            save_state(p, self.state)
            self.state = load_state(p)
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.assertEqual(self.send.call_count, 1)
        self.assertEqual(sum(url.args[0] == URL for url in self.client.text.call_args_list), 1)

    def test_payload_is_attributed_community_info_not_live_stock(self):
        self.run_at()
        msg = self.send.call_args.args[0]
        e = msg['embeds'][0]
        self.assertEqual(e['url'], URL)
        self.assertIn('nicht live bestätigt', e['description'])
        self.assertIn('MyDealz', e['footer']['text'])
        self.assertNotIn('PREORDER LIVE', e['title'])
        self.assertEqual(msg['allowed_mentions'], {'parse': []})
        self.assertIn('timestamp', e)

    def test_expired_original_wins_over_fresh_positive_feed(self):
        self.obj['isExpired'] = True
        self.assertEqual(self.run_at()['rejected']['EXPIRED_OR_INACTIVE'], 1)
        self.send.assert_not_called()

    def test_parser_requires_exact_original_id_not_recommendation(self):
        self.obj['threadId'] = '999'
        self.assertEqual(self.run_at()['sent'], 0)
        self.assertTrue(self.run_at(NOW+300)['errors'])

    def test_de_evidence_must_be_explicit_not_german_feed_or_eur(self):
        obj = article(title='Pokemon Center Booster Display')
        self.assertEqual(c.qualify(obj, NOW, {})[1], 'GERMANY_NOT_EXPLICIT')
        obj['descriptionPurified'] = '<a href="'+DE+'">Produkt</a>'
        self.assertIsNone(c.qualify(obj, NOW, {})[1])
        for url in [DE.replace('de-de', 'en-gb'), DE.replace('de-de', 'en-us'), DE.replace('.com/', '.com.evil/'), 'https://pokemoncenter.com.de/de-de/product/1', 'https://www.pokemoncenter.com@evil.test/de-de/product/1']:
            obj['descriptionPurified'] = '<a href="'+url+'">Produkt</a>'
            self.assertEqual(c.qualify(obj, NOW, {})[1], 'GERMANY_NOT_EXPLICIT')

    def test_foreign_or_unknown_region_queue_never_posted(self):
        for title in ['Pokemon Center UK Queue live', 'Pokemon Center Queue live', 'Pokemon Center Deutschland Display English', 'Pokemon Center US live']:
            self.assertIsNotNone(c.qualify(article(title=title), NOW, {})[1])

    def test_fresh_explicit_german_queue_allowed_but_not_old_or_closed(self):
        obj = article(title='Pokemon Center DE Warteschlange ist live', price=None)
        self.assertEqual(c.qualify(obj, NOW, {})[0]['kind'], 'queue')
        self.assertEqual(c.qualify(obj | {'publishedAt':NOW-901}, NOW, {})[1], 'STALE_OR_UNDATED')
        for title in ['Pokemon Center DE Queue live?', 'Pokemon Center Deutschland Queue geschlossen', 'Pokemon Center DE Queue morgen', 'Pokemon Center Deutschland Warteschlange']:
            self.assertIsNotNone(c.qualify(obj | {'title': title}, NOW, {})[1])
        self.assertIsNotNone(c.qualify(obj | {'descriptionPurified': 'Update: Warteschlange ist geschlossen'}, NOW, {})[1])

    def test_stale_missing_or_future_source_timestamp_rejected(self):
        for at in [None, NOW-1801, NOW+1, float('nan'), 'yesterday']:
            self.assertEqual(c.qualify(article(publishedAt=at), NOW, {})[1], 'STALE_OR_UNDATED')

    def test_no_old_feed_backfill(self):
        self.client.text.return_value = None
        self.client.text.side_effect = lambda url: feed(at=NOW-86400) if 'rss' in url else '<h2>Community-Deals</h2>'
        result = self.run_at()
        self.assertEqual(result['sent'], 0)
        self.assertEqual(result['rejected']['STALE_OR_UNDATED'], 2)

    def test_failed_send_retry_and_checkpoint_after_success_only(self):
        checkpoint = Mock()
        self.send.side_effect = RuntimeError('offline')
        result = self.run_at(checkpoint=checkpoint)
        self.assertEqual(result['sent'], 0)
        self.assertEqual(self.state['community_watch']['delivered'], {})
        checkpoint.assert_not_called()
        self.send.side_effect = None
        self.assertEqual(self.run_at(NOW+300, checkpoint=checkpoint)['sent'], 1)
        checkpoint.assert_called_once_with(self.state)

    def test_dry_run_does_not_mark_delivered(self):
        result = c.run(self.cfg, self.state, self.client, NOW)
        self.assertEqual(len(result['alerts']), 1)
        self.assertEqual(self.state['community_watch']['delivered'], {})
        self.assertEqual(self.run_at(NOW+300)['sent'], 1)

    def test_failure_of_one_source_does_not_stop_other_sources(self):
        def read(url):
            if url == c.SOURCES[0][1]:
                raise TimeoutError('timeout')
            return self.read(url)
        self.client.text.side_effect = read
        result = self.run_at()
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['sources'][0]['status'], 'unavailable')

    def test_radar_age_and_canonical_mirror_identity(self):
        body = '<h2>Community-Deals</h2><div class="deal"><a href="'+URL+'?utm_source=radar#x">'+TITLE+'</a><span>vor 1 Minute</span></div>'
        rows = c.radar(body, NOW)
        self.assertEqual(rows[0]['published'], NOW-120)
        self.assertEqual(c.article_url(rows[0]['url']), URL)
        self.assertIsNone(c.radar(body.replace('1 Minute', '1 Tag'), NOW)[0]['published'])

    def test_not_product_not_open_waitlist_and_overpriced(self):
        for obj in [article(title='Pokemon Center Deutschland Plüschtier'), article(title=TITLE+' ausverkauft'), article(title=TITLE+' Waitlist'), article(price=350), article(price='NaN'), article(status='Moderated'), article(deletedAt=NOW-10)]:
            self.assertIsNotNone(c.qualify(obj, NOW, {})[1])

    def test_non_article_links_or_parser_errors_do_not_alert(self):
        for link in ['https://www.mydealz.de/login', 'https://www.mydealz.de.evil/deals/a-123456', 'http://www.mydealz.de/deals/a-123456']:
            self.assertIsNone(c.article_url(link))
        for body in ['<html>Access denied</html>', '<rss><channel>', '<!DOCTYPE rss [<!ENTITY x "oops">]><rss><channel/></rss>']:
            with self.assertRaises(Exception): c.rss(body)
        with self.assertRaises(ValueError): c.original('<h1>Access denied</h1>', URL)

    def test_disabled_has_no_requests_or_mutation(self):
        self.assertEqual(c.run({}, self.state, self.client, NOW)['sent'], 0)
        self.client.text.assert_not_called()
        self.assertEqual(self.state, {})
