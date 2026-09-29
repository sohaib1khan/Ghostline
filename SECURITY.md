# Security

Ghostline stores accounts, progress, and content. It does not run learner code on the server.

## Reporting a vulnerability

Email the maintainers with a description, the affected version, and a way to reproduce the issue. Please give us a chance to fix it before writing about it in public.

Do not open a public GitHub issue for an undisclosed vulnerability.

## Secrets

- `.env` is git-ignored. Copy `.env.example` and replace every `change-me` value before a production deploy.
- `APP_SECRET_KEY` and `APP_ENCRYPTION_KEY` must be unique. The API refuses to start when `APP_ENV=production` and those values are missing, short, or still the examples.
- Notification and AI credentials are stored encrypted in the database. They are not environment variables, and they are not shown again after saving.
- Do not commit real passwords, tokens, or API keys. gitleaks runs in pre-commit and in CI.

## Local defaults

The example secrets are only for development. They are not safe on a reachable server.
