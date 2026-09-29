#!/bin/sh
set -eu

# The node_modules volume is created as root. Hand it to the node user, then
# install and start Vite without staying root.
mkdir -p /app/node_modules
chown -R node:node /app/node_modules

exec su -s /bin/sh node -c "cd /app && npm ci --cache /tmp/npm-cache && exec npm run dev -- --host 0.0.0.0 --port 5173"
