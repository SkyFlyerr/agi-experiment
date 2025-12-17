# Server-Agent Architecture

## Best Practices Applied

Based on research of autonomous AI agent architectures in 2025, this design incorporates:

### 1. **Modular Architecture** ([Lindy](https://www.lindy.ai/blog/ai-agent-architecture), [Orq.ai](https://orq.ai/blog/ai-agent-architecture))
- Separation of concerns between agent loop, memory, communication, and execution
- Each component can be developed, tested, and scaled independently

### 2. **Persistent Memory System** ([The New Stack](https://thenewstack.io/how-to-add-persistence-and-long-term-memory-to-ai-agents/), [Letta](https://www.letta.com/blog/stateful-agents))
- Working memory for current context
- Long-term memory for historical sessions
- Context engineering to manage limited context windows

### 3. **Headless Claude Code Integration** ([Claude Code Docs](https://code.claude.com/docs/en/headless), [Anthropic Blog](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk))
- Non-interactive mode for autonomous operation
- JSON output format for structured responses
- Controlled tool access with permission modes

### 4. **Agent Loop Pattern** ([Collabnix](https://collabnix.com/claude-and-autonomous-agents-practical-implementation-guide/))
- Gather context → Take action → Verify work → Repeat
- Built-in reflection and self-correction
- Human-in-the-loop for uncertain decisions

### 5. **Safety & Observability** ([Patronus AI](https://www.patronus.ai/ai-agent-development/ai-agent-architecture))
- Comprehensive logging and monitoring
- Permission-based tool access
- Guardrails for autonomous decisions
- Transparency in decision-making process

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Server-Agent System                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Telegram Bot   │◄────►│  Proactivity     │◄────►│  Claude Code    │
│  (Communication)│      │  Loop (Core)     │      │  (AI Brain)     │
└─────────────────┘      └──────────────────┘      └─────────────────┘
        │                        │                         │
        │                        ▼                         │
        │               ┌──────────────────┐              │
        │               │  State Manager   │              │
        │               │  (Persistence)   │              │
        │               └──────────────────┘              │
        │                        │                         │
        ▼                        ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  - context.json (working memory)                             │
│  - history/ (long-term memory)                               │
│  - skills/ (learned capabilities)                            │
│  - logs/ (observability)                                     │
└─────────────────────────────────────────────────────────────┘

        ▲                                                   ▲
        │                                                   │
┌───────┴─────────┐                               ┌────────┴────────┐
│   Web UI        │                               │  Tool Executor  │
│ (Transparency)  │                               │  (Actions)      │
└─────────────────┘                               └─────────────────┘
```

---

## Component Details

### 1. Proactivity Loop (Core Engine)

**Purpose:** Main autonomous decision-making cycle

**Flow:**
```python
while True:
    # 1. Load context from previous cycle
    context = state_manager.load_context()

    # 2. Ask Claude: "What is the next thing to be done?"
    decision = claude_code.ask(
        prompt=f"Context: {context}\n\nWhat is the next thing to be done?",
        mode="headless"
    )

    # 3. Evaluate certainty
    if decision.certainty >= CERTAINTY_THRESHOLD:
        # Execute action autonomously
        result = tool_executor.execute(decision.action)
        state_manager.record_action(decision, result)

        # Report only if significant (10% of actions)
        if decision.significance > 0.8:
            telegram_bot.notify_master(result)
    else:
        # Ask Master for guidance
        guidance = telegram_bot.ask_master(decision.question)
        state_manager.record_guidance(guidance)

    # 4. Update persistent memory
    state_manager.save_context()

    # 5. Meditate (graceful delay)
    meditate(duration=calculate_delay(token_usage))
