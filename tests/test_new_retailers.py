import copy
import json
import unittest
from unittest.mock import patch
from tcg_bot.__main__ import load_config
from tcg_bot.web_sources import parse_structured, html_catalog
from tcg_bot.checkout import single_product
from tcg_bot import preorders as p
from test_preorders import Client, NOW

URL = 'https://example.test/Dragon-Ball-FB11-Display-EN'
def shop(adapter='jtl'):
    return dict(id='example', name='Example Cards', base_url='https://example.test', adapter=adapter, currency='EUR')

def page(price=104.99, status='PreOrder', button='Vorbestellen', adapter='jtl', controls=''):
    data = {'@type':'Product', 'name':'Dragon Ball FB11 Display EN Preorder', 'sku':'merchant-42', 'url':URL,
            'description':'Release: 2026-10-16', 'offers':{'price':price,'priceCurrency':'EUR','availability':'https://schema.org/'+status, 'url':URL}}
    if adapter == 'jtl':
        form = '<form id="buy_form" method="POST" action="'+URL+'"><input name="a" value="88"><input name="anzahl" data-product-id="88">'+controls+'<button type="submit" name="inWarenkorb">'+button+'</button></form>'
    else:
        form = '<form class="cart" method="post">'+controls+'<button type="submit" name="add-to-cart" value="88" class="single_add_to_cart_button">'+button+'</button></form>'
    return '<h1>'+data['name']+'</h1><script type="application/ld+json">'+json.dumps(data)+'</script>'+form

class CheckoutTests(unittest.TestCase):
    def test_jtl_exact_form_live_price(self):
        row=single_product(shop(),page(),URL)[0]
        self.assertTrue(row['add_to_cart_available'])
        self.assertEqual(row['variant_id'],'merchant-42')
        self.assertEqual(row['cart_product_id'],'88')
        client=type('Client',(),{'text':lambda _,url:page(price=99.99)})()
        fresh,error=p.live(dict(row,price='1'),shop(),client,NOW)
        self.assertIsNone(error)
        self.assertEqual(fresh['price'],'99.99')
    def test_jtl_wrong_article_quantity_or_other_form(self):
        for body in [page().replace('data-product-id="88"','data-product-id="99"'),
                     page().replace('id="buy_form"','id="recommended"'),
                     page().replace('name="inWarenkorb"','name="wishlist"'),
                     page().replace('action="'+URL+'"','action="https://other.test/cart"')]:
            self.assertFalse(single_product(shop(),body,URL)[0]['add_to_cart_available'])
    def test_waitlist_soldout_and_disabled(self):
        for body in [page(button='Notify me'),page(status='OutOfStock'),page().replace('<button','<button disabled'),
                     page(controls='<select name="language"><option>DE</option><option>EN</option></select>'),
                     page(controls='<input type="radio" name="attribute_language" value="EN">')]:
            self.assertFalse(single_product(shop(),body,URL)[0]['add_to_cart_available'])
    def test_hidden_and_disabled_ancestor(self):
        body=page().replace('<input name="a"','<fieldset disabled><input name="a"').replace('</form>','</fieldset></form>')
        self.assertFalse(single_product(shop(),body,URL)[0]['add_to_cart_available'])
    def test_currency_and_search_only_page_rejected(self):
        self.assertEqual(single_product(shop(),page().replace('"EUR"','"USD"'),URL),[])
        self.assertEqual(single_product(shop(),page().replace('<h1>','<h2>').replace('</h1>','</h2>'),URL),[])
    def test_woocommerce_simple_and_negative(self):
        for available in (True,False):
            body=page(adapter='woocommerce',status='InStock' if available else 'OutOfStock')
            row=parse_structured(shop('woocommerce'),body,URL)[0][0]
            self.assertEqual(row['add_to_cart_available'],available)
    def test_no_price_from_another_product(self):
        body=page().replace('"name": "Dragon Ball FB11 Display EN Preorder"','"name": "Other product"')
        self.assertEqual(single_product(shop(),body,URL),[])
    def test_member_restriction(self):
        body=page().replace('Release: 2026-10-16','Nur für freigeschaltete Mitglieder')
        self.assertFalse(single_product(shop(),body,URL)[0]['add_to_cart_available'])
    def test_jtl_lifecycle_dedupe_restock_waitlist_price(self):
        cfg=load_config('config/config.json')
        cfg['shops']=[shop()]
        cfg['preorder_watch']['trusted_shop_ids']=['example']
        row=single_product(shop(),page(),URL)[0]
        state={'version':1,'offers':{}}
        client=type('Client',(),{'body':page(), 'text':lambda self,url:self.body})()
        def scan(at): return p.scan([row],cfg,state,client,at)[1]
        first=scan(NOW)[0]
        p.delivered(state,first,NOW,'id')
        self.assertEqual(scan(NOW+60),[])
        client.body=page(status='OutOfStock')
        self.assertEqual(scan(NOW+120),[])
        client.body=page()
        reopened=scan(NOW+180)[0]
        p.delivered(state,reopened,NOW+180,'id2')
        client.body=page(button='Notify me')
        self.assertEqual(scan(NOW+240),[])
        client.body=page()
        wave=scan(NOW+300)[0]
        p.delivered(state,wave,NOW+300,'id3')
        client.body=page(price=90)
        self.assertEqual(len(scan(NOW+360)),1)
    def test_wrong_live_language(self):
        body=page().replace('Display EN','Display JP')
        row=single_product(shop(),body,URL)[0]
        self.assertEqual(p.identity(row,load_config('config/config.json'))[1],'WRONG_LANGUAGE')

