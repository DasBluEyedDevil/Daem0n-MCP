#!/bin/bash
set -e

# Run migrations if enabled
if [ "$DAEM0NMCP_AUTO_MIGRATE" != "false" ]; then
    echo "Running database migrations..."
    python -c "from daem0nmcp.database import run_migrations; from daem0nmcp.config import settings; run_migrations(settings.get_database_url())"
fi

# Start server
exec python -m daem0nmcp.server "$@"
