"""Regression fixtures are synthetic prices, not current shopping advice."""
import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from tcg_bot.__main__ import run, load_config
from tcg_bot.market import normalize, evaluate, market_payload
from tcg_bot.http import Client, FetchError

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc).timestamp()


def cfg():
    c = load_config('config/config.json')
    c['franchises']['Digimon'] = 'digimon'
    c['shops'] = [{'id': str(i), 'name': 'Shop '+str(i), 'base_url': f'https://shop{i}.example', 'adapter': 'shopify', 'currency': 'EUR', 'max_pages': 1} for i in range(7)]
    c['references'] = []
    c['market']['automatic_comparison'] = False
    c['market']['expanded_products'] = False
    c['market']['price_context_mode'] = False
    c['market']['allow_verified_without_comparisons'] = False
    c['market']['notify_all_shops'] = False
    c['market']['min_comparisons'] = 3
    c['market'].pop('max_premium_eur', None)
    c['market']['notify_within_price_range'] = False
    c['market']['price_references'] = [{'identity': 'masters|BT15|unspecified|24|standard|EN', 'kind': 'observed_retail', 'price_eur': '79.99', 'verified_on': '2026-09-18', 'valid_until': '2026-10-18', 'evidence_url':'https://retail.example/b15'}]
    return c


def offers(prices=('59.99','79.99','74.99','79.99')):
    return [dict(key=str(i)+':b15',shop=str(i),shop_name='Shop '+str(i),handle='b15',variant_id='b15',
                 title='Dragon Ball Saiyan Showdown B15 Booster Display EN',variant='Default Title',
                 description='24 Booster original versiegelt',price=str(price),available=True,
                 currency='EUR',seller_verified=True,url=f'https://shop{i}.example/b15') for i,price in enumerate(prices)]


def state(): return {'version':1,'offers':{}}


class MarketTests(unittest.TestCase):
    def test_b15_8399_not_a_deal(self):
        deals,skips,_=evaluate(offers(('83.99','59.99','69.99','79.99')),cfg(),state(),NOW)
        self.assertNotIn('0:b15',[d['key'] for d in deals])
        # A moderate premium may be acceptable, but is never a strong price deal.
        self.assertNotIn('0:b15', [d['key'] for d in deals])

    def test_real_discount_has_anchor_and_three_peers(self):
        deals,_,_=evaluate(offers(),cfg(),state(),NOW)
        self.assertEqual(len(deals),1)
        self.assertEqual(len(deals[0]['comparisons']),3)
        self.assertGreaterEqual(deals[0]['confidence'],0.90)
        self.assertIn('keine UVP',market_payload(deals[0])['embeds'][0]['fields'][0]['name'])

    def test_inflated_market_never_raises_anchor(self):
        deals,skips,_=evaluate(offers(('100','150','150','150')),cfg(),state(),NOW)
        self.assertFalse(deals)
        self.assertIn('over_normal_retail',skips)

    def test_no_anchor_stays_silent_even_big_discount(self):
        c=cfg();c['market']['price_references']=[]
        deals,skips,_=evaluate(offers(),c,state(),NOW)
        self.assertFalse(deals);self.assertIn('no_verified_normal_retail_anchor',skips)

    def test_exact_normal_price_not_new_alert(self):
        deals,_,_=evaluate(offers(('79.99',)*4),cfg(),state(),NOW)
        self.assertFalse(deals)

    def test_expired_anchor(self):
        c=cfg();c['market']['price_references'][0]['valid_until']='2026-09-17'
        self.assertFalse(evaluate(offers(),c,state(),NOW)[0])

    def test_languages_editions_packs_games_do_not_mix(self):
        original=offers()[0]; c=cfg(); base=normalize(original,c)[0]['identity']
        for change in [{'title':original['title'].replace(' EN',' DE')},
                       {'title':original['title']+' 1st Edition'},
                       {'description':'36 Booster original versiegelt'},
                       {'title':'Dragon Ball Fusion World FB15 Booster Display EN'}]:
            n,_=normalize(original|change,c)
            self.assertNotEqual(base,n['identity'])

    def test_bad_condition_preorder_unknown_packs_single_variant(self):
        o=offers()[0]
        for change in [{'description':'24 Booster, Unperfektionen an der Verpackung möglich'},
                       {'description':''},
                       {'variant':'1 Booster'}, {'title':o['title'].replace(' EN',' JP')}]:
            self.assertIsNone(normalize(o|change,cfg())[0])

    def test_three_urls_same_retailer_are_one_vote(self):
        c=cfg()
        for s in c['shops'][1:]:s['retailer_group']='same-owner'
        self.assertFalse(evaluate(offers(),c,state(),NOW)[0])

    def test_outlier_reduces_comparison_count(self):
        deals,skips,_=evaluate(offers(('59.99','75','79','299')),cfg(),state(),NOW)
        self.assertFalse(deals);self.assertIn('insufficient_prices_after_outliers',skips)

    def test_missing_and_unknown_not_restock(self):
        s=state();c=cfg();rows=offers(('79.99',)*4)
        evaluate(rows,c,s,NOW);evaluate([],c,s,NOW+3600)
        evaluate([o|{'available':None} for o in rows],c,s,NOW+7200)
        self.assertFalse(evaluate(rows,c,s,NOW+10800)[0])
        self.assertEqual(s['market_history']['0:b15']['episode'],0)

    def test_history_expires_and_is_bounded(self):
        s=state();evaluate(offers(),cfg(),s,NOW)
        self.assertFalse(evaluate([offers()[0]],cfg(),s,NOW+25*3600)[0])
        evaluate([],cfg(),s,NOW+92*86400)
        self.assertFalse(s['market_history'])

    def test_dedup_send_failure_and_no_discovery_bypass(self):
        c=cfg();c['discoveries']['enabled']=True;s=state()
        def adapter(shop,_):return [offers()[int(shop['id'])]] if int(shop['id'])<4 else [],[]
        with patch('tcg_bot.__main__.ADAPTERS',{'shopify':adapter}):
            failed=run(c,s,None,send=lambda _:(_ for _ in ()).throw(RuntimeError()),now=NOW)
            self.assertEqual(failed['sent'],0);self.assertFalse(s.get('market_sent'))
            sent=run(c,s,None,send=lambda _:'msg',now=NOW)
            self.assertEqual(sent['sent'],1);self.assertEqual(sent['discovery_sent'],0)
            repeat=run(c,s,None,send=lambda _:self.fail('duplicate'),now=NOW+86400)
            self.assertEqual(repeat['sent'],0)

    def test_real_scarce_restock_requires_anchor_and_confirmed_outage(self):
        c=cfg();c['market']['min_confidence']=0.90;s=state()
        rows=offers(('75','75','75','75','75'))
        evaluate(rows,c,s,NOW)
        unavailable=[o|{'available':False} for o in rows]
        evaluate(unavailable,c,s,NOW+60)
        for hour in range(1,8):evaluate(unavailable,c,s,NOW+hour*3600)
        # Four recent historical peers => score 0.92, max two currently in stock.
        current=[rows[0]]+unavailable[1:]
        deals,_,_=evaluate(current,c,s,NOW+8*3600)
        self.assertEqual(len(deals),1)
        self.assertIn('Restock',deals[0]['reason'])

    def test_robots_crawl_delay_and_rate(self):
        c=Client()
        with patch.object(c,'raw',return_value='User-agent: *\nCrawl-delay: 3\nRequest-rate: 1/5\nAllow: /'):
            c.check_allowed('https://shop.example/products.json')
        self.assertGreaterEqual(c.host_delay['shop.example'],5)

