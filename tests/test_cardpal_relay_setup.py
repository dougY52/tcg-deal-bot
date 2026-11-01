import contextlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from scripts import configure_cardpal_relay as setup


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SetupTests(unittest.TestCase):
    @patch.object(setup, 'github_token', return_value='synthetic-job-token')
    @patch.object(setup, 'build_opener')
    def test_fixed_owner_origin_and_redacted_status(self, opener, token):
        opener.return_value.open.return_value = Reply(json.dumps({
            'configured': True, 'status': 'stream_connected', 'password': 'PRIVATE',
            'webhook': 'PRIVATE', 'browser_minutes_used': 0,
        }).encode())
        result = setup.request('/cardpal/status')
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, setup.ORIGIN + '/cardpal/status')
        self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-job-token')
        self.assertEqual(request.get_header('User-agent'), 'TCGRetailWatch/1.0')
        self.assertNotIn('PRIVATE', json.dumps(result))

    @patch.object(setup, 'github_token', return_value='synthetic-job-token')
    @patch.object(setup, 'build_opener')
    def test_http_error_does_not_print_url_or_arbitrary_body(self, opener, token):
        for body in (b'PRIVATE', b'{"error":"https://private/SECRET"}', b'{"error":"INVALID_CONFIGURATION"}'):
            opener.return_value.open.side_effect = HTTPError('https://private/SECRET', 400, 'PRIVATE', {}, io.BytesIO(body))
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError):
                setup.request('/cardpal/configure', {'password': 'PRIVATE'})
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertNotIn('SECRET', output.getvalue())
            self.assertIn('400', output.getvalue())

    @patch.dict(setup.os.environ, {'CARDPAL_EMAIL': '', 'CARDPAL_PASSWORD': '', 'DISCORD_WEBHOOK_URL': ''})
    @patch.object(setup, 'request')
    def test_missing_secret_never_attempts_configure(self, request):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.main(), 2)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