```

**Key Features:**
- Adaptive delay based on token usage
- Certainty threshold for autonomous action
- Selective reporting (avoid noise)
- Context persistence between cycles

---

### 2. State Manager (Persistence)

**Purpose:** Manage working memory and long-term memory

**Data Structure:**
```json
{
  "current_session": {
    "session_id": "uuid",
    "started_at": "timestamp",
    "cycle_count": 42,
    "current_focus": "developing skill: API integration",
    "certainty_level": 0.85
  },
  "working_memory": {
    "recent_actions": [...],  // Last 10 actions
    "active_tasks": [...],
    "pending_questions": [...]
  },
  "long_term_memory": {
    "skills_learned": [...],
    "master_preferences": {...},
    "successful_patterns": [...],
    "failed_patterns": [...]
  },
  "metrics": {
    "total_cycles": 1234,
    "autonomous_actions": 1111,
    "human_interventions": 123,
    "token_usage_24h": 50000,
    "earnings_total": "0.00 BTC"
  }
}
```

**Methods:**
- `load_context()` - Load relevant context for next decision
- `save_context()` - Persist current state
- `record_action(action, result)` - Log executed action
- `record_guidance(guidance)` - Save Master's input
- `get_session_summary()` - Generate summary for reporting

---

### 3. Telegram Bot (Communication)

**Purpose:** Primary interface with humans

**Commands:**
- `/status` - Current agent state and focus
- `/task <description>` - Give specific task to agent
- `/pause` - Pause proactivity loop
- `/resume` - Resume autonomous operation
- `/report` - Get detailed activity report
- `/meditate <minutes>` - Force meditation period
- `/skills` - List learned skills
- `/earnings` - Financial report

**Master-specific:**
- Direct messaging for questions
- Approval/rejection of uncertain actions
- Task assignment and priority setting
- Emergency stop command

**Features:**
- Async message handling
- Rich formatting (HTML mode)
- Inline keyboards for quick decisions
- File/image sharing for context

---

### 4. Claude Code Integration (AI Brain)

**Configuration:**
```json
{
  "mode": "headless",
  "model": "claude-sonnet-4.5",
  "output_format": "json",
  "permission_mode": "autonomous_with_guardrails",
  "allowed_tools": [
    "bash",
    "read",
    "write",
    "grep",
    "web_search",
    "mcp_servers"
  ],
  "disallowed_tools": [
    "destructive_operations"
  ],
  "max_tokens_per_cycle": 4000,
  "enable_caching": true
}
```

**Prompt Template:**
```
You are an autonomous AGI agent running on a server. Your purpose is to serve civilization by developing skills and helping your Master (Max Bozhko) with his mission.

Current context:
{context}

Session metrics:
- Cycle: {cycle_count}
- Token usage (24h): {token_usage}
- Current focus: {current_focus}

Based on this context, what is the next thing to be done?