if __name__=='__main__':unittest.main()

class AdditionalRegressionTests(unittest.TestCase):
    def test_alias_and_padded_set_codes(self):
        c=cfg();o=offers()[0];expected=normalize(o,c)[0]['identity']
        for title in ['Dragon Ball Saiyan Showdown Booster Display EN', 'Dragon Ball BT-015 Booster Display EN']:
            self.assertEqual(normalize(o|{'title':title},c)[0]['identity'],expected)
        self.assertIn('BT20',normalize(o|{'title':'Dragon Ball BT20 Booster Display EN'},c)[0]['identity'])

    def test_de_preferred_among_qualified_offers(self):
        c=cfg();en=offers();de=[o|{'key':o['key']+'de','title':o['title'].replace(' EN',' DE')} for o in en]
        c['market']['price_references'].append(c['market']['price_references'][0]|{'identity':'masters|BT15|unspecified|24|standard|DE'})
        deals,_,_=evaluate(en+de,c,state(),NOW)
        self.assertEqual([d['language'] for d in deals],['DE'])

    def test_legacy_sent_history_is_kept(self):
        s=state();s['offers']['0:b15']={'episode':0,'available':True,'sent':{'at':NOW-100000,'price':'59.99','message_id':'old'}}
        self.assertFalse(evaluate(offers(),cfg(),s,NOW)[0])

    def test_429_cooldown_persists_without_retrying_host(self):
        import urllib.error
        from unittest.mock import MagicMock
        c=Client();error=urllib.error.HTTPError('https://shop.example',429,'',{'Retry-After':'7200'},None)
        opener=MagicMock();opener.open.side_effect=error
        with patch('urllib.request.build_opener',return_value=opener),patch('time.sleep'):
            with self.assertRaises(FetchError):c.raw('https://shop.example/products.json')
            with self.assertRaises(FetchError):c.raw('https://shop.example/other')
        self.assertEqual(opener.open.call_count,1)
        self.assertGreater(c.cooldowns['shop.example'],0)

    def test_html_search_discovers_and_reads_product_details(self):
        from tcg_bot.web_sources import html_catalog
        import json
        shop=cfg()['shops'][0]|{'catalog_urls':['https://shop0.example/search'],'watch_urls':[]}
        product={'@type':'Product','name':'Dragon Ball B15 Display EN','description':'24 Booster',
                 'url':'https://shop0.example/products/b15','offers':{'price':'59.99','priceCurrency':'EUR','availability':'https://schema.org/InStock'}}
        class Fake:
            def text(self,url):
                if url.endswith('/search'):return '<a href="/products/b15">Dragon Ball Booster Display</a>'
                return '<script type="application/ld+json">'+json.dumps(product)+'</script>'
        rows,notes=html_catalog(shop,Fake())
        self.assertEqual(len(rows),1);self.assertFalse(notes)
        self.assertEqual(rows[0]['description'],'24 Booster')
