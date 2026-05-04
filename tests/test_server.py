import unittest
from types import SimpleNamespace
from xml.etree import ElementTree

from aiohttp import web

from email_blog_server import EmailBlogServer


class EmailBlogServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
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
        resp = await self.server.handle_blog(None)
        self.assertEqual(resp.content_type, "text/html")
        self.assertIn("Test Blog", resp.text)
        self.assertIn("/feed.xml", resp.text)
        self.assertIn("Content-Security-Policy", resp.headers)

    async def test_blog_with_email_and_escape(self):
        self.server.emails_cache.appendleft(
            {
                "subject": "Hello <b>X</b>",
                "from": "User <script>",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Line1\nLine2<script>",
                "uid": "1",
            }
        )
        resp = await self.server.handle_blog(None)
        html = resp.text
        self.assertIn("Hello &lt;b&gt;X&lt;/b&gt;", html)
        self.assertIn("Line1<br>Line2&lt;script&gt;", html)

    async def test_single_email_found_and_not_found(self):
        self.server.emails_cache.appendleft(
            {
                "subject": "Post",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Body",
                "uid": "42",
            }
        )
        # Found
        req = SimpleNamespace(match_info={"uid": "42"})
        resp = await self.server.handle_single_email(req)
        self.assertEqual(resp.status, 200)
        self.assertIn("Post", resp.text)

        # Not found
        with self.assertRaisesRegex(Exception, "Not Found"):
            req2 = SimpleNamespace(match_info={"uid": "404"})
            await self.server.handle_single_email(req2)

    async def test_rss_uses_public_url_and_parses_date(self):
        self.server.emails_cache.appendleft(
            {
                "subject": "RSS Item",
                "from": "User",
                "date": "Tue, 02 Jan 2024 08:00:00 +0000",
                "content": "Content",
                "uid": "10",
            }
        )
        resp = await self.server.handle_rss(None)
        xml = resp.text
        self.assertIn("application/rss+xml", resp.content_type)
        self.assertIn("<title>RSS Item</title>", xml)
        self.assertIn("http://example.com/email/10", xml)
        self.assertIn("<pubDate>", xml)
        ElementTree.fromstring(xml.split("\n", 1)[1])

    async def test_rss_escapes_channel_fields(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            blog_title="Bad <title> & Blog",
            public_url="https://example.com/blog?a=1&b=2",
            enable_imap=False,
        )
        xml = (await server.handle_rss(None)).text
        parsed = ElementTree.fromstring(xml.split("\n", 1)[1])
        channel = parsed.find("channel")
        self.assertIsNotNone(channel)
        self.assertEqual(channel.findtext("description"), "Bad <title> & Blog")
        self.assertEqual(channel.findtext("link"), "https://example.com/blog?a=1&b=2")

    async def test_access_token_required_for_content_routes(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            access_token="token",
            enable_imap=False,
        )

        with self.assertRaises(web.HTTPUnauthorized):
            await server.handle_blog(SimpleNamespace(headers={}, query={}))

        req = SimpleNamespace(headers={"Authorization": "Bearer token"}, query={})
        resp = await server.handle_blog(req)
        self.assertEqual(resp.status, 200)

    async def test_public_bind_requires_explicit_opt_in_and_auth(self):
        with self.assertRaisesRegex(ValueError, "ALLOW_PUBLIC_BIND"):
            EmailBlogServer("imap.example.com", "user@example.com", "secret", host="0.0.0.0")

        with self.assertRaisesRegex(ValueError, "BLOG_ACCESS_TOKEN"):
            EmailBlogServer(
                "imap.example.com",
                "user@example.com",
                "secret",
                host="0.0.0.0",
                allow_public_bind=True,
            )

        server = EmailBlogServer(
            "imap.example.com",
            "user@example.com",
            "secret",
            host="0.0.0.0",
            access_token="token",
            allow_public_bind=True,
        )
        self.assertEqual(server.host, "0.0.0.0")

    async def test_start_stop_cleans_only_owned_resources(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=0,
            enable_imap=False,
        )

        await server.start(register_signals=False)
        await server.stop()
        await server.wait_closed()

        self.assertIsNone(server._runner)

    async def test_uid_validity_change_clears_instance_state(self):
        self.server.uid_validity = "1"
        self.server.processed_uids.add("10")
        self.server.emails_cache.appendleft(
            {
                "subject": "Post",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Body",
                "uid": "10",
            }
        )

        with self.assertLogs("email_blog_imap", level="WARNING"):
            self.server._set_uid_validity("2")

        self.assertEqual(self.server.uid_validity, "2")
        self.assertEqual(list(self.server.emails_cache), [])
        self.assertEqual(self.server.processed_uids, set())


if __name__ == "__main__":
    unittest.main()
