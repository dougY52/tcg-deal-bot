import json
import time
import unittest
from unittest.mock import Mock, patch

from scripts.test_pc_discord import FIXTURE, label_test, public_report, simulate, usage_report


def capture(html):
    data = dict(version=1, home_path='/de-de/', primary_frames=0,
                documents=[dict(kind='home', html=html)])
    return '<script id="tcg-queue-visible-v1">'+json.dumps(data).replace('<', '\\u003c')+'</script>'


class DiscordSimulationTests(unittest.TestCase):
    def test_one_labeled_message_and_persistent_duplicate_suppressed(self):
        post = Mock(return_value='test-receipt')
        report = simulate(capture(FIXTURE), time.time(), time.perf_counter(), post)
        self.assertEqual(report['discord_messages_sent'], 1)
        self.assertEqual(report['duplicate_messages_sent'], 0)
        self.assertEqual(report['duplicate_rejections'], 1)
        self.assertEqual(report['provider_credits_consumed'], 0)
        self.assertFalse(report['live_queue_detection_verified'])
        self.assertFalse(report['phone_push_latency_verified'])
        post.assert_called_once()
        message = post.call_args.args[0]
        self.assertIn('KEIN ECHTER DROP', message['content'])
        self.assertTrue(message['embeds'][0]['title'].startswith('🧪 TEST'))
        self.assertEqual(message['allowed_mentions'], {'parse': []})
        self.assertNotIn('url', message['embeds'][0])

    def test_missing_realistic_queue_evidence_never_sends(self):
        post = Mock()
        with self.assertRaises(RuntimeError):
            simulate(capture('<h1>Additional security check is required</h1>'), time.time(), time.perf_counter(), post)
        post.assert_not_called()

    def test_delivery_uncertainty_does_not_send_second_message(self):
        post = Mock(side_effect=RuntimeError('uncertain'))
        with self.assertRaises(RuntimeError):
            simulate(capture(FIXTURE), time.time(), time.perf_counter(), post)
        post.assert_called_once()

    def test_labels_cannot_mutate_regular_payload(self):
        original = {'embeds': [{'title': 'DE Queue', 'description': 'Live!', 'url': 'https://example.test/'}]}
        label_test(original, time.time())
        self.assertEqual(original['embeds'][0]['title'], 'DE Queue')

    def test_usage_only_reads_balance_without_spending_or_exposing_key(self):
        data = dict(plan_name='Free', plan_total_credits=10000, remained_credits=6000,
                    start_date='2030-01-01T00:00:00', end_date='2030-02-01T00:00:00', private='not exported')
        with patch('scripts.test_pc_discord.FreeAccessProbe') as factory:
            factory.return_value.request_json.return_value = data, None
            result = usage_report('secret-key')
            factory.return_value.request_json.assert_called_once_with('usage')
        self.assertEqual(result['reads_before_reserve'], 40)
        self.assertEqual(result['period_end'], '2030-02-01T00:00:00')
        self.assertNotIn('secret', str(result))
        self.assertNotIn('private', str(result))

    def test_public_report_excludes_receipt_timestamps_and_account_details(self):
        report = simulate(capture(FIXTURE), time.time(), time.perf_counter(), Mock(return_value='private-receipt'))
        report['provider_usage'] = {'remaining_credits': 6000, 'period_end': 'private-date'}
        safe = public_report(report)
        for key in ('provider_usage', 'discord_message_id', 'simulation_started_at', 'discord_acknowledged_at'):
            self.assertNotIn(key, safe)
        self.assertNotIn('private', json.dumps(safe))
        self.assertEqual(safe['discord_messages_sent'], 1)


if __name__ == '__main__':
    unittest.main()
