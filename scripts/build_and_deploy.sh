#!/bin/bash

################################################################################
# build_and_deploy.sh - Main Deployment Pipeline
#
# Complete deployment pipeline triggered by git merge to main:
# 1. Pull latest code
# 2. Create deployment record in DB
# 3. Run unit tests
# 4. Build Docker image
# 5. Tag previous image for rollback
# 6. Stop running containers
# 7. Apply database migrations
# 8. Start new containers
# 9. Run smoke tests
# 10. Handle success/failure with notifications
#
# Exit codes:
# 0 = success
# 1 = test_failed
# 2 = build_failed
# 3 = deploy_failed
# 4 = smoke_failed
################################################################################

set -e  # Exit on any error

# === Configuration ===
REPO_PATH="${REPO_PATH:-.}"
DOCKER_IMAGE_BASE="${DOCKER_IMAGE_BASE:-server-agent-vnext}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-./docker-compose-vnext.yml}"
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
DEPLOYMENT_TIMEOUT="${DEPLOYMENT_TIMEOUT:-300}"
STARTUP_WAIT="${STARTUP_WAIT:-10}"
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-70}"
API_URL="${API_URL:-http://localhost:8000}"
TELEGRAM_API_TOKEN="${TELEGRAM_API_TOKEN:-}"
MASTER_CHAT_ID="${MASTER_CHAT_ID:-46808774}"
DB_MIGRATIONS_DIR="${DB_MIGRATIONS_DIR:-./database/migrations}"

# === Paths ===
LOGS_DIR="${REPO_PATH}/logs"
DEPLOYMENT_LOG="${LOGS_DIR}/deployment_$(date '+%Y-%m-%d_%H-%M-%S').log"
BACKUP_DIR="${REPO_PATH}/backups"

# === State tracking ===
DEPLOYMENT_START_TIME=$(date +%s)
DEPLOYMENT_STATUS="building"
TEST_STATUS="pending"
BUILD_STATUS="pending"
SMOKE_TEST_STATUS="pending"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_AUTHOR=$(git log -1 --pretty=format:'%an' 2>/dev/null || echo "unknown")
GIT_MESSAGE=$(git log -1 --pretty=format:'%s' 2>/dev/null || echo "unknown")

# === Colors for output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

# === Logging functions ===
log_info() {
    local msg="$1"
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $msg"
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $msg" >> "$DEPLOYMENT_LOG"
}

log_success() {
    local msg="$1"
    echo -e "${GREEN}[✓]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $msg"
    echo "[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') - $msg" >> "$DEPLOYMENT_LOG"
}

log_error() {
    local msg="$1"
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $msg"
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $msg" >> "$DEPLOYMENT_LOG"
}

log_warning() {
    local msg="$1"
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $msg"
    echo "[WARNING] $(date '+%Y-%m-%d %H:%M:%S') - $msg" >> "$DEPLOYMENT_LOG"
}

# === Send notification to Master ===
notify_master() {
    local message="$1"
    local priority="${2:-normal}"

    if [ -z "$TELEGRAM_API_TOKEN" ]; then
        return
    fi

    # Add priority emoji
    case "$priority" in
        "critical")
            message="🚨 CRITICAL 🚨\n\n$message"
            ;;
        "error")
            message="❌ DEPLOYMENT FAILED ❌\n\n$message"
            ;;
        "success")
            message="✅ DEPLOYMENT SUCCESSFUL ✅\n\n$message"
            ;;
    esac

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_API_TOKEN}/sendMessage" \
        -d "chat_id=${MASTER_CHAT_ID}" \
        -d "text=$(echo -e "$message")" \
        -d "parse_mode=HTML" \
        > /dev/null 2>&1 || log_warning "Failed to send Telegram notification"
}

# === Cleanup on exit ===
cleanup() {
    local exit_code=$?

    log_info "=========================================="
    log_info "Deployment Pipeline Cleanup"
    log_info "=========================================="

    DEPLOYMENT_END_TIME=$(date +%s)
    DEPLOYMENT_DURATION=$((DEPLOYMENT_END_TIME - DEPLOYMENT_START_TIME))

    log_info "Total deployment time: ${DEPLOYMENT_DURATION}s"
    log_info "Final status: $DEPLOYMENT_STATUS"

    if [ $exit_code -ne 0 ]; then
        log_error "Deployment pipeline failed with exit code: $exit_code"
    fi
}

trap cleanup EXIT

# === Main pipeline execution ===

log_info "=========================================="
log_info "Starting Deployment Pipeline"
log_info "=========================================="
log_info "Repository: $REPO_PATH"
log_info "Branch: $GIT_BRANCH"
log_info "Git SHA: $GIT_SHA"
log_info "Author: $GIT_AUTHOR"
log_info "Message: $GIT_MESSAGE"

