"""Parse IMAP fetch responses and extract publishable email bodies."""

from __future__ import annotations

import email
import re
from collections.abc import Iterable
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses

MARKDOWN_TYPES = {"text/markdown", "text/x-markdown"}
TEXT_TYPES = {"text/html", *MARKDOWN_TYPES, "text/plain"}
TRUNCATION_NOTICE = "\n\n[Message truncated at {limit} characters.]"


def safe_decode(header: str | None) -> str:
    """Decode an RFC 2047 email header without raising on bad input."""
    if not header:
        return ""

    parts = []
    for content, charset in decode_header(header):
        if isinstance(content, bytes):
            try:
                parts.append(content.decode(charset or "utf-8", errors="replace"))
            except Exception:
                parts.append(content.decode("utf-8", errors="replace"))
        else:
            parts.append(str(content))
    return " ".join(parts)


def sender_allowed(from_header: str, allowed_senders: Iterable[str] | None) -> bool:
    """Return whether a decoded From header matches the optional sender allowlist."""
    allowed = {sender.strip().lower() for sender in allowed_senders or [] if sender.strip()}
    if not allowed:
        return True

    addresses = {addr.lower() for _, addr in getaddresses([from_header]) if addr}
    return bool(addresses & allowed)


def extract_email_content(
    msg: Message,
    max_body_chars: int | None = None,
) -> tuple[str, str]:
    """Extract the best inline text body and its MIME type from a message."""
    preferred: dict[str, str | None] = {
        "text/html": None,
        "text/markdown": None,
        "text/plain": None,
    }

    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue

        ctype = part.get_content_type() or "text/plain"
        if ctype not in TEXT_TYPES:
            continue

        body = _decode_text_part(part)
        if body is None:
            continue

        if ctype in MARKDOWN_TYPES:
            ctype = "text/markdown"
        if preferred[ctype] is None:
            preferred[ctype] = _limit_text(body, max_body_chars)

    for ctype in ("text/html", "text/markdown", "text/plain"):
        if preferred[ctype] is not None:
            return preferred[ctype] or "", ctype

    return "Could not decode email content", "text/plain"


def parse_email_message(
    uid: str,
    msg_bytes: bytes,
    allowed_senders: Iterable[str] | None = None,
    max_body_chars: int | None = None,
) -> dict[str, str] | None:
    """Parse a raw email message into the internal blog-post dictionary."""
    msg = email.message_from_bytes(msg_bytes)
    subject = safe_decode(msg["subject"])
    from_addr = safe_decode(msg["from"])

    if not sender_allowed(from_addr, allowed_senders):
        return None

    content, content_type = extract_email_content(msg, max_body_chars=max_body_chars)
    return {
        "subject": subject,
        "from": from_addr,
        "date": safe_decode(msg["date"]),
        "content": content,
        "content_type": content_type,
        "uid": str(uid),
        "message_id": safe_decode(msg["message-id"]),
    }


def parse_rfc822_size(data: object) -> int | None:
    """Parse RFC822.SIZE from an IMAP FETCH response."""
    for item in _flatten_response_items(data):
        text = item.decode("ascii", errors="ignore") if isinstance(item, bytes) else str(item)
        match = re.search(r"RFC822\.SIZE\s+(\d+)", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def parse_uid_validity(data: object) -> str | None:
    """Parse UIDVALIDITY from an IMAP SELECT response."""
    for item in _flatten_response_items(data):
        text = item.decode("ascii", errors="ignore") if isinstance(item, bytes) else str(item)
        match = re.search(r"UIDVALIDITY\s+(\d+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_fetch_message_bytes(data: object) -> bytes | None:
    """Extract raw message bytes from common aioimaplib FETCH response shapes."""
    candidates = [
        bytes(item)
        for item in _flatten_response_items(data)
        if isinstance(item, (bytes, bytearray))
    ]
    message_candidates = [
        item
        for item in candidates
        if (b"\r\n\r\n" in item or b"\n\n" in item) and not item.lstrip().startswith(b"* ")
    ]
    if message_candidates:
        return max(message_candidates, key=len)

    non_metadata = [
        item
        for item in candidates
        if not item.lstrip().startswith((b"* ", b")")) and b"FETCH" not in item[:80].upper()
    ]
    return max(non_metadata, key=len) if non_metadata else None


def parse_id_list(data: object) -> list[str]:
    """Parse a SEARCH response containing space-separated IDs."""
    for item in _flatten_response_items(data):
        if isinstance(item, bytes):
            text = item.decode("ascii", errors="ignore").strip()
        else:
            text = str(item).strip()
        if text and all(part.isdigit() for part in text.split()):
            return text.split()
    return []


def _decode_text_part(part: Message) -> str | None:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw_payload = part.get_payload()
        return raw_payload if isinstance(raw_payload, str) else None

    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _limit_text(text: str, limit: int | None) -> str:
    if limit is None or limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_NOTICE.format(limit=limit)


def _flatten_response_items(data: object) -> list[object]:
    if isinstance(data, tuple):
        return list(data)
    if not isinstance(data, list):
        return [data]

    flattened = []
    for item in data:
        if isinstance(item, tuple):
            flattened.extend(item)
        else:
            flattened.append(item)
    return flattened
