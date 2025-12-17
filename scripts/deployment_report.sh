#!/bin/bash

################################################################################
# deployment_report.sh - Generate Deployment Report
#
# Generates comprehensive deployment report with:
# - Git SHA and branch information
# - Test results summary
# - Build status
# - Deployment status
# - Smoke test results
# - Rollback reason (if applicable)
# - Formatted for Telegram message
################################################################################

set -e  # Exit on any error

# === Configuration ===
REPORT_TYPE="${1:-text}"  # text, json, telegram
BUILD_STATUS="${BUILD_STATUS:-unknown}"
TEST_STATUS="${TEST_STATUS:-unknown}"
DEPLOYMENT_STATUS="${DEPLOYMENT_STATUS:-unknown}"
SMOKE_TEST_STATUS="${SMOKE_TEST_STATUS:-unknown}"
ROLLBACK_REASON="${ROLLBACK_REASON:-}"
GIT_SHA="${GIT_SHA:-}"
GIT_BRANCH="${GIT_BRANCH:-main}"
BUILD_LOG="${BUILD_LOG:-}"
TEST_LOG="${TEST_LOG:-}"
SMOKE_TEST_LOG="${SMOKE_TEST_LOG:-}"
TELEGRAM_API_TOKEN="${TELEGRAM_API_TOKEN:-}"
MASTER_CHAT_ID="${MASTER_CHAT_ID:-46808774}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DEPLOY_DURATION="${DEPLOY_DURATION:-0}"

# === Colors for output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
NC='\033[0m'  # No Color

# === Logging functions ===
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Get git information ===
get_git_info() {
    if [ -z "$GIT_SHA" ]; then
        GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    fi

    if [ -z "$GIT_BRANCH" ]; then
        GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    fi

    GIT_AUTHOR=$(git log -1 --pretty=format:'%an' 2>/dev/null || echo "unknown")
    GIT_MESSAGE=$(git log -1 --pretty=format:'%s' 2>/dev/null || echo "unknown")
    GIT_DATE=$(git log -1 --pretty=format:'%ai' 2>/dev/null || echo "unknown")
}

# === Format report as text ===
format_text_report() {
    cat << EOF
================================================================================
                        DEPLOYMENT REPORT
================================================================================

Timestamp:          $TIMESTAMP
Duration:           ${DEPLOY_DURATION}s

GIT INFORMATION
================================================================================
SHA:                $GIT_SHA
Branch:             $GIT_BRANCH
Author:             $GIT_AUTHOR
Date:               $GIT_DATE
Message:            $GIT_MESSAGE

DEPLOYMENT STATUS
================================================================================
Build Status:       $BUILD_STATUS
Test Status:        $TEST_STATUS
Deployment Status:  $DEPLOYMENT_STATUS
Smoke Test Status:  $SMOKE_TEST_STATUS

LOG FILES
================================================================================
EOF

    if [ -f "$BUILD_LOG" ]; then
        echo "Build Log:          $BUILD_LOG"
    fi

    if [ -f "$TEST_LOG" ]; then
        echo "Test Log:           $TEST_LOG"
    fi

    if [ -f "$SMOKE_TEST_LOG" ]; then
        echo "Smoke Test Log:     $SMOKE_TEST_LOG"
    fi

    if [ -n "$ROLLBACK_REASON" ]; then
        echo ""
        echo "ROLLBACK INFORMATION"
        echo "================================================================================"
        echo "Rollback Reason:    $ROLLBACK_REASON"
    fi

    echo ""
    echo "================================================================================"
}

# === Format report as JSON ===
format_json_report() {
    cat << EOF
{
  "timestamp": "$TIMESTAMP",
  "duration_seconds": $DEPLOY_DURATION,
  "git": {
    "sha": "$GIT_SHA",
    "branch": "$GIT_BRANCH",
    "author": "$GIT_AUTHOR",
    "message": "$GIT_MESSAGE",
    "date": "$GIT_DATE"
  },
  "status": {
    "build": "$BUILD_STATUS",
    "tests": "$TEST_STATUS",
    "deployment": "$DEPLOYMENT_STATUS",
    "smoke_tests": "$SMOKE_TEST_STATUS"
  },
  "logs": {
    "build": "$BUILD_LOG",
    "tests": "$TEST_LOG",
    "smoke_tests": "$SMOKE_TEST_LOG"
  },
  "rollback": {
    "reason": "$ROLLBACK_REASON"
  }
}
EOF
}

