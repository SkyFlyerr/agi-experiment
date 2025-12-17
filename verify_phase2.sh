#!/bin/bash
# Phase 2 Implementation Verification Script

echo "🔍 Verifying Phase 2: Telegram Webhook Ingestion Implementation"
echo "================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

MISSING_FILES=0
TOTAL_FILES=0

check_file() {
    local file=$1
    local description=$2
    TOTAL_FILES=$((TOTAL_FILES + 1))

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        echo "  └─ $file"
    else
        echo -e "${RED}✗${NC} $description"
        echo "  └─ MISSING: $file"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
}

check_dir() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $description"
        echo "  └─ $dir/"
    else
        echo -e "${RED}✗${NC} $description"
        echo "  └─ MISSING: $dir/"
    fi
}

echo "📦 Core Telegram Module (app/telegram/)"
echo "----------------------------------------"
check_file "app/telegram/__init__.py" "Package initialization"
check_file "app/telegram/bot.py" "Bot initialization and webhook setup"
check_file "app/telegram/webhook.py" "Webhook endpoint handler"
check_file "app/telegram/normalizer.py" "Update normalization"
check_file "app/telegram/media.py" "Media download and storage"
check_file "app/telegram/callbacks.py" "Callback query handling"
check_file "app/telegram/responses.py" "Message formatting and sending"
check_file "app/telegram/ingestion.py" "Ingestion pipeline"
echo ""

echo "🛣️  Routes Module (app/routes/)"
echo "----------------------------------------"
check_file "app/routes/__init__.py" "Package initialization"
check_file "app/routes/webhook.py" "FastAPI webhook router"
echo ""

echo "🧪 Test Suite (tests/)"
echo "----------------------------------------"
check_file "tests/__init__.py" "Package initialization"
check_file "tests/test_telegram.py" "Telegram webhook tests"
echo ""

echo "📝 Configuration Files"
echo "----------------------------------------"
check_file "requirements.txt" "Python dependencies"
check_file ".env.example" "Environment variables template"
check_file "app/config.py" "Application settings"
check_file "app/main.py" "FastAPI application"
echo ""

echo "📚 Documentation"
echo "----------------------------------------"
check_file "TELEGRAM_WEBHOOK_IMPLEMENTATION.md" "Implementation guide"
check_file "PHASE2_COMPLETION_SUMMARY.md" "Completion summary"
echo ""

echo "📁 Directories"
echo "----------------------------------------"
check_dir "app/telegram" "Telegram module directory"
check_dir "app/routes" "Routes module directory"
check_dir "tests" "Tests directory"
echo ""

# Check for required dependencies
echo "🔧 Dependencies Check"
echo "----------------------------------------"
if grep -q "aiogram==3.15.0" requirements.txt; then
    echo -e "${GREEN}✓${NC} aiogram 3.15.0 in requirements.txt"
else
    echo -e "${RED}✗${NC} aiogram 3.15.0 NOT FOUND in requirements.txt"
fi

if grep -q "asyncpg==0.30.0" requirements.txt; then
    echo -e "${GREEN}✓${NC} asyncpg 0.30.0 in requirements.txt"
else
    echo -e "${RED}✗${NC} asyncpg 0.30.0 NOT FOUND in requirements.txt"
fi

if grep -q "pytest==8.3.4" requirements.txt; then
    echo -e "${GREEN}✓${NC} pytest 8.3.4 in requirements.txt"
else
    echo -e "${RED}✗${NC} pytest 8.3.4 NOT FOUND in requirements.txt"
fi
echo ""

# Check environment configuration
echo "⚙️  Environment Configuration"
echo "----------------------------------------"
if grep -q "TELEGRAM_WEBHOOK_URL" .env.example; then
    echo -e "${GREEN}✓${NC} TELEGRAM_WEBHOOK_URL in .env.example"
else
    echo -e "${RED}✗${NC} TELEGRAM_WEBHOOK_URL NOT FOUND in .env.example"
fi

if grep -q "TELEGRAM_WEBHOOK_SECRET" .env.example; then
    echo -e "${GREEN}✓${NC} TELEGRAM_WEBHOOK_SECRET in .env.example"
else
    echo -e "${RED}✗${NC} TELEGRAM_WEBHOOK_SECRET NOT FOUND in .env.example"
fi
echo ""

# Count lines of code
echo "📊 Code Statistics"
echo "----------------------------------------"
if command -v wc &> /dev/null; then
    TELEGRAM_LINES=$(find app/telegram -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')
    ROUTES_LINES=$(find app/routes -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')
    TESTS_LINES=$(wc -l tests/test_telegram.py 2>/dev/null | awk '{print $1}')

    echo "  Telegram module: $TELEGRAM_LINES lines"
    echo "  Routes module: $ROUTES_LINES lines"
    echo "  Tests: $TESTS_LINES lines"
    echo "  Total: $((TELEGRAM_LINES + ROUTES_LINES + TESTS_LINES)) lines"
else
    echo -e "${YELLOW}⚠${NC} wc command not found, skipping line count"
fi
echo ""

# Final summary
echo "================================================================"
if [ $MISSING_FILES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL FILES PRESENT${NC} ($TOTAL_FILES/$TOTAL_FILES files verified)"
    echo ""
    echo "🎉 Phase 2: Telegram Webhook Ingestion - COMPLETE"
    echo ""
    echo "Next steps:"
    echo "  1. Install dependencies: pip install -r requirements.txt"
    echo "  2. Configure .env file (copy from .env.example)"
    echo "  3. Run tests: pytest tests/test_telegram.py -v"
    echo "  4. Start server: python -m app.main"
    echo "  5. Set webhook: curl -X POST http://localhost:8000/webhook/telegram"
    exit 0
else
    echo -e "${RED}❌ MISSING FILES${NC} ($MISSING_FILES files missing)"
    echo ""
    echo "Please ensure all Phase 2 files are created before proceeding."
    exit 1
fi
