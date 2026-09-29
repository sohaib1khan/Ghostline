#!/bin/sh
# Write a custom-format dump of the Compose Postgres service.
# Uses the project in this directory. Set COMPOSE_PROJECT_NAME to target
# another project. The file is created under backups/ and is not committed.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$root/backups/ghostline-${stamp}.dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$out"
echo "$out"
