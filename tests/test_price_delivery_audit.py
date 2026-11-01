import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import URLError
from scripts.audit_price_delivery import read_receipt, delivery_record, receipt_ids


class ReceiptAudit(unittest.TestCase):
    def test_only_reads_recorded_message_and_redacts_unneeded_data(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps({'id':'123456789012345678',
            'embeds':[{'title':'Guter Retailpreis', 'fields':[{'name':'Cardmarket',
            'value':'Trend **87.86 €**'}]}]}).encode())
        result = read_receipt('https://discord.com/api/webhooks/123/test-secret',
                              '123456789012345678',opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.method,'GET')
        self.assertIsNone(request.data)
        self.assertTrue(request.full_url.endswith('/messages/123456789012345678'))
        self.assertEqual(result['status'],'confirmed')
        self.assertTrue(result['has_cardmarket_text'])
        self.assertNotIn('test-secret',json.dumps(result))

    def test_bad_ids_and_urls_do_not_request(self):
        opener=Mock()
        for secret, mid in [('https://example.com/secret','123456789012345678'),
                            ('https://discord.com/api/webhooks/123/test-secret','../other')]:
            self.assertNotEqual(read_receipt(secret,mid,opener)['status'],'confirmed')
        opener.open.assert_not_called()

    def test_exception_does_not_leak_secret(self):
        opener=Mock()
        opener.open.side_effect=URLError('https://discord.com/api/webhooks/123/test-secret')
        result=read_receipt('https://discord.com/api/webhooks/123/test-secret','123456789012345678',opener)
        self.assertEqual(result['status'],'read_error')
        self.assertNotIn('test-secret',json.dumps(result))

    def test_new_daily_receipt_preferred_over_old_instant_alert(self):
        state={'preorder_products':{'en':{'last_alert':{'at':1,'message_id':'old'}}},
               'daily_price_delivery':{'products':{'en':{'at':10,'message_id':'today'}}},
               'near_retail_discord_sent':{'en':{'at':9,'message_id':'previous'}}}
        self.assertEqual(delivery_record(state,'en')['message_id'],'today')
        self.assertEqual(delivery_record(state,'de'),{})

    def test_receipts_cover_each_english_family_not_only_newest_overall(self):
        products=[dict(franchise=f,language='EN',message_id=f,delivered_at=1)
                  for f in ('Pokémon','Dragon Ball','One Piece')]
        products.append(dict(franchise='Pokémon',language='DE',message_id='de-only',delivered_at=100))
        self.assertEqual(receipt_ids(products),['Pokémon','Dragon Ball','One Piece'])

    def test_out_of_stock_reference_does_not_become_stock_evidence(self):
        from tcg_bot.__main__ import load_config
        from tcg_bot import preorders, price_comparison
        from datetime import datetime, timezone
        cfg=load_config('config/config.json')
        offer={'title':'Pokémon Mega Zygarde ex Premium Collection Englisch',
               'variant':'Default Title','description':'8 Booster','gtin':'196214135017',
               'shop':'play-maniac','variant_id':'57773110526216','price':'48.99','currency':'EUR'}
        en,error=preorders.identity(offer,cfg)
        self.assertIsNone(error)
        now=datetime(2026,11,1,tzinfo=timezone.utc).timestamp()
        result=price_comparison.assess(en,cfg,{},now)
        self.assertEqual(result['code'],'retail_deal')
        self.assertIs(result['retail']['source_available'],False)
        self.assertNotIn('available',en)
        de,_=preorders.identity(dict(offer,title=offer['title'].replace('Englisch','Deutsch')),cfg)
        self.assertIsNone(price_comparison.assess(de,cfg,{},now)['retail'])
