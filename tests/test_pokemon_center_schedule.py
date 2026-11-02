from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from tcg_bot.pc_schedule import peak_window, effective_config, due
from tcg_bot.pokemon_center_watch import run
from scripts.watch_pokemon_center_de import main


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()


class PokemonCenterScheduleTests(unittest.TestCase):
    def test_winter_window_exact_boundaries(self):
        for time, active in [('14:59:59', False), ('15:00:00', True), ('18:59:59', True), ('19:00:00', False)]:
            self.assertEqual(peak_window(stamp('2026-11-02T'+time)), active)

    def test_summer_window_exact_boundaries(self):
        for time, active in [('13:59:59', False), ('14:00:00', True), ('17:59:59', True), ('18:00:00', False)]:
            self.assertEqual(peak_window(stamp('2027-07-02T'+time)), active)

    def test_config_only_changes_peak_sources_without_mutating_input(self):
        cfg = {'sources': [{'id': 'store'}], 'community_watch': {'interval_seconds': 240}}
        result = effective_config(cfg, stamp('2026-11-02T15:30:00'))
        self.assertEqual(result['sources'][0]['interval_seconds'], 60)
        self.assertTrue(result['community_watch']['minute_slots'])
        self.assertNotIn('interval_seconds', cfg['sources'][0])
        self.assertEqual(effective_config(cfg, stamp('2026-11-02T19:00:00')), cfg)

    def test_minute_bucket_handles_jitter_but_not_duplicate_starts(self):
        self.assertTrue(due(121, 180, 60, True))
        self.assertFalse(due(121, 179, 60, True))
        self.assertFalse(due(121, 120, 60, True))
        self.assertFalse(due(121, 180, 240, False))

    def test_real_queue_is_checked_next_minute_without_resending(self):
        source = dict(id='pc', name='PC', kind='store', url='https://www.pokemoncenter.com/de-de/')
        cfg = effective_config({'sources': [source], 'community_watch': {}}, stamp('2026-11-02T15:00:00'))
        client, state, send = Mock(spec=['text']), {}, Mock(return_value='receipt')
        client.text.return_value = '<h1>Virtual Queue Germany</h1><p>You are now in line. Keep this window open.</p>'
        now = stamp('2026-11-02T15:00:20')
        run(cfg, state, client, now, send)
        run(cfg, state, client, now+10, send)
        run(cfg, state, client, now+55, send)
        self.assertEqual(client.text.call_count, 2)
        send.assert_called_once()

    def test_delayed_minute_trigger_after_window_performs_no_scan(self):
        with patch('sys.argv', ['watch', '--minute', '--send']), patch('scripts.watch_pokemon_center_de.time.time', return_value=stamp('2026-11-02T19:00:00')), patch('scripts.watch_pokemon_center_de.QueueClient') as client:
            self.assertEqual(main()['skipped'], 'outside_peak_window')
            client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
