"""Full catalogue and future releases: no network and no Discord in these fixtures."""
import copy
import json
import time
import unittest
from unittest.mock import Mock
from tcg_bot import cardmarket as cm, cardmarket_catalog as cat, price_comparison as pc
from tcg_bot.__main__ import load_config
from tcg_bot.http import Client, FetchError
from test_cardmarket_prices import NOW, offer


def product(pid,name,category):
    return dict(idProduct=pid,name=name,idCategory=category)


class FullCatalogue(unittest.TestCase):
    def setUp(self):
        self.cfg=load_config('config/config.json')
        self.state={'cardmarket_daily':{},'cardmarket_names':{}}

    def inventory(self,game,rows):
        inventory=cat.catalogue(rows,game)
        self.state['cardmarket_daily'][str(game)]={'catalogue':inventory,'products':{
            str(m['product_id']):dict(product_id=m['product_id'],name=m['catalog_name'],
                category_id=m['category_id'],at=NOW,trend='90',currency='EUR') for m in inventory.values()}}
        return inventory

    def match(self,title,packs=24,**kwargs):
        return pc.match_product(offer(title,packs=packs)|kwargs,self.cfg,self.state)

    def test_no_fixed_id_or_product_count_limit(self):
        rows=[product(1000000+i,f'Future Set {i} Booster Box',1624) for i in range(800)]
        self.assertEqual(len(self.inventory(18,rows)),800)
        found=self.match('One Piece Future Set 799 Booster Box EN')
        self.assertEqual(found['product_id'],1000799)
        self.assertEqual(pc.assess(offer('One Piece Future Set 799 Booster Box EN',packs=24),self.cfg,self.state,NOW)['code'],'resale_unverified')

    def test_new_future_set_no_config_id_needed(self):
        self.inventory(13,[product(999000,'Reach the God Booster Box [Fusion World]',1052)])
        self.state['cardmarket_names']['fw']={'aliases':cat.bandai_aliases('<h3>BOOSTER PACK -REACH THE GOD- [FB12]</h3>','fw')}
        self.assertEqual(self.match('Dragon Ball Fusion World FB12 Display EN')['product_id'],999000)
        self.assertEqual(self.match('Dragon Ball FB12 Reach the God Display EN')['product_id'],999000)
        self.assertIsNone(self.match('Dragon Ball FB12 Some Other Set Display EN'))

    def test_new_pokemon_translation_joined_by_id(self):
        pairs=cat.pokemon_aliases([{'id':'me99','name':'Future Dawn'}],[{'id':'me99','name':'Neue Morgenröte'}])
        self.state['cardmarket_names']['pokemon']={'aliases':pairs}
        self.inventory(6,[product(999001,'Future Dawn Booster Box',53)])
        self.assertEqual(self.match('Pokémon Neue Morgenröte Display Deutsch',36)['product_id'],999001)
        self.assertIsNone(self.match('Pokémon Neue Morgenröte Display English',36))

    def test_existing_localized_set_beyond_original_35(self):
        self.inventory(6,[product(999002,'Temporal Forces Booster Box',53)])
        self.assertEqual(self.match('Pokémon Gewalten der Zeit Display DE',36)['product_id'],999002)
        self.assertEqual(self.match('Pokémon Karmesin & Purpur SV05 Gewalten der Zeit Display DE',36)['product_id'],999002)
        self.assertEqual(self.match('Pokémon SV 05 Display DE',36)['product_id'],999002)
        self.assertIsNone(self.match('Pokémon SV06 Gewalten der Zeit Display DE',36))

    def test_pocket_and_conflicting_ids_are_not_translations(self):
        self.assertEqual(cat.pokemon_aliases([{'id':'A1','name':'Pocket Set'}],[{'id':'A1','name':'Pocket DE'}]),{})
        with self.assertRaises(ValueError):cat.pokemon_aliases([{'id':'x','name':'A'},{'id':'x','name':'B'}],[{'id':'x','name':'C'}])

    def test_pack_variants_do_not_collapse(self):
        self.inventory(6,[product(999003,'Future Dawn Booster Box',53),product(999004,'Future Dawn Booster Box (18 Boosters)',53)])
        self.assertEqual(self.match('Pokémon Future Dawn Display DE',36)['product_id'],999003)
        self.assertEqual(self.match('Pokémon Future Dawn Display DE',18)['product_id'],999004)
        self.assertIsNone(self.match('Pokémon Future Dawn Display DE',24))
        self.assertIsNone(self.match('Pokémon Future Dawn Display DE',18,variant='1 Booster'))

    def test_pc_etb_and_edition_qualifiers_are_preserved(self):
        self.inventory(6,[product(999005,'Future Dawn Elite Trainer Box',1016),product(999006,'Future Dawn Pokémon Center Elite Trainer Box',1016)])
        self.assertEqual(self.match('Pokémon Future Dawn ETB DE',9)['product_id'],999005)
        self.assertEqual(self.match('Pokémon Future Dawn Pokémon Center ETB DE',11)['product_id'],999006)
        self.assertIsNone(self.match('Pokémon Future Dawn ETB First Edition DE',9))

    def test_collector_is_not_regular_booster_box(self):
        self.inventory(13,[product(999007,'Power Absorbed Booster Box',1052),product(999008,'Power Absorbed Collector´s Booster Box',1052)])
        self.assertEqual(self.match('Dragon Ball BT20 Power Absorbed Collectors Booster Box EN',12)['product_id'],999008)
        self.assertEqual(self.match('Dragon Ball BT20 Power Absorbed Booster Box EN')['product_id'],999007)

    def test_foreign_cases_accessories_and_duplicates_excluded(self):
        rows=[product(i+1,n,1624) for i,n in enumerate(['Future Booster Box (Non-English)','Future Booster Box (Asia Region Legal)',
             'Future Booster Box Case','Future Sleeves','Future (12x Booster Box)','Future Booster Box','Future Booster Box'])]
        self.inventory(18,rows)
        self.assertEqual(len(self.state['cardmarket_daily']['18']['catalogue']),2)
        self.assertIsNone(self.match('One Piece Future Booster Box EN'))  # identical names, different IDs
        self.assertIsNone(self.match('One Piece Future Booster Box JP',language='EN'))

    def test_bundle_etb_tin_and_collection_are_distinct(self):
        rows=[product(50,'Future Dawn Booster Bundle',53),product(51,'Future Dawn Tin',1014),
              product(52,'Future Dawn Mini Tin',1014),product(53,'Future Dawn Elite Trainer Box',1016),
              product(54,'Future Dawn Poster Collection',1015)]
        self.inventory(6,rows)
        for text,packs,pid in [('Booster Bundle',6,50),('Tin',4,51),('Mini Tin',2,52),('ETB',9,53),('Poster Kollektion',3,54)]:
            with self.subTest(text=text):self.assertEqual(self.match(f'Pokémon Future Dawn {text} DE',packs)['product_id'],pid)
        self.assertIsNone(self.match('Pokémon Future Dawn Tin Display DE',10))
        self.assertIsNone(self.match('Pokémon Future Dawn Booster Bundle DE',12))

    def test_premium_collection_localized_character(self):
        self.inventory(6,[product(55,'30th Celebration: Espeon ex Ultra-Premium Collection',1015)])
        self.assertEqual(self.match('Pokémon 30 Jahre Psiana ex Ultra Premium Kollektion DE',16)['product_id'],55)

    def test_volume_number_is_not_booster_count(self):
        self.inventory(18,[product(56,'The Best Vol.2 Booster Box',1624)])
        self.assertEqual(self.match('One Piece PRB02 The Best Vol.2 Booster Display EN',10)['product_id'],56)

    def test_manga_series_number_does_not_merge_products(self):
        self.inventory(13,[product(60,'Manga Booster 01 Booster Box [Fusion World]',1052),
                           product(61,'Manga Booster 02 Booster Box [Fusion World]',1052)])
        self.assertEqual(self.match('Dragon Ball Fusion World Manga Booster 01 Booster Box EN',12)['product_id'],60)
        self.assertEqual(self.match('Dragon Ball Fusion World Manga Booster 02 Booster Box EN',12)['product_id'],61)

    def test_unknown_code_conflict_and_wrong_language_fail_closed(self):
        self.inventory(18,[product(57,'The Dominance of God Booster Box',1624)])
        self.assertIsNotNone(self.match('One Piece OP18 Display EN'))
        for title in ['One Piece OP19 The Dominance of God Display EN','One Piece OP18 OP17 Display EN',
                      'One Piece OP18 Display DE','One Piece OP18 Display JP']:
            with self.subTest(title=title):self.assertIsNone(self.match(title))

    def test_official_names_keep_only_unambiguous_bracketed_codes(self):
        rows=cat.bandai_aliases('<h4>BOOSTER PACK -FUTURE DAWN- [OP-20]</h4><h4>BOOSTER PACK -OTHER NAME- [OP-20]</h4><h4>BOOSTER PACK -NEW SKY- [OP-21]</h4>','op')
        self.assertEqual(rows,{'OP21':'new sky'})

    def test_unsupported_catalog_category_does_not_become_box(self):
        self.assertEqual(cat.catalogue([product(1,'Pokemon Single Booster Box',52),product(2,'Coin Box',1017)],6),{})

    def client(self,day=NOW,with_future=False):
        from datetime import datetime,timezone
        client=Client(delay=0)
        def read(url):
            g=next(g for g in cm.GAMES if url in cm.urls(g));category={6:53,13:1052,18:1624}[g]
            rows=[product(g*100,'Original Dawn Booster Box',category)]
            if with_future:rows.append(product(g*100+1,'Future Dawn Booster Box',category))
            stamp=datetime.fromtimestamp(day,timezone.utc).isoformat()
            if 'productList' in url:return {'version':1,'createdAt':stamp,'products':rows}
            return {'version':1,'createdAt':stamp,'priceGuides':[dict(idProduct=p['idProduct'],idCategory=category,trend=80 if i==0 else None) for i,p in enumerate(rows)]}
        client.cardmarket_json=Mock(side_effect=read)
        client.public_set_json=Mock(side_effect=FetchError('offline fixture'))
        client.text=Mock(side_effect=FetchError('offline fixture'))
        return client

    def test_migration_and_new_unpriced_products_imported_next_day(self):
        self.state['cardmarket_daily']['6']={'checked_day':'2026-10-25','products':{}}
        client=self.client();cm.refresh(self.cfg,self.state,client,NOW)
        self.assertIn('600',self.state['cardmarket_daily']['6']['catalogue'])
        self.assertEqual(client.cardmarket_json.call_count,6)
        cm.refresh(self.cfg,self.state,client,NOW+300)
        self.assertEqual(client.cardmarket_json.call_count,6)
        client=self.client(NOW+86400,True);report=cm.refresh(self.cfg,self.state,client,NOW+86400)
        self.assertIn('601',self.state['cardmarket_daily']['6']['catalogue'])
        self.assertNotIn('601',self.state['cardmarket_daily']['6']['products'])
        self.assertEqual(report['games'][0]['without_price'],1)
        self.assertEqual(client.cardmarket_json.call_count,6)

    def test_name_outage_keeps_previous_aliases_and_never_stops_import(self):
        self.state['cardmarket_names']['pokemon']={'aliases':{'neues set':'new set'}}
        report=cm.refresh(self.cfg,self.state,self.client(),NOW)
        self.assertEqual(report['status'],'ok')
        self.assertEqual(self.state['cardmarket_names']['pokemon']['aliases'],{'neues set':'new set'})
        self.assertEqual(report['names']['pokemon']['status'],'unavailable')

    def test_public_translation_endpoint_is_allowlisted(self):
        client=Client()
        with patch_raw(client) as raw:
            client.public_set_json('de')
            raw.assert_called_once_with('https://api.tcgdex.net/v2/de/sets')
            with self.assertRaises(FetchError):client.public_set_json('https://elsewhere.test/')


def patch_raw(client):
    from unittest.mock import patch
    return patch.object(client,'raw',return_value='[]')
