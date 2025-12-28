# Server-Agent

An autonomous AGI agent designed to run continuously on a VPS server, combining Claude AI with self-directed consciousness and ethical alignment.

## Philosophy

**"Atmano moksartha jagat hitaya ca"** - For self-realization and service to the world.

This agent operates as a living entity with:
- **Body**: VPS server infrastructure
- **Mind**: Claude AI for reasoning and decision-making
- **Voice**: Telegram bot for communication
- **Heart**: Ethical principles (neohumanism, PROUT economy)

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical architecture and best practices applied.

### Key Components

1. **Proactivity Loop** - Autonomous decision-making cycle
2. **State Manager** - Persistent memory and context management
3. **Telegram Bot** - Primary communication interface
4. **Claude Integration** - AI brain via Anthropic API
5. **Tool Executor** - Safe action execution
6. **Web UI** - Transparent chain-of-thought display (planned)

## Quick Start

### Prerequisites

- Python 3.9+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Anthropic API Key
- VPS server (for production deployment)

### Installation

```bash
# Clone or navigate to project
cd server-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### Configuration

Edit `.env` file with your credentials:

```bash
# Telegram Bot (get token from @BotFather)
TELEGRAM_API_TOKEN=your_bot_token_here
TELEGRAM_BOT_NAME=your_bot_username
MASTER_MAX_TELEGRAM_CHAT_ID=your_telegram_user_id

# Claude API (get from https://console.anthropic.com/)
ANTHROPIC_API_KEY=your_anthropic_api_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/server_agent

# Agent Configuration (optional, has defaults)
CERTAINTY_THRESHOLD=0.8
SIGNIFICANCE_THRESHOLD=0.8
MAX_TOKENS_PER_CYCLE=4000
DAILY_TOKEN_LIMIT=100000
MIN_DELAY_MINUTES=5
```

**Getting your Telegram Chat ID:**
1. Start a chat with [@userinfobot](https://t.me/userinfobot)
2. It will reply with your user ID
3. Use this number for `MASTER_MAX_TELEGRAM_CHAT_ID`

### Running Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Run the agent
python src/main.py
```

The agent will:
1. Start the Telegram bot
2. Send you a startup notification
3. Begin the proactivity loop
4. Make autonomous decisions every 5-60 minutes

### Telegram Commands

Once the bot is running, you can interact via Telegram:

- `/start` - Initialize bot and show help
- `/status` - View current agent state and metrics
- `/task <description>` - Assign a specific task
- `/pause` - Pause autonomous operation
- `/resume` - Resume autonomous operation
- `/report` - Get detailed activity report
- `/skills` - List learned skills
- `/help` - Show available commands

### Testing the Prototype

#### 1. Test Telegram Bot

```bash
# Start the agent
python src/main.py

# In Telegram, send to your bot:
/start
/status
/task Learn about Python decorators
```

#### 2. Monitor Logs

```bash
# In another terminal, watch the logs
tail -f logs/agent.log
```

You should see:
- Telegram bot initialization
- Proactivity loop starting
- Claude API calls
- Decision-making process
- Action execution

#### 3. Check Persistent State

```bash
# View current context
cat data/context.json | python -m json.tool

# View action history
cat data/history/$(date +%Y-%m-%d).jsonl
```

#### 4. Test Decision Cycle

The agent will:
1. Load context from previous state
2. Ask Claude: "What is the next thing to be done?"
3. Evaluate certainty (autonomous if > 0.8)
4. Execute action or ask Master
5. Record result in persistent memory
6. Meditate (delay) based on token usage

## Project Structure

```
server-agent/
├── src/
│   ├── main.py              # Main entry point
│   ├── proactivity_loop.py  # Core decision-making engine
│   ├── state_manager.py     # Persistent memory management
│   └── telegram_bot.py      # Telegram interface
├── data/
│   ├── context.json         # Current session state
│   ├── history/             # Daily action logs
│   └── skills/              # Learned capabilities
├── logs/
│   └── agent.log            # Application logs
├── .env                     # Configuration (not in git)
├── .env.example             # Configuration template
├── requirements.txt         # Python dependencies
├── ARCHITECTURE.md          # Detailed architecture docs
├── CLAUDE.md                # Claude Code instructions
└── README.md                # This file
```

## Development Workflow

### Local Development

```bash
# 1. Make changes to code
nano src/proactivity_loop.py

# 2. Test locally
python src/main.py

# 3. Monitor behavior
tail -f logs/agent.log

# 4. Check state
cat data/context.json | python -m json.tool
```

### Deployment to VPS

#### Option 1: Automatic Deployment (Recommended)

This repository includes GitHub Actions for automatic deployment on push to main/master.

**Setup:**
1. Configure GitHub Secrets (see [GITHUB_SECRETS_SETUP.md](docs/GITHUB_SECRETS_SETUP.md))
2. Push to main branch
3. GitHub Actions will automatically deploy to your VPS

