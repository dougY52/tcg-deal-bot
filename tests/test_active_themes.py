import unittest
from tcg_bot.__main__ import load_config
from tcg_bot.market import normalize
from test_market import offers

class ActiveThemeTests(unittest.TestCase):
    def test_exactly_three_active_themes(self):
        c=load_config('config/config.json')
        self.assertEqual(set(c['franchises'])-set(c.get('disabled_franchises', [])),{'Pokémon','One Piece','Dragon Ball'})
        for name in ('Naruto','Fairy Tail','JoJo','Bleach','My Hero Academia','Hunter x Hunter','Demon Slayer','Jujutsu Kaisen','Attack on Titan','Black Clover','Sword Art Online','Digimon','Yu-Gi-Oh'):
            row=offers()[0]|{'title':name+' Booster Display EN'}
            self.assertEqual(normalize(row,c)[1],'irrelevant',name)
    def test_selected_themes_still_pass_normalization(self):
        c=load_config('config/config.json')
        for title in ('Pokémon Dunkelnacht Display DE','One Piece OP16 Display EN','Dragon Ball FB03 Display EN'):
            row=offers()[0]|{'title':title}
            self.assertIsNotNone(normalize(row,c)[0],title)

    def test_naruto_pause_covers_saved_targets_preorders_and_daily_quotes(self):
        from tcg_bot import preorders, fast_watch, daily_prices
        c=load_config('config/config.json')
        row=offers()[0]|{'title':'Naruto Mythos Shinobi Shiren Display EN', 'variant':'Default Title',
                         'validated_at':1000, 'live_validated':True, 'add_to_cart_available':True,
                         'availability_status':'preorder'}
        self.assertIsNone(preorders.identity(row,c)[0])
        state={'fast_targets':{'old':{'offer':row}}, 'preorder_quotes':{'old':row}}
        self.assertEqual(fast_watch.select(c,state),[])
        self.assertEqual(daily_prices.eligible(c,state,1000),[])
        self.assertIn('old',state['fast_targets'])  # Pausing must preserve history.
        fast_watch.remember([row],c,{},1000)
        c['disabled_franchises']=[]
        self.assertIsNotNone(preorders.identity(row,c)[0])

    def test_no_naruto_drop_alert_or_explicit_crawl(self):
        from tcg_bot import drop_watch
        from unittest.mock import Mock
        from test_drop_watch import NOW, EVENT
        c=load_config('config/config.json')
        for shop in c['shops']:
            for key in ('watch_handles','watch_urls','catalog_urls','catalog_collections'):
                self.assertFalse(any('naruto' in v.lower() for v in shop.get(key,[])))
        c['shops']=[]
        c['drop_watch']['sources']=[{'id':'shop','name':'Shop','url':'https://example.test'}]
        client=Mock(spec=['text']);client.text.return_value=EVENT.replace('Pokémon','Naruto Mythos')
        send=Mock(return_value='id')
        self.assertEqual(drop_watch.run(c,{},client,NOW,send)['sent'],0)
        send.assert_not_called()
