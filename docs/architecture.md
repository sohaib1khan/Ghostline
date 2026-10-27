# Architecture

Ghostline is a typing-first lesson app. The browser shows the next command or line. The server checks the answer string. It does not run learner code.

## Processes

```text
browser  →  nginx (web)  →  FastAPI (backend)  →  Postgres (db)
```

- **web** serves the React app, the service worker, fonts, sounds, and the self-hosted Pyodide files. The image starts from nginx 1.28.3 and upgrades Alpine packages that have a fixed advisory. `/api` is proxied to the backend. The sandbox page `/sandbox/runner.html` is the only frame allowed to use `eval` and WebAssembly. Learner JavaScript and Python run in a worker inside that frame, with `fetch` replaced, and a 3 second limit (15 seconds for Ghostwalk runs).
- **backend** is FastAPI on Python 3.12. The production image starts the virtualenv's uvicorn and does not include the `uv` binaries. Sessions are opaque random tokens stored as hashes. Passwords use Argon2id. Notification and AI secrets are Fernet-encrypted in `app_settings`. Alembic migrates the schema on startup, then starter lessons load if the lesson table is empty.
- **db** is Postgres 16. It has no published host port.

Compose gives each service a restart policy, a memory cap, and rotated logs. Images run as non-root except the Postgres entrypoint, which drops to the `postgres` user after it initializes the volume.

## Request path

The React app calls `/api` with cookies. Mutating requests send the double-submit CSRF header. Nginx adds the content security policy: scripts, styles, and connections stay on this origin.

Published lessons are what learners and the public demo can open. Drafts stay in the admin editor. An AI draft is saved only after the JSON validates, and it stays a draft until an admin publishes it.

## Learning progression

- **Checks** stay string-based in `services/check_engine.py` (optional partial credit for `must_contain_all`). Learner code never runs on the API.
- **Spaced review** stores `next_review_at` / `ease` / `interval_days` on `exercise_progress`; `services/review.py` schedules; `GET /api/review/due` interleaves due items (journal struggles first).
- **Mastery gates** live in `services/gating.py` and `module_progress`. The next module unlocks at 80% recall completion; a module boss (no hints, 70% pass) sets `mastered_at`. Certificates require every module boss on the track.
- **Mistake journal** (`attempt_log`, 90-day retention) powers “usual slips” and prefers struggling items in review.
- **Preferences** JSON on the user (and localStorage for demo) drives rem/`--ui-scale`, contrast themes, and editor comfort.

## Ghostwalk

Maze levels teach Python sequencing with a shared pure-Python engine (`app/ghostwalk/world.py`).

```text
editor → sandbox (runtime: ghostwalk) → world.run_learner_code → actions
      → POST /api/ghostwalk/levels/{slug}/submit → world.replay → progress / XP
```

- The API never executes learner source; it only replays the action list.
- Tables: `ghostwalk_levels`, `ghostwalk_progress` (migration `0014_ghostwalk`).
- Seed YAML: `backend/app/seed/ghostwalk/levels.yaml` when the levels table is empty.
- Admin CRUD / reorder / YAML export under `/api/admin/ghostwalk`.
- Struggle (3+ failed submits or 2+ hints) sets `next_review_at` for a free replay in `/review`.

## What is cached in the browser

The service worker keeps the app shell, fonts, sounds, and Pyodide files. It also keeps successful reads of the signed-in home page and of lessons that were opened. Answer checks are not cached and are not queued while offline.

## Security controls

| Control | Where it lives |
| --- | --- |
| Argon2id, 12 character minimum, common-password list | `backend/app/security/passwords.py` |
| Hashed session tokens, HttpOnly cookie, Secure in production, SameSite=Lax, rotation on login | `backend/app/security/cookies.py` |
| CSRF cookie plus `X-CSRF-Token` | `backend/app/security/csrf.py` |
| Login lockout and a generic failure message | `backend/app/services/auth.py` |
| Pydantic limits on input | `backend/app/schemas/` |
| Markdown skips raw HTML; links are sanitized | `frontend/src/components/content/MarkdownView.jsx` |
| Regex length limit and a match timeout | `backend/app/services/check_engine.py` |
| Security headers | `frontend/nginx.conf` |
| Rate limits on login, signup, setup, demo checks, and AI | route decorators |
| Production refuses example secrets | `backend/app/config.py` |
| Encrypted notification and AI secrets, not returned after save | settings store |
| gitleaks | pre-commit and CI |
| Audit log for admin changes | `backend/app/services/audit.py` |
| Trivy image scan | `.github/workflows/ci.yml` |

The API does not enable cross-origin browser access. The app and the API share one origin through nginx.

HSTS is not set by this container. The same image serves plain HTTP on localhost, and a remembered HSTS policy would break that. Put `Strict-Transport-Security` on the TLS proxy. See `docs/deployment.md`.

Notification delivery logs the exception type, not the traceback, so an SMTP or HTTP failure cannot write a credential into the log.
