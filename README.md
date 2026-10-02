# Ghostline

A calm, typing-first way to learn coding — and keep the muscle memory.

Ghostline is a self-hosted web app for trace, fill, recall, and challenge exercises. Learners type real commands and code; the server checks answer strings (it does not execute learner code on the server). Admins manage tracks, lessons, users, notifications, and optional AI-assisted drafts.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- For optional **Playground** (ephemeral code boxes): Docker socket access on the host running Compose

## Quick start

```bash
git clone https://github.com/sohaib1khan/Ghostline.git
cd Ghostline
cp .env.example .env
docker compose up --build
```

Open http://localhost:8080 (or the port you set as `WEB_PORT` in `.env`).

Health check: http://localhost:8080/api/health → `{"status":"ok"}`

Postgres is **not** published on the host. Only the `web` container listens on `WEB_PORT`.

### Generate secrets (recommended before first run)

Replace every `change-me` in `.env`:

```bash
python3 -c "import secrets; print('APP_SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "from cryptography.fernet import Fernet; print('APP_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Set `POSTGRES_PASSWORD` to a long random password. Compose builds `DATABASE_URL` from the Postgres variables.

For local development, the example values in `.env.example` are enough. **Production** (`APP_ENV=production`) refuses to start with missing, short, or example secrets.

## First admin

A fresh database has no admin. Choose one path:

### Automated (lab / CI)

Add to `.env` **before** the first boot:

```bash
BOOTSTRAP_ALLOW=true
BOOTSTRAP_ADMIN_EMAIL=you@example.com
BOOTSTRAP_ADMIN_PASSWORD='a-long-unique-passphrase'
BOOTSTRAP_ADMIN_FIRST_NAME=Ada
BOOTSTRAP_ADMIN_LAST_NAME=Lovelace
```

Then `docker compose up --build`. Logs show `GHOSTLINE BOOTSTRAP: super admin ready for …`. Sign in with that email and password. After it works, set `BOOTSTRAP_ALLOW=false` and remove the bootstrap password from `.env`.

### Interactive

Leave `BOOTSTRAP_ALLOW=false`. After the backend starts:

```bash
docker compose logs backend | grep "GHOSTLINE SETUP TOKEN"
```

Open the app → `/setup`. Enter the token, your name, email, and a password (12+ characters). The token is one-time; a backend restart before setup finishes prints a new token.

## What you get

- **Tracks** — Bash, Python, JavaScript, Go, SQL starter content loads on first boot (`backend/app/seed/lessons/`).
- **Ghost editor** — trace exercises with live WPM/accuracy; fill, recall, and challenge with string checks.
- **Games** — Speed Drill, Bug Hunt, Command Roulette, Fill Frenzy (published exercises only).
- **Demo** — `/demo` for visitors without an account (rate-limited checks).
- **Admin** — Content, Users, Notifications, AI drafts, Settings.
- **PWA** — installable; offline re-read of lessons already opened (checks require network).

## Playground

Throwaway Python / JavaScript / Bash workspaces in isolated Docker workers. On by default when Compose is up.

1. Set a shared token in `.env` (required):

   ```bash
   PLAYGROUND_TOKEN=<long-random-token>
   ```

2. Build the worker image once:

   ```bash
   docker compose --profile build build playground-worker
   ```

3. `docker compose up -d --build`

See [docs/playground.md](docs/playground.md).

## Development

### Hot reload (Docker)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Vite dev server: http://localhost:5173 (proxies `/api` to the backend).

### On the host

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm ci && npm run dev
```

### Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm run format:check && npm run build
./scripts/e2e.sh
```

Auth/database tests need Postgres. Set `TEST_DATABASE_URL` to a disposable database, e.g. `postgresql+asyncpg://ghostline:test@127.0.0.1:5432/ghostline_test`. Without it, those tests are skipped.

Install [pre-commit](https://pre-commit.com/) and run `pre-commit install` (Ruff, frontend lint/format, gitleaks).

## Production

See [docs/deployment.md](docs/deployment.md) for HTTPS reverse proxy, `APP_BASE_URL`, and operations.

Backups: `./scripts/backup-postgres.sh` and `./scripts/restore-postgres.sh` — [docs/backup-restore.md](docs/backup-restore.md).

## Documentation

| Doc | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Services, security controls, request path |
| [docs/deployment.md](docs/deployment.md) | Production deploy and HTTPS |
| [docs/content-format.md](docs/content-format.md) | YAML lesson import/export |
| [docs/playground.md](docs/playground.md) | Ephemeral worker playground |
| [docs/backup-restore.md](docs/backup-restore.md) | Postgres backup/restore |
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities, secrets policy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup and contribution rules |

## Layout

```
backend/     FastAPI API, Alembic migrations, seed lessons
frontend/    React + Vite + Tailwind PWA
playground/  Internal manager for ephemeral worker containers
docs/        Architecture, deployment, content format
scripts/     Backup, restore, e2e helper
```

Fonts (Inter, JetBrains Mono) are self-hosted under `frontend/src/assets/fonts/`.

## License

MIT — see [LICENSE](LICENSE).
