import json
import unittest
from tcg_bot.checkout import single_product
from tcg_bot import preorders as p
from tcg_bot.__main__ import load_config
from tcg_bot.http import FetchError
from tcg_bot.retailer_coverage import check_sources
from test_preorders import NOW

URL = 'https://example.test/sammelkarten/dragon-ball/fb11'
UUID = '019f127fc546727eb790a6d08f6cc541'
TITLE = 'Dragon Ball FB11 Display EN Preorder'
SHOP = dict(id='example', name='Example Cards', base_url='https://example.test', adapter='shopware', currency='EUR')


def page(price=104.99, status='PreOrder', button='Vorbestellen'):
    data = {'@type':'Product', 'name':TITLE, 'sku':'fb11-en', 'url':URL,
            'offers':{'price':price, 'priceCurrency':'EUR', 'availability':'https://schema.org/'+status}}
    prefix = 'lineItems['+UUID+']'
    inputs = ''.join('<input type="hidden" name="'+prefix+'['+k+']" value="'+v+'">'
                     for k,v in [('id',UUID), ('referencedId',UUID), ('type','product')])
    return ('<h1 class="product-detail-name">'+TITLE+'</h1><h1>Newsletter</h1>'
            '<script type="application/ld+json">'+json.dumps(data)+'</script>'
            '<form id="productDetailPageBuyProductForm" method="post" action="/checkout/line-item/add">'+inputs+
            '<input type="hidden" name="product-name" value="'+TITLE+'">'
            '<input type="hidden" name="redirectParameters" value=\'{"productId":"'+UUID+'"}\'>'
            '<input type="number" name="'+prefix+'[quantity]" min="1" max="1" value="1">'
            '<button class="btn btn-buy" type="submit">'+button+'</button></form>')


class ShopwareTests(unittest.TestCase):
    def test_production_config_registers_adapter_and_exact_seed(self):
        from tcg_bot.__main__ import ADAPTERS
        cfg = load_config('config/config.json')
        for sid in ('comicplanet', 'kartenmeier'):
            source = next(s for s in cfg['shops'] if s['id'] == sid)
            self.assertTrue(source['enabled'])
            self.assertIn(source['adapter'], ADAPTERS)
            self.assertIn(sid, cfg['preorder_watch']['trusted_shop_ids'])
        comic = next(s for s in cfg['shops'] if s['id'] == 'comicplanet')
        self.assertTrue(comic['watch_urls'])

    def test_exact_variant_and_live_price_override(self):
        row = single_product(SHOP,page(),URL)[0]
        self.assertTrue(row['add_to_cart_available'])
        self.assertEqual(row['cart_product_id'],UUID)
        client = type('Client',(),{'text':lambda _,url:page(price=99.99)})()
        fresh, reason = p.live(dict(row,price='1.00'),SHOP,client,NOW)
        self.assertIsNone(reason)
        self.assertEqual(fresh['price'],'99.99')

    def test_contradictory_form_or_variant_fails_closed(self):
        cases = [page().replace('[referencedId]" value="'+UUID,'[referencedId]" value="'+'a'*32),
                 page().replace('productId','wrongId'),
                 page().replace('name="product-name" value="'+TITLE,'name="product-name" value="Other'),
                 page().replace('id="productDetailPageBuyProductForm"','id="crosssell"'),
                 page().replace('action="/checkout','action="https://other.test/checkout'),
                 page().replace('max="1"','max="0"'),
                 page().replace('<button','<button disabled'),
                 page().replace('<button','<select name="language"><option>JP</option></select><button'),
                 page().replace('<input type="number"','<input disabled type="number"'),
                 page().replace('<form ','<form hidden ')]
        for body in cases:
            with self.subTest(body=body[-250:]):
                self.assertFalse(single_product(SHOP,body,URL)[0]['add_to_cart_available'])

    def test_waitlist_sold_out_backorder_not_buyable(self):
        for body in [page(button='Notify me'), page(button='Benachrichtigen'),
                     page(status='OutOfStock'), page(status='BackOrder'), page(button='Coming soon')]:
            self.assertFalse(single_product(SHOP,body,URL)[0]['add_to_cart_available'])

    def test_primary_form_and_crosssell_do_not_mix(self):
        body = page() + page()[page().index('<form'):].replace('id="productDetailPageBuyProductForm"','id="crosssell"')
        self.assertTrue(single_product(SHOP,body,URL)[0]['add_to_cart_available'])
        body = page()+page()[page().index('<form'):]
        self.assertFalse(single_product(SHOP,body,URL)[0]['add_to_cart_available'])

    def test_missing_price_currency_or_product_title_not_inferred(self):
        for body in [page().replace('"EUR"','"USD"'),page().replace('product-detail-name','other'),
                     page().replace('"price": 104.99','"lowPrice": 104.99')]:
            self.assertEqual(single_product(SHOP,body,URL),[])

    def test_lifecycle_dedupe_restock_and_waitlist(self):
        cfg = load_config('config/config.json')
        cfg['shops'] = [SHOP]
        cfg['preorder_watch']['trusted_shop_ids'] = ['example']
        row = single_product(SHOP,page(),URL)[0]
        state = {'version':1,'offers':{}}
        client = type('Client',(),{'body':page(), 'text':lambda self,url:self.body})()
        def scan(t): return p.scan([row],cfg,state,client,t)[1]
        first = scan(NOW)[0]; p.delivered(state,first,NOW,'receipt')
        self.assertEqual(scan(NOW+60),[])
        client.body=page(status='OutOfStock'); self.assertEqual(scan(NOW+120),[])
        client.body=page(); restock=scan(NOW+180)[0]; p.delivered(state,restock,NOW+180,'receipt2')
        client.body=page(button='Notify me'); self.assertEqual(scan(NOW+240),[])
        client.body=page(); opened=scan(NOW+300)[0]; p.delivered(state,opened,NOW+300,'receipt3')
        client.body=page(price=90); self.assertEqual(len(scan(NOW+360)),1)

    def test_wrong_language_remains_rejected(self):
        row = single_product(SHOP,page().replace('Display EN','Display JP'),URL)[0]
        self.assertEqual(p.identity(row,load_config('config/config.json'))[1],'WRONG_LANGUAGE')


class CoverageBudgetTests(unittest.TestCase):
    def test_local_budget_is_not_a_retailer_block_and_retries_next_run(self):
        cfg = {'retailer_coverage':{'enabled':True},'retailer_sources':[{'id':'shop','url':URL}]}
        state = {}
        client = type('Client',(),{'text':lambda _,url: (_ for _ in ()).throw(FetchError('Run request budget exhausted'))})()
        result = check_sources(cfg,state,client,NOW)
        self.assertEqual(result['checked'],0)
        self.assertEqual(result['deferred'],1)
        self.assertEqual(state['retailer_coverage']['shop']['status'],'deferred_budget')
        client.text=lambda url:'<title>Cards</title>'
        retry=check_sources(cfg,state,client,NOW+300)
        self.assertEqual(retry['checked'],1)
        self.assertEqual(retry['sources'][0]['status'],'reachable_discovery_only')
        self.assertFalse(retry['sources'][0]['inventory_confirmed'])
