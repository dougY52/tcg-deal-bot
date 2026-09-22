import unittest
from tcg_bot.__main__ import load_config
from tcg_bot.market import normalize
from test_market import offers

class ActiveThemeTests(unittest.TestCase):
    def test_exactly_four_active_themes(self):
        c=load_config('config/config.json')
        self.assertEqual(set(c['franchises']),{'Pokémon','One Piece','Naruto','Dragon Ball'})
        for name in ('Fairy Tail','JoJo','Bleach','My Hero Academia','Hunter x Hunter','Demon Slayer','Jujutsu Kaisen','Attack on Titan','Black Clover','Sword Art Online','Digimon','Yu-Gi-Oh'):
            row=offers()[0]|{'title':name+' Booster Display EN'}
            self.assertEqual(normalize(row,c)[1],'irrelevant',name)
    def test_selected_themes_still_pass_normalization(self):
        c=load_config('config/config.json')
        for title in ('Pokémon Dunkelnacht Display DE','One Piece OP16 Display EN','Naruto Mythos Shinobi Shiren Display EN','Dragon Ball FB03 Display EN'):
            row=offers()[0]|{'title':title}
            self.assertIsNotNone(normalize(row,c)[0],title)
