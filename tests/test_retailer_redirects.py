import io
import unittest
import urllib.error
from unittest.mock import patch
from tcg_bot.http import Client, FetchError

class Response(io.BytesIO):
    def __init__(self,url,text):
        super().__init__(text.encode())
        self.url=url

class RedirectTests(unittest.TestCase):
    def test_relocated_robots_is_read_and_rules_enforced(self):
        c=Client(0)
        def request(req,**kwargs):
            if req.full_url=="https://example.test/robots.txt":
                raise urllib.error.HTTPError(req.full_url,301,"",{"Location":"/de/robots.txt"},None)
            return Response(req.full_url,"User-agent: *\nDisallow: /private\n")
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect=request
            c.check_allowed("https://example.test/public")
            with self.assertRaises(FetchError):
                c.check_allowed("https://example.test/private")
    def test_same_host_product_redirect_rechecks_robots(self):
        c=Client(0); c.robots["https://example.test"]="User-agent: *\nDisallow: /private\n"
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect=urllib.error.HTTPError("https://example.test/old",301,"",{"Location":"/private"},None)
            with self.assertRaisesRegex(FetchError,"robots"):
                c.text("https://example.test/old")
            self.assertEqual(opener.return_value.open.call_count,1)
    def test_cross_host_and_downgrade_blocked(self):
        for target in ["https://evil.test/x","http://example.test/x","https://user:pass@example.test/x"]:
            c=Client(0);c.robots["https://example.test"]="User-agent: *\nAllow: /"
            with patch("urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect=urllib.error.HTTPError("https://example.test/old",301,"",{"Location":target},None)
                with self.assertRaises(FetchError): c.text("https://example.test/old")
    def test_allowed_canonical_redirect(self):
        c=Client(0);c.robots["https://example.test"]="User-agent: *\nAllow: /"
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect=[
                urllib.error.HTTPError("https://example.test/old",301,"",{"Location":"/new"},None),
                Response("https://example.test/new","product")]
            self.assertEqual(c.text("https://example.test/old"),"product")
    def test_redirect_loop_bounded(self):
        c=Client(0);c.robots["https://example.test"]="User-agent: *\nAllow: /"
        with patch("urllib.request.build_opener") as opener:
            def request(req,**kwargs):
                raise urllib.error.HTTPError(req.full_url,302,"",{"Location":"/b" if req.full_url.endswith("/a") else "/a"},None)
            opener.return_value.open.side_effect=request
            with self.assertRaises(FetchError): c.text("https://example.test/a")
            self.assertLessEqual(opener.return_value.open.call_count,4)
