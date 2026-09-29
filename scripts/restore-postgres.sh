#!/bin/sh
# Replace the Compose database with a dump from backup-postgres.sh.
# Stop the backend first so it is not writing while the restore runs.
# Example: docker compose stop backend && ./scripts/restore-postgres.sh backups/ghostline-....dump
set -eu
if [ $# -ne 1 ]; then
  echo "usage: $0 backups/ghostline-YYYYMMDDTHHMMSSZ.dump" >&2
  exit 1
fi
dump=$1
if [ ! -f "$dump" ]; then
  echo "dump not found: $dump" >&2
  exit 1
fi
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' < "$dump"
echo "restored $dump"
