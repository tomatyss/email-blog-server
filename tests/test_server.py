import base64
import unittest
from types import SimpleNamespace

from aiohttp import web

from email_blog_server import EmailBlogServer, emails_cache, processed_uids


class EmailBlogServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        emails_cache.clear()
        processed_uids.clear()
        self.server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            blog_title="Test Blog",
            public_url="http://example.com",
            enable_imap=False,
        )

    async def test_health(self):
        resp = await self.server.handle_health(None)
        self.assertEqual(resp.text, "OK")

    async def test_blog_empty(self):
        req = SimpleNamespace(headers={})
        resp = await self.server.handle_blog(req)
        self.assertEqual(resp.content_type, "text/html")
        self.assertIn("Test Blog", resp.text)
        self.assertIn("/feed.xml", resp.text)
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertIn("Strict-Transport-Security", resp.headers)
        self.assertIn("Referrer-Policy", resp.headers)
        self.assertIn("Permissions-Policy", resp.headers)

    async def test_blog_with_email_and_escape(self):
        emails_cache.appendleft(
            {
                "subject": "Hello <b>X</b>",
                "from": "User <script>",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Line1\nLine2<script>",
                "uid": "1",
            }
        )
        req = SimpleNamespace(headers={})
        resp = await self.server.handle_blog(req)
        html = resp.text
        self.assertIn("Hello &lt;b&gt;X&lt;/b&gt;", html)
        self.assertIn("Line1<br>Line2&lt;script&gt;", html)

    async def test_single_email_found_and_not_found(self):
        emails_cache.appendleft(
            {
                "subject": "Post",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Body",
                "uid": "42",
            }
        )
        # Found
        req = SimpleNamespace(match_info={"uid": "42"}, headers={})
        resp = await self.server.handle_single_email(req)
        self.assertEqual(resp.status, 200)
        self.assertIn("Post", resp.text)

        # Not found
        with self.assertRaisesRegex(Exception, "Not Found"):
            req2 = SimpleNamespace(match_info={"uid": "404"}, headers={})
            await self.server.handle_single_email(req2)

    async def test_rss_uses_public_url_and_parses_date(self):
        emails_cache.appendleft(
            {
                "subject": "RSS Item",
                "from": "User",
                "date": "Tue, 02 Jan 2024 08:00:00 +0000",
                "content": "Content",
                "uid": "10",
            }
        )
        req = SimpleNamespace(headers={})
        resp = await self.server.handle_rss(req)
        xml = resp.text
        self.assertIn("application/rss+xml", resp.content_type)
        self.assertIn("<title>RSS Item</title>", xml)
        self.assertIn("http://example.com/email/10", xml)
        self.assertIn("<pubDate>", xml)
        self.assertIn("Strict-Transport-Security", resp.headers)

    async def test_blog_requires_auth_when_configured(self):
        protected = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8082,
            blog_title="Protected Blog",
            public_url="http://example.com",
            enable_imap=False,
            auth_username="admin",
            auth_password="passw0rd",
        )

        with self.assertRaises(web.HTTPUnauthorized):
            req = SimpleNamespace(headers={})
            await protected.handle_blog(req)

        token = base64.b64encode(b"admin:passw0rd").decode("utf-8")
        auth_req = SimpleNamespace(headers={"Authorization": f"Basic {token}"})
        resp = await protected.handle_blog(auth_req)
        self.assertEqual(resp.status, 200)
        self.assertIn("Protected Blog", resp.text)


if __name__ == "__main__":
    unittest.main()
