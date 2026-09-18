import unittest
from datetime import date
from test_bot import config, offer
from tcg_bot.discovery import discovery, discovery_payload
from tcg_bot.rules import language, assess
from tcg_bot.price_guides import orientation

class EuropeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.cfg['franchises']['Dragon Ball'] = r'Dragon\s*Ball'
        self.row = offer() | {'key':'new:123','variant_id':'123','handle':'fb10','title':'Dragon Ball FB10 Booster Box English'}

    def test_currency_preserved_and_import_never_euro_deal(self):
        for currency in ('GBP','CHF'):
            row=self.row | {'international':True,'ships_to_de':True,'import_costs':True,'currency':currency,'shipping_note':'Versand und Importkosten zusätzlich.'}
            found=discovery(row,self.cfg)
            self.assertIsNotNone(found)
            text=discovery_payload(found)['embeds'][0]['description']
            self.assertIn(currency,text)
            self.assertNotIn('139.99 €',text)
            self.assertIsNone(assess(row,self.cfg)[0])
            self.assertIsNone(discovery(row | {'ships_to_de':False},self.cfg))
        self.assertIsNone(discovery(self.row | {'currency':'GBP'},self.cfg))

    def test_europe_languages_and_accessory_false_positives(self):
        for title in ['Pokémon - Display de Boosters - FR','Pokemon Display IT','Pokemon Booster Box ES','Pokemon Acrylcase Display EN','Pokemon Assorted Deck Display EN']:
            self.assertIsNone(discovery(self.row | {'title':title},self.cfg))
        for name,expected in [('Engels','EN'),('Anglais','EN'),('Duits','DE')]:
            self.assertEqual(language(self.row | {'title':'Pokemon Booster Box '+name}),expected)

    def test_us_price_is_context_not_european_reference(self):
        self.cfg['price_guides']=[{'title_pattern':r'Dragon\s*Ball.*\bFB10\b','usd_per_pack':'4.99','packs':24,'verified_on':'2026-01-01','valid_until':'2099-01-01','url':'https://example.org/msrp'}]
        found=discovery(self.row,self.cfg)
        self.assertIn('119.76 USD',found['price_orientation'])
        self.assertIn('keine Display-UVP',found['price_orientation'])
        self.assertIsNone(assess(self.row,self.cfg)[0])
        self.assertEqual(orientation(self.row,self.cfg,'DE'),'')
        self.assertEqual(orientation(self.row | {'title':'Dragon Ball FB100 Booster Box EN'},self.cfg,'EN'),'')
        self.cfg['price_guides'][0]['valid_until']='2020-01-01'
        self.assertEqual(orientation(self.row,self.cfg,'EN'),'')

    def test_targeted_english_collection_is_read_and_deduplicated(self):
        from test_bot import product
        from tcg_bot.sources import shopify
        calls=[]
        p=product()
        extra=product() | {'handle':'english-extra','variants':[product()['variants'][0] | {'id':99}]}
        class Client:
            def get(self,url):
                calls.append(url)
                return {'products':[p,extra] if '/collections/' in url else [p]}
        shop=config()['shops'][0] | {'catalog_collections':['english-booster-boxes']}
        rows,warnings=shopify(shop,Client())
        self.assertEqual(len(rows),2)
        self.assertEqual(warnings,[])
        self.assertTrue(any('/collections/english-booster-boxes/products.json' in u for u in calls))