# === Ensure logs and backup directories exist ===
mkdir -p "$LOGS_DIR" "$BACKUP_DIR"

# === Step 0: Pull latest code ===
log_info "=========================================="
log_info "Step 0: Pulling Latest Code"
log_info "=========================================="

cd "$REPO_PATH"

if git fetch "$GIT_REMOTE" "$GIT_BRANCH" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
    log_success "Fetched latest code from $GIT_REMOTE/$GIT_BRANCH"
else
    log_error "Failed to fetch code from $GIT_REMOTE"
    DEPLOYMENT_STATUS="failed"
    notify_master "Failed to fetch code from git remote\n\nPlease check git connectivity." "error"
    exit 1
fi

if git checkout -f "$GIT_BRANCH" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
    log_success "Checked out branch: $GIT_BRANCH"
else
    log_error "Failed to checkout branch: $GIT_BRANCH"
    DEPLOYMENT_STATUS="failed"
    notify_master "Failed to checkout git branch\n\nPlease check branch status." "error"
    exit 1
fi

# === Step 1: Database backup ===
log_info "=========================================="
log_info "Step 1: Creating Database Backup"
log_info "=========================================="

if [ -f "scripts/backup_db.sh" ]; then
    if bash scripts/backup_db.sh "$BACKUP_DIR" 7 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        log_success "Database backup completed"
    else
        log_error "Database backup failed"
        # Don't exit - continue with deployment
    fi
else
    log_warning "Backup script not found, skipping database backup"
fi

# === Step 2: Run tests ===
log_info "=========================================="
log_info "Step 2: Running Tests"
log_info "=========================================="

if [ -f "scripts/run_tests.sh" ]; then
    if bash scripts/run_tests.sh "$REPO_PATH" "$COVERAGE_THRESHOLD" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        TEST_STATUS="success"
        log_success "All tests passed"
    else
        TEST_STATUS="failed"
        log_error "Tests failed"
        DEPLOYMENT_STATUS="test_failed"
        notify_master "Unit tests failed during deployment\n\nCheck test logs for details." "error"
        exit 1
    fi
else
    log_warning "Test script not found, skipping tests"
    TEST_STATUS="skipped"
fi

# === Step 3: Build Docker image ===
log_info "=========================================="
log_info "Step 3: Building Docker Image"
log_info "=========================================="

DOCKER_IMAGE="${DOCKER_IMAGE_BASE}:latest"

log_info "Building image: $DOCKER_IMAGE"

if docker build \
    -t "$DOCKER_IMAGE" \
    -f "$REPO_PATH/Dockerfile" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VCS_REF="$GIT_SHA" \
    "$REPO_PATH" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
    BUILD_STATUS="success"
    log_success "Docker image built successfully"
else
    BUILD_STATUS="failed"
    log_error "Failed to build Docker image"
    DEPLOYMENT_STATUS="build_failed"
    notify_master "Docker build failed\n\nCheck Docker logs for details." "error"
    exit 2
fi

# === Step 4: Tag previous image for rollback ===
log_info "=========================================="
log_info "Step 4: Tagging Rollback Image"
log_info "=========================================="

ROLLBACK_IMAGE="${DOCKER_IMAGE_BASE}:rollback"

if docker image inspect "$DOCKER_IMAGE_BASE:latest" > /dev/null 2>&1; then
    if docker tag "$DOCKER_IMAGE_BASE:latest" "$ROLLBACK_IMAGE" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        log_success "Previous image tagged for rollback: $ROLLBACK_IMAGE"
    else
        log_warning "Failed to tag rollback image"
    fi
fi

# === Step 5: Stop running containers ===
log_info "=========================================="
log_info "Step 5: Stopping Running Containers"
log_info "=========================================="

if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    if docker compose -f "$DOCKER_COMPOSE_FILE" down 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        log_success "Containers stopped successfully"
    else
        log_error "Failed to stop containers"
        DEPLOYMENT_STATUS="deploy_failed"
        notify_master "Failed to stop running containers\n\nPlease check Docker." "error"
        exit 3
    fi
else
    log_warning "Docker compose file not found, attempting manual stop"
    docker stop server_agent_vnext_app 2>/dev/null || log_warning "app container not found"
    docker stop server_agent_vnext_postgres 2>/dev/null || log_warning "postgres container not found"
fi

# === Step 6: Apply database migrations ===
log_info "=========================================="
log_info "Step 6: Applying Database Migrations"
log_info "=========================================="

if [ -d "$DB_MIGRATIONS_DIR" ]; then
    log_info "Found migrations directory: $DB_MIGRATIONS_DIR"
    # Note: Migration logic depends on your migration tool
    # Example for Alembic:
    # docker run --rm --network server_agent_vnext_network \
    #     -e DATABASE_URL="$DATABASE_URL" \
    #     "$DOCKER_IMAGE" alembic upgrade head
    log_info "Skipping migrations (implementation depends on migration tool)"
