"""Explicit, read-only CardPal connection test. Never sends Discord messages."""
import json
import os
from pathlib import Path

from tcg_bot.cardpal import CardPalClient, audit


def main():
    report = audit(CardPalClient(), os.environ.get('CARDPAL_EMAIL', ''),
                   os.environ.get('CARDPAL_PASSWORD', ''))
    Path('cardpal-access-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('CARDPAL_AUDIT '+json.dumps(report))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as out:
            out.write('## CardPal – nur Verbindungstest\n\n')
            out.write('Status: **'+report['status']+'**\n\n')
            out.write('Discord: 0 Nachrichten. Sofortige Erkennung eines Shop-Drops: nicht nachgewiesen.\n\n')
            out.write('Posteingangsalter ist keine Zustellzeit. Ein Ereignis-Stream belegt nur den Transport.\n')
    return 0 if report['status'] == 'transport_verified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
