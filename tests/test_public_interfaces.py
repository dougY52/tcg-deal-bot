import json
from pathlib import Path
import unittest
from scripts.audit_public_interfaces import endpoint, page_info

class PublicInterfaces(unittest.TestCase):
    def test_endpoint_does_not_record_query_values_userinfo_or_fragment(self):
        data=endpoint('https://name:secret@shop.test/api?token=private&operationName=Catalog#secret')
        self.assertEqual(data,{'host':'shop.test','path':'/api','query_keys':['operationName','token']})
        self.assertNotIn('private',json.dumps(data))
        self.assertNotIn('secret',json.dumps(data))

    def test_opaque_path_ids_redacted(self):
        self.assertEqual(endpoint('https://shop.test/a/a953d7fa-a07f-4fac-a9d4-31b2e9cee6e4')['path'],'/a/:opaque')

    def test_page_and_search_hints_do_not_confirm_inventory(self):
        body='<h1>Pokémon Sammelkarten Neuheiten</h1><a href="/products/pokemon">Pokémon Booster Display Deutsch</a>'
        row=page_info(body,'https://shop.test/')
        self.assertFalse(row['inventory_confirmed'])
        self.assertEqual(len(row['candidate_links']),1)
        self.assertEqual(page_info('<h1>Access denied</h1>','https://shop.test/')['status'],'challenge')

    def test_captured_queries_are_read_only_public_catalog_operations(self):
        for row in json.loads(Path('config/public-mms-queries.json').read_text()):
            q=row['query']
            self.assertIn(q['operation'],('CategoryV4','SearchV4'))
            self.assertFalse(set(q['headers']) & {'authorization','cookie','x-api-key'})
            self.assertEqual(set(q['extensions']),{'persistedQuery','pwa'})

    def test_coverage_collects_relative_links_paused_theme_and_offsite_excluded(self):
        from tcg_bot.retailer_coverage import check_sources
        cfg={'franchises':{'Pokémon':'pok[eé]mon','Naruto':'naruto'},'disabled_franchises':['Naruto'],
             'retailer_coverage':{'enabled':True,'recheck_seconds':3600},
             'retailer_sources':[{'id':'shop','url':'https://shop.test/catalog'}]}
        class Client:
            def text(self,url):
                return '''<title>Produkte</title>
<a href="/p/one?variant=12&utm_source=ads">Pokémon Booster Display Deutsch</a>
<a href="/p/two">Naruto Mythos Display EN</a>
<a href="https://unknown.test/p">Pokémon Booster Display Deutsch</a>
<a href="/p/empty">Pokémon Acryl Display Hülle</a>'''
        state={};check_sources(cfg,state,Client(),10000)
        values=list(state['retailer_product_candidates'].values())
        self.assertEqual(len(values),1)
        self.assertEqual(values[0]['url'],'https://shop.test/p/one?variant=12')
        self.assertFalse(values[0]['inventory_confirmed'])
        self.assertNotIn('price',values[0])
        check_sources(cfg,state,Client(),14000)
        values=list(state['retailer_product_candidates'].values())
        self.assertEqual(len(values),1)
        self.assertEqual(values[0]['first_seen'],10000)
        self.assertEqual(values[0]['last_seen'],14000)

    def test_public_catalog_only_yields_exact_same_site_urls(self):
        from tcg_bot.public_catalog import product_links
        row={'productAggregate':{'product':{'id':'123'}},'cofrProductAggregate':{'cofrCoreFeature':{
            'productName':'Pokémon Booster Display Deutsch','urlRelative':'/de/product/_pokemon-123.html'},
            'cofrPriceFeature':{'price':{'amount':1}},'cofrOnlineStatusFeature':{'isAvailableAndBuyable':True}}}
        shop={'base_url':'https://www.saturn.de'}
        self.assertEqual(product_links({'data':[row]},shop),['https://www.saturn.de/de/product/_pokemon-123.html'])
        row['cofrProductAggregate']['cofrCoreFeature']['urlRelative']='https://untrusted.test/de/product/_pokemon-123.html'
        self.assertEqual(product_links({'data':[row]},shop),[])

    def test_public_catalog_rotates_queries_and_pages_not_on_error(self):
        from tcg_bot.public_catalog import discover
        from urllib.parse import parse_qs,urlsplit
        profile=json.loads(Path('config/public-mms-queries.json').read_text())[1]
        shop={'base_url':'https://www.saturn.de','_public_catalog_query':profile,
              'public_catalog_searches':['Pokemon Sammelkarten','Dragon Ball Display','One Piece Display']}
        class Client:
            def public_catalog_json(self,url,headers):
                self.variables=json.loads(parse_qs(urlsplit(url).query)['variables'][0])
                return {'data':{'searchV4':{}}}
        c=Client()
        for cursor in range(4):
            shop['_catalog_pages']={'_public_catalog_cursor':cursor}
            discover(shop,c)
            self.assertEqual(c.variables['query'],shop['public_catalog_searches'][cursor%3])
            self.assertEqual(c.variables['page'],1+cursor//3)
            self.assertEqual(shop['_catalog_next_pages']['_public_catalog_cursor'],cursor+1)
        from unittest.mock import Mock
        failed=dict(shop);failed.pop('_catalog_next_pages',None)
        c.public_catalog_json=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):discover(failed,c)
        self.assertNotIn('_catalog_next_pages',failed)

    def test_public_catalog_transport_rejects_auth_and_non_catalog_endpoints(self):
        from tcg_bot.http import Client,FetchError
        c=Client()
        for url,headers in [('https://www.saturn.de/api/v1/graphql?operationName=GetUser',{}),
                            ('https://www.saturn.de/api/v1/graphql?operationName=SearchV4',{'Authorization':'secret'}),
                            ('https://untrusted.test/api/v1/graphql?operationName=SearchV4',{})]:
            with self.assertRaises(FetchError):c.public_catalog_json(url,headers)

    def test_catalog_rejects_merchandise_and_explicit_wrong_languages(self):
        from tcg_bot.public_catalog import product_links
        for title in ('Dragon Ball Box DVD','Dragon Ball Vinyl Schlüsselanhänger Display',
                      'Pokémon Booster Display Englisch','One Piece Display Japanisch','Naruto Mythos Display EN'):
            row={'productAggregate':{'product':{'id':'123'}},'cofrProductAggregate':{'cofrCoreFeature':{
                'productName':title,'urlRelative':'/de/product/_item-123.html'}}}
            self.assertEqual(product_links({'data':[row]},{'base_url':'https://www.saturn.de'}),[],title)

    def test_catalog_stock_price_never_substitutes_for_failed_product_page(self):
        from tcg_bot.web_sources import mms
        from tcg_bot.http import FetchError
        from unittest.mock import patch
        shop={'id':'saturn','name':'Saturn','base_url':'https://www.saturn.de',
              '_public_catalog_query':{},'catalog_urls':['https://www.saturn.de/catalog'],
              'watch_urls':[],'currency':'EUR'}
        shop['_public_catalog_query']={'present':True}
        class Client:
            def text(self,url):raise FetchError('HTTP 403')
        with patch('tcg_bot.public_catalog.discover',return_value=['https://www.saturn.de/de/product/_pokemon-123.html']):
            rows,notes=mms(shop,Client())
        self.assertEqual(rows,[])
        self.assertTrue(any('Product page unavailable' in n for n in notes))