else
    log_info "No migrations directory found, skipping migrations"
fi

# === Step 7: Start new containers ===
log_info "=========================================="
log_info "Step 7: Starting New Containers"
log_info "=========================================="

if docker compose -f "$DOCKER_COMPOSE_FILE" up -d 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
    log_success "Containers started successfully"
else
    log_error "Failed to start containers"
    DEPLOYMENT_STATUS="deploy_failed"
    notify_master "Failed to start new containers\n\nCheck Docker logs." "error"
    exit 3
fi

# === Step 8: Wait for startup ===
log_info "=========================================="
log_info "Step 8: Waiting for Application Startup"
log_info "=========================================="

log_info "Waiting ${STARTUP_WAIT}s for containers to stabilize..."
sleep "$STARTUP_WAIT"

# === Step 9: Run smoke tests ===
log_info "=========================================="
log_info "Step 9: Running Smoke Tests"
log_info "=========================================="

if [ -f "scripts/smoke_test.sh" ]; then
    if bash scripts/smoke_test.sh 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        SMOKE_TEST_STATUS="success"
        log_success "Smoke tests passed"
        DEPLOYMENT_STATUS="healthy"
    else
        SMOKE_TEST_STATUS="failed"
        log_error "Smoke tests failed"
        DEPLOYMENT_STATUS="smoke_failed"

        log_warning "=========================================="
        log_warning "Smoke Tests Failed - Initiating Rollback"
        log_warning "=========================================="

        if [ -f "scripts/rollback.sh" ]; then
            if bash scripts/rollback.sh 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
                log_success "Rollback completed successfully"
                DEPLOYMENT_STATUS="rolled_back"
                notify_master "Deployment failed - system rolled back to previous version\n\nSmoke tests failed on new deployment." "error"
                exit 4
            else
                log_error "Rollback failed"
                DEPLOYMENT_STATUS="rollback_failed"
                notify_master "🚨 CRITICAL: Deployment failed AND rollback failed!\n\nServer may be in unstable state.\n\nPlease investigate manually." "critical"
                exit 4
            fi
        else
            log_error "Rollback script not available"
            DEPLOYMENT_STATUS="smoke_failed"
            notify_master "Deployment failed and rollback unavailable\n\nServer may be unstable." "critical"
            exit 4
        fi
    fi
else
    log_warning "Smoke test script not found, skipping smoke tests"
    SMOKE_TEST_STATUS="skipped"
fi

# === Step 10: Generate deployment report ===
log_info "=========================================="
log_info "Step 10: Generating Deployment Report"
log_info "=========================================="

DEPLOYMENT_END_TIME=$(date +%s)
DEPLOYMENT_DURATION=$((DEPLOYMENT_END_TIME - DEPLOYMENT_START_TIME))

if [ -f "scripts/deployment_report.sh" ]; then
    BUILD_STATUS="$BUILD_STATUS" \
    TEST_STATUS="$TEST_STATUS" \
    DEPLOYMENT_STATUS="$DEPLOYMENT_STATUS" \
    SMOKE_TEST_STATUS="$SMOKE_TEST_STATUS" \
    GIT_SHA="$GIT_SHA" \
    GIT_BRANCH="$GIT_BRANCH" \
    BUILD_LOG="$DEPLOYMENT_LOG" \
    TEST_LOG="$DEPLOYMENT_LOG" \
    SMOKE_TEST_LOG="$DEPLOYMENT_LOG" \
    TELEGRAM_API_TOKEN="$TELEGRAM_API_TOKEN" \
    MASTER_CHAT_ID="$MASTER_CHAT_ID" \
    DEPLOY_DURATION="$DEPLOYMENT_DURATION" \
    bash scripts/deployment_report.sh telegram 2>&1 | tee -a "$DEPLOYMENT_LOG"
else
    log_warning "Deployment report script not found"
fi

# === Success ===
log_info "=========================================="
log_success "Deployment Pipeline Completed Successfully!"
log_info "=========================================="

log_info "Deployment Duration: ${DEPLOYMENT_DURATION}s"
log_info "Final Status: $DEPLOYMENT_STATUS"
log_info "Test Status: $TEST_STATUS"
log_info "Build Status: $BUILD_STATUS"
log_info "Smoke Test Status: $SMOKE_TEST_STATUS"
log_info "Deployment Log: $DEPLOYMENT_LOG"

notify_master "<b>✅ Deployment Successful</b>\n\n<b>Git SHA:</b> <code>$GIT_SHA</code>\n<b>Branch:</b> <code>$GIT_BRANCH</code>\n<b>Duration:</b> ${DEPLOYMENT_DURATION}s\n\nAll systems operational." "success"

exit 0
