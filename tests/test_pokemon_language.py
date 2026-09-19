import unittest
from test_market import cfg, offers
from tcg_bot.market import normalize

class PokemonLanguageTests(unittest.TestCase):
    def pokemon(self, suffix):
        return offers()[0] | {'title':'Pokémon Dunkelnacht Display '+suffix,'description':'36 Booster original versiegelt'}

    def test_german_cards_and_preorders_allowed(self):
        for suffix in ('DE','Deutsch','DE Vorbestellung'):
            row,reason=normalize(self.pokemon(suffix),cfg())
            self.assertIsNotNone(row,reason)
            self.assertEqual(row['language'],'DE')

    def test_english_cards_excluded_even_at_german_shop(self):
        for suffix in ('EN','Englisch','English Vorbestellung'):
            row,reason=normalize(self.pokemon(suffix),cfg())
            self.assertIsNone(row)
            self.assertEqual(reason,'language_excluded')

    def test_unknown_language_not_inferred_from_german_description(self):
        self.assertIsNone(normalize(self.pokemon(''),cfg())[0])

    def test_other_tcg_english_still_allowed(self):
        self.assertEqual(normalize(offers()[0],cfg())[0]['language'],'EN')
