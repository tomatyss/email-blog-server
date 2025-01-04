#!/usr/bin/env python3
import os
import ssl
import html
import email
import logging
import asyncio
from dotenv import load_dotenv
from email.header import decode_header
from datetime import datetime
from aiohttp import web
from aioimaplib import aioimaplib
from collections import deque
import signal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store emails in memory (recent 100 emails)
emails_cache = deque(maxlen=100)


class EmailBlogServer:
    def __init__(self, imap_server, email_addr, password, host='0.0.0.0', port=8080):
        self.imap_server = imap_server
        self.email_addr = email_addr
        self.password = password
        self.host = host
        self.port = port
        self.imap_client = None
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_blog)
        self.app.router.add_get('/health', self.handle_health)
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        async def shutdown(signal, loop):
            logger.info(f"Received exit signal {signal.name}...")
            if self.imap_client and self.imap_client.has_pending_idle():
                await self.imap_client.idle_done()
            await self.app.shutdown()
            await self.app.cleanup()
            loop.stop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(
                    shutdown(s, asyncio.get_event_loop()))
            )

    async def connect_imap(self):
        """Establish secure IMAP connection"""
        try:
            # Create SSL context with secure defaults
            ssl_context = ssl.create_default_context()

            logger.info(f"Creating IMAP client for {self.imap_server}")
            self.imap_client = aioimaplib.IMAP4_SSL(
                host=self.imap_server,
                ssl_context=ssl_context
            )

            logger.info("Waiting for server hello...")
            try:
                await self.imap_client.wait_hello_from_server()
            except Exception as e:
                logger.error(f"Failed at hello: {str(e)}", exc_info=True)
                raise

            logger.info("Attempting login...")
            try:
                await self.imap_client.login(self.email_addr, self.password)
            except Exception as e:
                logger.error(f"Failed at login: {str(e)}", exc_info=True)
                raise

            logger.info("Selecting INBOX...")
            try:
                await self.imap_client.select('INBOX')
            except Exception as e:
                logger.error(f"Failed at select: {str(e)}", exc_info=True)
                raise

            logger.info("Successfully connected to IMAP server")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def safe_decode(header):
        """Safely decode email headers"""
        if not header:
            return ''
        decoded_header = decode_header(header)
        parts = []
        for content, charset in decoded_header:
            if isinstance(content, bytes):
                try:
                    parts.append(content.decode(
                        charset or 'utf-8', errors='replace'))
                except:
                    parts.append(content.decode('utf-8', errors='replace'))
            else:
                parts.append(str(content))
        return ' '.join(parts)

    @staticmethod
    def get_email_content(msg):
        """Extract email content safely"""
        content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content += part.get_payload(
                            decode=True).decode(errors='replace')
                    except:
                        continue
        else:
            try:
                content = msg.get_payload(decode=True).decode(errors='replace')
            except:
                content = "Could not decode email content"
        return content

    async def fetch_email(self, uid):
        """Fetch and process a single email"""
        response = await self.imap_client.uid('fetch', uid, '(RFC822)')
        if response.result == 'OK':
            email_data = response.lines[1]
            msg = email.message_from_bytes(email_data)

            # Safely extract and encode email details
            subject = self.safe_decode(msg['subject'])
            from_addr = self.safe_decode(msg['from'])
            date = self.safe_decode(msg['date'])
            content = self.get_email_content(msg)

            return {
                'subject': subject,
                'from': from_addr,
                'date': date,
                'content': content,
                'uid': uid
            }
        return None

    async def monitor_inbox(self):
        """Monitor inbox for new emails"""
        while True:
            try:
                # Create new connection
                logger.info(f"Connecting to {self.imap_server} as {
                            self.email_addr}")
                self.imap_client = aioimaplib.IMAP4_SSL(host=self.imap_server)

                logger.info("Waiting for server hello...")
                await self.imap_client.wait_hello_from_server()

                logger.info("Logging in...")
                await self.imap_client.login(self.email_addr, self.password)

                logger.info("Selecting INBOX...")
                await self.imap_client.select('INBOX')

                logger.info("Searching for emails...")
                _, data = await self.imap_client.search('ALL')
                email_ids = data[0].split()
                logger.info(f"Found {len(email_ids)} emails")

                # Fetch and cache emails
                if email_ids:
                    for email_id in email_ids[-100:]:  # Get last 100 emails
                        logger.info(f"Fetching email {email_id.decode()}...")
                        response = await self.imap_client.fetch(email_id.decode(), '(RFC822)')
                        if response[0] == 'OK':
                            email_data = await self.fetch_email(email_id.decode())
                            if email_data:
                                emails_cache.appendleft(email_data)

                # Start IDLE mode
                logger.info("Starting IDLE mode...")
                idle = await self.imap_client.idle_start()
                try:
                    while True:
                        logger.info("Waiting for new emails...")
                        response = await self.imap_client.wait_server_push()

                        if response is None:
                            logger.info(
                                "IDLE connection closed, reconnecting...")
                            break

                        logger.info(f"Received server push: {response}")

                        # Check for new messages
                        if any(b'EXISTS' in line for line in response):
                            logger.info("New email detected!")
                            await self.imap_client.idle_done()

                            # Fetch new messages
                            _, data = await self.imap_client.search('ALL')
                            email_ids = data[0].split()
                            # Get last 5 messages
                            for email_id in email_ids[-5:]:
                                email_data = await self.fetch_email(email_id.decode())
                                if email_data:
                                    emails_cache.appendleft(email_data)
                                    logger.info(f"New email fetched: {
                                                email_data['subject']}")

                            idle = await self.imap_client.idle_start()

                except Exception as e:
                    logger.error(f"Error in IDLE loop: {str(e)}")
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in monitor_inbox: {str(e)}")
                await asyncio.sleep(30)

    def generate_html(self):
        """Generate HTML blog content"""
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="DENY">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
    <title>Live Email Blog</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; margin: 0; padding: 20px; max-width: 800px; margin: 0 auto; }}
        article {{ margin-bottom: 2em; border-bottom: 1px solid #eee; padding-bottom: 1em; }}
        .meta {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <header>
        <h1>Live Email Blog</h1>
        <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </header>
    <main>'''

        for email_data in emails_cache:
            html_content += f'''
        <article>
            <h2>{html.escape(email_data['subject'])}</h2>
            <div class="meta">
                <p><strong>From:</strong> {html.escape(email_data['from'])}</p>
                <p><strong>Date:</strong> {html.escape(email_data['date'])}</p>
            </div>
            <div class="content">
                {html.escape(email_data['content']).replace(chr(10), '<br>')}
            </div>
        </article>'''

        html_content += '''
    </main>
    <footer>
        <p>Secure Email Blog - All content is properly sanitized and encoded</p>
    </footer>
</body>
</html>'''

        return html_content

    async def handle_blog(self, request):
        """Handle blog page requests"""
        return web.Response(
            text=self.generate_html(),
            content_type='text/html',
            headers={
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY',
                'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline';"
            }
        )

    async def handle_health(self, request):
        """Handle health check requests"""
        return web.Response(text='OK')

    async def start(self):
        """Start the server and email monitor"""
        # Start email monitoring in background
        asyncio.create_task(self.monitor_inbox())
        # Start web server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Server started at http://{self.host}:{self.port}")


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    imap_server = os.getenv('IMAP_SERVER')
    email_addr = os.getenv('EMAIL')
    password = os.getenv('PASSWORD')
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8080'))

    if not all([imap_server, email_addr, password]):
        logger.error(
            "Please set IMAP_SERVER, EMAIL, and PASSWORD in your .env file")
        exit(1)

    # Create and start the server
    server = EmailBlogServer(imap_server, email_addr, password, host, port)
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(server.start())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
