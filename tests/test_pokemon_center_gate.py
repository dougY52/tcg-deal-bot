import unittest
from unittest.mock import Mock

from tcg_bot.http import FetchError
from tcg_bot.pokemon_center_gate import QueueProbe, public_signal, provider_snapshot

NOW = 1793647560
STAMP = '2026-11-02T19:26:00Z'
QUEUE = '<h1>Virtual Queue</h1><p>You are now in line.</p>'
DE = '<p>The queue is for the Germany store.</p>'
FRAME = '<iframe id="main-iframe" src="/_Incapsula_Resource?challenge=secret"></iframe>'


class GateTests(unittest.TestCase):
    def signal(self, state='live', **changes):
        return {'success': True, 'data': dict(state=state, lastChecked=STAMP, ageMs=0, **changes)}

    def test_only_live_is_a_trigger_and_never_germany_proof(self):
        for state in ('live', 'open', 'opening', 'gated', 'unknown'):
            value = public_signal(self.signal(state), NOW)
            self.assertEqual(value['trigger'], state == 'live')
            self.assertFalse(value['germany_confirmed'])

    def test_stale_future_or_bad_time_never_triggers(self):
        for key, value in [('lastChecked', '2026-11-01T19:26:00Z'),
                           ('lastChecked', '2026-11-03T19:26:00Z'),
                           ('lastChecked', '2026-11-02T19:26:00'),
                           ('ageMs', 180000), ('ageMs', float('nan')), ('ageMs', True)]:
            signal = self.signal(); signal['data'][key] = value
            self.assertFalse(public_signal(signal, NOW)['trigger'])

    def test_schema_errors_never_trigger(self):
        for value in (None, [], {}, {'success': True, 'data': None}):
            self.assertFalse(public_signal(value, NOW)['trigger'])

    def test_exact_observed_frame_can_confirm_de(self):
        result = provider_snapshot({'status_code': 200, 'html': FRAME,
            'iframes': [{'src': 'https://www.pokemoncenter.com/_Incapsula_Resource?challenge=secret',
                        'html': QUEUE+DE}], 'cookies': 'private'}, NOW)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertFalse(result['inventory_confirmed'])
        self.assertNotIn('secret', str(result))
        self.assertNotIn('private', str(result))

    def test_unrelated_or_missing_frame_never_confirms(self):
        for frames in ([], [{'src': 'https://evil.test/', 'html': QUEUE+DE}]):
            with self.assertRaises(FetchError):
                provider_snapshot({'status_code': 200, 'html': FRAME, 'iframes': frames}, NOW)

    def test_shared_queue_and_security_page_cannot_confirm_de(self):
        for body, expected in ((QUEUE, 'queue_open_region_unknown'),
                ('<h1>Additional security check is required</h1>', 'blocked')):
            result = provider_snapshot({'status_code': 200, 'html': body}, NOW)
            self.assertEqual(result['status'], expected)

    def test_target_error_never_confirms(self):
        with self.assertRaises(FetchError):
            provider_snapshot({'status_code': 403, 'html': QUEUE+DE}, NOW)

    def test_paid_or_exhausted_plan_never_fetches_target(self):
        for plan, credits in [('Enthusiast', 10000), ('Free', 124)]:
            probe = QueueProbe('test-key', Mock(), max_credits=125)
            probe.request_json = Mock(return_value=({'plan_name': plan,
                'plan_total_credits': 10000, 'remained_credits': credits}, None))
            with self.assertRaises(FetchError): probe.check(NOW)
            self.assertEqual(probe.reserved, 0)
            self.assertEqual(probe.request_json.call_count, 1)

    def test_free_page_request_has_no_main_selector_or_session_replay(self):
        probe = QueueProbe('test-key', Mock(), max_credits=125)
        probe.request_json = Mock(side_effect=[({'plan_name': 'Free',
            'plan_total_credits': 10000, 'remained_credits': 10000}, None),
            ({'status_code': 200, 'html': QUEUE+DE}, 125)])
        self.assertEqual(probe.check(NOW)['status'], 'queue_open_de')
        params = probe.request_json.call_args.args[1]
        self.assertNotIn('wait_for_selector', params)
        self.assertNotIn('cookies', params)
        self.assertEqual(params['proxy_country'], 'DE')
        self.assertEqual(probe.reserved, 125)


if __name__ == '__main__':
    unittest.main()
