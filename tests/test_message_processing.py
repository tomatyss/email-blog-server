import unittest
from email.message import EmailMessage

from email_blog_messages import extract_email_content, extract_fetch_message_bytes
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

    async def test_fetch_response_extracts_bytearray_payload(self):
        raw = b"Subject: Bytearray\r\n\r\nbody"
        data = [b"1 FETCH (UID 1 BODY[] {25}", bytearray(raw), b")"]

        self.assertEqual(extract_fetch_message_bytes(data), raw)

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

    async def test_sender_allowlist_ignores_display_name(self):
        msg = EmailMessage()
        msg["From"] = '"allowed@example.com" <attacker@example.net>'
        msg["Subject"] = "Spoof"
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
                ("FETCH", "125", "(RFC822.SIZE)"): (
                    "OK",
                    [f"1 (UID 125 RFC822.SIZE {len(raw)})".encode()],
                ),
                ("FETCH", "125", "(BODY.PEEK[])"): (
                    "OK",
                    [b"1 (UID 125 BODY[]", raw, b")"],
                ),
            }
        )

        self.assertIsNone(await server.fetch_email("125"))

    async def test_startup_marks_older_uids_processed(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            enable_imap=False,
        )
        server.imap_client = FakeImapClient(
            {
                ("SEARCH", "ALL"): ("OK", [b" ".join(str(uid).encode() for uid in range(1, 106))]),
            }
        )
        fetched = []

        async def fake_fetch_email(uid):
            fetched.append(uid)
            return {
                "subject": f"Post {uid}",
                "from": "User",
                "date": "Mon, 01 Jan 2024 12:34:56 +0000",
                "content": "Body",
                "content_type": "text/plain",
                "uid": uid,
            }

        server.fetch_email = fake_fetch_email

        await server._fetch_new_uids(limit_to_recent=True)
        await server._fetch_new_uids()

        self.assertEqual(fetched, [str(uid) for uid in range(6, 106)])
        self.assertEqual(server.processed_uids, {str(uid) for uid in range(1, 106)})
        self.assertEqual(len(server.emails_cache), 100)

    async def test_search_uids_uses_protocol_uid_search_when_available(self):
        server = EmailBlogServer(
            imap_server="imap.example.com",
            email_addr="user@example.com",
            password="secret",
            host="127.0.0.1",
            enable_imap=False,
        )
        server.imap_client = FakeImapClient({})
        server.imap_client.protocol = FakeImapProtocol()

        status, data = await server._search_uids()

        self.assertEqual(status, "OK")
        self.assertEqual(data, [b"10 11"])
        self.assertEqual(
            server.imap_client.protocol.calls,
            [("ALL", None, True)],
        )


class FakeImapClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def uid(self, command, uid, parts=None):
        call = (command, uid, parts) if parts else (command, uid)
        self.calls.append(call)
        return self.responses[call]


class FakeImapProtocol:
    def __init__(self):
        self.calls = []

    async def search(self, *criteria, charset="utf-8", by_uid=False):
        self.calls.append((*criteria, charset, by_uid))
        return "OK", [b"10 11"]


if __name__ == "__main__":
    unittest.main()
