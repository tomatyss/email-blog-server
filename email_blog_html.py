"""Generate HTML pages for the email blog."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from email_blog_rendering import render_content_to_html


def build_blog_html(
    template_path: Path,
    blog_title: str,
    emails: list[dict[str, str]],
    render_mode: str,
    single_email: dict[str, str] | None = None,
) -> str:
    """Render the blog index or single-post HTML page."""
    email_content = (
        build_email_html(single_email, render_mode)
        if single_email
        else "".join(
            build_email_html(email_data, render_mode, linked=True) for email_data in emails
        )
    )

    template = template_path.read_text()
    replacements = {
        "{title}": html.escape(blog_title),
        "{last_updated}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "{email_content}": email_content,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def build_email_html(
    email_data: dict[str, str],
    render_mode: str,
    linked: bool = False,
) -> str:
    """Render a single email post as an HTML article."""
    title = html.escape(email_data["subject"])
    if linked:
        uid = quote(str(email_data["uid"]), safe="")
        title = f'<a href="/email/{html.escape(uid)}">{title}</a>'

    back_link = "" if linked else '<p><a href="/">&larr; Back to all emails</a></p>'
    return f"""
        <article>
            <h2>{title}</h2>
            <div class="meta">
                <p><strong>From:</strong> {html.escape(email_data['from'])}</p>
                <p><strong>Date:</strong> {html.escape(email_data['date'])}</p>
            </div>
            <div class="content">
                {render_content_to_html(email_data.get('content', ''), email_data.get('content_type') or 'text/plain', render_mode)}
            </div>
            {back_link}
        </article>"""
