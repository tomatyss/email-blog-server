# Repository Guidelines

## Project Structure & Module Organization
- `blog_server.py`: entry point hosting the IMAP-driven HTTP server.
- `email_blog_server.py`: reusable mail ingestion logic plus shared caches.
- `templates/`: HTML skeletons (`blog_template.html`) rendered per request.
- `tests/`: mirrors runtime modules; async helpers live beside their targets.
- Root holds `.env.example`, dependency manifests, and `Makefile`; keep new assets with their feature.

## Build, Test, and Development Commands
```bash
make install        # runtime dependencies
make install-dev    # runtime + lint/format tooling
make run            # start local blog server
make test           # unittest suite (async + sync)
make lint           # ruff check
make format         # black reformatting
```
Use Python 3.12+ inside `.venv`. `python blog_server.py` is acceptable for one-off manual checks.

## Coding Style & Maintainability
- Black + Ruff enforce 4-space indentation and a 100-column budget; keep the linters clean before sending PRs.
- Keep modules DRY; refactor shared blocks into helpers rather than duplicating logic.
- Target files under ~300 lines—split into modules when new features push past that boundary.
- Write descriptive docstrings for every public function, class, and module; follow the imperative style used in existing code.
- Stick to snake_case functions/variables, PascalCase classes, lowercase module names, and uppercase constants declared at module top.

## Testing Guidelines
- Extend `tests/` with `test_*.py` files that cover the new paths; always include positive and failure/sanitization cases.
- Reset shared state (`emails_cache`, `processed_uids`) in `setUp`.
- Every new feature or bug fix must ship with at least one test; run `make test` plus any targeted scenario before pushing.

## Commit & Pull Request Guidelines
- Follow conventional summaries (`feat(rendering):`, `fix(server):`); keep them imperative and under ~75 characters.
- Each commit should be a focused change with accompanying docs/tests.
- PR descriptions must outline problem, solution, validation commands, and attach screenshots when rendering changes.
- Reference issues and call out security-sensitive edits, especially environment or sanitization changes.

## Security & Configuration Tips
- `.env` feeds configuration; update `.env.example` whenever introducing a new setting and never commit secrets.
- Prefer `RENDER_MODE=plain`; document any move to `markdown` or `auto` and justify sanitization coverage.
- Pin new dependencies in `requirements*.txt` and mention security implications in PR notes.
