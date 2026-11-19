#!/bin/sh
# Apply database migrations, then run the container's command (Gunicorn by default).
# Set RUN_MIGRATIONS=0 on extra containers from this image (e.g. the scheduler) so only one
# container migrates. `flask db upgrade` is idempotent, so a repeat run is harmless anyway.
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "Applying database migrations..."
    flask db upgrade
fi

exec "$@"