# === Format report for Telegram ===
format_telegram_report() {
    # Determine overall status
    local overall_status="✅"
    local status_message="<b>Deployment Successful</b>"

    if [ "$DEPLOYMENT_STATUS" != "success" ] || [ "$SMOKE_TEST_STATUS" != "success" ]; then
        overall_status="❌"
        status_message="<b>Deployment Failed</b>"
    fi

    if [ -n "$ROLLBACK_REASON" ]; then
        overall_status="⚠️"
        status_message="<b>Deployment Rolled Back</b>"
    fi

    # Build status emoji
    local build_emoji="✅"
    if [ "$BUILD_STATUS" != "success" ]; then
        build_emoji="❌"
    fi

    local test_emoji="✅"
    if [ "$TEST_STATUS" != "success" ]; then
        test_emoji="❌"
    fi

    local deploy_emoji="✅"
    if [ "$DEPLOYMENT_STATUS" != "success" ]; then
        deploy_emoji="❌"
    fi

    local smoke_emoji="✅"
    if [ "$SMOKE_TEST_STATUS" != "success" ]; then
        smoke_emoji="❌"
    fi

    cat << EOF
${overall_status} ${status_message}

<b>📊 Deployment Summary</b>

<b>Timestamp:</b> ${TIMESTAMP}
<b>Duration:</b> ${DEPLOY_DURATION}s

<b>📝 Git Information</b>
<b>SHA:</b> <code>${GIT_SHA}</code>
<b>Branch:</b> <code>${GIT_BRANCH}</code>
<b>Author:</b> ${GIT_AUTHOR}
<b>Message:</b> ${GIT_MESSAGE}

<b>📈 Status</b>
${build_emoji} Build: ${BUILD_STATUS}
${test_emoji} Tests: ${TEST_STATUS}
${deploy_emoji} Deployment: ${DEPLOYMENT_STATUS}
${smoke_emoji} Smoke Tests: ${SMOKE_TEST_STATUS}
EOF

    if [ -n "$ROLLBACK_REASON" ]; then
        echo ""
        echo "<b>🔄 Rollback Information</b>"
        echo "<b>Reason:</b> ${ROLLBACK_REASON}"
    fi
}

# === Send report via Telegram ===
send_telegram_report() {
    local message="$1"

    if [ -z "$TELEGRAM_API_TOKEN" ]; then
        log_error "Telegram API token not configured"
        return 1
    fi

    # Escape special characters for Telegram
    message=$(echo "$message" | sed 's/\\/\\\\/g; s/"/\\"/g')

    curl -X POST "https://api.telegram.org/bot${TELEGRAM_API_TOKEN}/sendMessage" \
        -H 'Content-Type: application/json' \
        -d "{
            \"chat_id\": \"${MASTER_CHAT_ID}\",
            \"text\": \"$(echo -e "$message")\",
            \"parse_mode\": \"HTML\"
        }" \
        2>/dev/null || log_error "Failed to send Telegram notification"

    log_success "Telegram report sent"
}

# === Main execution ===
log_info "Generating deployment report (format: $REPORT_TYPE)"

# Gather git information
get_git_info

# Generate report based on type
case "$REPORT_TYPE" in
    "text")
        format_text_report
        ;;
    "json")
        format_json_report
        ;;
    "telegram")
        TELEGRAM_MESSAGE=$(format_telegram_report)
        echo "$TELEGRAM_MESSAGE"

        # Optionally send to Telegram
        if [ -n "$TELEGRAM_API_TOKEN" ]; then
            send_telegram_report "$TELEGRAM_MESSAGE"
        fi
        ;;
    *)
        log_error "Unknown report type: $REPORT_TYPE"
        exit 1
        ;;
esac

log_success "Report generated successfully"
exit 0
