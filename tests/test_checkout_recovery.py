import unittest
from unittest.mock import Mock
import test_preorders as fixtures
from tcg_bot import preorders as p


class CheckoutRecovery(unittest.TestCase):
    setUp = fixtures.Preorders.setUp
    scan = fixtures.Preorders.scan
    rejected = fixtures.Preorders.rejected

    def test_einkaufswagen_label(self):
        self.client.button = '<button>In den Einkaufswagen legen</button>'
        self.assertEqual(len(self.scan()[1]), 1)

    def test_external_form_owner_button(self):
        self.client.text = Mock(return_value='''<script>Shopify.currency={"active":"EUR"}</script>
            <form id="exact" method="post" action="/cart/add"><input name="id" value="123"></form>
            <button type="submit" form="exact">In den Warenkorb</button>''')
        self.assertEqual(len(self.scan()[1]), 1)

    def test_wrong_form_owner_cannot_confirm_variant(self):
        self.client.text = Mock(return_value='''<script>Shopify.currency={"active":"EUR"}</script>
            <form id="exact" method="post" action="/cart/add"><input name="id" value="123"></form>
            <button type="submit" form="another">In den Warenkorb</button>''')
        self.rejected('NO_CHECKOUT')

    def test_disabled_id_still_rejected_without_browser(self):
        self.client.text = Mock(return_value='''<script>Shopify.currency={"active":"EUR"}</script>
            <form method="post" action="/cart/add"><input disabled name="id" value="123"><button>In den Warenkorb</button></form>''')
        self.rejected('AMBIGUOUS_VARIANT')

    def test_rendered_variant_required_and_render_failure_closed(self):
        html = self.client.text('https://example.test')
        self.shop['browser_checkout'] = True
        self.client.render_product = Mock(return_value=html)
        self.assertEqual(len(self.scan()[1]), 1)
        self.client.render_product.assert_called_once()
        self.client.render_product.side_effect = TimeoutError()
        self.rejected('LIVE_CHECK_FAILED_TimeoutError')

    def test_rendered_wrong_variant_rejected(self):
        self.shop['browser_checkout'] = True
        self.client.render_product = Mock(return_value=self.client.text('').replace('value="123"','value="456"'))
        self.rejected('AMBIGUOUS_VARIANT')
