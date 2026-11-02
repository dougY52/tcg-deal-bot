import unittest
import json
from datetime import datetime, timezone
from unittest.mock import Mock

from tcg_bot.http import FetchError
from tcg_bot.pokemon_center_gate import QueueProbe, public_signal, provider_snapshot, run_gate, acknowledge
from tcg_bot import pokemon_center_watch

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


class GatedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.send = Mock(return_value='discord-receipt')
        self.probe = Mock(side_effect=lambda now: provider_snapshot({'status_code': 200, 'html': QUEUE+DE}, now))
        self.cfg = {'enabled': True}
        self.source = {'id': 'pc-de-store', 'name': 'Pokemon Center DE', 'kind': 'store',
                       'url': 'https://www.pokemoncenter.com/de-de/', 'interval_seconds': 60}

    def scan(self, now, state='live', direct='<h1>Additional security check is required</h1>'):
        data = {'success': True, 'data': {'state': state, 'ageMs': 0,
            'lastChecked': datetime.fromtimestamp(now, timezone.utc).isoformat()}}
        client = Mock(spec=['text'])
        client.text.side_effect = lambda url: json.dumps(data) if 'stock-watch' in url else direct
        gate, observation = run_gate(self.cfg, self.state, client, now, self.probe, interval=60)
        report = pokemon_center_watch.run({'sources': [self.source]}, self.state, client,
                                         now, self.send, queue_observation=observation)
        acknowledge(self.state)
        return gate, report

    def test_no_queue_never_uses_credits_or_sends(self):
        for i, status in enumerate(('open', 'opening', 'gated', 'unknown')):
            self.scan(NOW+i*60, status)
        self.probe.assert_not_called()
        self.send.assert_not_called()

    def test_real_de_evidence_sends_once_and_new_wave_can_alert(self):
        self.scan(NOW)
        self.scan(NOW+60)
        self.assertEqual(self.send.call_count, 1)
        self.assertEqual(self.probe.call_count, 1)
        self.scan(NOW+120, 'open')
        self.scan(NOW+180, 'open')
        self.scan(NOW+240)
        self.assertEqual(self.send.call_count, 2)
        self.assertEqual(self.probe.call_count, 2)
        self.assertEqual(self.state['pc_de']['sources']['pc-de-store']['queue_episode'], 2)

    def test_shared_queue_and_failed_page_never_alert_and_attempts_are_bounded(self):
        self.probe.side_effect = lambda now: provider_snapshot({'status_code': 200, 'html': QUEUE}, now)
        for offset in (0, 60, 120, 420, 720): self.scan(NOW+offset)
        self.assertEqual(self.probe.call_count, 3)
        self.send.assert_not_called()
        self.assertEqual(len(self.state['pc_queue_gate']['reservations']), 3)

    def test_failed_discord_delivery_reuses_fresh_confirmation_without_new_credits(self):
        self.send.side_effect = [RuntimeError('send failed'), 'discord-receipt']
        self.scan(NOW)
        self.assertFalse(self.state['pc_queue_gate']['acknowledged'])
        self.scan(NOW+60)
        self.assertTrue(self.state['pc_queue_gate']['acknowledged'])
        self.assertEqual(self.probe.call_count, 1)
        self.assertEqual(len(self.state['pc_de']['delivered']), 1)

    def test_monthly_and_daily_reservations_stop_provider(self):
        for entries in ([NOW-2*86400]*48, [NOW-1000]*6):
            self.state = {'pc_queue_gate': {'reservations': entries}}
            gate, _ = self.scan(NOW)
            self.assertEqual(gate['status'], 'confirmation_budget_exhausted')
        self.probe.assert_not_called()

    def test_no_second_alert_when_direct_page_already_confirmed_same_wave(self):
        self.probe.side_effect = [provider_snapshot({'status_code': 200, 'html': QUEUE}, NOW),
                                 provider_snapshot({'status_code': 200, 'html': QUEUE+DE}, NOW+120)]
        self.scan(NOW, direct=QUEUE+DE)
        self.scan(NOW+60, direct=QUEUE+DE)
        self.scan(NOW+120)
        self.assertEqual(self.send.call_count, 1)

    def test_write_failure_cannot_spend_before_reservation_is_saved(self):
        client = Mock()
        client.text.return_value = json.dumps({'success': True, 'data': {
            'state': 'live', 'lastChecked': STAMP, 'ageMs': 0}})
        with self.assertRaises(OSError):
            run_gate(self.cfg, self.state, client, NOW, self.probe,
                     checkpoint=Mock(side_effect=OSError('disk failure')))
        self.probe.assert_not_called()

    def test_unknown_does_not_close_and_restart_wave(self):
        self.scan(NOW)
        self.scan(NOW+60, 'unknown')
        self.scan(NOW+120)
        self.assertEqual(self.send.call_count, 1)
        self.assertEqual(self.probe.call_count, 1)

    def test_cost_change_halts_future_paid_requests(self):
        self.probe.side_effect = FetchError('PC_PROVIDER_COST_CHANGED_STOPPED')
        self.scan(NOW)
        self.scan(NOW+300)
        self.assertEqual(self.probe.call_count, 1)
        self.assertTrue(self.state['pc_queue_gate']['provider_halted'])

    def test_public_rate_limit_is_persisted_across_runs(self):
        client = Mock(spec=['text', 'cooldowns'])
        client.cooldowns = {'stock-watch.co.uk': NOW+3600}
        client.text.side_effect = FetchError('HTTP 429')
        run_gate(self.cfg, self.state, client, NOW, self.probe)
        result, observation = run_gate(self.cfg, self.state, client, NOW+300, self.probe)
        self.assertEqual(result['status'], 'public_signal_backoff')
        self.assertIsNone(observation)
        client.text.assert_called_once()
        self.probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
