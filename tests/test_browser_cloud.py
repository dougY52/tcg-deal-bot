import json
import time
import unittest
from unittest.mock import patch
from tcg_bot.browser import BrowserClient, validate_page
from tcg_bot.http import Client, FetchError
from tcg_bot.scanning import collect
from tcg_bot.web_sources import html_catalog, mueller_candidate
from tcg_bot.drop_watch import read_source


class BrowserCloudTests(unittest.TestCase):
    def test_worker_preserves_transport_and_closes_it(self):
        seen = []
        class Transport(Client):
            def text(self, url):
                seen.append(('read', id(self)))
                return 'rendered'
            def close(self):
                seen.append(('close', id(self)))
        client = Transport()
        shop = {'id':'mueller','adapter':'test','base_url':'https://www.mueller.de'}
        def adapter(shop, child):
            self.assertIsInstance(child, Transport)
            self.assertIsNot(child, client)
            return [child.text(shop['base_url'])], []
        result = collect([shop], client, {'test':adapter}, workers=2)
        self.assertEqual(result[0][1], ['rendered'])
        self.assertEqual(seen[0][1], seen[1][1])
        self.assertEqual(seen[1][0], 'close')

    def test_browser_deadline_and_backoff_prevent_start(self):
        for expired in (True, False):
            c = BrowserClient()
            if expired: c.deadline = time.monotonic()-1
            else: c.cooldowns['www.mueller.de'] = time.time()+100
            with patch.object(c, 'check_allowed'):
                with self.assertRaises(FetchError): c.text('https://www.mueller.de/p/test/')
            self.assertIsNone(c.runtime)

    def test_mueller_readable_does_not_require_mms_state(self):
        url = 'https://www.mueller.de/b/pokemon/'
        body = '<main><h1>Pokémon</h1>Viele Sammelkarten und aktuelle Produktinformationen.</main>'
        self.assertEqual(validate_page(url,url,200,'Pokémon',body),body)
        for bad in ('<html></html>','<h1>Access denied</h1>Verify you are human captcha'):
            with self.assertRaises(FetchError): validate_page(url,url,200,'',bad)

    def test_pagination_advances_and_filters_accessories_before_details(self):
        base = 'https://www.mueller.de/b/pokemon/'
        shop = {'id':'mueller','name':'Müller','base_url':'https://www.mueller.de',
                'adapter':'html_catalog','catalog_urls':[base],'pagination_mode':'mueller','max_detail_pages':1}
        def product(name, suffix):
            return {'@type':'Product','name':name,'url':f'https://www.mueller.de/p/{suffix}-PPN42/',
                    'offers':{'price':29.99,'priceCurrency':'EUR'}}
        products = [product('Pokémon ETB Acryl Case','case'),product('Pokémon Booster Bundle Deutsch','bundle')]
        body = '<script type="application/ld+json">'+json.dumps(products)+'</script>'
        calls = []
        class HTTP:
            def text(self,url):
                calls.append(url)
                if url == base: return '<a data-testid="pageLink-2" href="?page=2">2</a>'
                return body
        html_catalog(shop,HTTP())
        self.assertEqual(calls,[base])
        shop['_catalog_pages'] = dict(shop['_catalog_next_pages'])
        rows, _ = html_catalog(shop,HTTP())
        self.assertEqual(calls[1],base+'?page=2')
        self.assertFalse(any('/case-' in url for url in calls))
        self.assertEqual(shop['_catalog_next_pages']['_mueller_next:'+base],base)
        self.assertTrue(any('Bundle' in r['title'] for r in rows))

    def test_only_card_candidates(self):
        for title in ('Pokémon Booster Bundle DE','Dragon Ball FB12 Booster Display EN','One Piece Premium Collection EN'):
            self.assertTrue(mueller_candidate(title))
        for title in ('Pokémon Trainer Expert','Pokémon Elite Trainer Box Acryl Case','Pokémon Playmat','Disney Lorcana Display'):
            self.assertFalse(mueller_candidate(title))

    def test_press_following_ignores_external_links_and_merchandise(self):
        source={'url':'https://pokemon.gamespress.com/de','follow_center_articles':True}
        old={};calls=[]
        class HTTP:
            def text(self,url):
                calls.append(url)
                if url==source['url']:
                    return '<main><h1>Offizielle Pokémon Neuigkeiten und aktuelle Meldungen</h1><a href="/de/holiday">Pokémon Center Feiertage</a><a href="https://evil.test/de/drop">Pokémon Center</a></main>'
                return '<main><h1>Pokémon Center Feiertage</h1>Neue Kleidung und Plüsch für Weihnachten in Deutschland.</main>'
        status, events=read_source(source,old,HTTP(),200000)
        self.assertEqual(status,'readable');self.assertEqual(events,[])
        self.assertEqual(calls,[source['url'],'https://pokemon.gamespress.com/de/holiday'])
        read_source(source,old,HTTP(),200100)
        self.assertEqual(len(calls),3)

    def test_press_announcement_requires_language_and_preserves_article_link(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        source={'url':'https://pokemon.gamespress.com/de','follow_center_articles':True}
        now=datetime(2026,10,25,10,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        class HTTP:
            def text(self,url):
                if url == source['url']:
                    return '<main><h1>Aktuelle offizielle Pokémon Mitteilungen</h1><a href="/de/cards">Pokémon Center Karten</a></main>'
                return '<main><p>Pokémon Center Booster Display Deutsch Verkaufsstart am 25.10.2026 um 12:00 Uhr.</p></main>'
        status, events=read_source(source,{},HTTP(),now)
        self.assertEqual(status,'readable')
        self.assertTrue(events)
        self.assertEqual(events[0]['source_url'],'https://pokemon.gamespress.com/de/cards')
        self.assertEqual(events[0]['kind'],'announcement')

    def test_failed_catalog_page_retains_cursor(self):
        base='https://www.mueller.de/b/pokemon/'
        shop={'id':'mueller','name':'Müller','base_url':'https://www.mueller.de','catalog_urls':[base],
              'pagination_mode':'mueller','_catalog_pages':{'_mueller_next:'+base:base+'?page=2'}}
        class HTTP:
            def text(self,url): raise FetchError('HTTP 503')
        rows,notes=html_catalog(shop,HTTP())
        self.assertEqual(rows,[])
        self.assertTrue(notes)
        self.assertEqual(shop['_catalog_next_pages']['_mueller_next:'+base],base+'?page=2')
