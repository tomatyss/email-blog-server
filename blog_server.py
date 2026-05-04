import asyncio
import logging
import os

from dotenv import load_dotenv

from email_blog_server import EmailBlogServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_bool(value: str | None) -> bool:
    """Parse common truthy environment values."""
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_int(name: str, default: int) -> int:
    """Parse an integer environment variable with a clear error."""
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc


def parse_csv(name: str) -> list[str]:
    """Parse a comma-separated environment variable."""
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


async def main() -> None:
    """Load configuration and run the email blog server."""
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    imap_server = os.getenv("IMAP_SERVER")
    email_addr = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    host = os.getenv("HOST", "127.0.0.1")
    port = parse_int("PORT", 8080)
    blog_title = os.getenv("BLOG_TITLE")
    public_url = os.getenv("PUBLIC_URL")
    render_mode = os.getenv("RENDER_MODE", "plain")
    mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
    access_token = os.getenv("BLOG_ACCESS_TOKEN")
    allowed_senders = parse_csv("ALLOWED_SENDERS")
    max_email_bytes = parse_int("MAX_EMAIL_BYTES", 1_048_576)
    max_body_chars = parse_int("MAX_BODY_CHARS", 100_000)
    allow_public_bind = parse_bool(os.getenv("ALLOW_PUBLIC_BIND"))
    allow_public_without_auth = parse_bool(os.getenv("ALLOW_PUBLIC_WITHOUT_AUTH"))

    if not all([imap_server, email_addr, password]):
        logger.error("Please set IMAP_SERVER, EMAIL, and PASSWORD in your .env file")
        raise SystemExit(1)

    # Create and start the server
    server = EmailBlogServer(
        imap_server,
        email_addr,
        password,
        host,
        port,
        blog_title,
        public_url=public_url,
        render_mode=render_mode,
        mailbox=mailbox,
        access_token=access_token,
        allowed_senders=allowed_senders,
        max_email_bytes=max_email_bytes,
        max_body_chars=max_body_chars,
        allow_public_bind=allow_public_bind,
        allow_public_without_auth=allow_public_without_auth,
    )
    await server.start()
    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
