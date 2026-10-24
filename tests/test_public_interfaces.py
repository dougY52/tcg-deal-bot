import json
from pathlib import Path
import unittest
from scripts.audit_public_interfaces import endpoint, page_info

class PublicInterfaces(unittest.TestCase):
    def test_endpoint_does_not_record_query_values_userinfo_or_fragment(self):
        data=endpoint('https://name:secret@shop.test/api?token=private&operationName=Catalog#secret')
        self.assertEqual(data,{'host':'shop.test','path':'/api','query_keys':['operationName','token']})
        self.assertNotIn('private',json.dumps(data))
        self.assertNotIn('secret',json.dumps(data))

    def test_opaque_path_ids_redacted(self):
        self.assertEqual(endpoint('https://shop.test/a/a953d7fa-a07f-4fac-a9d4-31b2e9cee6e4')['path'],'/a/:opaque')

    def test_page_and_search_hints_do_not_confirm_inventory(self):
        body='<h1>Pokémon Sammelkarten Neuheiten</h1><a href="/products/pokemon">Pokémon Booster Display Deutsch</a>'
        row=page_info(body,'https://shop.test/')
        self.assertFalse(row['inventory_confirmed'])
        self.assertEqual(len(row['candidate_links']),1)
        self.assertEqual(page_info('<h1>Access denied</h1>','https://shop.test/')['status'],'challenge')

    def test_captured_queries_are_read_only_public_catalog_operations(self):
        for row in json.loads(Path('config/public-mms-queries.json').read_text()):
            q=row['query']
            self.assertIn(q['operation'],('CategoryV4','SearchV4'))
            self.assertFalse(set(q['headers']) & {'authorization','cookie','x-api-key'})
            self.assertEqual(set(q['extensions']),{'persistedQuery','pwa'})
