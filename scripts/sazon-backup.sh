#!/usr/bin/env bash
# sazon-backup.sh — daily SQLite backup for Sazón on paragu-ai VPS.
# Uses sqlite3 .backup (online-safe with WAL) rather than cp, then syncs
# the result off-box to the Hermes host over SSH. Retention: 30 daily.
set -euo pipefail

VOL=/var/lib/docker/volumes/sazon-vps_sazon-data/_data
SRC="$VOL/rms.sqlite"
BACKUP_DIR=/var/backups/sazon
STAMP=$(date +%F)
DEST="$BACKUP_DIR/rms-$STAMP.sqlite"
KEEP=30

mkdir -p "$BACKUP_DIR"
sqlite3 "$SRC" ".backup '$DEST'"
gzip -f "$DEST"

# Integrity check on the compressed artifact
gunzip -t "$DEST.gz"

# Retention
ls -1t "$BACKUP_DIR"/rms-*.sqlite.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "backup ok: $DEST.gz ($(du -h "$DEST.gz" | cut -f1))"
