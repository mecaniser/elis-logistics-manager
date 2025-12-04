#!/bin/sh
# Startup script for Railway deployment
# Reads PORT from environment (Railway sets this automatically)

# Run database migrations before starting the server
echo "Running database migrations..."
python migrate_add_repair_miles.py || echo "Migration warning (may already exist)"

PORT=${PORT:-8000}
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

