#!/bin/bash

# Server-Agent Setup Script

echo "🤖 Server-Agent Setup"
echo "===================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create directories
echo ""
echo "Creating data directories..."
mkdir -p data/history data/skills logs

# Check for .env file
echo ""
if [ -f .env ]; then
    echo "✅ .env file found"
else
    echo "⚠️  .env file not found"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "❗ IMPORTANT: Edit .env file with your credentials:"
    echo "   - TELEGRAM_API_TOKEN (from @BotFather)"
    echo "   - TELEGRAM_BOT_NAME"
    echo "   - MASTER_MAX_TELEGRAM_CHAT_ID (from @userinfobot)"
    echo "   - ANTHROPIC_API_KEY (from console.anthropic.com)"
    echo ""
    echo "Run: nano .env"
fi

# Test imports
echo ""
echo "Testing Python imports..."
python3 -c "
import sys
try:
    import telegram
    import anthropic
    import dotenv
    import aiofiles
    import pydantic
    print('✅ All required packages installed successfully')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file: nano .env"
    echo "2. Get Telegram bot token from @BotFather"
    echo "3. Get your chat ID from @userinfobot"
    echo "4. Get Anthropic API key from console.anthropic.com"
    echo "5. Run the agent: python src/main.py"
    echo ""
    echo "For testing individual components:"
    echo "  - Test bot: python src/telegram_bot.py"
    echo "  - Test state: python -c 'from src.state_manager import StateManager; s = StateManager(); print(s.get_session_summary())'"
else
    echo ""
    echo "❌ Setup failed. Please check error messages above."
    exit 1
fi
