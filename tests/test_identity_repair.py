import unittest
from tcg_bot.__main__ import load_config
from tcg_bot.market import normalize, evaluate
from test_market import offers,state,NOW

class IdentityRepairTests(unittest.TestCase):
    def setUp(self):
        self.c=load_config('config/config.json')
        self.c['shops']=[{'id':str(i),'name':f'Shop {i}','base_url':f'https://shop{i}.example'} for i in range(5)]

    def test_naruto_same_set_same_edition_across_names(self):
        ids=[]
        for title in ['Naruto Mythos Konoha Shido Display 2. Edition EN','Naruto Mythos Konoha Shidō Display 2nd Edition EN','Naruto TCG First Set 2nd Edition Display EN','Naruto Mythos 1st Set 2nd Edition Display EN']:
            n,reason=normalize(offers()[0]|{'title':title},self.c)
            self.assertIsNotNone(n,reason);ids.append(n['identity'])
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(ids[0],'Naruto:mythos|KONOHA-SHIDO|2|24|standard|EN')

    def test_first_edition_and_other_system_not_merged(self):
        base=offers()[0]
        first=normalize(base|{'title':'Naruto Mythos Konoha Shido Display 1st Edition EN'},self.c)[0]
        second=normalize(base|{'title':'Naruto Mythos Konoha Shido Display 2nd Edition EN'},self.c)[0]
        self.assertNotEqual(first['identity'],second['identity'])
        self.assertIsNone(normalize(base|{'title':'Naruto Weiss Schwarz Konoha Shido Display EN'},self.c)[0])

    def test_18er_format_without_description_count(self):
        n,reason=normalize(offers()[0]|{'title':'Pokémon Gewalten der Zeit 18er Display DE','description':'Original versiegelt'},self.c)
        self.assertIsNotNone(n,reason);self.assertEqual(n['packs'],18)

    def test_three_total_retailers_with_anchor_qualify(self):
        titles=['Naruto Mythos First Set 2nd Edition Display EN','Naruto Mythos Konoha Shido Display 2. Edition EN','Naruto TCG Konoha Shidō Display 2nd Edition EN']
        rows=[o|{'title':title} for o,title in zip(offers(('54.99','69.90','79.95')),titles)]
        deals,_,_=evaluate(rows,self.c,state(),NOW)
        self.assertEqual(len(deals),1)
        self.assertEqual(deals[0]['price'],'54.99')
        self.assertEqual(len(deals[0]['comparisons']),2)
        self.assertGreaterEqual(deals[0]['confidence'],0.90)

    def test_only_two_total_retailers_or_missing_anchor_still_blocked(self):
        rows=[o|{'title':'Naruto Mythos First Set 2nd Edition Display EN'} for o in offers(('54.99','69.90','79.95'))]
        self.assertFalse(evaluate(rows[:2],self.c,state(),NOW)[0])
        self.c['market']['price_references']=[]
        self.assertFalse(evaluate(rows,self.c,state(),NOW)[0])

    def test_excluded_games_stay_excluded(self):
        for title in ['Digimon BT24 Display EN','Yu-Gi-Oh Display EN']:
            self.assertEqual(normalize(offers()[0]|{'title':title},self.c)[1],'irrelevant')

    def test_delivery_history_survives_alias_repair(self):
        from tcg_bot.market import migrate_alias_identities
        old='Naruto:mythos|name:mythos first set 2nd edition|2|24|standard|EN'
        new='Naruto:mythos|KONOHA-SHIDO|2|24|standard|EN'
        s={'market_sent':{old:{'at':NOW,'price':'54.99'}},'market_history':{'x':{'identity':old}}}
        migrate_alias_identities(s,self.c['market'])
        self.assertEqual(s['market_history']['x']['identity'],new)
        self.assertIn(new,s['market_sent']);self.assertNotIn(old,s['market_sent'])
