# Email Blog Server

A secure server that turns your email inbox into a live blog. New emails automatically appear as blog posts in real-time.

## Features

- Real-time email monitoring using IMAP IDLE
- Automatic blog updates when new emails arrive
- Secure email fetching over SSL/TLS
- XSS prevention through proper content encoding
- Content Security Policy implementation
- Memory-efficient (stores last 100 emails)
- Health check endpoint at /health
 - Optional Markdown/HTML rendering (opt-in via env var)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with your email settings:
     ```ini
     # Required settings
     IMAP_SERVER=imap.gmail.com
     EMAIL=your-email@gmail.com
     PASSWORD=your-app-password

     # Optional settings
     PORT=8080
     HOST=127.0.0.1
     # Base URL used in RSS feed links (useful behind reverse proxies)
     # Example: https://blog.example.com
     PUBLIC_URL=
     
     # Optional: Protect the blog with HTTP Basic authentication
     BASIC_AUTH_USERNAME=
     BASIC_AUTH_PASSWORD=
     
     # Optional: Content rendering mode (defaults to plain)
     # Options: plain | markdown | auto
     # - plain: escape content and render newlines as <br>
     # - markdown: convert plain/markdown to HTML; sanitize; sanitize HTML parts
     # - auto: prefer sanitized text/html part; else markdown->HTML; else plain
     RENDER_MODE=plain
     ```

3. Run the server (binds to localhost by default):
```bash
python blog_server.py
```

4. Visit `http://localhost:8080` in your browser to view your email blog

## Gmail Setup

If using Gmail:
1. Enable 2-Factor Authentication in your Google Account
2. Generate an App Password:
   - Go to Google Account settings
   - Search for "App Passwords"
   - Select "Mail" and your device
   - Use the generated 16-character password
3. Use imap.gmail.com as your IMAP server

## Security Features

- SSL/TLS encryption for email fetching
- Localhost bind by default; opt-in if you need to expose it externally
- Optional HTTP Basic authentication for the web UI
- Content Security Policy (CSP) headers
- X-Frame-Options to prevent clickjacking
- X-Content-Type-Options to prevent MIME-type sniffing
- Strict-Transport-Security, Referrer-Policy, and Permissions-Policy headers
- By default all content is HTML-escaped to prevent XSS attacks
- When Markdown/HTML is enabled, content is sanitized (using bleach if installed)
- No JavaScript used - pure server-side rendering
- Memory-based caching (no file system access)

## How It Works

1. The server connects to your email inbox using IMAP over SSL
2. It uses IMAP IDLE for real-time email notifications
3. When new emails arrive, they're automatically fetched and cached
4. The blog page shows the most recent 100 emails
5. All email content is properly encoded (and sanitized when rendering HTML)
6. The page auto-updates when you refresh

## Health Check

The server provides a health check endpoint at `/health` that returns "OK" when the server is running properly.
## Development

- Run locally:
  - `python blog_server.py`
- Tests (unit tests focus on rendering and RSS; IMAP is disabled during tests):
  - `python -m unittest discover -s tests -p 'test_*.py'`

- Dev tooling:
  - Install: `make install-dev`
  - Lint: `make lint` (auto-fix: `make lint-fix`)
  - Format: `make format` (check only: `make format-check`)
  - All configs live in `pyproject.toml` (Black/Ruff)
