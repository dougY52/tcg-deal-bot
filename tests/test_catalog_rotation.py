import unittest
from tcg_bot.sources import shopify


class CatalogPages(unittest.TestCase):
    def setUp(self):
        self.shop = {'id':'example','name':'Example','currency':'EUR',
                     'base_url':'https://example.test','max_pages':2}
        self.pages=[]
        self.product={'handle':'example','title':'Dragon Ball FB04 Display EN',
                      'variants':[{'id':1,'price':'79.99','available':True}]}

    def get(self, url):
        from urllib.parse import urlsplit, parse_qs
        page=int(parse_qs(urlsplit(url).query)['page'][0])
        self.pages.append(page)
        return {'products':[self.product]*250 if page<=3 else []}

    def test_pages_beyond_previous_limit_are_reached(self):
        shopify(self.shop,self)
        self.assertEqual(self.pages,[1,2])
        self.shop['_catalog_pages']=self.shop['_catalog_next_pages']
        shopify(self.shop,self)
        self.assertEqual(self.pages,[1,2,1,3])
        self.shop['_catalog_pages']=self.shop['_catalog_next_pages']
        shopify(self.shop,self)
        self.assertEqual(self.pages,[1,2,1,3,1,4])
        self.assertEqual(self.shop['_catalog_next_pages']['https://example.test/products.json'],1)

    def test_invalid_cursor_starts_at_first_page(self):
        self.shop['_catalog_pages']={'https://example.test/products.json':-4}
        shopify(self.shop,self)
        self.assertEqual(self.pages,[1,2])

    def test_failed_page_does_not_skip_unread_products(self):
        product=self.product
        class Client:
            def get(_,url):
                if 'page=2' in url:
                    raise TimeoutError()
                return {'products':[product]*250}
        offers,warnings=shopify(self.shop,Client())
        self.assertTrue(offers)
        self.assertTrue(warnings)
        self.assertEqual(self.shop['_catalog_next_pages']['https://example.test/products.json'],2)

    def test_single_page_windows_still_advance(self):
        self.shop['max_pages']=1
        shopify(self.shop,self)
        self.shop['_catalog_pages']=self.shop['_catalog_next_pages']
        shopify(self.shop,self)
        self.assertEqual(self.pages,[1,2])
