import copy
import unittest
from unittest.mock import patch
from tcg_bot.cardpal_discovery import candidate_offers, product_rows, shop_for, discover

AID = 'b98ec690-f022-46db-a1a7-4cf3750b1450'
SHOP = {'id':'cards','name':'Cards Shop','adapter':'shopify','currency':'EUR','base_url':'https://cards.example','enabled':True}
CFG = {'shops':[SHOP], 'preorder_watch':{'max_price_eur':200},
       'franchises':{'Pokémon':r'pok[eé]mon','Dragon Ball':r'dragon.?ball','One Piece':r'one.?piece'},
       'cardpal_discovery':{'enabled':True,'max_requests':20,'max_articles':6}}
OFFER = {'language':'de','availability':'IN_STOCK','currency':'EUR','price':79.99,'vat_included':True,
         'url':'https://cards.example/products/pokemon-box-de','is_invite':False,
         'vendor':{'company_name':'Cards Shop','is_marketplace':False}}
DETAIL = {'article':{'id':AID,'franchise_code':'POKEMON','product_type':'BOOSTER_BOX'},'offers':[OFFER]}
PRODUCT = {'handle':'pokemon-box-de','title':'Pokemon Dunkelnacht Booster Display Deutsch',
           'description':'36 Booster deutsch', 'variants':[{'id':123,'title':'Deutsch','price':8999,'available':True}]}


class FakeClient:
    def __init__(self):
        self.urls = []
    def get(self, url):
        self.urls.append(url)
        if '/api/search/' in url:
            return [{'id':AID,'product_type':'BOOSTER_BOX','has_in_stock':True}]
        if '/api/articles/' in url:
            return copy.deepcopy(DETAIL)
        if '/products/' in url:
            return copy.deepcopy(PRODUCT)
        raise AssertionError(url)


