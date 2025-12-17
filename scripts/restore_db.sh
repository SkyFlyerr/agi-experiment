#!/bin/bash

################################################################################
# restore_db.sh - Database Restore Utility
#
# Restores PostgreSQL database from a backup file (compressed or uncompressed)
# Verifies restore success and logs restoration process
################################################################################

set -e  # Exit on any error

# === Configuration ===
BACKUP_FILE="${1:-}"
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

# === Validate arguments ===
if [ -z "$BACKUP_FILE" ]; then
    log_error "Usage: $0 <backup_file> [db_host] [db_port] [db_name] [db_user]"
    echo ""
    echo "Example:"
    echo "  $0 ./backups/server_agent_2024-12-18_10-30-45.sql.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

log_info "Starting database restore from: $BACKUP_FILE"

# === Decompress if necessary ===
RESTORE_FILE="$BACKUP_FILE"
TEMP_DECOMPRESSED=false

if [[ "$BACKUP_FILE" == *.gz ]]; then
    log_info "Backup is compressed, decompressing..."
    RESTORE_FILE="${BACKUP_FILE%.gz}"

    # Decompress to temporary file
    if ! gunzip -c "$BACKUP_FILE" > "$RESTORE_FILE"; then
        log_error "Failed to decompress backup file"
        exit 1
    fi
    TEMP_DECOMPRESSED=true
    log_success "Backup decompressed successfully"
fi

# === Verify backup file format ===
log_info "Verifying backup file format..."
if ! head -n 1 "$RESTORE_FILE" | grep -q "PostgreSQL"; then
    log_warning "Backup file does not appear to be a PostgreSQL dump"
    log_warning "Proceeding anyway - restore may fail"
fi

# === Perform database restore ===
log_info "Restoring database: $DB_NAME to $DB_HOST:$DB_PORT"
log_warning "This will overwrite existing data in the database!"
log_info "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

if psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    -f "$RESTORE_FILE" 2>&1; then
    log_success "Database restored successfully"
else
    log_error "Failed to restore database"
    [ "$TEMP_DECOMPRESSED" = true ] && rm -f "$RESTORE_FILE"
    exit 1
fi

# === Verify restore success ===
log_info "Verifying database restore..."
if psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    -c "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public';" > /dev/null 2>&1; then
    log_success "Database verification passed"
else
    log_error "Database verification failed"
    [ "$TEMP_DECOMPRESSED" = true ] && rm -f "$RESTORE_FILE"
    exit 1
fi

# === Cleanup temporary files ===
if [ "$TEMP_DECOMPRESSED" = true ]; then
    log_info "Cleaning up temporary decompressed file..."
    rm -f "$RESTORE_FILE"
fi

log_success "Database restore completed successfully!"
log_info "Restored from: $BACKUP_FILE"
log_info "Database: $DB_NAME on $DB_HOST:$DB_PORT"

exit 0