class ShopifyCartTests(unittest.TestCase):
    def setUp(self):
        self.client=Client()
        self.offer=dict(shop='example',shop_name='Example Cards',seller='Example Cards',seller_verified=True,
                        key='example:123',handle='fb11',variant_id='123',title=self.client.product['title'],
                        description='',variant='Default Title',price='1',currency='EUR',available=True,
                        url='https://example.test/products/fb11?variant=123')
        self.shop=shop('shopify')
    def test_selected_option_cart(self):
        original=self.client.text
        self.client.text=lambda url:original(url).replace('<input name="id" value="123">',
           '<select name="id"><option value="456">JP</option><option value="123" selected>EN</option></select>')
        self.assertIsNone(p.live(self.offer,self.shop,self.client,NOW)[1])
    def test_other_selected_or_disabled_select_rejected(self):
        original=self.client.text
        for select in ['<select name="id"><option value="456" selected>JP</option><option value="123">EN</option></select>',
                       '<select name="id" disabled><option value="123" selected>EN</option></select>']:
            self.client.text=lambda url:original(url).replace('<input name="id" value="123">',select)
            self.assertEqual(p.live(self.offer,self.shop,self.client,NOW)[1],'AMBIGUOUS_VARIANT')
    def test_disabled_id_is_not_assumed_javascript_enabled(self):
        original=self.client.text
        self.client.text=lambda url:original(url).replace('name="id"','disabled name="id"')
        self.assertEqual(p.live(self.offer,self.shop,self.client,NOW)[1],'AMBIGUOUS_VARIANT')
    def test_zum_warenkorb(self):
        self.client.button='<button type="submit">Zum Warenkorb</button>'
        self.assertIsNone(p.live(self.offer,self.shop,self.client,NOW)[1])
    def test_member_only_preorder_rejected(self):
        self.client.product['description']='Nur für Mitglieder des Zirkels'
        self.assertEqual(p.live(self.offer,self.shop,self.client,NOW)[1],'WAITLIST')
    def test_first_set_is_not_first_edition(self):
        row=dict(self.offer,title='Naruto Mythos First Set Display 2nd Edition EN')
        self.assertEqual(p.identity(row,load_config('config/config.json'))[0]['edition'],'second')

class DiscoveryTests(unittest.TestCase):
    def test_html_catalog_and_details_rotate(self):
        source=shop()|{'catalog_urls':['https://example.test/a','https://example.test/b'],
                       'rotate_catalogs':True,'max_detail_pages':1,'product_link_pattern':'/Dragon-Ball-'}
        links=''.join('<a href="'+URL+str(n)+'">Dragon Ball FB11 Collection EN</a>' for n in range(3))
        calls=[]
        class Client:
            def text(self,url):
                calls.append(url)
                return links if url.endswith(('/a','/b')) else ''
        html_catalog(source,Client())
        self.assertEqual(calls[0],'https://example.test/a')
        self.assertIn(URL+'0',calls)
        source['_catalog_pages']=source['_catalog_next_pages']
        calls.clear()
        html_catalog(source,Client())
        self.assertEqual(calls[0],'https://example.test/b')
        source['_catalog_pages']=source['_catalog_next_pages']
        calls.clear()
        html_catalog(source,Client())
        self.assertIn(URL+'1',calls)

if __name__=='__main__': unittest.main()
