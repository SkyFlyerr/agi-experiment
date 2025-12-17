#!/bin/bash

################################################################################
# rollback.sh - Rollback to Previous Version
#
# Performs emergency rollback to the previous stable version:
# - Stops current containers
# - Starts containers with rollback image
# - Waits for startup and runs smoke tests
# - Updates deployment record
# - Alerts Master if rollback fails
################################################################################

set -e  # Exit on any error

# === Configuration ===
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-./docker-compose-vnext.yml}"
DOCKER_IMAGE_BASE="${DOCKER_IMAGE_BASE:-server-agent-vnext}"
ROLLBACK_IMAGE="${DOCKER_IMAGE_BASE}:rollback"
CURRENT_IMAGE="${DOCKER_IMAGE_BASE}:latest"
API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-60}"
STARTUP_WAIT="${STARTUP_WAIT:-10}"
TELEGRAM_API_TOKEN="${TELEGRAM_API_TOKEN:-}"
MASTER_CHAT_ID="${MASTER_CHAT_ID:-46808774}"
DEPLOYMENT_DB_URL="${DEPLOYMENT_DB_URL:-}"

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

# === Send notification to Master ===
notify_master() {
    local message="$1"
    local priority="${2:-normal}"

    if [ -z "$TELEGRAM_API_TOKEN" ]; then
        log_warning "Telegram API token not configured, skipping notification"
        return
    fi

    # Format message with emoji prefix
    case "$priority" in
        "critical")
            message="🚨 CRITICAL 🚨\n\n$message"
            ;;
        "error")
            message="❌ ERROR ❌\n\n$message"
            ;;
        "warning")
            message="⚠️ WARNING ⚠️\n\n$message"
            ;;
        "success")
            message="✅ SUCCESS ✅\n\n$message"
            ;;
    esac

    curl -X POST "https://api.telegram.org/bot${TELEGRAM_API_TOKEN}/sendMessage" \
        -d "chat_id=${MASTER_CHAT_ID}" \
        -d "text=$(echo -e "$message")" \
        -d "parse_mode=HTML" \
        2>/dev/null || log_warning "Failed to send Telegram notification"
}

log_warning "=========================================="
log_warning "INITIATING EMERGENCY ROLLBACK"
log_warning "=========================================="

# === Verify rollback image exists ===
log_info "Checking if rollback image exists: $ROLLBACK_IMAGE"

if ! docker image inspect "$ROLLBACK_IMAGE" > /dev/null 2>&1; then
    log_error "Rollback image not found: $ROLLBACK_IMAGE"
    log_info "Available images:"
    docker images | grep "$DOCKER_IMAGE_BASE" || echo "  None found"
    notify_master "Rollback image not available!\n\nImage: $ROLLBACK_IMAGE\n\nPlease restore manually." "critical"
    exit 1
fi

log_success "Rollback image found"

# === Update deployment record (building) ===
if [ -n "$DEPLOYMENT_DB_URL" ]; then
    log_info "Updating deployment status: rolling_back"
    # This would be done via API or direct DB access
fi

# === Stop current containers ===
log_info "Stopping current containers..."

if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    if docker compose -f "$DOCKER_COMPOSE_FILE" down 2>&1; then
        log_success "Containers stopped successfully"
    else
        log_error "Failed to stop containers"
        notify_master "Failed to stop containers during rollback\n\nPlease check server manually." "critical"
        exit 1
    fi
else
    log_warning "Docker compose file not found: $DOCKER_COMPOSE_FILE"
    log_info "Attempting to stop containers by name..."

    docker stop server_agent_vnext_app 2>/dev/null || log_warning "app container not found"
    docker stop server_agent_vnext_postgres 2>/dev/null || log_warning "postgres container not found"
fi

# === Update image reference ===
log_info "Updating deployment to use rollback image..."

# Create a temporary docker-compose file with rollback image
if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    TEMP_COMPOSE=$(mktemp)
    sed "s|image: ${DOCKER_IMAGE_BASE}:latest|image: ${ROLLBACK_IMAGE}|g" "$DOCKER_COMPOSE_FILE" > "$TEMP_COMPOSE"

    # Start with rollback image
    log_info "Starting containers with rollback image..."
    if docker compose -f "$TEMP_COMPOSE" up -d 2>&1; then
        log_success "Containers started with rollback image"
        rm -f "$TEMP_COMPOSE"
    else
        log_error "Failed to start containers with rollback image"
        rm -f "$TEMP_COMPOSE"
        notify_master "Failed to start rollback containers\n\nPlease check Docker and server logs manually." "critical"
        exit 1
    fi
else
    log_warning "Cannot update image reference without docker-compose file"
fi

# === Wait for containers to start ===
log_info "Waiting ${STARTUP_WAIT}s for containers to start..."
sleep "$STARTUP_WAIT"

# === Run smoke tests ===
log_info "=========================================="
log_info "Running smoke tests on rollback..."
log_info "=========================================="

if [ -f "scripts/smoke_test.sh" ]; then
    if bash scripts/smoke_test.sh 2>&1; then
        log_success "Smoke tests passed - rollback successful!"

        # Update deployment record
        log_info "Updating deployment status: rolled_back"
        notify_master "✅ <b>Rollback Successful</b>\n\nSystem has been restored to previous version.\n\nPlease verify application status." "success"

        log_success "Rollback completed successfully"
        exit 0
    else
        log_error "Smoke tests failed - rollback verification failed"
        notify_master "🚨 <b>CRITICAL: Rollback Failed</b>\n\nSmoke tests failed on rollback image.\n\n<b>URGENT ACTION REQUIRED:</b> Please investigate manually.\n\nServer may be in unstable state." "critical"
        exit 1
    fi
else
    log_warning "Smoke test script not found, skipping validation"
    log_warning "Assuming rollback is successful"
    notify_master "Rollback executed but smoke tests unavailable.\n\nPlease verify system manually." "warning"
    exit 0
fi
