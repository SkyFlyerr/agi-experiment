#!/bin/bash

################################################################################
# run_tests.sh - Test Runner with Coverage
#
# Runs comprehensive test suite:
# - Unit tests (tests/unit/)
# - Integration tests (tests/integration/)
# - Smoke tests (tests/smoke/)
# Generates coverage report and exit codes based on test results
################################################################################

set -e  # Exit on any error

# === Configuration ===
PROJECT_ROOT="${1:-.}"
COVERAGE_THRESHOLD="${2:-70}"
VERBOSE="${VERBOSE:-false}"

# === Colors for output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
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

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# === Test counters ===
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# === Change to project root ===
cd "$PROJECT_ROOT"
log_info "Running tests in: $(pwd)"

# === Verify pytest is available ===
if ! command -v pytest &> /dev/null; then
    log_error "pytest is not installed"
    exit 1
fi

# === Create coverage directory ===
mkdir -p coverage

# === Unit Tests ===
log_info "=========================================="
log_info "Running Unit Tests..."
log_info "=========================================="

if [ -d "tests/unit" ] && [ "$(find tests/unit -name 'test_*.py' 2>/dev/null)" ]; then
    PYTEST_ARGS="tests/unit"

    if [ "$VERBOSE" = "true" ]; then
        PYTEST_ARGS="$PYTEST_ARGS -vv"
    fi

    if pytest $PYTEST_ARGS \
        --cov=app \
        --cov-report=term-missing \
        --cov-report=html:coverage/unit_coverage \
        --junit-xml=coverage/unit_results.xml \
        --tb=short; then
        log_success "Unit tests passed"
        ((TESTS_PASSED++))
    else
        log_error "Unit tests failed"
        ((TESTS_FAILED++))
    fi
else
    log_warning "No unit tests found in tests/unit/"
    ((TESTS_SKIPPED++))
fi

# === Integration Tests ===
log_info "=========================================="
log_info "Running Integration Tests..."
log_info "=========================================="

if [ -d "tests/integration" ] && [ "$(find tests/integration -name 'test_*.py' 2>/dev/null)" ]; then
    PYTEST_ARGS="tests/integration"

    if [ "$VERBOSE" = "true" ]; then
        PYTEST_ARGS="$PYTEST_ARGS -vv"
    fi

    if pytest $PYTEST_ARGS \
        --cov=app \
        --cov-report=term-missing \
        --cov-report=html:coverage/integration_coverage \
        --cov-append \
        --junit-xml=coverage/integration_results.xml \
        --tb=short; then
        log_success "Integration tests passed"
        ((TESTS_PASSED++))
    else
        log_error "Integration tests failed"
        ((TESTS_FAILED++))
    fi
else
    log_warning "No integration tests found in tests/integration/"
    ((TESTS_SKIPPED++))
fi

# === Smoke Tests ===
log_info "=========================================="
log_info "Running Smoke Tests..."
log_info "=========================================="

if [ -d "tests/smoke" ] && [ "$(find tests/smoke -name 'test_*.py' 2>/dev/null)" ]; then
    PYTEST_ARGS="tests/smoke"

    if [ "$VERBOSE" = "true" ]; then
        PYTEST_ARGS="$PYTEST_ARGS -vv"
    fi

    if pytest $PYTEST_ARGS \
        --cov=app \
        --cov-report=term-missing \
        --cov-report=html:coverage/smoke_coverage \
        --cov-append \
        --junit-xml=coverage/smoke_results.xml \
        --tb=short; then
        log_success "Smoke tests passed"
        ((TESTS_PASSED++))
    else
        log_error "Smoke tests failed"
        ((TESTS_FAILED++))
    fi
else
    log_warning "No smoke tests found in tests/smoke/"
    ((TESTS_SKIPPED++))
fi

# === All Tests ===
log_info "=========================================="
log_info "Running All Tests with Coverage..."
log_info "=========================================="

PYTEST_ARGS="tests"
if [ "$VERBOSE" = "true" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -vv"
fi

if pytest $PYTEST_ARGS \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:coverage/all_coverage \
    --cov-report=term \
    --cov-fail-under=$COVERAGE_THRESHOLD \
    --junit-xml=coverage/all_results.xml \
    --tb=short 2>&1 | tee coverage/test_output.log; then
    COVERAGE_EXIT=0
    log_success "All tests passed with coverage ≥ ${COVERAGE_THRESHOLD}%"
else
    COVERAGE_EXIT=$?
    if [ $COVERAGE_EXIT -eq 5 ]; then
        log_warning "Test collection error - continuing anyway"
        COVERAGE_EXIT=0
    elif grep -q "failed to meet the minimum coverage" coverage/test_output.log; then
        log_error "Coverage below ${COVERAGE_THRESHOLD}% threshold"
    else
        log_error "Tests failed (exit code: $COVERAGE_EXIT)"
    fi
fi

# === Generate Coverage Report ===
log_info "=========================================="
log_info "Coverage Report"
log_info "=========================================="

if [ -f "coverage/.coverage" ]; then
    log_info "Coverage HTML report: coverage/all_coverage/index.html"
    log_success "Coverage data saved"
else
    log_warning "No coverage data generated"
fi

# === Summary ===
log_info "=========================================="
log_info "Test Summary"
log_info "=========================================="

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
echo ""
echo "  Passed:  $TESTS_PASSED"
echo "  Failed:  $TESTS_FAILED"
echo "  Skipped: $TESTS_SKIPPED"
echo "  Total:   $TOTAL_TESTS"
echo ""

# === Determine exit code ===
if [ $TESTS_FAILED -gt 0 ]; then
    log_error "Test execution failed"
    exit 1
elif [ $COVERAGE_EXIT -ne 0 ]; then
    log_error "Coverage check failed"
    exit 1
else
    log_success "All tests passed successfully!"
    exit 0
fi
