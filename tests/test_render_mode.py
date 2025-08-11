import unittest

from email_blog_server import EmailBlogServer, emails_cache, processed_uids


class RenderModeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        emails_cache.clear()
        processed_uids.clear()

    async def test_auto_prefers_html_and_blocks_script(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            blog_title="Test Blog",
            public_url="http://example.com",
            enable_imap=False,
            render_mode="auto",
        )

        emails_cache.appendleft(
            {
                "subject": "HTML Email",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "<b>ok</b><script>alert(1)</script>",
                "content_type": "text/html",
                "uid": "2",
            }
        )
        resp = await server.handle_blog(None)
        html = resp.text
        # Always blocks script content (sanitized or escaped)
        self.assertNotIn("<script>", html)
        self.assertIn("ok", html)
        # Accept either sanitized <b> or escaped &lt;b&gt;
        self.assertTrue("<b>ok</b>" in html or "&lt;b&gt;ok&lt;/b&gt;" in html)

    async def test_markdown_mode_blocks_script(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            blog_title="Test Blog",
            public_url="http://example.com",
            enable_imap=False,
            render_mode="markdown",
        )

        emails_cache.appendleft(
            {
                "subject": "MD Email",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "**bold**\n<script>x</script>",
                "content_type": "text/markdown",
                "uid": "3",
            }
        )
        resp = await server.handle_blog(None)
        html = resp.text
        self.assertNotIn("<script>", html)
        self.assertIn("bold", html)

    async def test_generate_content_type_defaults_plain(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            port=8081,
            blog_title="Test Blog",
            public_url="http://example.com",
            enable_imap=False,
        )
        # Old entries without content_type should still render safely
        emails_cache.appendleft(
            {
                "subject": "Plain Email",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "line1\nline2",
                "uid": "4",
            }
        )
        resp = await server.handle_blog(None)
        html = resp.text
        self.assertIn("line1<br>line2", html)


if __name__ == "__main__":
    unittest.main()

