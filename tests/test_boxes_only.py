import unittest
from tcg_bot.__main__ import load_config
from tcg_bot.market import normalize, evaluate
from test_market import offers, state, NOW

class BoxesOnlyTests(unittest.TestCase):
    def setUp(self):self.c=load_config('config/config.json')
    def row(self,title,description='9 Booster original versiegelt'):
        return offers()[0]|dict(title=title,description=description)
    def test_tins_and_mixed_tin_boxes_excluded(self):
        for title in ['Pokémon Glurak Tin DE','Pokémon Mini-Tin-Box DE','Pokémon Tinstapel DE','Pokémon Tin Tower Box DE','Pokémon ETB + 3 Tins DE','Pokémon MiniTins Box DE','Pokémon 151 Booster Bundle DE','Pokémon 151 Blister DE']:
            self.assertIsNone(normalize(self.row(title),self.c)[0],title)
    def test_original_box_formats_allowed(self):
        for title in ['Pokémon ME04 Display DE','Pokémon ME04 Top Trainer Box DE','Pokémon ME04 Elite Trainer Box DE','Pokémon Ultra Premium Collection Glurak DE','One Piece Anniversary Box EN']:
            self.assertIsNotNone(normalize(self.row(title, '36 Booster original versiegelt'),self.c)[0],title)
    def test_seller_assortments_excluded(self):
        for row in [self.row('Pokémon ETB Stapel DE'),self.row('Pokémon 3x Top Trainer Box DE'),self.row('Pokémon Glurak Box DE','9 Booster. Von uns zusammengestellt.')]:
            self.assertIsNone(normalize(row,self.c)[0])
    def test_old_unsent_tin_not_delivered(self):
        row=self.row('Pokémon Glurak Tin DE')
        self.assertFalse(evaluate([row],self.c,state(),NOW)[0])

    def test_price_cap_is_inclusive_and_applies_to_all_allowed_formats(self):
        for title in ['Pokémon ME04 Display DE','Pokémon ME04 Top Trainer Box DE','One Piece Anniversary Box EN']:
            for price in ['179.99','200.00']:
                self.assertIsNotNone(normalize(self.row(title)|{'price':price},self.c)[0])
            for price in ['200.01','350.00']:
                self.assertEqual(normalize(self.row(title)|{'price':price},self.c)[1],'over_user_budget')
    def test_high_price_never_reaches_send_even_with_price_context_enabled(self):
        row=self.row('Pokémon ME04 Top Trainer Box DE')|{'price':'350.00'}
        self.assertFalse(evaluate([row],self.c,state(),NOW)[0])
