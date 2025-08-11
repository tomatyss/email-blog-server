import asyncio
import logging
import os
from dotenv import load_dotenv
from email_blog_server import EmailBlogServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    imap_server = os.getenv("IMAP_SERVER")
    email_addr = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    blog_title = os.getenv("BLOG_TITLE")
    public_url = os.getenv("PUBLIC_URL")
    render_mode = os.getenv("RENDER_MODE", "plain")

    if not all([imap_server, email_addr, password]):
        logger.error("Please set IMAP_SERVER, EMAIL, and PASSWORD in your .env file")
        exit(1)

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
    )
    await server.start()

    try:
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except asyncio.CancelledError:
        logger.info("Server shutdown initiated...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
