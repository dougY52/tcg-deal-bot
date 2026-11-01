"""Bootstrap owner secrets directly from GitHub to the authenticated own Worker.

No secret file, credential output, test Discord message or account setting edit.
"""
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from tcg_bot.cardpal import NoRedirects
from tcg_bot.cloud_reader import github_token

ORIGIN = 'https://tcg-mms-reader.tcg-deal-bot-dougy52.workers.dev'


def request(path, body=None):
    token = github_token(ORIGIN, 15)
    req = Request(ORIGIN + path, data=json.dumps(body).encode() if body is not None else None,
                  headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                           'User-Agent': 'TCGRetailWatch/1.0'})
    try:
        with build_opener(NoRedirects()).open(req, timeout=20) as response:
            value = json.loads(response.read(10001))
    except HTTPError as error:
        code = error.code
        try:
            payload = json.loads(error.read(1000))
            reason = payload.get('error', '')
        except Exception:
            reason = ''
        error.close()
        reason = reason if isinstance(reason, str) and re.fullmatch('[A-Z_0-9]{1,60}', reason) else 'NO_SAFE_DETAIL'
        print('CARDPAL_RELAY_HTTP', code, reason)
        raise RuntimeError('WORKER_REQUEST_FAILED') from None
    # Only known telemetry fields can leave the private service boundary.
    keys = ('configured', 'status', 'enabled_at', 'baseline_at', 'last_inbox_at',
            'last_stream_at', 'last_cycle_at', 'next_alarm', 'sent', 'last_error',
            'failures', 'delivery_unknown', 'delivery_errors', 'browser_minutes_used',
            'shop_drop_latency_verified', 'last_publication_to_delivery_seconds',
            'pokemon_deals_enabled', 'dealz_threshold_percent', 'discovery_articles')
    return {k: value[k] for k in keys if k in value}


def main():
    try:
        if os.environ.get('CARDPAL_RELAY_STATUS_ONLY') != 'true':
            fields = {'email': 'CARDPAL_EMAIL', 'password': 'CARDPAL_PASSWORD', 'webhook': 'DISCORD_WEBHOOK_URL'}
            body = {k: os.environ.get(v, '') for k, v in fields.items()}
            if not all(body.values()):
                print('CARDPAL_RELAY_MISSING_SECRET'); return 2
            body['pokemon_deals'] = True
            request('/cardpal/configure', body)
        result = {}
        for _ in range(12):
            result = request('/cardpal/status')
            if (result.get('status') == 'stream_connected' and result.get('pokemon_deals_enabled')) or result.get('last_error'):
                break
            time.sleep(5)
        print(json.dumps(result, indent=2))
        return 0 if result.get('status') == 'stream_connected' and result.get('pokemon_deals_enabled') else 2
    except Exception:
        # HTTPError and URLs can contain credentials. Never print the exception.
        print('CARDPAL_RELAY_SETUP_OR_STATUS_FAILED'); return 2


if __name__ == '__main__':
    raise SystemExit(main())
