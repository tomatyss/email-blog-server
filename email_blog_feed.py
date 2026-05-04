"""Build RSS output for the email blog."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import formatdate, parsedate_to_datetime
from xml.etree import ElementTree


def build_rss(emails: list[dict[str, str]], blog_title: str, base_url: str) -> str:
    """Build an XML-safe RSS 2.0 feed for cached email posts."""
    root = ElementTree.Element("rss", version="2.0")
    channel = ElementTree.SubElement(root, "channel")
    _add_text(channel, "title", blog_title)
    _add_text(channel, "link", base_url)
    _add_text(channel, "description", blog_title)
    _add_text(channel, "language", "en-us")
    _add_text(channel, "lastBuildDate", formatdate(usegmt=True))

    for email_data in emails:
        item = ElementTree.SubElement(channel, "item")
        post_url = f"{base_url}/email/{email_data['uid']}"
        _add_text(item, "title", email_data["subject"])
        _add_text(item, "link", post_url)
        _add_text(item, "guid", post_url)
        _add_text(item, "description", email_data["content"])
        _add_text(item, "author", email_data["from"])
        _add_text(item, "pubDate", _rss_date(email_data.get("date", "")))

    xml_body = ElementTree.tostring(root, encoding="unicode", short_empty_elements=False)
    return f'<?xml version="1.0" encoding="UTF-8" ?>\n{xml_body}'


def _add_text(parent: ElementTree.Element, tag: str, text: str) -> None:
    child = ElementTree.SubElement(parent, tag)
    child.text = text or ""


def _rss_date(date_text: str) -> str:
    try:
        dt = parsedate_to_datetime(date_text)
        if dt is None:
            raise ValueError("parsedate_to_datetime returned None")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        timestamp = float(dt.timestamp())
    except Exception:
        timestamp = float(datetime.now(tz=UTC).timestamp())
    return formatdate(timestamp, usegmt=True)
