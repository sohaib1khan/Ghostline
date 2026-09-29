# Contributing

Thanks for helping improve Ghostline.

## Setup

```bash
cp .env.example .env
cd backend && uv sync
cd ../frontend && npm ci
```

Install [pre-commit](https://pre-commit.com/) and run `pre-commit install` so Ruff, frontend checks, and gitleaks run before each commit.

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm run format:check && npm run build
```

## Rules

- Do not commit secrets. Real values belong in `.env` or in the encrypted settings table (notification/AI keys saved via the admin UI).
- Prefer the more secure option when a choice is ambiguous, and leave a `# DECISION:` comment that explains it.
- Keep the app runnable with `docker compose up`.
- Match existing code style and keep diffs focused.
