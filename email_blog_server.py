"""Serve an IMAP-backed email blog over HTTP."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections import deque
from pathlib import Path
from threading import RLock

from aiohttp import web

from email_blog_config import (
    CONTENT_SECURITY_POLICY,
    DEFAULT_MAX_BODY_CHARS,
    DEFAULT_MAX_EMAIL_BYTES,
    request_has_token,
    validate_exposure,
    validate_public_url,
)
from email_blog_feed import build_rss
from email_blog_html import build_blog_html, build_email_html
from email_blog_imap import EmailBlogImapMixin
from email_blog_messages import (
    extract_email_content,
    safe_decode,
)
from email_blog_rendering import render_content_to_html

logger = logging.getLogger(__name__)


class EmailBlogServer(EmailBlogImapMixin):
    """Host a small HTTP blog populated from an IMAP mailbox."""

    def __init__(
        self,
        imap_server: str,
        email_addr: str,
        password: str,
        host: str = "127.0.0.1",
        port: int = 8080,
        blog_title: str | None = None,
        public_url: str | None = None,
        enable_imap: bool = True,
        render_mode: str = "plain",
        mailbox: str = "INBOX",
        access_token: str | None = None,
        allowed_senders: list[str] | None = None,
        max_email_bytes: int = DEFAULT_MAX_EMAIL_BYTES,
        max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
        allow_public_bind: bool = False,
        allow_public_without_auth: bool = False,
    ):
        self.imap_server = imap_server
        self.email_addr = email_addr
        self.password = password
        self.host = host
        self.port = port
        self.blog_title = blog_title or "Live Email Blog"
        self.public_url = validate_public_url(public_url) if public_url else None
        self.enable_imap = enable_imap
        self.render_mode = (render_mode or "plain").lower()
        self.mailbox = mailbox or "INBOX"
        self.access_token = access_token
        self.allowed_senders = allowed_senders or []
        self.max_email_bytes = max_email_bytes
        self.max_body_chars = max_body_chars

        validate_exposure(host, access_token, allow_public_bind, allow_public_without_auth)

        self.emails_cache: deque[dict[str, str]] = deque(maxlen=100)
        self.processed_uids: set[str] = set()
        self.uid_validity: str | None = None
        self._cache_lock = RLock()
        self._monitor_task: asyncio.Task | None = None
        self._runner: web.AppRunner | None = None
        self._closed_event: asyncio.Event | None = None
        self.imap_client = None

        self.app = web.Application()
        self.app.router.add_get("/", self.handle_blog)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/email/{uid}", self.handle_single_email)
        self.app.router.add_get("/feed.xml", self.handle_rss)
        self.template_path = Path(__file__).parent / "templates" / "blog_template.html"

    safe_decode = staticmethod(safe_decode)
    get_email_content = staticmethod(extract_email_content)

    def render_content_to_html(self, content: str, content_type: str) -> str:
        """Render email content to safe HTML using this server's mode."""
        return render_content_to_html(content, content_type, self.render_mode)

    def generate_html(self, single_email: dict[str, str] | None = None) -> str:
        """Generate HTML blog content."""
        return build_blog_html(
            self.template_path,
            self.blog_title,
            self._emails(),
            self.render_mode,
            single_email,
        )

    def generate_email_html(self, email_data: dict[str, str], linked: bool = False) -> str:
        """Generate HTML for one email post."""
        return build_email_html(email_data, self.render_mode, linked)

    def generate_rss(self) -> str:
        """Generate an XML-safe RSS feed."""
        return build_rss(self._emails(), self.blog_title, self._base_url())

    async def handle_blog(self, request: web.Request) -> web.Response:
        """Handle blog page requests."""
        self._require_auth(request)
        return self._html_response(self.generate_html())

    async def handle_single_email(self, request: web.Request) -> web.Response:
        """Handle single email view requests."""
        self._require_auth(request)
        uid = request.match_info["uid"]
        email_data = next(
            (email for email in self._emails() if str(email["uid"]) == str(uid)), None
        )
        if not email_data:
            raise web.HTTPNotFound(text="Email not found")
        return self._html_response(self.generate_html(single_email=email_data))

    async def handle_rss(self, request: web.Request) -> web.Response:
        """Handle RSS feed requests."""
        self._require_auth(request)
        return web.Response(
            text=self.generate_rss(),
            content_type="application/rss+xml",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    async def handle_health(self, request: web.Request | None) -> web.Response:
        """Handle health check requests."""
        return web.Response(text="OK")

    async def start(self, register_signals: bool = True) -> None:
        """Start the web server and optional IMAP monitor."""
        if self._closed_event is None:
            self._closed_event = asyncio.Event()
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        if self.enable_imap:
            self._monitor_task = asyncio.create_task(self.monitor_inbox())
        if register_signals:
            self._setup_signal_handlers()
        logger.info("Server started at http://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        """Stop this server's own IMAP and HTTP resources."""
        if self._monitor_task:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
            self._monitor_task = None

        await self._close_imap()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        if self._closed_event:
            self._closed_event.set()

    async def wait_closed(self) -> None:
        """Block until the server is stopped."""
        if self._closed_event is None:
            self._closed_event = asyncio.Event()
        await self._closed_event.wait()

    def _append_email(self, email_data: dict[str, str]) -> None:
        with self._cache_lock:
            self.emails_cache.appendleft(email_data)

    def _emails(self) -> list[dict[str, str]]:
        with self._cache_lock:
            return list(self.emails_cache)

    def _base_url(self) -> str:
        return (self.public_url or f"http://{self.host}:{self.port}").rstrip("/")

    def _require_auth(self, request: web.Request | None) -> None:
        if not self.access_token:
            return
        if not request or not request_has_token(request, self.access_token):
            raise web.HTTPUnauthorized(
                text="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def _html_response(self, text: str) -> web.Response:
        return web.Response(
            text=text,
            content_type="text/html",
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": CONTENT_SECURITY_POLICY,
            },
        )

    def _setup_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._stop_for_signal(s))
                )
            except (NotImplementedError, RuntimeError):
                pass

    async def _stop_for_signal(self, sig: signal.Signals) -> None:
        logger.info("Received exit signal %s", sig.name)
        await self.stop()