class DiscoveryTests(unittest.TestCase):
    def test_relevant_german_offer(self):
        self.assertEqual(len(candidate_offers(DETAIL, CFG)), 1)

    def test_wrong_languages_unavailable_invites_expensive(self):
        for change in ({'language':'en'}, {'language':'ja'}, {'availability':'SOLD_OUT'},
                       {'is_invite':True}, {'price':350}, {'price':'NaN'}, {'vat_included':False},
                       {'currency':'GBP'}, {'availability':'WAITLIST'}):
            self.assertEqual(candidate_offers(dict(DETAIL,offers=[dict(OFFER,**change)]), CFG), [])

    def test_preorder_allowed_but_cards_and_other_franchises_not(self):
        self.assertTrue(candidate_offers(dict(DETAIL,offers=[dict(OFFER,availability='PREORDER')]), CFG))
        for change in ({'product_type':'SINGLE_CARD'},{'franchise_code':'ONEPIECE'}):
            self.assertFalse(candidate_offers(dict(DETAIL,article=dict(DETAIL['article'],**change)), CFG))

    def test_unknown_or_foreign_seller_not_automatically_trusted(self):
        self.assertIsNone(shop_for(dict(OFFER,url='https://unknown.example/products/pokemon'),CFG))
        self.assertIsNone(shop_for(OFFER,dict(CFG,shops=[dict(SHOP,international=True)])))
        self.assertIsNone(shop_for(dict(OFFER,vendor={'is_marketplace':True}),CFG))

    def test_shopify_alias_only_targets_configured_domain(self):
        offer=dict(OFFER,url='https://some-store.myshopify.com/products/pokemon-box-de')
        self.assertEqual(shop_for(offer,CFG),SHOP)
        client=FakeClient();product_rows(offer,SHOP,client)
        self.assertTrue(all(url.startswith(SHOP['base_url']) for url in client.urls))
        self.assertIsNone(shop_for(dict(offer,vendor={'company_name':'Unknown'}),CFG))

    def test_live_price_wins_and_unavailable_stays_unavailable(self):
        rows=product_rows(OFFER,SHOP,FakeClient())
        self.assertEqual(rows[0]['price'],'89.99')
        self.assertNotIn('live_validated',rows[0], 'catalog JSON is still not checkout validation')
        with patch.dict(PRODUCT,variants=[{'id':123,'price':8999,'available':False}]):
            self.assertIs(product_rows(OFFER,SHOP,FakeClient())[0]['available'],False)

    def test_concrete_variant_preserved(self):
        offer=dict(OFFER,url=OFFER['url']+'?variant=999')
        self.assertEqual(product_rows(offer,SHOP,FakeClient()),[])

    @patch('tcg_bot.cardpal_discovery.relay_articles',return_value=[])
    def test_discovery_remembers_targets_rotation_and_budget(self, relay):
        client=FakeClient();state={}
        rows,report=discover(CFG,state,client,10000)
        self.assertEqual(report['targets'],1)
        self.assertEqual(rows[0]['discovered_by'],'cardpal')
        self.assertEqual(report['requests'],3)
        self.assertEqual(state['cardpal_discovery']['scope_cursors']['POKEMON'],1)
        self.assertEqual(discover(CFG,state,client,10001)[0],[])
        self.assertTrue(discover(CFG,state,client,10001)[1]['not_due'])

    @patch('tcg_bot.cardpal_discovery.relay_articles',return_value=[])
    def test_live_language_wins_over_provider_german_label(self, relay):
        with patch.dict(PRODUCT,title='Pokemon Booster Display English',description='English',
                        variants=[{'id':123,'title':'English','price':8999,'available':True}]):
            self.assertEqual(discover(CFG,{},FakeClient(),10000)[0],[])

    def test_disabled_has_no_requests(self):
        client=FakeClient()
        self.assertEqual(discover(dict(CFG,cardpal_discovery={}),{},client,10000)[0],[])
        self.assertEqual(client.urls,[])

    def expanded(self):
        cfg=copy.deepcopy(CFG)
        cfg['market']={'franchise_languages':{'Pokémon':['DE','EN'],'Dragon Ball':['EN'],'One Piece':['EN']}}
        cfg['cardpal_discovery']['franchises']=['DRAGONBALL','POKEMON','ONEPIECE']
        return cfg

    def test_all_requested_franchises_and_languages(self):
        for code, langs in [('POKEMON',['de','en']),('DRAGONBALL',['en']),('ONEPIECE',['en'])]:
            detail=dict(DETAIL,article=dict(DETAIL['article'],franchise_code=code))
            for lang in ['de','en','ja']:
                accepted=candidate_offers(dict(detail,offers=[dict(OFFER,language=lang)]),self.expanded())
                self.assertEqual(bool(accepted),lang in langs,(code,lang))

    @patch('tcg_bot.cardpal_discovery.relay_articles',return_value=[])
    def test_english_live_variant_accepted_in_expanded_config(self,relay):
        with patch.dict(PRODUCT,title='Pokemon Booster Display English',description='English',
                        variants=[{'id':123,'title':'English','price':8999,'available':True}]):
            self.assertTrue(discover(self.expanded(),{},FakeClient(),10000)[0])

    @patch('tcg_bot.cardpal_discovery.relay_articles',return_value=[])
    def test_each_franchise_searched_and_backlog_does_not_starve_others(self,relay):
        from urllib.parse import urlsplit,parse_qs
        ids={'DRAGONBALL':'11111111-1111-1111-1111-111111111111',
             'POKEMON':AID,'ONEPIECE':'22222222-2222-2222-2222-222222222222'}
        class MultiClient(FakeClient):
            def get(self,url):
                if '/api/search/' in url:
                    self.urls.append(url)
                    code=parse_qs(urlsplit(url).query)['franchise'][0]
                    return [{'id':ids[code],'product_type':'BOOSTER_BOX','has_in_stock':True}]
                if '/api/articles/' in url:
                    self.urls.append(url)
                    return {'article':{'franchise_code':'POKEMON','product_type':'SINGLE_CARD'},'offers':[]}
                return super().get(url)
        state={'cardpal_discovery':{'pending':{f'aaaaaaaa-aaaa-aaaa-aaaa-{i:012x}':9000 for i in range(40)}}}
        client=MultiClient();discover(self.expanded(),state,client,10000)
        for aid in ids.values():
            self.assertTrue(any(aid in url for url in client.urls),aid)
        discover(self.expanded(),state,client,10300)
        pokemon=[parse_qs(urlsplit(u).query)['language'][0] for u in client.urls if '/api/search/' in u and 'franchise=POKEMON' in u]
        self.assertEqual(pokemon,['German','English'])


if __name__ == '__main__':
    unittest.main()
