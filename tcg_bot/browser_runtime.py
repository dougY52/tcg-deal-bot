"""Reuse the runner's supported Chrome channel without runtime installation."""
import os
from .http import FetchError


def launch_browser(runtime):
    channel = os.environ.get('TCG_BROWSER_CHANNEL', '')
    if channel not in ('', 'chrome'):
        raise FetchError('Unsupported browser channel')
    return runtime.chromium.launch(headless=True, **({'channel':channel} if channel else {}))
