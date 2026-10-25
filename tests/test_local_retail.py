"""Public-form/status contracts, including local-only stock and selected Qwik offers."""
import copy
import html
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from tcg_bot import local_retail as r, preorders as p, fast_watch as f, cloud_reader
from tcg_bot.__main__ import load_config

PID='61214461';SID='100971990';UUID='33455728-b070-4a6f-9fa1-77e18279e651'
URL='https://www.vedes.com/p/dragon-ball-fb11-display-'+PID+'?subsidiary%5B__identity%5D='+SID
TITLE='Dragon Ball Fusion World FB11 Brightness of Hope Display EN'
REGION=dict(postal_code='65934',latitude=50.1038972,longitude=8.5756857,radius_km=50)
SHOP=dict(id='vedes',name='VEDES',base_url='https://www.vedes.com',adapter='vedes',currency='EUR',max_pages=1,marketplace=True,local_region=REGION)
def body(price=99.99,cart=True,selector=False):
    item=dict(item_id=PID,subsidiary_id=SID,retailer_id=SID,item_name=TITLE,item_url=URL,item_ean='0196214142152',price=price,currency='EUR')
    product={'@type':'Product','sku':PID,'name':TITLE,'description':'24 Boosterpacks','offers':{'@type':'AggregateOffer','lowPrice':1,'highPrice':199}}
    status=URL.replace('/p/','/status/json/')
    return ('<script type="application/ld+json">'+json.dumps(product)+'</script>'+
        '<script data-current-location="'+html.escape(json.dumps(REGION|{'zip':'65934'}),quote=True)+'"></script>'+
        '<form method="post" action="/basketupdate/addtobasket" data-ga4="AddArticleToCart" data-ga4-product="'+html.escape(json.dumps({'items':[item]}),quote=True)+'">'+
        '<h1>'+TITLE+'</h1><input data-ff-cart-event-trigger-receive="'+SID+'_'+UUID+'">'+
        ('<select data-options-uri="'+html.escape(status,quote=True)+'"></select>' if selector else '<span data-subsidiaries-uri="'+html.escape(status,quote=True)+'"></span>')+
        '<input data-form-target="service" value="sendHome"><input data-form-target="service" value="reserve">'+
        '<a data-modal="/modals/showcontentpage?contentPage%5B__identity%5D='+UUID+'&amp;subsidiary%5B__identity%5D='+SID+'">Impressum</a>'+
        '<button '+('' if cart else 'disabled')+'>In den Warenkorb</button></form>')
def status(stock=5,distance=10):
    return [dict(value=SID,productIdentity=UUID,subsidiaryProductStatus=UUID,stock=stock,distance=distance,
        availableServices=dict(sendHome=True,reserve=True),shippingPrice='4,99 €',
        subsidiary=dict(name='Example GmbH',zip='65934',country='Germany',street='Teststraße',streetNumber='1',city='Frankfurt'))]
class Client:
    def __init__(self):self.page=body();self.status=status();self.calls=[]
    def text(self,url):
        self.calls.append(url)
        return 'Example GmbH 65934 Telefon: 123 Geschäftsführer: Test' if '/modals/' in url else self.page
    def get(self,url):self.calls.append(url);return copy.deepcopy(self.status)

def duo_body(quantity=3,disabled=False,price=95.99,live_price=None,product_id='32E0448B'):
    objs=[]
    def base36(n):
        digits='0123456789abcdefghijklmnopqrstuvwxyz';out=''
        while n:out=digits[n%36]+out;n//=36
        return out or '0'
    def put(x):objs.append(x);return base36(len(objs)-1)
    def obj(**kw):return put({k:put(v) for k,v in kw.items()})
    shipping=obj(countryCode='DE',currency='EUR',selfPickup=False,default=True,fee=4.99)
    selected=obj(id='merchant-'+product_id,productId=product_id,urlId='pokemon-box-32E0448B',title='Pokemon Box Deutsch',quantity=quantity,price=price,legalName='Example GmbH',application='merchant',shipping=[shipping])
    signal=put('\x12'+selected);context=put({'selectedOffer':signal})
    state=dict(objs=objs,refs={'cart':context+'!'})
    product={'@type':'Product','sku':'32E0448B','name':'Pokemon Box Deutsch','offers':dict(price=price if live_price is None else live_price,priceCurrency='EUR',availability='https://schema.org/InStock',url='https://www.duo-shop.de/offers/pokemon-box-32E0448B/')}
    return '<script type="application/ld+json">'+json.dumps(product)+'</script><script type="qwik/json">'+json.dumps(state)+'</script><button q:id="cart" class="_add-product-to-cart-btn_1z133_278" '+('disabled' if disabled else '')+'>In den Warenkorb</button>'
