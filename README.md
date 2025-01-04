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
     HOST=0.0.0.0
     ```

3. Run the server:
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
- Content Security Policy (CSP) headers
- X-Frame-Options to prevent clickjacking
- X-Content-Type-Options to prevent MIME-type sniffing
- All content is HTML-escaped to prevent XSS attacks
- No JavaScript used - pure server-side rendering
- Memory-based caching (no file system access)

## How It Works

1. The server connects to your email inbox using IMAP over SSL
2. It uses IMAP IDLE for real-time email notifications
3. When new emails arrive, they're automatically fetched and cached
4. The blog page shows the most recent 100 emails
5. All email content is properly sanitized and encoded
6. The page auto-updates when you refresh

## Health Check

The server provides a health check endpoint at `/health` that returns "OK" when the server is running properly.
