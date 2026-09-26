"""
SQLite backup/restore for local dev or small single-file deployments.
For production Postgres, use backup_postgres.sh / restore_postgres.sh instead.

Usage:
    python scripts/backup_sqlite.py backup
    python scripts/backup_sqlite.py restore backups/platform_20260101_120000.db
    python scripts/backup_sqlite.py backup --keep 10   # prune older backups, keep newest 10
"""
import argparse
import os
import shutil
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from config import Config  # noqa: E402

BACKUP_DIR = os.path.join(BASE_DIR, 'backups')


def _db_path():
    uri = Config.SQLALCHEMY_DATABASE_URI
    if not uri.startswith('sqlite:///'):
        raise SystemExit('DATABASE_URL is not SQLite — use backup_postgres.sh instead.')
    return uri.replace('sqlite:///', '', 1)


def backup(keep=None):
    src = _db_path()
    if not os.path.exists(src):
        raise SystemExit(f'No database found at {src}.')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'platform_{stamp}.db')
    shutil.copy2(src, dest)
    print(f'Backed up {src} -> {dest}')

    if keep:
        backups = sorted(
            (f for f in os.listdir(BACKUP_DIR) if f.startswith('platform_') and f.endswith('.db')),
            reverse=True
        )
        for old in backups[keep:]:
            os.remove(os.path.join(BACKUP_DIR, old))
            print(f'Pruned old backup: {old}')


def restore(backup_file):
    if not os.path.exists(backup_file):
        raise SystemExit(f'Backup file not found: {backup_file}')
    dest = _db_path()
    if os.path.exists(dest):
        safety_copy = dest + '.before-restore'
        shutil.copy2(dest, safety_copy)
        print(f'Existing database saved to {safety_copy} before overwriting.')
    shutil.copy2(backup_file, dest)
    print(f'Restored {backup_file} -> {dest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    backup_p = sub.add_parser('backup')
    backup_p.add_argument('--keep', type=int, default=None, help='Keep only the N most recent backups.')
    restore_p = sub.add_parser('restore')
    restore_p.add_argument('backup_file')
    args = parser.parse_args()

    if args.command == 'backup':
        backup(keep=args.keep)
    elif args.command == 'restore':
        restore(args.backup_file)
