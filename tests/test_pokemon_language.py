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

    def test_english_cards_and_preorders_allowed(self):
        for suffix in ('EN','Englisch','English Vorbestellung'):
            row,reason=normalize(self.pokemon(suffix),cfg())
            self.assertIsNotNone(row,reason)
            self.assertEqual(row['language'],'EN')

    def test_unknown_language_not_inferred_from_german_description(self):
        self.assertIsNone(normalize(self.pokemon(''),cfg())[0])

    def test_other_tcg_english_still_allowed(self):
        self.assertEqual(normalize(offers()[0],cfg())[0]['language'],'EN')

    def test_language_changes_keep_price_identity_separate(self):
        de=normalize(self.pokemon('DE'),cfg())[0]
        en=normalize(self.pokemon('EN'),cfg())[0]
        self.assertNotEqual(de['identity'],en['identity'])

    def test_japanese_and_ambiguous_still_rejected(self):
        for suffix in ('JP','DE EN'):
            self.assertIsNone(normalize(self.pokemon(suffix),cfg())[0])
