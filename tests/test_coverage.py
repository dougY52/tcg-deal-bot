import json
import threading
import time
import unittest
from pathlib import Path
from tcg_bot.http import Client
from tcg_bot.scanning import collect
from tcg_bot.web_sources import parse_woocommerce, html_catalog
from tcg_bot.preorders import candidate, release_day, live
from tcg_bot.product_types import product_kind


class Coverage(unittest.TestCase):
    def shop(self, name='a', host=None):
        return {'id':name,'name':name,'base_url':'https://'+(host or name)+'.test','adapter':'fake'}

    def test_retailers_parallel_but_one_host_serial(self):
        lock=threading.Lock();active={};peak={};total=[0,0]
        def adapter(shop, client):
            h=shop['base_url']
            with lock:
                active[h]=active.get(h,0)+1;peak[h]=max(peak.get(h,0),active[h]);total[0]+=1;total[1]=max(total)
            time.sleep(.03)
            with lock:active[h]-=1;total[0]-=1
            return [shop['id']],[]
        c=Client(0)
        shops=[self.shop('a'),self.shop('a2','a'),self.shop('b')]
        rows=collect(shops,c,{'fake':adapter},workers=4)
        self.assertEqual([r[0]['id'] for r in rows],['a','a2','b'])
        self.assertEqual(peak['https://a.test'],1)
        self.assertGreater(total[1],1)

    def test_failed_retailer_does_not_discard_other_results(self):
        def adapter(shop, client):
            if shop['id']=='bad':raise ValueError('secret must not appear')
            client.cooldowns['good.test']=12345
            return ['offer'],[]
        c=Client(0);rows=collect([self.shop('bad'),self.shop('good')],c,{'fake':adapter},workers=2)
        self.assertEqual(rows[0][3],'ValueError');self.assertEqual(rows[1][1],['offer'])
        self.assertEqual(c.cooldowns['good.test'],12345)

    def test_old_release_not_a_preorder(self):
        self.assertFalse(candidate({'title':'Dragon Ball FB04 Display EN','description':'Release: 15.11.2024','release_date':'2024-11-15'}))
        self.assertTrue(candidate({'title':'Dragon Ball FB04 Display EN Preorder','description':''}))
        self.assertEqual(release_day('Releasedatum ist der 13.11.2026!').isoformat(),'2026-11-13')

    def test_graded_etb_card_not_sealed_etb(self):
        self.assertIsNone(product_kind('Pokémon Evoli Promo Top Trainer Box Deutsch PSA 10'))
        self.assertEqual(product_kind('Pokémon Top Trainer Box Deutsch'),'etb')

    def woo(self, **changes):
        v={'variation_id':11,'attributes':{'attribute_pa_sprache':'englisch'},'display_price':84.99,
           'is_in_stock':True,'is_purchasable':True,'variation_is_active':True,'variation_is_visible':True,
           'max_qty':4,'is_pre_order':'no','availability_html':'Vorrätig'}
        v.update(changes)
        import html
        data=html.escape(json.dumps([v]),quote=True)
        return '''<h1>Dragon Ball FB04 Display EN</h1>
<script type="application/ld+json">{"@type":"Product","name":"Dragon Ball FB04 Display EN","description":"24 Booster","offers":{"priceSpecification":{"priceCurrency":"EUR","price":"84.99"}}}</script>
<form method="post" action="/produkt/fb04/" data-product_id="10" data-product_variations="'''+data+'''">
<select name="attribute_pa_sprache"><option value="englisch">Englisch</option></select>
<input name="product_id" value="10"><input name="add-to-cart" value="10"><input name="variation_id" value="0">
<button type="submit" class="single_add_to_cart_button">In den Warenkorb</button></form>'''

    def woo_shop(self):
        return dict(self.shop('sapphire-cards','sapphire'),adapter='woocommerce')

    def test_woo_concrete_variant(self):
        rows=parse_woocommerce(self.woo_shop(),self.woo(),'https://sapphire.test/produkt/fb04/')
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['available']);self.assertEqual(rows[0]['variant_id'],'11')
        self.assertEqual(rows[0]['variant'],'englisch');self.assertIn('24 Booster',rows[0]['description'])

    def test_woo_visible_button_unpurchasable(self):
        rows=parse_woocommerce(self.woo_shop(),self.woo(is_purchasable=False),'https://sapphire.test/produkt/fb04/')
        self.assertFalse(rows[0]['available'])

    def test_woo_language_option_not_selectable(self):
        page=self.woo().replace('value="englisch"','value="deutsch"')
        rows=parse_woocommerce(self.woo_shop(),page,'https://sapphire.test/produkt/fb04/')
        self.assertFalse(rows[0]['available'])

    def test_woo_backorder_without_preorder(self):
        rows=parse_woocommerce(self.woo_shop(),self.woo(backorders_allowed=True),'https://sapphire.test/produkt/fb04/')
        self.assertFalse(rows[0]['available'])

    def test_woo_live_rejects_changed_variant_stock(self):
        shop=self.woo_shop();url='https://sapphire.test/produkt/fb04/'
        o=parse_woocommerce(shop,self.woo(is_pre_order='yes'),url)[0]
        class Fake:
            def text(_,url):return self.woo(is_pre_order='yes',is_in_stock=False)
        row,reason=live(o,shop,Fake(),1791021600)
        self.assertEqual(reason,'OUT_OF_STOCK');self.assertFalse(row['available'])

    def test_wix_description_from_product_section_only(self):
        body='''<script type="application/ld+json">{"@type":"Product","name":"Dragon Ball FB04 Display EN","offers":{"price":"79.99","priceCurrency":"EUR","availability":"https://schema.org/InStock"}}</script><div data-hook="info-section-description">24 Booster</div><div data-hook="info-section-description">Other recommended product: 12 boosters</div>'''
        shop=dict(self.shop(),adapter='html_catalog',watch_urls=['https://a.test/product-page/fb04'],detail_description_hook='info-section-description')
        class Fake:
            def text(_,url):return body
        rows,_=html_catalog(shop,Fake())
        self.assertIn('24 Booster',rows[0]['description']);self.assertNotIn('12 boosters',rows[0]['description'])

    def test_single_booster_not_display(self):
        from tcg_bot.product_types import single_pack_variant
        from tcg_bot.preorders import identity
        from tcg_bot.__main__ import load_config
        from tcg_bot.market import normalize
        self.assertTrue(single_pack_variant('Booster'))
        self.assertTrue(single_pack_variant('1x Booster'))
        self.assertFalse(single_pack_variant('Display'))
        self.assertFalse(single_pack_variant('24 Booster'))
        cfg=load_config('config/config.json')
        offer={'title':'Pokémon Mega Entwicklung Dunkelnacht Display Booster - DE',
               'variant':'Booster','description':'36 Booster im Display','shop':'test','variant_id':'1'}
        self.assertEqual(normalize(offer,cfg)[1],'ambiguous_variant')
        self.assertEqual(identity(offer,cfg)[1],'AMBIGUOUS_VARIANT')

    def test_woo_disabled_submit_rejected(self):
        page=self.woo().replace('<button type="submit"','<button disabled type="submit"')
        self.assertFalse(parse_woocommerce(self.woo_shop(),page,'https://sapphire.test/produkt/fb04/')[0]['available'])

    def test_woo_conflicting_stock_text_rejected(self):
        page=self.woo(availability_html='Ausverkauft')
        self.assertFalse(parse_woocommerce(self.woo_shop(),page,'https://sapphire.test/produkt/fb04/')[0]['available'])

    def test_displaybreak_not_sealed_display(self):
        self.assertIsNone(product_kind('Pokemon Optimale Ordnung Displaybreak am 09.04.2026'))
