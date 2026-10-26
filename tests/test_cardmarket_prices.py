import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from tcg_bot import cardmarket as cm, price_comparison as pc
from tcg_bot.__main__ import load_config, load_state, save_state
from tcg_bot.http import Client, FetchError

NOW = datetime(2026, 10, 25, 15, tzinfo=timezone.utc).timestamp()


def offer(title='Pokémon Paldeas Schicksale Booster Bundle DE', price='59.99', packs=6):
    return dict(title=title, variant='Default Title', description=f'{packs} Booster',
                price=price, currency='EUR', shop='test', handle='test', variant_id='1')


def snapshot(mappings, now=NOW):
    stamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
    catalog = dict(version=1, createdAt=stamp, products=[dict(idProduct=m['product_id'],
                   name=m['catalog_name'], idCategory=m['category_id']) for m in mappings])
    guide = dict(version=1, createdAt=stamp, priceGuides=[dict(idProduct=m['product_id'],
                 idCategory=m['category_id'], trend=69.99, low=0.99, avg1=None) for m in mappings])
    return catalog, guide


class CardmarketPrices(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config('config/config.json')
        self.o = offer()
        self.mapping = pc.match_product(self.o, self.cfg)
        self.state = {'version':1, 'offers':{}, 'cardmarket_daily':{}}
        for game in cm.GAMES:
            mappings = [m for m in self.cfg['price_comparison']['products'] if m['game_id']==game]
            catalog, guide = snapshot(mappings)
            self.state['cardmarket_daily'][str(game)] = {'products':cm.join(catalog,guide,mappings,NOW)}

    def test_over_retail_under_resale_is_not_deal(self):
        result = pc.assess(self.o, self.cfg, self.state, NOW)
        self.assertEqual(result['code'], 'resale_only')
        self.assertEqual(result['retail']['price_eur'], '29.99')
        self.assertEqual(result['cardmarket']['trend'], '69.99')
        self.assertNotIn('Bestpreis', result['label'])

    def test_retail_and_five_percent_threshold(self):
        for price, code in [('29.99','retail_deal'),('30.99','near_retail'),('70','above_retail')]:
            with self.subTest(price=price):
                self.assertEqual(pc.assess(self.o|{'price':price},self.cfg,self.state,NOW)['code'],code)

    def test_missing_retail_never_promotes_market_price(self):
        self.mapping.pop('retail')
        for price, code in [('5','resale_unverified'),('90','unknown')]:
            self.assertEqual(pc.assess(self.o|{'price':price},self.cfg,self.state,NOW)['code'],code)

    def test_expired_retail_becomes_unknown(self):
        self.mapping['retail']['valid_until'] = '2026-10-24'
        self.assertEqual(pc.assess(self.o,self.cfg,self.state,NOW)['code'],'resale_unverified')

    def test_inflated_cm_does_not_change_retail(self):
        self.state['cardmarket_daily']['6']['products'][str(self.mapping['product_id'])]['trend']='9999'
        self.assertEqual(pc.assess(self.o,self.cfg,self.state,NOW)['code'],'resale_only')
        self.assertEqual(pc.retail_reference(self.o,self.cfg,NOW)['price_eur'],'29.99')

    def test_exact_pack_count_and_language(self):
        for packs, pid in [(18,692093),(36,692092)]:
            row=offer('Pokémon Karmesin & Purpur Display DE',packs=packs)
            self.assertEqual(pc.match_product(row,self.cfg)['product_id'],pid)
        for row in [offer(packs=12),offer().copy()|{'description':''},offer().copy()|{'variant':'1 Booster'},
                    offer().copy()|{'title':offer()['title'].replace(' DE',' EN')}]:
            with self.subTest(row=row):self.assertIsNone(pc.match_product(row,self.cfg))

    def test_case_special_edition_and_conflicting_set_are_excluded(self):
        base='Dragon Ball Fusion World FB04 Ultra Limit Display EN'
        self.assertEqual(pc.match_product(offer(base,packs=24),self.cfg)['product_id'],790838)
        for title in [base+' Case',base+' Asia',base+' Enhanced',base+' 1st Edition',
                      base+' Special',base.replace('FB04','FB99'),base+' FB03', '2x Display '+base]:
            with self.subTest(title=title):self.assertIsNone(pc.match_product(offer(title,packs=24),self.cfg))

    def test_pc_etb_is_separate_product(self):
        standard=offer('Pokémon 30 Jahre Top-Trainer-Box DE',packs=9)
        exclusive=offer('Pokémon 30 Jahre Pokémon Center Top-Trainer-Box DE',packs=11)
        self.assertEqual(pc.match_product(standard,self.cfg)['product_id'],895551)
        self.assertEqual(pc.match_product(exclusive,self.cfg)['product_id'],895552)

    def test_exact_ean_supplies_missing_display_pack_count(self):
        row = offer('Dragon Ball Fusion World Raging Roar FB03 Display Englisch')
        row.update(description='', gtin='810059786523', price='85')
        result = pc.assess(row, self.cfg, self.state, NOW)
        self.assertIsNotNone(result['cardmarket'])
        self.assertEqual(result['code'], 'retail_deal')
        # The same barcode must never override a contradictory selected package.
        for changes in ({'gtin':'9999999999999'}, {'variant':'1 Booster'},
                        {'description':'12 Booster'}, {'packs':12},
                        {'title':row['title'].replace('Englisch','Japanisch')}):
            with self.subTest(changes=changes):
                self.assertIsNone(pc.match_product(row|changes,self.cfg))
        result = pc.assess(row|{'price':'99.99'}, self.cfg, self.state, NOW)
        self.assertEqual(result['retail']['price_eur'], '85.00')
        self.assertEqual(result['code'], 'above_retail')

    def test_near_retail_threshold_rounds_to_currency_cent(self):
        row = offer('Dragon Ball Fusion World FB04 Ultra Limit Display EN', price='83.99', packs=24)
        self.assertEqual(pc.assess(row,self.cfg,self.state,NOW)['code'],'near_retail')
        self.assertEqual(pc.assess(row|{'price':'84.00'},self.cfg,self.state,NOW)['code'],'above_retail')

    def test_expired_or_future_market_data_is_not_used(self):
        for at in [NOW-48*3600-1,NOW+1]:
            self.state['cardmarket_daily']['6']['products'][str(self.mapping['product_id'])]['at']=at
            self.assertIsNone(pc.assess(self.o,self.cfg,self.state,NOW)['cardmarket'])

    def test_embed_replaces_conflicting_praise(self):
        old={'embeds':[{'title':'BESTPREIS','color':0x26A269,'description':'Live geprüft\n💡 Super Deal',
                       'fields':[{'name':'Warum qualifiziert?','value':'günstig'},{'name':'Händler','value':'Geprüft'}]}]}
        new=pc.decorate(old,self.o,self.cfg,self.state,NOW)['embeds'][0]
        self.assertIn('kein Retail-Deal',new['title'])
        self.assertEqual(new['color'],0xE66100)
        self.assertNotIn('Super Deal',str(new))
        self.assertNotIn('Warum qualifiziert?',str(new))
        self.assertIn('keine Sprach-/DE-Verkäuferfilter',str(new))
        self.assertIn('kein eigener Herstellerbeleg',str(new))
        self.assertIn('Geprüft',str(new))
        self.assertEqual(old['embeds'][0]['title'],'BESTPREIS')
        self.assertNotIn('0.99',str(new))  # unfiltered low never advertised as best offer

    def test_compact_feed_same_verdict(self):
        text=pc.compact(self.o,self.cfg,self.state,NOW)
        for expected in ['kein Retail-Deal','29.99','69.99','kein Liveangebot','UVP laut Händler']:
            self.assertIn(expected,text)

    def test_disabled_preserves_legacy_message(self):
        self.cfg['price_comparison']['enabled']=False
        old={'embeds':[{'title':'legacy'}]}
        self.assertIs(pc.decorate(old,self.o,self.cfg,self.state,NOW),old)

    def test_matching_catalog_name_and_category_required(self):
        for field, value in [('name','Other Box'),('idCategory',1)]:
            catalog,guide=snapshot([self.mapping]);catalog['products'][0][field]=value
            self.assertEqual(cm.join(catalog,guide,[self.mapping],NOW),{})
        catalog,guide=snapshot([self.mapping]);guide['priceGuides'][0]['idCategory']=1
        self.assertEqual(cm.join(catalog,guide,[self.mapping],NOW),{})

    def test_schema_date_and_duplicate_rejected(self):
        for mode in ['schema','stale','future','undated','duplicate']:
            catalog,guide=snapshot([self.mapping])
            if mode=='schema':guide['version']=2
            elif mode=='stale':guide['createdAt']='2026-10-20T00:00:00Z'
            elif mode=='future':guide['createdAt']='2026-10-26T00:00:00Z'
            elif mode=='undated':guide['createdAt']='2026-10-25T00:00:00'
            else:guide['priceGuides']*=2
            with self.subTest(mode=mode), self.assertRaises(ValueError):cm.join(catalog,guide,[self.mapping],NOW)

    def test_invalid_prices_are_not_zero_prices(self):
        for value in [None,0,-1,'NaN','Infinity',False,'bad']:
            catalog,guide=snapshot([self.mapping]);guide['priceGuides'][0]['trend']=value
            self.assertEqual(cm.join(catalog,guide,[self.mapping],NOW),{})
        catalog,guide=snapshot([self.mapping]);row=cm.join(catalog,guide,[self.mapping],NOW)[str(self.mapping['product_id'])]
        self.assertIsNone(row['avg1'])
        self.assertIsNone(row['avg7'])

    def client(self, failed_game=None):
        client=Client(delay=0)
        client.public_set_json=Mock(side_effect=FetchError('offline fixture'))
        client.text=Mock(side_effect=FetchError('offline fixture'))
        def read(url):
            game=next(g for g in cm.GAMES if url in cm.urls(g))
            if game==failed_game:raise FetchError('HTTP 503')
            maps=[m for m in self.cfg['price_comparison']['products'] if m['game_id']==game]
            return snapshot(maps)[0 if 'productList' in url else 1]
        client.cardmarket_json=Mock(side_effect=read)
        return client

    def test_daily_cache_persisted_and_no_second_download(self):
        client=self.client();deadline=client.deadline
        result=cm.refresh(self.cfg,self.state,client,NOW)
        self.assertEqual([g['products'] for g in result['games']],[21,12,2])
        self.assertEqual(client.cardmarket_json.call_count,6)
        self.assertEqual(client.deadline,deadline)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';save_state(path,self.state);state=load_state(path)
            cm.refresh(self.cfg,state,client,NOW+300)
            self.assertEqual(client.cardmarket_json.call_count,6)
            self.assertIsNotNone(cm.lookup(self.mapping,state,NOW+300))
        self.assertLess(len(json.dumps(self.state)),30000)

    def test_failure_keeps_fresh_cache_backs_off_and_other_games_continue(self):
        client=self.client(6)
        result=cm.refresh(self.cfg,self.state,client,NOW)
        self.assertEqual(result['status'],'partial')
        self.assertEqual([r['status'] for r in result['games']],['unavailable','updated','updated'])
        self.assertIsNotNone(cm.lookup(self.mapping,self.state,NOW))
        calls=client.cardmarket_json.call_count
        cm.refresh(self.cfg,self.state,client,NOW+300)
        self.assertEqual(client.cardmarket_json.call_count,calls)
        cm.refresh(self.cfg,self.state,client,NOW+3601)
        self.assertEqual(client.cardmarket_json.call_count,calls+1)

    def test_no_transport_graceful(self):
        self.assertEqual(cm.refresh(self.cfg,{},None,NOW)['status'],'unavailable')

    def test_published_download_allowlist(self):
        client=Client()
        with patch.object(client,'raw',return_value='{"version":1}') as raw, patch.object(client,'check_allowed') as crawl:
            self.assertEqual(client.cardmarket_json(cm.urls(6)[0]),{'version':1})
            crawl.assert_not_called();raw.assert_called_once()
            for url in [cm.urls(6)[0]+'?key=x',cm.urls(6)[0].replace('_6','_9'),
                        'https://www.cardmarket.com/en/Pokemon',cm.urls(6)[0].replace('https:','http:')]:
                with self.assertRaises(FetchError):client.cardmarket_json(url)
            raw.assert_called_once()

class CardmarketDeliveryIntegration(unittest.TestCase):
    def setUp(self):
        from test_fast_lane import FastLane
        self.lane=FastLane();self.lane.setUp();self.lane.stock()
        self.lane.cfg['community_watch']['enabled']=False
        self.lane.cfg['drop_watch']['enabled']=False
        m=pc.match_product(self.lane.offer,self.lane.cfg)
        catalog,guide=snapshot([m])
        self.lane.state['cardmarket_daily']={'13':{'checked_day':'2026-10-25',
            'products':cm.join(catalog,guide,[m],NOW)}}

    def test_real_restock_and_duplicate_keep_comparison(self):
        report,sent=self.lane.run_fast(NOW)
        self.assertEqual(report['sent'],1)
        self.assertIn('Guter Retailpreis',sent[0]['embeds'][0]['title'])
        self.assertIn('69.99',str(sent[0]))
        self.assertIn('79,99',sent[0]['embeds'][0]['description'])  # live price beats search 69.99
        self.assertEqual(self.lane.run_fast(NOW+300)[1],[])
        self.lane.client.product['variants'][0]['available']=False
        self.assertEqual(self.lane.run_fast(NOW+600)[1],[])
        self.lane.client.product['variants'][0]['available']=True
        self.assertEqual(len(self.lane.run_fast(NOW+900)[1]),1)

    def test_waitlist_preorder_and_market_change_is_not_new_alert(self):
        self.lane.client.product['title']+=' Preorder'
        self.lane.offer['title']=self.lane.client.product['title']
        self.lane.client.button='<button>Notify me</button>'
        self.assertEqual(self.lane.run_fast(NOW)[1],[])
        self.lane.client.button='<button>Preorder</button>'
        sent=self.lane.run_fast(NOW+300)[1]
        self.assertEqual(len(sent),1)
        self.assertIn('PREORDER',sent[0]['embeds'][0]['title'])
        self.lane.state['cardmarket_daily']['13']['products']['790838']['trend']='180'
        self.assertEqual(self.lane.run_fast(NOW+600)[1],[])

    def test_shipping_not_invented_and_no_market_best_price(self):
        sent=self.lane.run_fast(NOW)[1]
        text=str(sent[0])
        self.assertIn('kein Versand',text)
        self.assertIn('Versand separat prüfen',text)
        self.assertNotIn('UVP / BESTPREIS',text)
