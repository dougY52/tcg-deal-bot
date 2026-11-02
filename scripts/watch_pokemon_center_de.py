"""Run only the Pokémon Center DE monitor; reuse the existing Discord Secret."""
import argparse
import copy
import json
import os
from pathlib import Path
import time

from tcg_bot.__main__ import load_state, save_state
from tcg_bot.http import send_discord, webhook_url
from tcg_bot import community_watch, pokemon_center_watch
from tcg_bot.pokemon_center_queue import QueueClient


def relay_health(now, fetch=None):
    """One read of our own relay, no configuration/credentials/Discord writes."""
    if fetch is None:
        if not os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL'):
            return {'status': 'not_checked_outside_github'}
        from scripts.configure_cardpal_relay import request
        fetch = request
    try:
        result = fetch('/cardpal/status')
        last = result.get('last_stream_at', 0)
        age = now-last/1000 if type(last) in (int, float) else float('inf')
        # Relay reconnects every four minutes; status alone can be stale.
        fresh = result.get('status') == 'stream_connected' and -60 <= age <= 600
        return {**result, 'connection_fresh': fresh, 'shop_drop_latency_verified': False}
    except Exception:
        return {'status': 'unavailable', 'connection_fresh': False,
                'shop_drop_latency_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/pokemon-center-de.json')
    parser.add_argument('--state', default='pokemon-center-state.json')
    parser.add_argument('--report', default='pokemon-center-report.json')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    state_path = Path(args.state)
    state = copy.deepcopy(load_state(state_path))
    client = QueueClient()
    client.deadline = time.monotonic()+100
    send, checkpoint = None, None
    if args.send:
        secret = os.environ.get('DISCORD_WEBHOOK_URL', '')
        webhook_url(secret)
        send = lambda payload: send_discord(secret, payload)
        checkpoint = lambda value: save_state(state_path, value)
    now = time.time()
    try:
        report = pokemon_center_watch.run(cfg, state, client, now, send, checkpoint)
        # Keep the existing exact-original MyDealz checks and their dedupe.
        report['mydealz'] = community_watch.run({'community_watch': cfg['community_watch']},
                                               state, client, now, send, checkpoint)
        report['sent'] += report['mydealz']['sent']
        report['cardpal_relay'] = relay_health(time.time())
    finally:
        client.close()
        if args.send:
            save_state(state_path, state)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('PC_DE_REPORT '+json.dumps(report, ensure_ascii=False))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write('## Pokémon Center Deutschland\n\n')
            f.write('Geprüft: '+report['checked_at']+' · Discord bestätigt: '+str(report['sent'])+'\n\n')
            f.write('| Quelle | Zugriff | Einträge |\n|---|---|---|\n')
            for row in report['sources']:
                f.write('| '+row['id']+' | '+row['status']+' | '+str(row.get('items', '–'))+' |\n')
            f.write('\nCommunity-Vorwarnungen sind keine bestätigten Shopbestände. Blockiert bedeutet unbekannt, nicht ausverkauft.\n')
            health = report['cardpal_relay']
            f.write('\nCardPal-Relay: '+str(health['status'])+' · frische Verbindung: '+str(health.get('connection_fresh', False))+' · Shop-Drop-Latenz weiterhin unbestätigt.\n')
    return report


if __name__ == '__main__':
    main()
