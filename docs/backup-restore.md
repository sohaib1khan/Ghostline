# Backup and restore

Ghostline keeps accounts, progress, and lessons in the Postgres service named `db`. The host does not publish that database. Backups run through Compose.

## Backup

From the repository root, with the stack running:

```bash
./scripts/backup-postgres.sh
```

The script writes `backups/ghostline-YYYYMMDDTHHMMSSZ.dump`. That directory is git-ignored. Copy the file off the machine. The dump is Postgres custom format (`pg_dump -Fc`).

`COMPOSE_PROJECT_NAME` selects the Compose project when you have more than one.

## Restore

Stop the API so it is not writing during the restore:

```bash
docker compose stop backend
./scripts/restore-postgres.sh backups/ghostline-YYYYMMDDTHHMMSSZ.dump
docker compose start backend
```

Restore replaces the objects in the database with the dump. Take a fresh backup first if the current data might still be needed.

The web container can stay up. It will show errors until the API is healthy again.

## Check a restore

On a copy of the instance, not on the only copy of the data:

1. Note a value you can recognize, such as the number of lessons.
2. Take a backup.
3. Restore that file onto a second Compose project.
4. Confirm the lesson count matches.

A second project needs its own `COMPOSE_PROJECT_NAME`, its own `.env`, and a `WEB_PORT` that is free.
