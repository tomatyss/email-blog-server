# Repository Guidelines

## Scope & Source of Truth
- This root `AGENTS.md` applies to the whole repository. Add a nested `AGENTS.md` only when a subdirectory needs different commands or constraints.
- Treat `README.md`, `.env.example`, `Makefile`, and `pyproject.toml` as the current operational sources before changing setup, commands, or configuration behavior.
- Keep changes focused on the requested task; avoid broad rewrites, file moves, or dependency changes unless they are necessary for the task.

## Project Structure
- `blog_server.py`: small executable entry point that loads `.env` and starts `EmailBlogServer`.
- `email_blog_server.py`: reusable HTTP server and request-handler orchestration.
- `email_blog_imap.py`, `email_blog_messages.py`, `email_blog_rendering.py`, `email_blog_feed.py`, `email_blog_html.py`, `email_blog_config.py`: focused helpers for IMAP ingestion, MIME parsing, rendering, RSS, HTML generation, and exposure/auth validation.
- `templates/blog_template.html`: server-rendered HTML skeleton used by `generate_html`.
- `tests/`: unittest coverage for runtime modules; async request handlers use `unittest.IsolatedAsyncioTestCase`.
- `.env.example`: documented configuration contract. Update it whenever adding, renaming, or changing an environment variable.
- `requirements.txt` and `requirements-dev.txt`: pinned dependency lists for runtime and developer tooling.

## Development Commands
Use Python 3.12+ in a local `.venv`.

```bash
make install        # install runtime dependencies
make install-dev    # install runtime + lint/format tooling
make run            # start the local server from blog_server.py
make test           # run the full unittest suite
make lint           # ruff check .
make lint-fix       # ruff check --fix .
make format         # black .
make format-check   # black --check .
```

Focused validation is preferred while iterating:

```bash
.venv/bin/python -m unittest tests.test_server
.venv/bin/python -m unittest tests.test_render_mode
.venv/bin/python -m unittest tests.test_server.EmailBlogServerTests.test_health
.venv/bin/ruff check path/to/file.py
.venv/bin/black --check path/to/file.py
```

Run `make test` before finishing code changes. Run `make lint` and `make format-check` when Python files changed; use `make format` only when formatting is needed.

## Agent Operating Rules
- Read the nearby implementation and tests before editing; mirror existing patterns unless the task clearly requires a new pattern.
- Ask before adding production dependencies, changing dependency pins, deleting files, or introducing long-running services outside `make run`.
- Do not use real IMAP credentials or connect to a live mailbox during tests. Instantiate `EmailBlogServer(..., enable_imap=False)` for handler, rendering, and RSS tests.
- Never commit secrets or generated local artifacts such as `.env`, `.venv/`, `__pycache__/`, or `.ruff_cache/`.
- Preserve unrelated user changes. If a touched file has unrelated edits, work around them instead of reverting them.

## Python Style & Maintainability
- Black and Ruff enforce 4-space indentation, Python 3.12 syntax, and a 100-column target. Ruff ignores `E501`; still keep lines readable.
- Keep modules DRY. Extract helpers when logic is shared across handlers, rendering paths, or tests.
- Prefer small, cohesive functions and modules. If a file approaches roughly 300 lines because of new behavior, consider splitting by responsibility.
- Public modules, classes, and functions should have concise docstrings in the existing imperative style.
- Use snake_case for functions and variables, PascalCase for classes, and uppercase constants at module top.
- Avoid ad hoc parsing when the standard library already provides email, URL, date, HTML, or XML helpers.

## Security & Rendering
- Default to `RENDER_MODE=plain`. Any move toward `markdown` or `auto` must include sanitization tests and a short explanation in docs or PR notes.
- Escape or sanitize all email-controlled fields: subject, sender, date, body, UID-derived links, and RSS content.
- Keep the CSP intentionally restrictive. Do not add client-side JavaScript, external styles, images, or relaxed CSP directives without a security reason and tests.
- When handling HTML or Markdown email parts, preserve the existing fallback behavior for missing optional packages: unsafe HTML should render as escaped plain text if sanitization dependencies are unavailable.
- Treat `.env` as local-only configuration. Reflect any new setting in `.env.example` with safe defaults and comments.

## Testing Guidelines
- Add or update tests for every feature or bug fix, including at least one positive case and one failure, escaping, or sanitization case when user-controlled content is involved.
- Keep cache state instance-owned in tests by using `server.emails_cache` and `server.processed_uids`.
- Keep tests deterministic: avoid wall-clock assertions unless values are controlled, avoid network access, and do not require real environment variables.
- Prefer focused unittest targets while developing, then run the full suite with `make test`.
- Rendering changes should verify the emitted HTML or RSS text for both intended output and blocked unsafe content.

## Commit & Pull Request Guidelines
- Use conventional commit summaries such as `feat(rendering): add markdown mode` or `fix(server): handle empty fetch responses`; keep summaries imperative and under about 75 characters.
- Keep each commit focused and include matching tests/docs.
- PR descriptions should cover problem, solution, validation commands, and screenshots for visible rendering changes.
- Call out security-sensitive edits, especially changes to environment handling, sanitization, CSP, or dependency pins.
