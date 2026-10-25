import json
import time
import unittest
from unittest.mock import Mock, patch
from tcg_bot.http import FetchError
from tcg_bot import pokemon_center_access as pc, drop_watch

FREE = {'plan_name': 'Free', 'plan_total_credits': 10000, 'remained_credits': 9000}
PAGE = '<main><h1>Pokémon Center Deutschland</h1><p>Entdecke unsere Produkte und Kollektionen im offiziellen Shop.</p><a href="/de-de/product/123/deutsche-booster-box">Pokémon deutsche Booster Box</a></main>'


class PokemonCenterAccess(unittest.TestCase):
    def test_public_german_pages_only(self):
        self.assertTrue(pc.public_de_url(pc.TARGETS[0]))
        self.assertTrue(pc.public_de_url(pc.ORIGIN+'/en-de/product/123/box'))
        for url in [pc.ORIGIN+'/de-de/cart', pc.ORIGIN+'/cortex',pc.ORIGIN+'/de-de/product/a?token=x',
                    pc.ORIGIN+'/en-gb/product/123/box', 'https://www.pokemoncenter.com.evil/de-de/',
                    pc.ORIGIN+'/de-de/product/%2e%2e/account', pc.ORIGIN+':443/de-de/',
                    'https://user@www.pokemoncenter.com/de-de/']:
            self.assertFalse(pc.public_de_url(url), url)

    def test_encoded_german_slug_and_category_discovery(self):
        url=pc.ORIGIN+'/de-de/product/123/pok%C3%A9mon-box'
        self.assertTrue(pc.public_de_url(url))
        result=pc.page_result(PAGE+'<a href="/de-de/category/trading-card-game?utm_source=test">Sammelkartenspiel</a>',pc.TARGETS[0],time.time())
        self.assertEqual(result['category_links'][0]['url'],pc.ORIGIN+'/de-de/category/trading-card-game')
        for segment in ['%252e%252e','%2faccount','%5caccount','%2e%2e']:
            self.assertFalse(pc.public_de_url(pc.ORIGIN+'/de-de/product/'+segment))

    def test_followup_pages_share_one_bounded_credit_budget(self):
        p=pc.FreeAccessProbe('test-key',Mock(),max_credits=375)
        p.request_json=Mock(side_effect=[(FREE,None),({'status_code':200,'html':PAGE},125)]*3)
        for url in [pc.TARGETS[0],pc.ORIGIN+'/de-de/category/cards',pc.ORIGIN+'/de-de/product/123/box']:
            p.fetch(url,pc.MODES[-1])
        self.assertEqual(p.reserved,375)
        with self.assertRaisesRegex(FetchError,'BUDGET'):
            p.fetch(pc.ORIGIN+'/de-de/product/456/box',pc.MODES[-1])

    def test_http_200_challenge_not_success(self):
        page='<html><iframe src="/_Incapsula_Resource?abc"></iframe></html>'
        self.assertEqual(pc.page_result(page,pc.TARGETS[0],time.time())['status'],'blocked_or_unreadable')

    def test_product_metadata_never_stock_proof(self):
        result=pc.page_result(PAGE,pc.TARGETS[0],time.time())
        self.assertEqual(result['status'],'readable_discovery_only')
        self.assertFalse(result['inventory_confirmed'])
        self.assertEqual(len(result['candidate_links']),1)

    def test_paid_trial_unknown_and_insufficient_credit_refused(self):
        for changes in [{'plan_name':'Enthusiast'}, {'plan_name':'Trial'}, {'plan_name':None},
                        {'remained_credits':0}, {'remained_credits':True}, {'remained_credits':float('nan')},
                        {'plan_total_credits':100000}, {'remained_credits':11000}]:
            with self.assertRaises(FetchError):pc.free_usage(FREE|changes,125)
        self.assertEqual(pc.free_usage(FREE,125)['plan'],'free')

    def probe(self):
        p=pc.FreeAccessProbe('test-key-never-log',Mock())
        p.request_json=Mock(side_effect=[(FREE,None),({'status_code':200,'html':PAGE,'cookies':'secret-cookie'},1)])
        return p

    def test_key_only_in_header_no_cookie_or_cart_operation(self):
        p=pc.FreeAccessProbe('test-key-never-log',Mock())
        response=Mock();response.read.return_value=json.dumps(FREE).encode();response.headers={}
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch.object(pc,'build_opener',return_value=opener):p.request_json('usage')
        request=opener.open.call_args.args[0]
        self.assertNotIn(p.key,request.full_url)
        self.assertEqual(request.get_header('X-api-key'),p.key)
        self.assertEqual(request.get_method(),'GET')

    def test_provider_checks_free_plan_before_scrape(self):
        p=self.probe();body,meta=p.fetch(pc.TARGETS[0],pc.MODES[0])
        self.assertEqual(body,PAGE);self.assertNotIn('secret-cookie',str(meta))
        self.assertEqual(p.request_json.call_args_list[0].args[0],'usage')
        self.assertEqual(p.reserved,1)
        with self.assertRaises(FetchError):p.fetch(pc.TARGETS[0],pc.MODES[0])

    def test_paid_plan_never_fetches_page(self):
        p=self.probe();p.request_json.side_effect=[(FREE|{'plan_name':'Hobby'},None)]
        with self.assertRaises(FetchError):p.fetch(pc.TARGETS[0],pc.MODES[0])
        self.assertEqual(p.request_json.call_count,1)
        self.assertEqual(p.reserved,0)

    def test_target_error_and_missing_html_fail_closed(self):
        for data in [{'status_code':403,'html':PAGE},{'status_code':200,'text':PAGE},{'status_code':True,'html':PAGE}]:
            p=self.probe();p.request_json.side_effect=[(FREE,None),(data,1)]
            with self.assertRaises(FetchError):p.fetch(pc.TARGETS[0],pc.MODES[0])

    def test_cost_change_stops_remaining_tests(self):
        p=self.probe();p.request_json.side_effect=[(FREE,None),({'status_code':200,'html':PAGE},100)]
        with self.assertRaisesRegex(FetchError,'COST_CHANGED'):p.fetch(pc.TARGETS[0],pc.MODES[0])
        with self.assertRaisesRegex(FetchError,'BUDGET'):p.fetch(pc.TARGETS[0],pc.MODES[1])

    def test_alternate_germany_page_is_checked_without_duplicate_source(self):
        client=Mock();client.text.side_effect=[FetchError('HTTP 403'),PAGE]
        old={};source={'id':'pokemon-center-de','url':pc.TARGETS[0],'alternate_urls':[pc.TARGETS[1],pc.ORIGIN+'/en-us/']}
        status,events=drop_watch.read_source(source,old,client,time.time())
        self.assertEqual(status,'readable');self.assertEqual(events,[])
        self.assertEqual(old['checked_url'],pc.TARGETS[1]);self.assertEqual(client.text.call_count,2)

    def test_blocked_alternates_never_create_alert(self):
        client=Mock();client.text.return_value='<html>captcha</html>'
        source={'id':'pokemon-center-de','url':pc.TARGETS[0],'alternate_urls':[pc.TARGETS[1]]}
        status,events=drop_watch.read_source(source,{},client,time.time())
        self.assertEqual(status,'blocked_or_unreadable');self.assertEqual(events,[])

    def test_probe_missing_key_has_no_provider_request_or_discord(self):
        from scripts import check_pokemon_center as script
        with patch.dict('os.environ',{'SCRAPINGANT_API_KEY':''}),patch.object(script,'Client') as client,patch.object(script.Path,'write_text'),patch('builtins.print'):
            client.return_value.text.return_value='<html>captcha</html>'
            with patch.object(script,'FreeAccessProbe') as provider:
                result=script.run();provider.assert_not_called()
        self.assertFalse(result['discord_sent']);self.assertEqual(result['provider'],'not_configured')
