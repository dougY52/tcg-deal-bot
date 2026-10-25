"""Local DOM smoke check: no shop requests, credentials, cart or Discord."""
from playwright.sync_api import sync_playwright
from tcg_bot.browser_runtime import launch_browser
from tcg_bot.browser import pokemon_queue_document


def run():
    with sync_playwright() as runtime:
        browser = launch_browser(runtime)
        try:
            page = browser.new_page()
            page.set_content('<title>TCG browser ready</title><main><button>Test</button></main>')
            assert page.title() == 'TCG browser ready'
            assert page.locator('main button').is_enabled()
            # Entirely intercepted fixtures: verifies real Playwright frame /
            # navigation behavior without contacting Pokémon Center or Discord.
            queue = '<title>Virtual Queue</title><h1>You are now in line</h1><p>Estimated wait time: 4 minutes. Keep this window open.</p>'
            url = 'https://www.pokemoncenter.com/de-de/'
            statuses = {}
            def record(response):
                if response.request.is_navigation_request():
                    statuses[response.frame] = response.status
            page.on('response', record)
            page.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=(
                queue if '/_Incapsula_Resource' in route.request.url else
                '<iframe src="/_Incapsula_Resource?fixture=1"></iframe>')))
            page.goto(url, wait_until='load')
            result = pokemon_queue_document(page, url, statuses, lambda _: None)
            assert result and 'You are now in line' in result[0]
            assert pokemon_queue_document(page, url+'product/test', statuses, lambda _: None) is None
            print('Queue iframe fixture passed (simulation, not live retailer access)')
            print('Browser runtime ready: launch and DOM validation passed')
        finally:
            browser.close()


if __name__ == '__main__':
    run()
