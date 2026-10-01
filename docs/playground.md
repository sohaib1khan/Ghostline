# Playground

Throwaway coding box for signed-in learners. Files are **not** stored in Postgres. When the session ends, the worker container is removed.

## Shape

- **API (public):** `/api/playground/*` — auth + rate limits. Surface: status, start, ttl, stop, fs, run, preview, packages.
- **Manager (internal):** `playground` Compose service. Only this service mounts the Docker socket.
- **Worker:** `ghostline-playground-worker:local` — **no network**, read-only root, tmpfs `/workspace`, memory/pids caps, non-root. Nothing inside the worker can reach the host or the internet.

## Templates

Starters are seeded under `templates/`, one project per folder:

| Folder | Chip |
|---|---|
| `templates/python-hello` | Python |
| `templates/python-flask` | Flask (install `flask` first; test client, no ports) |
| `templates/javascript-hello` | JavaScript |
| `templates/bash-hello` | Bash |
| `templates/web-hello` | Web → **Browser** tab |

Installed pip/npm packages live under `/tmp` inside the worker so they do not clutter the Files list.

## Session time

Each session lasts **12 hours** (`PLAYGROUND_TTL_DEFAULT_MINUTES=720`). A countdown shows time left. When it hits zero the worker container is destroyed and files are gone. **Extend** resets another full 12-hour window from now.

## Browser preview

Open **Web** or the **Browser** tab to render `templates/web-hello/index.html` (or any `.html` you add). Files stream through `/api/playground/preview/...` into a sandboxed iframe (`sandbox="allow-scripts"`, no `allow-same-origin`). No worker ports are published and nothing binds on the host.

## Packages (offline install)

Workers stay `NetworkDisabled`. **Install** downloads on the **manager** (pip/npm registries only), injects artifacts into the worker under `/tmp`, then installs offline. `PYTHONPATH` / `NODE_PATH` are set on Run.

## Enable

1. Set `PLAYGROUND_ENABLED=true` and a strong `PLAYGROUND_TOKEN` in `.env`.
2. Build the worker image: `docker compose --profile build build playground-worker`
3. `docker compose up -d --build`

## Security notes

- Outbound network is disabled on workers (`NetworkDisabled`) — always.
- No host mounts of Ghostline volumes into workers.
- No nested Docker in workers.
- One session per user.
- Run allowlist: `python3`, `node`, `bash` on workspace-relative paths; plus one-shot `shell` lines via `bash -c` (no interactive TTY).
- Preview CSP blocks `connect-src` (no fetch/XHR from rendered pages).
- Package names are allowlisted (no URLs / VCS); downloads capped by count and size.
