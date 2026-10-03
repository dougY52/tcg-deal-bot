import json
import unittest
from unittest.mock import patch
from tcg_bot.web_sources import parse_mms,mms,otto
from tcg_bot.preorders import live
from tcg_bot.retailer_coverage import check_sources
from tcg_bot.http import FetchError
from test_web_sources import mms_body,shop

class RetailerIntegrationTests(unittest.TestCase):
    def test_mms_requires_explicit_buyable_flag(self):
        source=shop(True)|{'adapter':'mms'}
        row=parse_mms(source,mms_body(),'https://example.org/item')[0]
        class Client:
            def text(self,url): return mms_body()
        self.assertEqual(live(row,source,Client(),100)[1],'NO_CHECKOUT')
    def test_mms_live_exact_variant_and_price(self):
        source=shop(True)|{'adapter':'mms'}
        body=mms_body().replace('"cofrOnlineStatusFeature": {}','"cofrOnlineStatusFeature": {"isAvailableAndBuyable": true}')
        row=parse_mms(source,body,'https://example.org/item')[0]
        class Client:
            def text(self,url): return body
        fresh,error=live(row|{'price':'1.00'},source,Client(),100)
        self.assertIsNone(error)
        self.assertTrue(fresh['add_to_cart_available'])
        self.assertEqual(fresh['price'],'139.99')
        self.assertEqual(live(row|{'variant_id':'different'},source,Client(),100)[1],'AMBIGUOUS_VARIANT')
    def test_mms_changed_seller_rejected(self):
        source=shop(True)|{'adapter':'mms'}
        row=parse_mms(source,mms_body(),'https://example.org/item')[0]
        class Client:
            def text(self,url): return mms_body(market=True)
        self.assertEqual(live(row,source,Client(),100)[1],'SELLER_RISK')
    def test_shop_failures_keep_diagnostic_reason(self):
        class Client:
            def text(self,url): raise FetchError('HTTP 403')
        source=shop(True)|{'catalog_urls':['https://example.org/catalog'],'watch_urls':['https://example.org/item']}
        for scanner in [mms,otto]:
            rows,notes=scanner(source,Client())
            self.assertEqual(rows,[])
            self.assertTrue(any('HTTP 403' in n for n in notes))
    def test_coverage_is_never_inventory_or_alert(self):
        cfg={'retailer_coverage':{'enabled':True},'retailer_sources':[{'id':'smyths','url':'https://example.org/cards'}]}
        class Client:
            def text(self,url):
                return '<title>Cards</title><script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Pokemon Display DE','url':url,'offers':{'price':99,'availability':'https://schema.org/InStock'}})+'</script>'
        state={}
        report=check_sources(cfg,state,Client(),100000)
        self.assertEqual(report['checked'],1)
        self.assertFalse(report['sources'][0]['inventory_confirmed'])
        self.assertEqual(report['sources'][0]['candidate_count'],1)
        self.assertEqual(check_sources(cfg,state,Client(),100001)['checked'],0)
    def test_coverage_isolates_blocked_source(self):
        cfg={'retailer_coverage':{'enabled':True},'retailer_sources':[{'id':'blocked','url':'https://example.org/blocked'},{'id':'edeka','url':'https://example.org/local'}]}
        class Client:
            def text(self,url):
                if url.endswith('blocked'): raise FetchError('HTTP 403')
                return '<title>Angebote</title>'
        report=check_sources(cfg,{},Client(),100000)
        self.assertEqual(report['checked'],2)
        self.assertEqual(report['sources'][0]['reason'],'HTTP 403')
        self.assertEqual(report['sources'][1]['status'],'reachable_discovery_only')
