"""German local-time peak window for the independent Pokémon Center watch."""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo


def peak_window(now):
    return 16 <= datetime.fromtimestamp(now, ZoneInfo('Europe/Berlin')).hour < 20


def effective_config(cfg, now):
    result = copy.deepcopy(cfg)
    if peak_window(now):
        for source in result['sources']:
            source.update(interval_seconds=60, minute_slots=True)
        result['community_watch'].update(interval_seconds=60, minute_slots=True)
    return result


def due(last, now, interval=240, minute_slots=False):
    # One observation per wall-clock minute survives small runner-start jitter.
    # Source errors and Retry-After are handled separately by the caller.
    return int(now//60) > int(last//60) if minute_slots else now-last >= interval
