"""Manage IMAP connections and message ingestion."""

from __future__ import annotations

import asyncio
import logging
import ssl

from aioimaplib import aioimaplib

from email_blog_messages import (
    extract_fetch_message_bytes,
    parse_email_message,
    parse_id_list,
    parse_rfc822_size,
    parse_uid_validity,
)

logger = logging.getLogger(__name__)


class EmailBlogImapMixin:
    """Provide IMAP UID search, fetch, and IDLE monitoring behavior."""

    async def connect_imap(self) -> bool:
        """Establish a TLS-protected IMAP connection and select the configured mailbox."""
        try:
            ssl_context = ssl.create_default_context()
            logger.info("Creating IMAP client for %s", self.imap_server)
            self.imap_client = aioimaplib.IMAP4_SSL(host=self.imap_server, ssl_context=ssl_context)

            await self.imap_client.wait_hello_from_server()
            await self.imap_client.login(self.email_addr, self.password)
            status, data = await self.imap_client.select(self.mailbox)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox {self.mailbox!r}: {data}")

            self._set_uid_validity(parse_uid_validity(data))
            logger.info("Connected to IMAP mailbox %s", self.mailbox)
            return True
        except Exception as exc:
            logger.error("Failed to connect to IMAP: %s", exc, exc_info=True)
            return False

    async def fetch_email(self, uid: str) -> dict[str, str] | None:
        """Fetch and process a single email by stable IMAP UID."""
        try:
            status, data = await self.imap_client.uid("FETCH", uid, "(RFC822.SIZE)")
            if status != "OK":
                logger.error("Size fetch failed for UID %s: %s", uid, data)
                return None

            message_size = parse_rfc822_size(data)
            if message_size is not None and message_size > self.max_email_bytes:
                logger.warning("Skipping UID %s because size %s exceeds limit", uid, message_size)
                return None

            status, data = await self.imap_client.uid("FETCH", uid, "(BODY.PEEK[])")
        except Exception as exc:
            logger.error("Fetch failed for UID %s: %s", uid, exc)
            return None

        if status != "OK":
            logger.error("Body fetch failed for UID %s: %s", uid, data)
            return None

        msg_bytes = extract_fetch_message_bytes(data)
        if not msg_bytes:
            logger.error("Unexpected FETCH response format for UID %s: %s", uid, data)
            return None
        if len(msg_bytes) > self.max_email_bytes:
            logger.warning("Skipping UID %s because payload exceeds limit", uid)
            return None

        return parse_email_message(
            uid,
            msg_bytes,
            allowed_senders=self.allowed_senders,
            max_body_chars=self.max_body_chars,
        )

    async def monitor_inbox(self) -> None:
        """Monitor the mailbox for new messages using IMAP IDLE."""
        while True:
            try:
                logger.info("Connecting to %s as %s", self.imap_server, self.email_addr)
                if not await self.connect_imap():
                    await asyncio.sleep(10)
                    continue

                await self._fetch_new_uids(limit_to_recent=True)
                await self._idle_until_new_message()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Error in monitor_inbox: %s", exc)
                await asyncio.sleep(30)

    async def _fetch_new_uids(self, limit_to_recent: bool = False) -> None:
        status, data = await self.imap_client.uid("SEARCH", "ALL")
        uids = parse_id_list(data) if status == "OK" else []
        logger.info("Found %s message UIDs", len(uids))

        for uid in uids[-100:] if limit_to_recent else uids:
            if uid in self.processed_uids:
                continue
            email_data = await self.fetch_email(uid)
            self.processed_uids.add(uid)
            if email_data:
                self._append_email(email_data)

    async def _idle_until_new_message(self) -> None:
        await self.imap_client.idle_start()
        try:
            while True:
                response = await self.imap_client.wait_server_push()
                if response is None:
                    logger.info("IDLE connection closed, reconnecting")
                    return
                if any(b"EXISTS" in line for line in response):
                    await self.imap_client.idle_done()
                    await self._fetch_new_uids()
                    await self.imap_client.idle_start()
        finally:
            if self.imap_client and self.imap_client.has_pending_idle():
                await self.imap_client.idle_done()

    def _set_uid_validity(self, uid_validity: str | None) -> None:
        if uid_validity and self.uid_validity and uid_validity != self.uid_validity:
            logger.warning("UIDVALIDITY changed; clearing cached posts and processed UIDs")
            with self._cache_lock:
                self.emails_cache.clear()
            self.processed_uids.clear()
        self.uid_validity = uid_validity or self.uid_validity

    async def _close_imap(self) -> None:
        if not self.imap_client:
            return
        try:
            if self.imap_client.has_pending_idle():
                await self.imap_client.idle_done()
            await self.imap_client.logout()
        except Exception as exc:
            logger.error("Error during IMAP cleanup: %s", exc)
        finally:
            self.imap_client = None
