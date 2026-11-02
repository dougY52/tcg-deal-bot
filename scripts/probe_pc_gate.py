"""Explicit one-page free-plan test. No Discord credentials or bot-state edits."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from tcg_bot.http import Client, FetchError
from tcg_bot.pokemon_center_gate import STATUS_URL, QueueProbe, public_signal


def main():
    client = Client()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'discord_sent': 0}
    try:
        report['signal'] = public_signal(json.loads(client.text(STATUS_URL)), time.time())
    except Exception:
        report['signal'] = {'state': 'unknown', 'trigger': False}
    key = os.environ.get('SCRAPINGANT_API_KEY', '')
    if not key:
        report['confirmation'] = {'status': 'MISSING_PROVIDER_SECRET'}
    else:
        probe = QueueProbe(key, client, max_credits=125)
        try:
            result = probe.check(time.time())
            result.pop('banner', None)
            report['confirmation'] = result
        except FetchError as error:
            report['confirmation'] = {'status': 'unavailable', 'reason': str(error)}
        except Exception:
            report['confirmation'] = {'status': 'unavailable', 'reason': 'UNEXPECTED_PROVIDER_ERROR'}
        report['reserved_credits'] = probe.reserved
    client.close()
    Path('pc-gate-probe.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PC_GATE_PROBE '+json.dumps(report))


if __name__ == '__main__':
    main()
