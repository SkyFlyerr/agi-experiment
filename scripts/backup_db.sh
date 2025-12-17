#!/bin/bash

################################################################################
# backup_db.sh - Database Backup Utility
#
# Creates PostgreSQL database dumps with timestamped filenames
# Rotates old backups to keep only the last 7 days
# Compresses backups with gzip
################################################################################

set -e  # Exit on any error

# === Configuration ===
BACKUP_DIR="${1:-.}/backups"
DAYS_TO_KEEP="${2:-7}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-server_agent}"
DB_USER="${DB_USER:-agent}"

# === Colors for output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

# === Logging functions ===
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# === Ensure backup directory exists ===
mkdir -p "$BACKUP_DIR"
log_info "Backup directory: $BACKUP_DIR"

# === Generate backup filename with timestamp ===
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql"
BACKUP_FILE_GZ="${BACKUP_FILE}.gz"

log_info "Starting database backup: $DB_NAME"

# === Perform database dump ===
log_info "Dumping database from $DB_HOST:$DB_PORT..."
if pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    --verbose \
    --format=plain \
    > "$BACKUP_FILE" 2>&1; then
    log_success "Database dumped successfully"
else
    log_error "Failed to dump database"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# === Verify backup file ===
if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
    log_error "Backup file is empty or doesn't exist: $BACKUP_FILE"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# === Display backup file size ===
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "Backup file size: $BACKUP_SIZE"

# === Compress backup ===
log_info "Compressing backup with gzip..."
if gzip -v "$BACKUP_FILE" > /dev/null 2>&1; then
    log_success "Backup compressed: $BACKUP_FILE_GZ"
else
    log_error "Failed to compress backup"
    exit 1
fi

# === Verify compressed backup ===
if ! gzip -t "$BACKUP_FILE_GZ" 2>&1; then
    log_error "Compressed backup integrity check failed"
    rm -f "$BACKUP_FILE_GZ"
    exit 1
fi

COMPRESSED_SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
log_success "Compressed backup size: $COMPRESSED_SIZE"

# === Rotate old backups ===
log_info "Rotating backups older than $DAYS_TO_KEEP days..."
CUTOFF_DATE=$(date -d "$DAYS_TO_KEEP days ago" '+%Y-%m-%d' 2>/dev/null || date -v-${DAYS_TO_KEEP}d '+%Y-%m-%d')
DELETED_COUNT=0

for backup in "$BACKUP_DIR"/${DB_NAME}_*.sql.gz; do
    if [ -f "$backup" ]; then
        # Extract date from filename (format: ${DB_NAME}_YYYY-MM-DD_HH-MM-SS.sql.gz)
        filename=$(basename "$backup")
        file_date=$(echo "$filename" | sed -E "s/${DB_NAME}_([0-9]{4}-[0-9]{2}-[0-9]{2}).*/\1/")

        # Compare dates
        if [[ "$file_date" < "$CUTOFF_DATE" ]]; then
            log_info "Deleting old backup: $filename"
            rm -f "$backup"
            ((DELETED_COUNT++))
        fi
    fi
done

if [ "$DELETED_COUNT" -gt 0 ]; then
    log_success "Deleted $DELETED_COUNT old backup(s)"
else
    log_info "No old backups to delete"
fi

# === List recent backups ===
log_info "Recent backups in $BACKUP_DIR:"
ls -lh "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | tail -5 | awk '{print "  " $9 " (" $5 ")"}'

log_success "Database backup completed successfully!"
log_info "Backup file: $BACKUP_FILE_GZ"

exit 0
