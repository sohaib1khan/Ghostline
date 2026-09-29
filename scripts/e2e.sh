#!/bin/sh
# Fresh Compose project, then the Playwright release tests.
# Does not use the .env in the repository, so it cannot attach to a running instance.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
port=${E2E_WEB_PORT:-8091}
# Ignore an inherited Compose project name so this cannot attach to a running instance.
project=${E2E_COMPOSE_PROJECT:-ghostline-e2e}
envfile=$(mktemp)
cleanup() {
  docker compose --env-file "$envfile" down -v >/dev/null 2>&1 || true
  rm -f "$envfile"
}
trap cleanup EXIT
cp .env.example "$envfile"
sed -i "s/^WEB_PORT=.*/WEB_PORT=${port}/" "$envfile"
set -a
# shellcheck disable=SC1090
. "$envfile"
set +a
export COMPOSE_PROJECT_NAME="$project"
export WEB_PORT="$port"
export E2E_BASE_URL="http://127.0.0.1:${port}"
docker compose --env-file "$envfile" up -d --build --wait
cd e2e
if [ ! -d node_modules/@playwright/test ]; then
  npm ci
fi
npx playwright install chromium
npx playwright test
