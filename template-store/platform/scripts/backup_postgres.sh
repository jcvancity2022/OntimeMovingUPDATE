#!/usr/bin/env bash
# Backs up the Postgres database pointed to by $DATABASE_URL into ./backups/.
# Usage: DATABASE_URL=postgresql://... ./scripts/backup_postgres.sh [--keep N]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$DIR/backups"
mkdir -p "$BACKUP_DIR"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set." >&2
  exit 1
fi

STAMP=$(date -u +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/platform_${STAMP}.sql.gz"

pg_dump "$DATABASE_URL" | gzip > "$DEST"
echo "Backed up $DATABASE_URL -> $DEST"

KEEP=""
if [ "${1:-}" = "--keep" ] && [ -n "${2:-}" ]; then
  KEEP="$2"
fi
if [ -n "$KEEP" ]; then
  ls -1t "$BACKUP_DIR"/platform_*.sql.gz | tail -n +"$((KEEP + 1))" | xargs -r rm -v
fi