DUO=dict(id='duo',name='duo',adapter='duo',currency='EUR',base_url='https://www.duo-shop.de',marketplace=True,seller_evidence={'Example GmbH':{'verified':True,'application_id':'merchant','url':'https://example.test/imprint'}})
DUOURL='https://www.duo-shop.de/offers/pokemon-box-32E0448B/'

class LocalRetailTests(unittest.TestCase):
    def test_live_seller_price_over_aggregate(self):
        rows,error=r.vedes_rows(SHOP,body(),URL,status(),True)
        self.assertIsNone(error);self.assertEqual(rows[0]['price'],'99.99');self.assertEqual(rows[0]['shipping_cost'],'4.99');self.assertTrue(rows[0]['available'])
    def test_local_and_delivery_separate(self):
        rows,_=r.vedes_rows(SHOP,body(),URL,status(),True)
        self.assertEqual({o['channel'] for o in rows},{'online','pickup'});self.assertEqual(len({o['variant_id'] for o in rows}),2)
        self.assertTrue(rows[1]['store_stock_confirmed'])
    def test_wrong_origin_distance_never_local(self):
        for page,states in [(body().replace('65934','60313'),status()),(body(),status(distance=51)),(body(),status(distance=float('nan')))]:
            rows,_=r.vedes_rows(SHOP,page,URL,states,True);self.assertEqual([o['channel'] for o in rows],['online'])
    def test_zero_stock_or_no_cart_no_alert(self):
        for page,states in [(body(),status(0)),(body(cart=False),status()),(body(),status(float('nan')))]:
            rows,_=r.vedes_rows(SHOP,page,URL,states,True);self.assertTrue(all(o['available'] is not True for o in rows))
    def test_wrong_variant_and_seller_rejected(self):
        for field,value in [('value','999999999'),('productIdentity','wrong'),('subsidiaryProductStatus','not-id')]:
            states=status();states[0][field]=value;self.assertEqual(r.vedes_rows(SHOP,body(),URL,states,True)[0],[])
    def test_canonical_page_other_selected_seller_rejected(self):
        self.assertIsNone(r.vedes_data(body().replace(SID,'999999999'),URL))
    def test_reserve_requires_positive_stock(self):
        states=status(0);rows,_=r.vedes_rows(SHOP,body(),URL,states,True);self.assertFalse(rows[1]['store_stock_confirmed'])
    def test_selected_branch_not_generic_shop_stock(self):
        shop=SHOP|{'branches':{'100642830':dict(name='Faix Darmstadt',postal_code='64283',latitude=49.8706922,longitude=8.6533294)}}
        states=status();states[0]['availableServices']['reserve']=False
        states.append(dict(states[0],value='100642830',stock=8,distance=999,availableServices=dict(sendHome=False,reserve=True),subsidiary=dict(name='Faix Darmstadt',zip='64283',country='Germany')))
        rows,_=r.vedes_rows(shop,body(selector=True),URL,states,True)
        local=next(o for o in rows if o.get('store_id')=='100642830')
        self.assertTrue(local['store_stock_confirmed']);self.assertLess(local['distance_km'],50)
        states[1]['subsidiary']['zip']='99999'
        self.assertFalse(any(o.get('store_id')=='100642830' for o in r.vedes_rows(shop,body(selector=True),URL,states,True)[0]))
    def test_unknown_language_not_shop_locale(self):
        o=dict(title='Pokemon Dunkelnacht Box',variant='',description='Eine tolle deutsche Webseite',product_id='x')
        self.assertEqual(r.language(r.evidence_language(o,{})),'UNKNOWN')
    def test_exact_description_language(self):
        o=dict(title='Pokemon Box',variant='',description='Pokemon Box (Deutsch) 4 Packs')
        self.assertEqual(r.language(r.evidence_language(o,{})),'DE')
    def test_duo_exact_selected_cart_binding(self):
        rows,error=r.duo_rows(DUO,duo_body(),DUOURL);self.assertIsNone(error);self.assertTrue(rows[0]['available']);self.assertTrue(rows[0]['seller_verified']);self.assertEqual(rows[0]['price'],'95.99')
    def test_duo_disabled_zero_wrong_variant_or_stale_price(self):
        for changes in [dict(disabled=True),dict(quantity=0),dict(live_price=79.99),dict(product_id='BAD')]:
            rows,_=r.duo_rows(DUO,duo_body(**changes),DUOURL);self.assertFalse(any(o['available'] for o in rows))
    def test_hidden_parent_and_waitlist_never_confirm(self):
        self.assertEqual(r.vedes_rows(SHOP,'<div hidden>'+body()+'</div>',URL,status(),True)[0],[])
        rows,_=r.vedes_rows(SHOP,body().replace('</form>','Waitlist</form>'),URL,status(),True)
        self.assertFalse(any(o['available'] for o in rows))
        rows,_=r.duo_rows(DUO,duo_body().replace('<button','<fieldset disabled><button').replace('</button>','</button></fieldset>'),DUOURL)
        self.assertFalse(any(o['available'] for o in rows))
    def test_duo_unknown_seller_not_trusted(self):
        rows,_=r.duo_rows(DUO|{'seller_evidence':{}},duo_body(),DUOURL);self.assertFalse(rows[0]['seller_verified'])
    def test_catalog_price_is_only_discovery_and_not_invented(self):
        class Catalog:
            def text(self,url):return '<a href="/offers/pokemon-box-32E0448B/">Pokemon Kollektion Deutsch 95,99 €</a>'
        rows,_=r.scan(DUO|{'catalog_urls':['https://www.duo-shop.de/produkte/spielzeug/sammelkarten/']},Catalog())
        self.assertEqual(rows[0]['price'],'95.99');self.assertIsNone(rows[0]['available']);self.assertTrue(rows[0]['discovery_only'])
    def test_catalog_does_not_replace_validated_variant(self):
        cfg=load_config('config/config.json');row=r.duo_rows(DUO,duo_body(),DUOURL)[0][0];state={}
        hint=dict(row,key='hint',variant_id='discovery-'+row['product_id'],seller=None,seller_id=None,discovery_only=True,available=None)
        f.remember([hint],cfg,state,1);f.remember([row],cfg,state,2);f.remember([hint],cfg,state,3)
        self.assertEqual(len(state['fast_targets']),1)
        self.assertFalse(next(iter(state['fast_targets'].values()))['offer'].get('discovery_only'))
    def test_cloud_allowlist(self):
        for url in [URL,URL.replace('/p/','/status/json/'),DUOURL,'https://www.faix.de/faix-online-shop-darmstadt/c/impressum']:self.assertTrue(cloud_reader.target_allowed(url),url)
        for url in [URL+'&token=x',URL.replace(SID,'oops'),'https://www.duo-shop.de/account','https://www.vedes.com/basketupdate/addtobasket','https://www.faix.de/other/status/json/x?subsidiary%5B__identity%5D='+SID]:self.assertFalse(cloud_reader.target_allowed(url),url)
    def test_budget_respected_for_fresh_phase_too(self):
        cfg=load_config('config/config.json');o=r.duo_rows(DUO,duo_body(),DUOURL)[0][0]
        state={'fast_targets':{o['key']:{'offer':o}},'retailer_live_checks':{'duo':10000}}
        self.assertEqual(f.select(cfg,state,10001),[]);self.assertEqual(len(f.select(cfg,state,15400)),1)
    def test_integrated_dedupe_restock_and_live_price(self):
        cfg=load_config('config/config.json');cfg['shops']=[SHOP];cfg['preorder_watch']['trusted_shop_ids']=['vedes'];cfg['_fast_lane']=True
        client=Client();o=r.vedes_live(SHOP,client,URL)[0][0];cfg['_fast_keys']=[o['key']];cfg['_fast_groups']={o['key']:0}
        state={};now=1791021600
        first=p.scan([o],cfg,state,client,now)[1];self.assertEqual(len(first),1)
        p.delivered(state,first[0],now,'synthetic-message')
        self.assertEqual(p.scan([o],cfg,state,client,now+300)[1],[])
        client.status=status(0);self.assertEqual(p.scan([o],cfg,state,client,now+600)[1],[])
        client.status=status();client.page=body(price=89.99)
        deals=p.scan([o],cfg,state,client,now+900)[1];self.assertEqual(len(deals),1);self.assertEqual(deals[0]['price'],'89.99');self.assertGreater(deals[0]['episode'],0)
    def test_local_payload_not_delivery_or_preorder(self):
        row=r.vedes_rows(SHOP,body(),URL,status(),True)[0][1]
        row.update(language='EN',pricing={'strong':False,'why':'Geprüfter Retailpreis'})
        msg=f.payload(row)['embeds'][0];self.assertIn('FILIALBESTAND',msg['title']);self.assertNotIn('Versand:',msg['description']);self.assertIn('Reservierungsbestätigung',msg['description'])
