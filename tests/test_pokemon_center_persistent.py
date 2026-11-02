import json
import unittest

from scripts.probe_pc_transport import observation_times, rendered_observation

NOW = 1793664000
QUEUE = '<h1>Virtual Queue</h1><p>You are now in line.</p>'
DE = '<p>Today German TCG products launch in the Germany store.</p>'


def captured(body, *, path='/de-de/'):
    value = {'version': 1, 'home_path': path, 'primary_frames': 0,
             'documents': [{'kind': 'home', 'html': body}]}
    return '<script id="tcg-queue-visible-v1">'+json.dumps(value)+'</script>'


class PersistentBrowserProbeTests(unittest.TestCase):
    def test_five_minute_window_is_bounded_and_not_only_an_initial_sample(self):
        samples = observation_times(300)
        self.assertEqual(samples[:3], [3, 15, 30])
        self.assertEqual(samples[-1], 300)
        self.assertEqual(len(samples), 12)
        self.assertTrue(all(0 < b-a <= 30 for a, b in zip(samples, samples[1:])))
        for value in (0, 29, 301, 3600, True, 30.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                observation_times(value)

    def test_error_http_response_overrides_positive_looking_document(self):
        for status in (None, 403, 429, 500):
            with self.subTest(status=status):
                result = rendered_observation(captured(QUEUE+DE), status, NOW)
                self.assertNotEqual(result['status'], 'queue_open_de')
                self.assertIsNone(result['region'])

    def test_only_visible_germany_queue_can_be_a_positive_observation(self):
        result = rendered_observation(captured(QUEUE+DE), 200, NOW)
        self.assertEqual(result['status'], 'queue_open_de')
        self.assertEqual(result['region'], 'DE')
        self.assertTrue(result['rendered_visibility'])
        self.assertFalse(result['inventory_confirmed'])

    def test_hidden_or_uncaptured_germany_cannot_turn_shared_queue_into_de(self):
        for body in (QUEUE+DE, QUEUE+DE+captured(QUEUE)):
            with self.subTest(body=body):
                self.assertNotEqual(rendered_observation(body, 200, NOW)['status'], 'queue_open_de')

    def test_bad_region_and_missing_or_incomplete_capture_fail_closed(self):
        for body in ('', captured(QUEUE+DE, path='/en-gb/'),
                     '<script id="tcg-queue-visible-v1">broken</script>'):
            with self.subTest(body=body):
                self.assertNotEqual(rendered_observation(body, 200, NOW)['status'], 'queue_open_de')
