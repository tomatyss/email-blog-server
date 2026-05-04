"""Render email bodies into safe HTML."""

from __future__ import annotations

import html

try:
    import markdown as _markdown  # type: ignore

    _MARKDOWN_AVAILABLE = True
except Exception:
    _markdown = None
    _MARKDOWN_AVAILABLE = False

try:
    import bleach  # type: ignore

    _BLEACH_AVAILABLE = True
except Exception:
    bleach = None
    _BLEACH_AVAILABLE = False


ALLOWED_TAGS = [
    "p",
    "br",
    "hr",
    "pre",
    "code",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def escape_plain_text(text: str) -> str:
    """Escape plain text and preserve line breaks."""
    return html.escape(text).replace("\n", "<br>")


def sanitize_html(html_in: str) -> str:
    """Remove unsafe HTML while preserving a small publishing-oriented subset."""
    if not _BLEACH_AVAILABLE:
        return escape_plain_text(html_in)

    cleaned = bleach.clean(
        html_in,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return bleach.linkify(
        cleaned,
        callbacks=[bleach.callbacks.nofollow, bleach.callbacks.target_blank],
        parse_email=False,
    )


def markdown_to_html(text: str) -> str:
    """Render Markdown into sanitized HTML."""
    if not _MARKDOWN_AVAILABLE:
        return escape_plain_text(text)

    html_out = _markdown.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br", "codehilite"],
        output_format="xhtml1",
    )
    return sanitize_html(html_out)


def render_content_to_html(content: str, content_type: str, render_mode: str = "plain") -> str:
    """Render email content to safe HTML based on the configured mode."""
    ctype = (content_type or "text/plain").lower()
    mode = (render_mode or "plain").lower()

    if mode == "plain":
        return escape_plain_text(content)

    if mode == "markdown":
        if ctype == "text/html":
            return sanitize_html(content)
        return markdown_to_html(content)

    if ctype == "text/html":
        return sanitize_html(content)
    if ctype in ("text/markdown", "text/x-markdown"):
        return markdown_to_html(content)
    return escape_plain_text(content)
