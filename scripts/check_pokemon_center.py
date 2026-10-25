"""Cloud-only access diagnostic; never sends Discord or modifies bot state."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from tcg_bot.http import Client, FetchError
from tcg_bot.pokemon_center_access import TARGETS, MODES, FreeAccessProbe, page_result


def run():
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'discord_sent': False,
              'inventory_confirmed': False, 'results': []}
    client = Client()
    client.deadline = time.monotonic() + 210
    for url in TARGETS:
        row = {'route': 'direct', 'url': url}
        try:
            row.update(page_result(client.text(url), url, time.time()))
        except FetchError as exc:
            row.update(status='unavailable', reason=str(exc))
        report['results'].append(row)
    key = os.environ.get('SCRAPINGANT_API_KEY', '').strip()
    if not key:
        report['provider'] = 'not_configured'
    else:
        probe = FreeAccessProbe(key, client, max_credits=375)
        for mode in [MODES[-1]]:
            row = {'route': 'scrapingant', 'proxy_type': mode[0], 'browser': mode[1], 'url': TARGETS[0]}
            try:
                body, metadata = probe.fetch(TARGETS[0], mode)
                row.update(metadata, **page_result(body, TARGETS[0], time.time()))
            except FetchError as exc:
                row.update(status='unavailable', reason=str(exc))
            report['results'].append(row)
            if row.get('status') == 'readable_discovery_only':
                # Successful access still needs an exact product/variant validator.
                report['provider'] = 'readable_requires_product_validation'
                current = row
                for kind in ('category_links', 'candidate_links'):
                    links = current.get(kind, [])
                    if not links:
                        continue
                    target = links[0]['url']
                    extra = {'route':'scrapingant', 'proxy_type':mode[0], 'browser':mode[1], 'url':target}
                    try:
                        body, metadata = probe.fetch(target, mode)
                        extra.update(metadata, **page_result(body, target, time.time()))
                    except FetchError as exc:
                        extra.update(status='unavailable', reason=str(exc))
                    report['results'].append(extra)
                    current = extra
                break
            if row.get('reason') not in (None, 'PC_PROVIDER_HTTP_423', 'PC_PROVIDER_TARGET_NOT_HTTP_200'):
                report['provider'] = 'stopped_safely'
                break
        else:
            report['provider'] = 'no_readable_page'
        report['reserved_credits'] = probe.reserved
    client.close()
    Path('pokemon-center-access-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('POKEMON_CENTER_ACCESS ' + json.dumps(report, ensure_ascii=False))
    return report


if __name__ == '__main__':
    run()
