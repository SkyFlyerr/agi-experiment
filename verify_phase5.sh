#!/bin/bash
# Verification script for Phase 5 implementation

echo "=== Phase 5: Proactive Scheduler Verification ==="
echo ""

# Check required files exist
files=(
    "app/ai/__init__.py"
    "app/ai/budget.py"
    "app/ai/client.py"
    "app/ai/proactive_prompts.py"
    "app/workers/__init__.py"
    "app/workers/decision_engine.py"
    "app/workers/proactive.py"
    "app/actions/__init__.py"
    "app/actions/develop_skill.py"
    "app/actions/work_on_task.py"
    "app/actions/communicate.py"
    "app/actions/meditate.py"
    "app/actions/ask_master.py"
    "app/memory/__init__.py"
    "app/memory/writeback.py"
    "tests/test_proactive.py"
    "tests/test_actions.py"
)

echo "Checking required files..."
missing=0
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ $file (MISSING)"
        missing=$((missing + 1))
    fi
done

echo ""
if [ $missing -eq 0 ]; then
    echo "✅ All files present!"
else
    echo "❌ $missing files missing"
    exit 1
fi

# Check Python syntax
echo ""
echo "Checking Python syntax..."
python3 -m py_compile app/ai/*.py app/workers/decision_engine.py app/workers/proactive.py app/actions/*.py app/memory/*.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ All Python files compile successfully!"
else
    echo "❌ Syntax errors found"
    exit 1
fi

# Count lines of code
echo ""
echo "Lines of code:"
echo "  AI modules:      $(find app/ai -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')"
echo "  Workers:         $(find app/workers -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')"
echo "  Actions:         $(find app/actions -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')"
echo "  Memory:          $(find app/memory -name "*.py" -exec wc -l {} + | tail -1 | awk '{print $1}')"
echo "  Tests:           $(wc -l tests/test_proactive.py tests/test_actions.py | tail -1 | awk '{print $1}')"

echo ""
echo "=== Phase 5 Implementation Complete ==="
echo ""
echo "Next steps:"
echo "1. Review PHASE_5_IMPLEMENTATION.md for full documentation"
echo "2. Set environment variables (CLAUDE_CODE_OAUTH_TOKEN, etc.)"
echo "3. Run tests: pytest tests/test_proactive.py tests/test_actions.py -v"
echo "4. Start server: docker compose up -d"
echo "5. Monitor logs: docker compose logs -f app"
echo ""
echo "Philosophy: Atmano moksartha jagat hitaya ca"
echo "           (For self-realization and service to the world)"