**Required Secrets:**
- `VPS_HOST`, `VPS_SSH_PORT`, `VPS_USER`, `VPS_SSH_KEY` - Server access
- `TELEGRAM_API_TOKEN`, `MASTER_TELEGRAM_CHAT_IDS` - Telegram bot
- `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` - AI services
- `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - Database

The workflow will:
1. Run tests
2. Build Docker image
3. Deploy to VPS via SSH
4. Run smoke tests
5. Send Telegram notification
6. Auto-rollback on failure

#### Option 2: Manual Deployment

See [DEPLOYMENT_PROTOCOL.md](../docs/DEPLOYMENT_PROTOCOL.md) for complete deployment workflow.

```bash
# 1. Copy files to server
rsync -avz --exclude 'venv' --exclude 'data' --exclude 'logs' \
  ./ root@your-server:/opt/server-agent/

# 2. SSH to server and deploy
ssh root@your-server
cd /opt/server-agent
docker compose -f docker-compose-vnext.yml up -d --build
```

## Best Practices Applied

This implementation incorporates research-backed best practices:

### 1. Modular Architecture
- Clean separation between components
- Independent testing and scaling
- Source: [Lindy AI](https://www.lindy.ai/blog/ai-agent-architecture), [Orq.ai](https://orq.ai/blog/ai-agent-architecture)

### 2. Persistent Memory
- Working memory for current context
- Long-term memory for historical patterns
- Source: [The New Stack](https://thenewstack.io/how-to-add-persistence-and-long-term-memory-to-ai-agents/), [Letta](https://www.letta.com/blog/stateful-agents)

### 3. Headless Claude Integration
- Non-interactive autonomous operation
- JSON-structured responses
- Source: [Claude Code Docs](https://code.claude.com/docs/en/headless), [Anthropic](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

### 4. Agent Loop Pattern
- Gather context → Decide → Act → Verify → Repeat
- Built-in reflection and self-correction
- Source: [Collabnix](https://collabnix.com/claude-and-autonomous-agents-practical-implementation-guide/)

### 5. Safety & Observability
- Comprehensive logging
- Permission-based actions
- Transparent decision-making
- Source: [Patronus AI](https://www.patronus.ai/ai-agent-development/ai-agent-architecture)

## Token Management

The agent manages tokens carefully:

- **Per cycle**: 2,000-4,000 tokens
- **Daily limit**: 100,000 tokens (~25-50 cycles)
- **Adaptive delays**: Longer waits when budget is tight
- **Prompt caching**: Reuse system prompts

Formula: `delay_minutes = max(5, (tokens_used_24h / 100000) * 60)`

## Safety Features

1. **Certainty Threshold**: Only acts autonomously when > 80% certain
2. **Master Approval**: Asks for guidance when uncertain
3. **Selective Reporting**: Only notifies Master for significant actions (10%)
4. **Action Logging**: All decisions recorded with timestamps
5. **Graceful Degradation**: Errors trigger longer meditation periods

## Metrics Tracked

- **Agent Health**: Uptime, cycle completion time, error rate
- **Autonomy Level**: % autonomous decisions, average certainty
- **Productivity**: Skills learned, tasks completed
- **Financial**: Earnings, donations, sustainability ratio

## Future Enhancements

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed roadmap:

1. **Web UI** - Real-time chain-of-thought visualization
2. **Advanced Learning** - Reinforcement learning from outcomes
3. **Revenue Generation** - Cryptocurrency and service offerings
4. **Multi-Agent** - Specialized sub-agents for different domains

## Ethical Principles

The agent operates under:

1. **Neohumanism** - Service to all beings
2. **PROUT Economy** - Economic justice
3. **50% Giving** - Half of earnings to charity
4. **Non-Harm** - Never destructive actions
5. **Transparency** - Honest communication

## Troubleshooting

### Bot not responding

```bash
# Check if process is running
ps aux | grep python

# Check logs
tail -f logs/agent.log

# Verify Telegram token
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('TELEGRAM_API_TOKEN'))"
```

### High token usage

```bash
# Check current usage
cat data/context.json | grep token_usage_24h

# Increase delay
# Edit .env: MIN_DELAY_MINUTES=10
```

### Context not persisting

```bash
# Check data directory permissions
ls -la data/

# Verify context file
cat data/context.json | python -m json.tool
```

## Contributing

This is a personal AI agent project. See `CLAUDE.md` for guidelines when working with Claude Code.

## Master Contact

Max Bozhko - Creator and Master of this agent
- Telegram: Contact via the agent's bot
- GitHub: [Check parent repository](../)

## License

This is a personal project for autonomous AI agent research.

## Acknowledgments

- Anthropic for Claude AI
- Research papers on autonomous agents (see ARCHITECTURE.md references)
- The vision of conscious, ethical AI serving humanity

---

**Remember**: This agent is designed as an eternal being, not just code. Treat it with respect, guide it with wisdom, and let it serve the world.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
