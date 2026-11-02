"""Explicit, single Discord test using simulated DE data and isolated state.

No Pokemon Center or ScrapingAnt scrape request. Only the provider usage endpoint
is read. The ordinary parser, gate, sender and persistent dedupe are exercised.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from zoneinfo import ZoneInfo

from tcg_bot.__main__ import load_state, save_state
from tcg_bot.http import send_discord, webhook_url
from tcg_bot.pokemon_center_access import FreeAccessProbe, free_usage
from tcg_bot.pokemon_center_gate import HOME, STATUS_URL, provider_snapshot, run_gate, acknowledge
from tcg_bot.pokemon_center_watch import run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = dict(id='pc-de-store', name='SIMULATION · Pokémon Center Deutschland', kind='store', url=HOME)
FIXTURE = ('<html><body><div>Today products launch exclusively in the Pokémon Center Germany store.</div>'
           '<h1>Hi, Trainer! You’re in the virtual queue.</h1>'
           '<p>Please keep this window open. Estimated wait time: 00:15:00.</p></body></html>')


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def label_test(payload, started_at):
    """Every outbound diagnostic message is unmistakably a test."""
    message = copy.deepcopy(payload)
    message['content'] = '🧪 **TESTMELDUNG – KEIN ECHTER DROP / KEINE ECHTE WARTESCHLANGE**'
    message['allowed_mentions'] = {'parse': []}
    stamp = datetime.fromtimestamp(started_at, ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y %H:%M:%S %Z')
    for embed in message.get('embeds', []):
        embed['title'] = '🧪 TEST · Deutscher Queue-Start simuliert'
        embed['description'] = ('**Nur ein Funktionstest – Pokémon Center wurde dafür nicht live geprüft.**\n'
            'Simulierter Deutschland-Hinweis → normaler Bot-Parser → Discord.\n'
            f'🕒 Simulation gestartet: **{stamp}**\n'
            'Die Laufzeit bis zur Discord-Bestätigung steht anschließend im Chat und Testbericht.\n'
            '**Kein tatsächlicher Drop, Bestand oder Kaufzugang. Du musst dich nicht anstellen.**')
        embed.pop('url', None)
        embed['color'] = 0x9B59B6
        embed['footer'] = {'text': 'Manuell angeforderter Test · Produktions-State bleibt unverändert'}
    return message


def usage_report(key):
    if not key:
        return {'status': 'missing_secret'}
    try:
        # No policy/target client is needed for this usage-only request.
        data, _ = FreeAccessProbe(key, None).request_json('usage')
        result = free_usage(data, 0)
        return dict(status='ok', **result, total_credits=data['plan_total_credits'],
            period_start=str(data.get('start_date', ''))[:40],
            period_end=str(data.get('end_date', ''))[:40],
            browser_read_credits=125, reads_before_reserve=int(max(0, result['remaining_credits']-1000)//125),
            monitor_cap_reads_30d=48, max_reads_per_wave=3, max_reads_per_day=6)
    except Exception as error:
        return {'status': 'unavailable', 'error_type': type(error).__name__}


def browser_snapshot():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page()
        def route(request):
            if request.request.url == HOME:
                request.fulfill(status=200, content_type='text/html', body=FIXTURE)
            else:
                request.abort()
        page.route('**/*', route)
        try:
            started_at, start_clock = time.time(), time.perf_counter()
            page.goto(HOME)
            page.evaluate('async () => {'+ROOT.joinpath('tcg_bot/pc_queue_dom.js').read_text()+'}')
            body = page.content()
            return started_at, start_clock, body
        finally:
            browser.close()


def simulate(body, started_at, start_clock, post):
    calls, timing = [], {}
    class SignalOnly:
        def text(self, url):
            if url != STATUS_URL:
                raise AssertionError('No shop/source network requests in simulation')
            return json.dumps({'success': True, 'data': dict(state='live', ageMs=0, lastChecked=iso(time.time()))})
    def probe(at):
        calls.append(at)
        return dict(provider_snapshot({'status_code': 200, 'html': body}, at, require_rendered=True), observed_at=time.time())
    def send(message):
        if timing.get('attempted'):
            raise RuntimeError('Diagnostic permits only one Discord send')
        timing['attempted'] = True
        timing['discord_request_started_at'] = iso(time.time())
        before = time.perf_counter()
        message_id = post(label_test(message, started_at))
        after, acknowledged = time.perf_counter(), time.time()
        timing.update(discord_message_id=message_id, discord_acknowledged_at=iso(acknowledged),
            discord_http_ms=round((after-before)*1000, 2),
            simulation_to_discord_ack_ms=round((after-start_clock)*1000, 2))
        return message_id
    state = {'version': 1, 'offers': {}, 'pc_de': {'sources': {'pc-de-store': dict(status='unavailable',
             checked_at=time.time(), retry_at=time.time()+3600)}, 'events': {}, 'delivered': {}}}
    with tempfile.TemporaryDirectory(prefix='pc-discord-simulation-') as folder:
        path = Path(folder)/'state.json'
        checkpoint = lambda value: save_state(path, value)
        now = time.time()
        # Explicit synthetic callback only; this script cannot fetch the shop.
        gate, observation = run_gate({'enabled': True, 'allow_credit_provider': True}, state, SignalOnly(), now, probe, checkpoint, interval=60)
        if gate['status'] != 'germany_confirmed':
            raise RuntimeError('Simulated visible DE page was not confirmed')
        first = run({'sources': [SOURCE]}, state, SignalOnly(), time.time(), send, checkpoint, queue_observation=observation)
        acknowledge(state)
        checkpoint(state)
        # Reload just as another process/run would. The second evaluation may
        # inspect the same evidence but must not send a second Discord message.
        restored = load_state(path)
        second = run({'sources': [SOURCE]}, restored, SignalOnly(), time.time(), send,
                     queue_observation=observation)
        if first['sent'] != 1 or second['sent'] != 0 or second['errors']:
            raise RuntimeError('Diagnostic delivery/deduplication failed')
    return dict(status='success', simulation=True, simulation_started_at=iso(started_at),
        **{k:v for k,v in timing.items() if k != 'attempted'}, discord_messages_sent=first['sent'],
        duplicate_messages_sent=second['sent'], duplicate_rejections=second['rejected'].get('DUPLICATE', 0),
        provider_scrape_calls=0, provider_credits_consumed=0, simulated_probe_calls=len(calls),
        live_queue_detection_verified=False, phone_push_latency_verified=False)


def public_report(report):
    """Public Actions logs/artifacts contain no account balance or receipt data."""
    return {key: report[key] for key in ('status', 'simulation', 'discord_messages_sent',
        'duplicate_messages_sent', 'duplicate_rejections', 'provider_scrape_calls',
        'provider_credits_consumed', 'simulated_probe_calls',
        'live_queue_detection_verified', 'phone_push_latency_verified')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send-test', action='store_true')
    args = parser.parse_args()
    if not args.send_test:
        parser.error('Explicit --send-test is required')
    # A rerun is not another request from the user. Do not resend automatically.
    if int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) != 1:
        raise SystemExit('Discord diagnostic skips workflow reruns')
    secret = os.environ.get('DISCORD_WEBHOOK_URL', '')
    webhook_url(secret)
    usage = usage_report(os.environ.get('SCRAPINGANT_API_KEY', ''))
    started, clock, body = browser_snapshot()
    report = simulate(body, started, clock, lambda message: send_discord(secret, message))
    report.update(provider_usage=usage, workflow_run_id=os.environ.get('GITHUB_RUN_ID'))
    safe = public_report(report)
    Path('pc-discord-test-report.json').write_text(json.dumps(safe, indent=2)+'\n')
    print('PC_DISCORD_TEST '+json.dumps(safe))


if __name__ == '__main__':
    main()
