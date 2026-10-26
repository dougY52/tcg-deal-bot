import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import URLError
from scripts.audit_price_delivery import read_receipt


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
