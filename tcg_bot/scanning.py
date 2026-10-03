"""Bounded parallelism across retailers; never parallel requests to one host."""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import time
from urllib.parse import urlsplit
from .http import Client


def collect(shops, client, adapters, workers=1, source_seconds=60):
    active = [s for s in shops if s.get('enabled', True)]
    def one(shop, transport):
        started = time.monotonic()
        try:
            rows, notes = adapters[shop['adapter']](shop, transport)
            return shop, rows, notes, None, round(time.monotonic()-started, 2)
        except Exception as exc:
            return shop, [], [], type(exc).__name__, round(time.monotonic()-started, 2)
    if workers == 1 or not isinstance(client, Client):
        return [one(s, client) for s in active]
    groups = defaultdict(list)
    for shop in active:
        groups[urlsplit(shop['base_url']).netloc].append(shop)
    # Browser APIs stay on their owning thread. Other hosts use ordinary HTTP.
    browser_shops = [s for s in active if s['adapter'] == 'mms']
    for s in browser_shops:
        groups.pop(urlsplit(s['base_url']).netloc, None)
    def group(batch):
        child = Client(client.delay)
        child.deadline = min(client.deadline, time.monotonic()+source_seconds)
        host = urlsplit(batch[0]['base_url']).netloc
        child.cooldowns = {host: client.cooldowns.get(host, 0)}
        child.last = dict(client.last)
        child.robots = dict(client.robots)
        child.host_delay = dict(client.host_delay)
        if host in client.blocked:
            child.blocked.add(host)
        result = [one(s, child) for s in batch]
        return result, child
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(group, batch) for batch in groups.values()]
        results.extend(one(s, client) for s in browser_shops)
        for future in futures:
            rows, child = future.result()
            results.extend(rows)
            client.robots.update(child.robots)
            client.host_delay.update(child.host_delay)
            for host, stamp in child.last.items():
                client.last[host] = max(client.last.get(host, 0), stamp)
            for host, stamp in child.cooldowns.items():
                client.cooldowns[host] = max(client.cooldowns.get(host, 0), stamp)
            client.blocked.update(child.blocked)
    order = {s['id']: i for i,s in enumerate(active)}
    return sorted(results, key=lambda r: order[r[0]['id']])
