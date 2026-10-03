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

class MuellerTests(unittest.TestCase):
    def fixture(self,disabled=False,sku='42',home=True):
        product={'@type':'Product','name':'Pokémon Test Top-Trainer-Box DE','sku':'42','description':'Deutsch',
                 'offers':[{'price':54.99,'priceCurrency':'EUR','availability':'https://schema.org/InStock','url':'https://www.mueller.de/p/test-PPN42/?itemId=42','seller':{'name':'Müller Handels GmbH & Co. KG'}}]}
        return '<main><h1>Pokémon Test Top-Trainer-Box DE</h1><script type="application/ld+json">'+json.dumps(product)+'</script><script>{"translation":"Dieses Produkt ist derzeit nicht nach Hause lieferbar"}</script>'+('Dieses Produkt ist derzeit nicht nach Hause lieferbar' if not home else 'Lieferung nach Hause: Lieferbar in 2 - 3 Werktagen')+'<button data-testid="pdp-addToCart-button" data-product-id="'+sku+'" aria-disabled="'+('true' if disabled else 'false')+'">In den Warenkorb</button></main>'
    def parse(self,body):
        from tcg_bot.retailers import mueller_product
        source={'id':'mueller','name':'Müller','base_url':'https://www.mueller.de','allowed_sellers':['Müller Handels GmbH & Co. KG']}
        return mueller_product(source,body,'https://www.mueller.de/p/test-PPN42/', '42')
    def test_exact_product_button_and_live_price(self):
        row,error=self.parse(self.fixture())
        self.assertIsNone(error)
        self.assertTrue(row['add_to_cart_available'])
        self.assertEqual(row['price'],'54.99')
    def test_disabled_or_other_variant_does_not_qualify(self):
        for body in [self.fixture(disabled=True),self.fixture(sku='99')]:
            self.assertEqual(self.parse(body)[1],'NO_CHECKOUT')
    def test_branch_delivery_is_not_online_stock(self):
        row,error=self.parse(self.fixture(home=False))
        self.assertEqual(error,'LOCAL_STOCK_UNCONFIRMED')
        self.assertFalse(row['available'])
    def test_product_and_offer_id_must_match(self):
        self.assertEqual(self.parse(self.fixture().replace('itemId=42','itemId=99'))[1],'AMBIGUOUS_VARIANT')
    def test_discovery_uses_actual_mueller_id(self):
        from tcg_bot.web_sources import parse_structured
        data={'@type':'Product','name':'Pokémon Box DE','url':'https://www.mueller.de/p/test-PPN42/','offers':{'price':54.99,'priceCurrency':'EUR'}}
        rows,_=parse_structured({'id':'mueller','name':'Müller','base_url':'https://www.mueller.de'},'<script type="application/ld+json">'+json.dumps(data)+'</script>','https://www.mueller.de/b/pokemon/')
        self.assertEqual(rows[0]['variant_id'],'42')
