import unittest
from email.message import EmailMessage

from email_blog_messages import extract_email_content
from email_blog_server import EmailBlogServer


class MessageProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_attachment_only_message_is_not_published_as_body(self):
        msg = EmailMessage()
        msg["From"] = "User <user@example.com>"
        msg["Subject"] = "Attachment"
        msg.make_mixed()
        attachment = EmailMessage()
        attachment.set_content("secret attachment only")
        attachment.add_header("Content-Disposition", "attachment", filename="secret.txt")
        msg.attach(attachment)

        content, content_type = extract_email_content(msg)

        self.assertEqual(content_type, "text/plain")
        self.assertEqual(content, "Could not decode email content")

    async def test_inline_body_wins_over_text_attachment(self):
        msg = EmailMessage()
        msg["From"] = "User <user@example.com>"
        msg["Subject"] = "Body"
        msg.set_content("public body")
        msg.add_attachment("secret attachment", subtype="plain", filename="secret.txt")

        content, content_type = extract_email_content(msg)

        self.assertEqual(content_type, "text/plain")
        self.assertEqual(content, "public body\n")

    async def test_fetch_email_uses_uid_fetch_and_size_limit(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            enable_imap=False,
            max_email_bytes=20,
        )
        server.imap_client = FakeImapClient(
            {
                ("FETCH", "123", "(RFC822.SIZE)"): ("OK", [b"1 (UID 123 RFC822.SIZE 100)"]),
            }
        )

        with self.assertLogs("email_blog_imap", level="WARNING"):
            email_data = await server.fetch_email("123")

        self.assertIsNone(email_data)
        self.assertEqual(server.imap_client.calls, [("FETCH", "123", "(RFC822.SIZE)")])

    async def test_fetch_email_stores_stable_uid(self):
        msg = EmailMessage()
        msg["From"] = "Allowed <allowed@example.com>"
        msg["Subject"] = "UID Post"
        msg["Date"] = "Mon, 01 Jan 2024 12:34:56 +0000"
        msg.set_content("hello")
        raw = msg.as_bytes()

        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            enable_imap=False,
            allowed_senders=["allowed@example.com"],
        )
        server.imap_client = FakeImapClient(
            {
                ("FETCH", "123", "(RFC822.SIZE)"): (
                    "OK",
                    [f"1 (UID 123 RFC822.SIZE {len(raw)})".encode()],
                ),
                ("FETCH", "123", "(BODY.PEEK[])"): (
                    "OK",
                    [b"1 (UID 123 BODY[]", raw, b")"],
                ),
            }
        )

        email_data = await server.fetch_email("123")

        self.assertIsNotNone(email_data)
        self.assertEqual(email_data["uid"], "123")
        self.assertEqual(email_data["content"], "hello\n")

    async def test_sender_allowlist_skips_untrusted_sender(self):
        msg = EmailMessage()
        msg["From"] = "Other <other@example.com>"
        msg["Subject"] = "Skip"
        msg.set_content("hello")
        raw = msg.as_bytes()

        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            enable_imap=False,
            allowed_senders=["allowed@example.com"],
        )
        server.imap_client = FakeImapClient(
            {
                ("FETCH", "124", "(RFC822.SIZE)"): (
                    "OK",
                    [f"1 (UID 124 RFC822.SIZE {len(raw)})".encode()],
                ),
                ("FETCH", "124", "(BODY.PEEK[])"): (
                    "OK",
                    [b"1 (UID 124 BODY[]", raw, b")"],
                ),
            }
        )

        self.assertIsNone(await server.fetch_email("124"))


class FakeImapClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def uid(self, command, uid, parts=None):
        call = (command, uid, parts) if parts else (command, uid)
        self.calls.append(call)
        return self.responses[call]


if __name__ == "__main__":
    unittest.main()
