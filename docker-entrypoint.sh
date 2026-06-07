#!/bin/sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
export HOME="/app/data"

mkdir -p /app/data/db

if [ "$(id -u)" = "0" ]; then
    chown -R "${PUID}:${PGID}" /app/data
    exec gosu "${PUID}:${PGID}" "$@"
fi

exec "$@"
