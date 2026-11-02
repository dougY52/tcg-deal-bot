"""Bounded parallelism across retailers; never parallel requests to one host."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import time
from urllib.parse import urlsplit
from .http import Client


def collect(shops, client, adapters, workers=1, source_seconds=60):
    """Retain configured ordering for the existing retailer scanners."""
    order = {s['id']: i for i, s in enumerate(shops)}
    return sorted(iter_collect(shops, client, adapters, workers, source_seconds),
                  key=lambda r: order[r[0]['id']])


def iter_collect(shops, client, adapters, workers=1, source_seconds=60):
    """Yield finished hosts immediately; only the caller mutates alert state."""
    active = [s for s in shops if s.get('enabled', True)]
    def one(shop, transport):
        started = time.monotonic()
        try:
            rows, notes = adapters[shop['adapter']](shop, transport)
            return shop, rows, notes, None, round(time.monotonic()-started, 2)
        except Exception as exc:
            return shop, [], [], type(exc).__name__, round(time.monotonic()-started, 2)
    if workers == 1 or not isinstance(client, Client):
        for shop in active:
            yield one(shop, client)
        return
    groups = defaultdict(list)
    for shop in active:
        groups[urlsplit(shop['base_url']).netloc].append(shop)
    # Browser APIs stay on their owning thread. Other hosts use ordinary HTTP.
    browser_shops = [s for s in active if s['adapter'] == 'mms']
    for s in browser_shops:
        groups.pop(urlsplit(s['base_url']).netloc, None)
    def group(batch):
        child = type(client)(client.delay)
        child.deadline = min(client.deadline, time.monotonic()+source_seconds)
        host = urlsplit(batch[0]['base_url']).netloc
        transport_keys = (host, 'browser:' + host)
        child.cooldowns = {key: client.cooldowns.get(key, 0) for key in transport_keys}
        child.last = dict(client.last)
        child.robots = dict(client.robots)
        child.host_delay = dict(client.host_delay)
        child.blocked.update(key for key in transport_keys if key in client.blocked)
        try:
            result = [one(s, child) for s in batch]
        finally:
            child.close()
        return result, child
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(group, batch) for batch in groups.values()]
        for shop in browser_shops:
            yield one(shop, client)
        for future in as_completed(futures):
            rows, child = future.result()
            client.robots.update(child.robots)
            client.host_delay.update(child.host_delay)
            for host, stamp in child.last.items():
                client.last[host] = max(client.last.get(host, 0), stamp)
            for host, stamp in child.cooldowns.items():
                client.cooldowns[host] = max(client.cooldowns.get(host, 0), stamp)
            client.blocked.update(child.blocked)
            yield from rows
