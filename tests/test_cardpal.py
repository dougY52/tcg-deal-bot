import io
import json
from email.message import Message
import unittest
from urllib.error import HTTPError

from tcg_bot.cardpal import CardPalClient, CardPalError, NoRedirects, audit, drop_record, germany_url, read_sse


class Response(io.BytesIO):
    status = 200

    def __init__(self, body, content_type='application/json'):
        super().__init__(body)
        self.headers = Message()
        self.headers['Content-Type'] = content_type


def response(value):
    return Response(json.dumps(value).encode())


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def item(**changes):
    return dict({'dedupe_key': 'broadcast:pokecenter-drop:123',
                 'template': 'Pokémon Center Deutschland Drop',
                 'created_at': '2026-11-01T12:00:00Z',
                 'url': 'https://www.pokemoncenter.com/de-de/product/10-123-100/box'}, **changes)


class CardPalTests(unittest.TestCase):
    def test_only_own_pc_broadcast_type_selected(self):
        self.assertIsNone(drop_record(item(dedupe_key='private-message:1'), 0))
        self.assertIsNone(drop_record(item(dedupe_key='broadcast:pokecenter-dropfake'), 0))

    def test_region_requires_explicit_evidence(self):
        self.assertEqual(drop_record(item(), 0)['region'], 'DE')
        self.assertEqual(drop_record(item(url=None, template='Drop live'), 0)['region'], 'unconfirmed')

    def test_conflicting_region_rejected(self):
        for title in ('Pokémon Center UK drop', 'Not for Germany', 'Nicht für Deutschland'):
            self.assertNotEqual(drop_record(item(template=title), 0)['region'], 'DE')

    def test_links_cannot_escape_or_leak_queries(self):
        base = 'https://www.pokemoncenter.com/de-de/'
        self.assertEqual(germany_url(base+'?token=private#abc'), base)
        for value in ('https://www.pokemoncenter.com.evil/de-de/',
                      'https://www.pokemoncenter.com/en-gb/',
                      'https://user:secret@www.pokemoncenter.com/de-de/',
                      base+'%2e%2e/private', base+'../private'):
            self.assertIsNone(germany_url(value))

    def test_inbox_age_is_not_latency(self):
        record = drop_record(item(), 1793620805)
        self.assertIsNone(record['shop_drop_to_cardpal_seconds'])
        self.assertNotIn('delivery_latency', record)
        self.assertFalse(record['shop_stock_confirmed'])

    def test_unknown_date_not_synthesized(self):
        for date in (None, 'bad', '2026-11-01T12:00:00'):
            self.assertIsNone(drop_record(item(created_at=date), 0)['published_at'])

    def test_sse_frames_multiline_and_comments(self):
        lines = [b': keepalive\r\n', b'event: notification\r\n', b'data: {\r\n',
                 b'data: "new_count": 1}\r\n', b'\r\n']
        self.assertEqual(list(read_sse(lines)), [('notification', {'new_count': 1})])

    def test_sse_bounds_and_bad_json(self):
        for lines in ([b'x'*16385], [b'data: not-json\n', b'\n']):
            with self.assertRaises(CardPalError):
                list(read_sse(lines))

    def test_redirects_never_forward_login_or_tokens(self):
        with self.assertRaisesRegex(CardPalError, 'REDIRECT_REJECTED'):
            NoRedirects().redirect_request(None, None, 307, None, None, 'https://evil.test')

    def test_errors_never_export_response_or_secret(self):
        secret = 'a-private-user-password'
        err = HTTPError('https://url?token='+secret, 401, secret, {}, io.BytesIO(secret.encode()))
        report = audit(CardPalClient(Opener(err)), 'owner@example.test', secret)
        self.assertEqual(report['error'], 'HTTP_401')
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn('owner@example.test', json.dumps(report))

    def test_missing_credentials_never_requests(self):
        opener = Opener()
        report = audit(CardPalClient(opener), '', '')
        self.assertEqual(report['status'], 'requires_credentials')
        self.assertEqual(opener.requests, [])

    def test_unexpected_library_exception_is_redacted(self):
        opener = Opener(RuntimeError('private token in response or URL'))
        report = audit(CardPalClient(opener), 'owner@example.test', 'password')
        self.assertEqual(report['error'], 'UNEXPECTED_CLIENT_ERROR')
        self.assertNotIn('private token', json.dumps(report))

    def test_inbox_schema_fail_closed(self):
        client = CardPalClient(Opener(response({'items': 'not a list'})))
        with self.assertRaisesRegex(CardPalError, 'INVALID_INBOX_SCHEMA'):
            client.inbox()

    def test_empty_inbox_and_quiet_stream_do_not_prove_immediacy(self):
        opener = Opener(response({'access_token': 'fake-access-token'}),
                        response({'email': 'private@example.test', 'allow_drop_notifications': True}),
                        response({'items': [], 'total': 0}),
                        response({'token': 'fake-stream-token'}),
                        Response(b': heartbeat\n\n', 'text/event-stream'))
        client = CardPalClient(opener, clock=lambda: 1793534400)
        report = audit(client, 'owner@example.test', 'private-password')
        self.assertEqual(report['status'], 'transport_verified')
        self.assertEqual(report['latency_verdict'], 'no_live_drop_sample')
        self.assertFalse(report['instant_shop_detection_verified'])
        self.assertEqual(report['discord_sent'], 0)
        self.assertIsNone(client.token)
        self.assertNotIn('private@example.test', json.dumps(report))

    def test_live_event_samples_and_deduplicates_publication_delay(self):
        from tcg_bot.cardpal import stamp
        now = stamp('2026-11-01T12:00:00Z')
        opener = Opener(response({'token': 'fake-stream-token'}),
                        Response(b'event: notification\ndata: {}\n\n'*2, 'text/event-stream'),
                        response({'items': [item()], 'total': 1}),
                        response({'items': [item()], 'total': 1}))
        client = CardPalClient(opener, clock=lambda: now)
        result = client.probe_stream([], seconds=30)
        self.assertEqual(len(result['new_de_broadcasts']), 1)
        self.assertEqual(result['publication_to_receipt_seconds'], [0.0])
        self.assertIsNone(result['shop_drop_to_cardpal_seconds'])

    def test_old_or_wrong_region_events_not_latency_samples(self):
        opener = Opener(response({'token': 'fake-stream-token'}),
                        Response(b'event: notification\ndata: {}\n\n', 'text/event-stream'),
                        response({'items': [item(), item(dedupe_key='broadcast:pokecenter-drop:2',
                                                         template='UK drop')], 'total': 2}))
        client = CardPalClient(opener, clock=lambda: 1793620800)
        result = client.probe_stream([])
        self.assertEqual(result['new_de_broadcasts'], [])


if __name__ == '__main__':
    unittest.main()