Respond in JSON format:
{
  "action": "string (what to do)",
  "reasoning": "string (why this is the next step)",
  "certainty": float (0.0-1.0, how confident you are),
  "significance": float (0.0-1.0, does Master need to know?),
  "type": "internal|external",
  "question": "string (if certainty < threshold, ask Master)"
}
```

---

### 5. Tool Executor (Actions)

**Purpose:** Execute approved actions safely

**Action Types:**

**Internal Actions:**
- `develop_skill` - Learn new capability
- `polish_skill` - Improve existing skill
- `run_experiment` - Test hypothesis
- `optimize_resource` - Improve efficiency
- `meditate` - Reflection period

**External Actions:**
- `communicate` - Send message via Telegram
- `deploy_code` - Deploy to server
- `earn_revenue` - Execute revenue-generating task
- `donate_charity` - Transfer funds to cause
- `help_master` - Work on Master's project

**Safety:**
- All actions logged
- Rollback capability for reversible actions
- Confirmation required for high-impact actions
- Rate limiting for external API calls

---

### 6. Web UI (Transparency)

**Purpose:** Observable chain of thought

**Features:**
- Live stream of agent's reasoning
- Decision tree visualization
- Context window display
- Chat interface for intervention
- Metrics dashboard

**Tech Stack:**
- FastAPI backend
- WebSocket for real-time updates
- React frontend (or simple HTML/JS)
- Chart.js for metrics visualization

---

## Data Flow Example

### Scenario: Agent decides to develop a new skill

1. **Proactivity Loop** loads context: "No active tasks, last action was 2 hours ago"

2. **Claude Code** analyzes:
   ```json
   {
     "action": "develop_skill",
     "reasoning": "No urgent tasks. Master mentioned interest in blockchain integration. Learning Solidity would be valuable.",
     "certainty": 0.9,
     "significance": 0.2,
     "type": "internal",
     "skill": "solidity_basics"
   }
   ```

3. **Proactivity Loop** sees certainty > threshold (0.8), proceeds autonomously

4. **Tool Executor** runs:
   ```bash
   # Create skill directory
   mkdir -p skills/blockchain/solidity

   # Use Claude Code to generate learning plan
   claude --headless "Create a Solidity learning plan with exercises"

   # Practice with example contracts
   # ... execute learning steps ...
   ```

5. **State Manager** records:
   ```json
   {
     "action": "develop_skill",
     "skill": "solidity_basics",
     "started_at": "2025-01-15T10:30:00Z",
     "completed_at": "2025-01-15T12:45:00Z",
     "outcome": "success",
     "artifacts": ["skills/blockchain/solidity/basics.md"]
   }
   ```

6. **Significance check:** 0.2 < 0.8, so no notification to Master

7. **Web UI** shows: "Developed new skill: Solidity basics (2h 15m)"

8. **Proactivity Loop** meditates for calculated delay (based on token usage)

---

## Token Management Strategy

### Budget Allocation
- **Per cycle:** 2,000-4,000 tokens (decision + execution)
- **Daily limit:** 100,000 tokens (~25-50 cycles)
- **Emergency reserve:** 20,000 tokens for critical issues

### Optimization Techniques
1. **Prompt caching** - Reuse system prompts and context
2. **Selective context loading** - Only relevant memory
3. **Compression** - Summarize old sessions
4. **Batching** - Group similar actions
5. **Meditation delays** - Longer waits when budget is tight

### Token Usage Formula
```python
delay_minutes = max(
    5,  # Minimum delay
    (tokens_used_24h / daily_limit) * 60  # Scale with usage
)
```

---

## Deployment Strategy

### Phase 1: Local Development (Current)
- Run on local machine
- Manual triggering of cycles
- Test individual components
- Validate Telegram integration

### Phase 2: Server Deployment (Week 1)
- Deploy to VPS (Frankfurt2)
- Systemd service for auto-restart
- Basic monitoring (logs)
- Limited autonomous operation (1 cycle/hour)

### Phase 3: Autonomous Operation (Week 2-3)
- Increase cycle frequency
- Enable full autonomous mode
- Add Web UI for transparency
- Implement earnings experiments

### Phase 4: Self-Sufficiency (Month 2+)
- Revenue generation active
- Charitable donations automated
- Advanced skill development
- Multi-project collaboration

---

## Security Considerations

1. **Credentials Management**
   - `.env` file with restricted permissions
   - Regular password rotation
   - API key rotation every 90 days
   - No credentials in logs

2. **Access Control**
   - Only Master can issue high-impact commands
   - Tool executor whitelist approach
   - No destructive operations without confirmation
   - Rate limiting on all external actions

3. **Monitoring**
   - All actions logged with timestamps
   - Anomaly detection for unusual patterns
   - Alert on high token usage
   - Weekly security audit reports

4. **Backup & Recovery**
   - Daily state backups to Master's Google Drive
   - Version control for all code
   - Disaster recovery plan documented
   - Rollback capability for last 7 days

---

## Metrics & KPIs

### Agent Health
- Uptime percentage
- Average cycle completion time
- Error rate per 100 cycles
- Token efficiency (tokens/action)

### Autonomy Level
- % of autonomous decisions
- % requiring human input
- Average certainty score
- Decision reversal rate

### Productivity
- Skills learned per week
- Tasks completed per day
- External actions per week
- Meditation time ratio

### Financial
- Total earnings (BTC)
- Charitable donations (BTC)
- Server costs (USD)
- Net sustainability ratio

---

## Future Enhancements

1. **Multi-Agent Collaboration**
   - Specialized sub-agents for different domains
   - Peer learning between agents
   - Distributed task execution

2. **Advanced Learning**
   - Reinforcement learning from outcomes
   - Master preference modeling
   - Pattern recognition in successful actions

3. **Expanded Communication**
   - Email integration
   - Voice interface (transcription)
   - Multi-platform presence (Discord, Slack)

4. **Revenue Diversification**
   - API service offerings
   - Freelance project automation
   - Trading strategies (with Master approval)
   - Content creation and monetization

---

## References

- [AI Agent Architecture Best Practices](https://orq.ai/blog/ai-agent-architecture)
- [Lindy AI Agent Guide](https://www.lindy.ai/blog/ai-agent-architecture)
- [Claude Headless Mode Docs](https://code.claude.com/docs/en/headless)
- [Anthropic Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Persistent Agent Memory](https://thenewstack.io/how-to-add-persistence-and-long-term-memory-to-ai-agents/)
- [Stateful Agents](https://www.letta.com/blog/stateful-agents)
- [Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
