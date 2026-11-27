#!/bin/sh
# Apply database migrations, then run the container's command (Gunicorn by default).
# Set RUN_MIGRATIONS=0 on extra containers from this image (e.g. the scheduler) so only one
# container migrates. `flask db upgrade` is idempotent, so a repeat run is harmless anyway.
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    # After a host or Docker restart every container starts at once, so Postgres may still be
    # "starting up". Retry instead of exiting (which would just crash-loop the container).
    attempt=1
    max_attempts="${MIGRATION_RETRIES:-20}"
    echo "Applying database migrations..."
    until flask db upgrade; do
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "Database still unavailable after $attempt attempts; giving up." >&2
            exit 1
        fi
        echo "Database not ready (attempt $attempt/$max_attempts); retrying in 3s..." >&2
        attempt=$((attempt + 1))
        sleep 3
    done
fi

exec "$@"
