# Playground

Throwaway coding box for signed-in learners. Files are **not** stored in Postgres. When the session ends, the worker container is removed.

## Shape

- **API (public):** `/api/playground/*` — auth + rate limits. Tiny surface: status, start, ttl, stop, fs, run.
- **Manager (internal):** `playground` Compose service. Only this service mounts the Docker socket.
- **Worker:** `ghostline-playground-worker:local` — no network, read-only root, tmpfs `/workspace`, memory/pids caps, non-root.

## Session time

Learners choose **session minutes** when starting (clamped by `PLAYGROUND_TTL_MIN_MINUTES` / `PLAYGROUND_TTL_MAX_MINUTES`). **Apply timer** resets the remaining lifetime from now.

## Enable

1. Set `PLAYGROUND_ENABLED=true` and a strong `PLAYGROUND_TOKEN` in `.env`.
2. Build the worker image: `docker compose --profile build build playground-worker`
3. `docker compose up -d --build`

## Security notes

- Outbound network is disabled on workers (`NetworkDisabled`).
- No host mounts of Ghostline volumes into workers.
- No nested Docker in workers.
- One session per user.
- Run allowlist: `python3`, `node`, `bash` on workspace-relative paths; plus one-shot `shell` lines via `bash -c` (no interactive TTY).
