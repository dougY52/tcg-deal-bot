import unittest
from tcg_bot import retail_research as r, preorders as p, daily_prices as d
from tcg_bot.price_comparison import retail_reference, assess
import test_preorders as fixtures
NOW = fixtures.NOW


class ResearchTests(unittest.TestCase):
    def setUp(self):
        fixtures.Preorders.setUp(self)
        self.cfg['references'] = []
        self.cfg['market']['price_references'] = []
        self.cfg['preorder_watch'].update(price_references=[], user_price_guides=[])
        self.cfg['price_comparison']['products'] = []
        self.benchmark = dict(self.shop, id='benchmark', name='Benchmark', base_url='https://benchmark.test')
        self.cfg['shops'].append(self.benchmark)
        self.cfg['preorder_watch']['trusted_shop_ids'].append('benchmark')
        self.cfg['retail_research'] = dict(enabled=True, max_products=2, max_requests=8,
            budget_seconds=5, retry_seconds=3600, anchor_shop_ids=['benchmark'])
        row, error = p.live(self.offer,self.shop,self.client,NOW)
        self.assertIsNone(error)
        self.target, error = p.identity(dict(row,validated_at=NOW,retailer_group='example.test'),self.cfg)
        self.state['preorder_quotes'] = {self.target['product_key']:self.target}
        self.source = dict(self.offer,shop='benchmark',shop_name='Benchmark',seller='Benchmark',
                           key='benchmark:123',url='https://benchmark.test/products/fb11?variant=123')
        self.state['fast_targets'] = {'source':{'offer':self.source}}

    def test_real_live_price_becomes_separate_retail_anchor_same_run(self):
        self.source['price']='1.00'  # Stale discovery price never becomes evidence.
        result = r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(result['resolved'],1)
        ref = retail_reference(self.target,self.cfg,NOW)
        self.assertEqual(ref['price_eur'],'104.99')
        self.assertEqual(ref['source_shop'],'benchmark')
        self.assertEqual(ref['kind'],'observed_retail')
        self.assertIn('keine Hersteller-UVP',ref['note'])
        self.assertEqual(assess(self.target,self.cfg,self.state,NOW)['code'],'retail_deal')
        self.assertIsNone(retail_reference(self.target,self.cfg,NOW+86400))

    def test_current_quotes_reused_without_duplicate_network_requests(self):
        row,error=p.live(self.source,self.benchmark,self.client,NOW)
        obj,error=p.identity(dict(row,validated_at=NOW,retailer_group='benchmark.test'),self.cfg)
        self.state['preorder_quotes'][obj['product_key']]=obj
        self.client.urls.clear()
        report=r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(report['resolved'],1)
        self.assertEqual(report['requests'],0)
        self.assertEqual(self.client.urls,[])

    def test_reviewed_retail_transfers_across_exact_catalog_identity_not_market_price(self):
        self.cfg['retail_research']['anchor_shop_ids']=[]
        self.cfg['price_comparison']['products']=[dict(game_id=13,product_id=999,category_id=1052,
            catalog_name='Brightness of Hope Booster Box',pattern='FB11',set_code='FB11',
            product_type='display',packs=24,language='EN',pokemon_center=False)]
        self.client.product['description']='24 Booster'
        target,error=p.identity(dict(self.target,gtin='',description='24 Booster',title='Dragon Ball FB11 Display EN Preorder'),self.cfg)
        self.state['preorder_quotes']={target['product_key']:target}
        source,error=p.live(self.source,self.benchmark,self.client,NOW)
        source,error=p.identity(dict(source,validated_at=NOW,retailer_group='benchmark.test'),self.cfg)
        self.state['preorder_quotes'][source['product_key']]=source
        self.assertNotEqual(source['comparison_key'],target['comparison_key'])
        self.cfg['preorder_watch']['price_references']=[dict(comparison_key=source['comparison_key'],
            price_eur='109.99',kind='observed_retail',verified_on='2026-10-01',valid_until='2026-10-31',
            evidence_url=source['url'],note='Checked retail source')]
        self.assertIsNone(retail_reference(target,self.cfg,NOW))
        result=r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(result['resolved'],1)
        self.assertEqual(retail_reference(target,self.cfg,NOW)['price_eur'],'104.99')
        self.assertFalse(r.same_product(target,dict(source,description='18 Booster'),self.cfg,self.state))

    def test_soldout_waitlist_wrong_language_or_scam_not_a_reference(self):
        for kind in ('soldout','waitlist','language','scam','variant'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='soldout': self.client.product['variants'][0]['available']=False
                elif kind=='waitlist': self.client.button='<button>Notify me</button>'
                elif kind=='language': self.client.product['title']=self.client.product['title'].replace(' EN ',' JP ')
                elif kind=='variant': self.client.form_id='456'
                else:self.cfg['preorder_watch']['seller_evidence']['Benchmark']={'red_flags':['serious_scam_signal']}
                self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],0)

    def test_different_pack_variant_not_pooled(self):
        self.source['variant']='18 Booster'
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],0)

    def test_unreviewed_shop_cannot_promote_its_own_price_to_normal_retail(self):
        self.cfg['retail_research']['anchor_shop_ids']=[]
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],0)

    def test_expired_anchor_renews_only_downward_from_live_product(self):
        self.cfg['preorder_watch']['price_references']=[dict(comparison_key=self.target['comparison_key'],
            price_eur='99.99',kind='observed_retail',verified_on='2026-09-01',valid_until='2026-09-02',
            evidence_url=self.source['url'],note='Earlier checked retail')]
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],0)
        self.client.product['variants'][0]['price']=8999
        self.target['validated_at']=NOW+3601
        result=r.run(self.cfg,self.state,self.client,NOW+3601)
        self.assertEqual(result['resolved'],1)
        self.assertEqual(retail_reference(self.target,self.cfg,NOW+3601)['price_eur'],'89.99')

    def test_failure_cached_and_retry_later(self):
        self.client.fail=True
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['attempted'],1)
        self.target['validated_at']=NOW+300
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW+300)['attempted'],0)
        self.target['validated_at']=NOW+3601
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW+3601)['attempted'],1)

    def test_shorter_retry_applies_to_existing_pending_records(self):
        self.state['retail_research']={'checks':{self.target['comparison_key']:{
            'at':NOW-3601,'retry_after':NOW+18000,'status':'NO_VERIFIED_RETAIL_REFERENCE'}}}
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],1)

    def test_search_snippet_price_not_trusted_or_posted(self):
        self.state['fast_targets']={}
        original=self.client.get
        def get(url):
            if '/search/suggest.json?' in url:
                return {'resources':{'results':{'products':[{'handle':'fb11','price':'1','available':True}]}}}
            return original(url)
        self.client.get=get
        self.client.product['variants'][0]['available']=False
        result=r.run(self.cfg,self.state,self.client,NOW)
        self.assertGreater(result['requests'],1)
        self.assertEqual(result['resolved'],0)
        self.assertIsNone(retail_reference(self.target,self.cfg,NOW))

    def test_request_budget_and_restored_client_deadline(self):
        self.cfg['retail_research']['max_requests']=1
        self.client.deadline=123
        result=r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(result['requests'],1)
        self.assertEqual(result['results'][0]['status'],'DEFERRED_BUDGET')
        self.assertEqual(self.client.deadline,123)

    def test_researched_reference_reaches_daily_discord_qualification(self):
        self.cfg['daily_prices'].update(enabled=True,discord_enabled=True,discord_near_retail_only=True,
                                        repeat_daily=True,require_good_retail=True)
        self.assertEqual(d.run(self.cfg,self.state,NOW)['eligible'],0)
        r.run(self.cfg,self.state,self.client,NOW)
        sent=[]
        result=d.run(self.cfg,self.state,NOW,lambda msg:sent.append(msg) or 'receipt')
        self.assertEqual(result['offers_sent'],1)
        self.assertIn('Gute Angebote heute',sent[0]['embeds'][0]['title'])
        self.assertIn('benchmark.test',sent[0]['embeds'][0]['description'])

    def test_cardmarket_is_never_retail_evidence(self):
        self.state['cardmarket_daily']={'6':{'prices':{'1':{'trend':'10'}}}}
        self.cfg['retail_research']['anchor_shop_ids']=[]
        self.assertEqual(r.run(self.cfg,self.state,self.client,NOW)['resolved'],0)

    def test_daily_berlin_boundary_repeats_but_failed_send_is_retryable(self):
        from datetime import datetime
        now=datetime(2026,10,27,23,58,tzinfo=d.BERLIN).timestamp()
        self.target['validated_at']=now
        r.run(self.cfg,self.state,self.client,now)
        self.cfg['daily_prices'].update(enabled=True,discord_enabled=True,discord_near_retail_only=True,
                                        repeat_daily=True,require_good_retail=True)
        def fail(_):raise RuntimeError('simulated Discord error')
        self.assertEqual(d.run(self.cfg,self.state,now,fail)['sent'],0)
        self.assertEqual(d.run(self.cfg,self.state,now,lambda _: 'first')['sent'],1)
        self.target['validated_at']=now+30
        self.assertEqual(d.run(self.cfg,self.state,now+30,lambda _:self.fail('duplicate'))['sent'],0)
        self.target['validated_at']=now+180
        self.assertEqual(d.run(self.cfg,self.state,now+180,lambda _: 'next-day')['sent'],1)
        # A new day does not make stale stock valid.
        self.assertEqual(d.run(self.cfg,self.state,now+86400)['eligible'],0)

    def test_overpriced_or_unreferenced_offer_not_in_good_daily_list(self):
        r.run(self.cfg,self.state,self.client,NOW)
        self.cfg['daily_prices'].update(enabled=True,discord_enabled=True,discord_near_retail_only=True,
                                        repeat_daily=True,require_good_retail=True)
        self.target['price']='115'
        self.assertEqual(d.run(self.cfg,self.state,NOW)['eligible'],0)

    def test_price_reference_lasts_seven_days_but_never_confirms_stock(self):
        self.cfg['retail_research']['reference_ttl_seconds']=604800
        r.run(self.cfg,self.state,self.client,NOW)
        self.assertIsNotNone(retail_reference(self.target,self.cfg,NOW+2*86400))
        self.assertIsNone(retail_reference(self.target,self.cfg,NOW+604800))
        self.cfg['daily_prices'].update(enabled=True,discord_enabled=True,discord_near_retail_only=True,
                                        repeat_daily=True,require_good_retail=True)
        self.assertEqual(d.run(self.cfg,self.state,NOW+86400)['eligible'],0)

    def test_available_cached_benchmark_resolves_even_during_search_cooldown(self):
        row,error=p.live(self.source,self.benchmark,self.client,NOW)
        obj,error=p.identity(dict(row,validated_at=NOW-60),self.cfg)
        self.state['preorder_quotes'][obj['product_key']]=obj
        self.state['retail_research']={'checks':{self.target['comparison_key']:{'at':NOW-10,'retry_after':NOW+7200}}}
        result=r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(result['reused'],1)
        self.assertEqual(result['requests'],0)
        self.assertEqual(retail_reference(self.target,self.cfg,NOW)['checked_at'],NOW-60)

    def test_unavailable_benchmark_price_is_not_a_stock_alert(self):
        self.benchmark['adapter']='mms'
        self.cfg['retail_research']['allow_unavailable_anchor_prices']=True
        source=dict(self.target,shop='benchmark',seller='Benchmark',key='benchmark:123',
            url=self.source['url'],available=False,availability_status='out_of_stock',add_to_cart_available=False)
        self.state['fast_targets']={}
        result=r.run(self.cfg,self.state,self.client,NOW,observations=[(source,'OUT_OF_STOCK')])
        self.assertEqual(result['reused'],1)
        ref=retail_reference(self.target,self.cfg,NOW)
        self.assertIs(ref['source_available'],False)
        self.cfg['daily_prices'].update(enabled=True,discord_enabled=True,discord_near_retail_only=True,
                                        repeat_daily=True,require_good_retail=True)
        sent=[]
        self.assertEqual(d.run(self.cfg,self.state,NOW,lambda x:sent.append(x) or 'receipt')['offers_sent'],1)
        self.assertIn('Referenz dort nicht lieferbar',sent[0]['embeds'][0]['description'])
        self.target['available']=False
        self.target['add_to_cart_available']=False
        self.assertEqual(d.run(self.cfg,self.state,NOW)['eligible'],0)

    def test_ambiguous_or_wrong_currency_listed_price_not_evidence(self):
        self.benchmark['adapter']='mms'
        self.cfg['retail_research']['allow_unavailable_anchor_prices']=True
        source=dict(self.target,shop='benchmark',seller='Benchmark',available=False,
                    availability_status='out_of_stock',add_to_cart_available=False)
        for changes in ({'variant_validated':False},{'currency':'USD'},{'seller':'Marketplace seller'},
                        {'availability_status':'waitlist'},{'live_validated':False}):
            self.assertFalse(r.listed_price(dict(source,**changes),self.benchmark,self.cfg,NOW))

    def test_marketplace_platform_direct_seller_is_retail_but_third_party_is_not(self):
        self.benchmark.update(adapter='mms',marketplace=True,allowed_sellers=['Benchmark'])
        row=dict(self.target,shop='benchmark',seller='Benchmark',seller_verified=True)
        self.assertTrue(r.trusted_live(row,self.benchmark,self.cfg,NOW))
        self.assertFalse(r.trusted_live(dict(row,seller='Third Party'),self.benchmark,self.cfg,NOW))
        self.cfg['retail_research']['allow_unavailable_anchor_prices']=True
        row.update(available=False,availability_status='out_of_stock',add_to_cart_available=False)
        self.assertTrue(r.listed_price(row,self.benchmark,self.cfg,NOW))
        self.assertFalse(r.listed_price(dict(row,seller='Third Party'),self.benchmark,self.cfg,NOW))

    def test_search_query_is_compact_but_matching_is_still_exact(self):
        self.assertEqual(r.search_query(dict(self.target,gtin='')),'FB11 Display')
        self.assertEqual(r.search_query(dict(self.target,gtin='0196214147119')),'196214147119')
        self.assertFalse(r.same_product(dict(self.target,description='24 Booster'),
            dict(self.target,description='18 Booster'),self.cfg,self.state))

    def test_known_targets_rotate_after_failed_research(self):
        self.state['fast_targets']={str(i):{'offer':dict(self.source,key='benchmark:'+str(i),variant_id=str(i))} for i in range(1,6)}
        self.client.fail=True
        r.run(self.cfg,self.state,self.client,NOW)
        self.assertEqual(self.state['retail_research']['checks'][self.target['comparison_key']]['candidate_cursor'],3)
        self.target['validated_at']=NOW+7201
        r.run(self.cfg,self.state,self.client,NOW+7201)
        self.assertEqual(self.state['retail_research']['checks'][self.target['comparison_key']]['candidate_cursor'],6)

    def test_search_details_rank_actual_format_before_recommendations(self):
        from unittest.mock import patch
        shop=dict(self.benchmark,product_link_pattern=r'/products/')
        body=''.join('<a href="/products/'+slug+'">'+label+'</a>' for slug,label in [
            ('tin','Dragon Ball FB11 Brightness of Hope Tin EN'),
            ('wrong','Dragon Ball FB04 Display EN'),
            ('exact','Dragon Ball FB11 Brightness of Hope Display EN')])
        calls=[]
        class Search:
            def text(_,url):calls.append(url);return body if '/search?' in url else '<exact product>'
        with patch('tcg_bot.web_sources.parse_structured',return_value=([{'key':'found'}],[])):
            first=next(r.benchmark_search(shop,self.target,Search()))
        self.assertEqual(first['key'],'found')
        self.assertTrue(calls[-1].endswith('/products/exact'))
        self.assertFalse(any(url.endswith('/products/tin') for url in calls))

