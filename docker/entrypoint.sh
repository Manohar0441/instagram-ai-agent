#!/usr/bin/env sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting: $*"
exec "$@"
