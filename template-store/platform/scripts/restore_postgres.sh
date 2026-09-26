#!/usr/bin/env bash
# Restores a backup produced by backup_postgres.sh.
# Usage: DATABASE_URL=postgresql://... ./scripts/restore_postgres.sh backups/platform_20260101_120000.sql.gz
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set." >&2
  exit 1
fi
if [ -z "${1:-}" ] || [ ! -f "$1" ]; then
  echo "Usage: DATABASE_URL=... $0 <backup_file.sql.gz>" >&2
  exit 1
fi

echo "This will overwrite the database at \$DATABASE_URL. Ctrl+C to abort."
sleep 3

gunzip -c "$1" | psql "$DATABASE_URL"
echo "Restored $1 -> $DATABASE_URL"
