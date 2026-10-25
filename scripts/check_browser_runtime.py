"""Local DOM smoke check: no shop requests, credentials, cart or Discord."""
from playwright.sync_api import sync_playwright
from tcg_bot.browser_runtime import launch_browser


def run():
    with sync_playwright() as runtime:
        browser = launch_browser(runtime)
        try:
            page = browser.new_page()
            page.set_content('<title>TCG browser ready</title><main><button>Test</button></main>')
            assert page.title() == 'TCG browser ready'
            assert page.locator('main button').is_enabled()
            print('Browser runtime ready: launch and DOM validation passed')
        finally:
            browser.close()


if __name__ == '__main__':
    run()
