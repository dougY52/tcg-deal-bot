from datetime import datetime, timezone
import unittest
from unittest.mock import Mock
from tcg_bot import community_watch as c, telegram_sources as t
from tests.test_community_watch import NOW, DE, URL, page, article


def preview(text=None, at=NOW-60, extra='', channel='Bisafans', message_id=42):
    text = text or ('Pokémon Center Deutschland: Booster Display Deutsch jetzt verfügbar <a href="'+DE+'">Shop</a> 99,99 €')
    date = datetime.fromtimestamp(at, timezone.utc).isoformat()
    post = channel+'/'+str(message_id)
    return '<div data-post="'+post+'">'+extra+'<div class="tgme_widget_message_text">'+text+'</div><a class="tgme_widget_message_date" href="https://t.me/'+post+'"><time datetime="'+date+'">12:00</time></a></div>'


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'community_watch': {'enabled': True, 'telegram_channels': ['Bisafans']}}
        self.state = {}
        self.body = preview()
        self.client = Mock(spec=['text'])
        self.client.text.side_effect = lambda url: self.body if 't.me/' in url else (page(article()) if url == URL else ('<rss><channel/></rss>' if '/rss/' in url else '<h2>Community-Deals</h2>'))
        self.send = Mock(return_value='id')

    def run_at(self, at=NOW, send=True):
        return c.run(self.cfg, self.state, self.client, at, self.send if send else None)

    def test_public_message_alert_and_persisted_dedup(self):
        self.assertEqual(self.run_at()['sent'], 1)
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        embed = self.send.call_args.args[0]['embeds'][0]
        self.assertIn('Telegram · Bisafans', embed['footer']['text'])
        self.assertEqual(embed['url'], 'https://t.me/Bisafans/42')
        self.assertIn('99.99', embed['description'])
        self.assertIn('nicht live bestätigt', embed['description'])

    def test_old_forwarded_future_missing_dates_and_quotes_rejected(self):
        for body in [preview(at=NOW-1801), preview(at=NOW+1), preview().replace('datetime=', 'unknown='), preview(extra='<a class="tgme_widget_message_forwarded_from">Forwarded</a>'), preview(text='<blockquote>Pokémon Center Deutschland ETB verfügbar</blockquote>')]:
            self.body = body
            self.state = {}
            self.assertEqual(self.run_at()['sent'], 0)

    def test_german_channel_does_not_imply_german_shop(self):
        for text in ['Pokémon Center ETB verfügbar', 'Pokémon Center UK ETB verfügbar', 'Pokémon Center Deutschland ETB English verfügbar', 'Pokémon Center Deutschland ETB nicht verfügbar', 'Pokémon Center Deutschland ETB morgen verfügbar', 'Pokémon Center Deutschland ETB angekündigt', 'Pokémon Center Deutschland Plüschtier verfügbar', 'Pokémon Center Deutschland ETB verfügbar für 350 €', 'Pokémon Center Deutschland ETB war verfügbar']:
            self.body = preview(text=text)
            self.state = {}
            self.assertEqual(self.run_at()['sent'], 0, text)

    def test_queue_current_germany_only(self):
        self.body = preview(text='Pokémon Center Deutschland Warteschlange jetzt offen')
        self.assertEqual(self.run_at()['sent'], 1)
        self.state = {}
        self.body = preview(text='Pokémon Center Deutschland Warteschlange jetzt offen', at=NOW-901)
        self.assertEqual(self.run_at()['sent'], 0)

    def test_mydealz_mirror_uses_original_id_and_original_expiry(self):
        self.body = preview(text='Pokémon Center Deutschland ETB verfügbar <a href="'+URL+'">Quelle</a>')
        self.assertEqual(self.run_at()['sent'], 1)
        self.assertIn('mydealz:123456', self.state['community_watch']['delivered'])
        self.body = self.body.replace('Bisafans/42', 'Bisafans/43')
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.state = {}
        reader = self.client.text.side_effect
        self.client.text.side_effect = lambda url: page(article(isExpired=True)) if url == URL else reader(url)
        self.assertEqual(self.run_at()['sent'], 0)

    def test_failure_retry_and_dry_run_never_mark_sent(self):
        self.assertEqual(len(self.run_at(send=False)['alerts']), 1)
        self.assertEqual(self.state['community_watch']['delivered'], {})
        self.send.side_effect = RuntimeError('offline')
        self.assertEqual(self.run_at(NOW+300)['sent'], 0)
        self.send.side_effect = None
        self.assertEqual(self.run_at(NOW+600)['sent'], 1)

    def test_no_message_preview_is_error_not_healthy_empty_feed(self):
        self.body = '<h1>Join Telegram</h1>'
        result = self.run_at()
        self.assertEqual(result['sources'][-1]['status'], 'unavailable')
        self.assertEqual(result['sent'], 0)

    def test_hidden_preview_text_and_wrong_channel_are_not_evidence(self):
        self.body = preview(text='Pokémon Center ETB verfügbar')+'<aside>Pokémon Center Deutschland</aside>'
        self.assertEqual(self.run_at()['sent'], 0)
        self.body = preview(channel='Untrusted')
        self.state = {}
        self.assertEqual(self.run_at()['sent'], 0)

    def test_safe_channel_names_and_timestamp_identity(self):
        for channel in ['../secret', 'https://host', 'Bisafans?x=1', 'a', '@Bisafans']:
            self.assertFalse(t.valid_channel(channel))
        self.assertEqual(t.parse(preview(), 'Bisafans')[0]['published'], NOW-60)
        self.assertEqual(t.parse(preview().replace('https://t.me/Bisafans/42', 'https://t.me/Other/42'), 'Bisafans'), [])
