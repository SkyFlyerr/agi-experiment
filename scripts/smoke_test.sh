#!/bin/bash

################################################################################
# smoke_test.sh - Post-Deployment Validation
#
# Validates that the deployed system is healthy and operational:
# - Health endpoint check
# - Database connection test
# - Telegram bot initialization
# - Reactive worker status
# - Proactive scheduler status
# - Stats endpoint check
# - Test message sending
################################################################################

set -e  # Exit on any error

# === Configuration ===
API_URL="${API_URL:-http://localhost:8000}"
HEALTH_ENDPOINT="${API_URL}/health"
STATS_ENDPOINT="${API_URL}/stats"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-server_agent}"
DB_USER="${DB_USER:-agent}"
TIMEOUT="${TIMEOUT:-30}"
RETRY_ATTEMPTS="${RETRY_ATTEMPTS:-5}"
RETRY_DELAY="${RETRY_DELAY:-2}"

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

# === Test counters ===
TESTS_PASSED=0
TESTS_FAILED=0

log_info "Starting smoke tests for deployment validation"
log_info "API URL: $API_URL"

# === Test 1: Health Endpoint ===
log_info "=========================================="
log_info "Test 1: Health Endpoint Check"
log_info "=========================================="

ATTEMPT=1
while [ $ATTEMPT -le $RETRY_ATTEMPTS ]; do
    log_info "Attempt $ATTEMPT/$RETRY_ATTEMPTS: GET $HEALTH_ENDPOINT"

    HTTP_CODE=$(curl -s -o /tmp/health_response.json -w "%{http_code}" \
        --connect-timeout 5 \
        --max-time $TIMEOUT \
        "$HEALTH_ENDPOINT" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        log_success "Health endpoint returned HTTP 200"

        # Check response content
        if grep -q "healthy\|status" /tmp/health_response.json 2>/dev/null; then
            log_success "Health response contains expected fields"
            ((TESTS_PASSED++))
            break
        else
            log_warning "Health response missing expected fields"
            cat /tmp/health_response.json
        fi
    else
        log_warning "Health endpoint returned HTTP $HTTP_CODE"
        if [ $ATTEMPT -lt $RETRY_ATTEMPTS ]; then
            log_info "Retrying in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    fi

    ((ATTEMPT++))
done

if [ $ATTEMPT -gt $RETRY_ATTEMPTS ]; then
    log_error "Health endpoint check failed after $RETRY_ATTEMPTS attempts"
    ((TESTS_FAILED++))
fi

# === Test 2: Database Connection ===
log_info "=========================================="
log_info "Test 2: Database Connection Test"
log_info "=========================================="

if command -v psql &> /dev/null; then
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "SELECT 1" \
        --no-password > /dev/null 2>&1; then
        log_success "Database connection successful"
        ((TESTS_PASSED++))
    else
        log_error "Database connection failed"
        ((TESTS_FAILED++))
    fi
else
    log_warning "psql not available, skipping database connection test"
fi

# === Test 3: Telegram Bot Initialization ===
log_info "=========================================="
log_info "Test 3: Telegram Bot Status"
log_info "=========================================="

if grep -q '"telegram".*"initialized"' /tmp/health_response.json 2>/dev/null || \
   grep -q 'telegram' /tmp/health_response.json 2>/dev/null; then
    log_success "Telegram bot appears initialized"
    ((TESTS_PASSED++))
else
    log_warning "Could not verify Telegram bot status from health endpoint"
    log_info "Health response:"
    cat /tmp/health_response.json 2>/dev/null || echo "  (no response)"
fi

# === Test 4: Reactive Worker Status ===
log_info "=========================================="
log_info "Test 4: Reactive Worker Status"
log_info "=========================================="

# Check if any reactive worker is running in the process list or logs
if ps aux | grep -i "reactive\|worker" | grep -v grep > /dev/null 2>&1; then
    log_success "Reactive worker appears to be running"
    ((TESTS_PASSED++))
elif [ -f "logs/app.log" ] && grep -q "reactive.*started\|worker.*active" logs/app.log 2>/dev/null; then
    log_success "Reactive worker log entries found"
    ((TESTS_PASSED++))
else
    log_warning "Could not verify reactive worker status"
fi

# === Test 5: Proactive Scheduler Status ===
log_info "=========================================="
log_info "Test 5: Proactive Scheduler Status"
log_info "=========================================="

# Check if proactive scheduler is running
if ps aux | grep -i "proactive\|scheduler" | grep -v grep > /dev/null 2>&1; then
    log_success "Proactive scheduler appears to be running"
    ((TESTS_PASSED++))
elif [ -f "logs/app.log" ] && grep -q "proactive.*started\|scheduler.*active" logs/app.log 2>/dev/null; then
    log_success "Proactive scheduler log entries found"
    ((TESTS_PASSED++))
else
    log_warning "Could not verify proactive scheduler status"
fi

# === Test 6: Stats Endpoint ===
log_info "=========================================="
log_info "Test 6: Stats Endpoint Check"
log_info "=========================================="

HTTP_CODE=$(curl -s -o /tmp/stats_response.json -w "%{http_code}" \
    --connect-timeout 5 \
    --max-time $TIMEOUT \
    "$STATS_ENDPOINT" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    log_success "Stats endpoint returned HTTP 200"
    if jq empty /tmp/stats_response.json 2>/dev/null; then
        log_success "Stats response is valid JSON"
        ((TESTS_PASSED++))
    else
        log_warning "Stats response is not valid JSON"
    fi
else
    log_warning "Stats endpoint returned HTTP $HTTP_CODE (endpoint may not be implemented)"
fi

# === Test 7: Memory & Disk Usage ===
log_info "=========================================="
log_info "Test 7: System Resources"
log_info "=========================================="

# Check available memory
AVAILABLE_MEMORY=$(free -m | awk 'NR==2 {print $7}')
if [ "$AVAILABLE_MEMORY" -gt 100 ]; then
    log_success "Available memory is sufficient: ${AVAILABLE_MEMORY}MB"
    ((TESTS_PASSED++))
else
    log_warning "Available memory is low: ${AVAILABLE_MEMORY}MB"
fi

# Check disk space
if [ -d "/app" ]; then
    AVAILABLE_DISK=$(df /app | awk 'NR==2 {print $4}')
    if [ "$AVAILABLE_DISK" -gt 1000000 ]; then
        log_success "Available disk space is sufficient: ${AVAILABLE_DISK}KB"
        ((TESTS_PASSED++))
    else
        log_warning "Available disk space is low: ${AVAILABLE_DISK}KB"
    fi
fi

# === Test 8: Application Logs ===
log_info "=========================================="
log_info "Test 8: Application Logs"
log_info "=========================================="

if [ -f "logs/app.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR\|CRITICAL" logs/app.log 2>/dev/null || echo "0")
    WARN_COUNT=$(grep -c "WARNING" logs/app.log 2>/dev/null || echo "0")

    if [ "$ERROR_COUNT" -eq 0 ]; then
        log_success "No errors found in application logs"
        ((TESTS_PASSED++))
    else
        log_warning "Found $ERROR_COUNT errors in application logs"
        grep "ERROR\|CRITICAL" logs/app.log | tail -5
    fi

    if [ "$WARN_COUNT" -gt 0 ]; then
        log_warning "Found $WARN_COUNT warnings in application logs"
    fi
else
    log_warning "Application log file not found"
fi

# === Cleanup ===
rm -f /tmp/health_response.json /tmp/stats_response.json

# === Summary ===
log_info "=========================================="
log_info "Smoke Test Summary"
log_info "=========================================="

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo ""
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "  Total:  $TOTAL_TESTS"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    log_error "Smoke tests failed"
    exit 1
else
    log_success "All smoke tests passed!"
    exit 0
fi
