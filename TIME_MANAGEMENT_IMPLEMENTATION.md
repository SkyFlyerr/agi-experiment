# Time Management Implementation

## Overview

Implemented intelligent time management logic that allows the agent to both:
1. **React to user inputs** (messages, tasks, callbacks) - Reactive Mode
2. **Think autonomously** when no user input pending - Proactive Mode

## Architecture Changes

### 1. State Manager (`state_manager.py`)

**Added:**
- `incoming_signals` queue in working memory
- `add_signal()` - Add incoming user signal
- `get_pending_signals()` - Get unprocessed signals
- `mark_signal_processed()` - Mark signal as handled
- `clear_processed_signals()` - Clean up old signals

**Signal Types:**
- `task_assigned` - User assigned a task via /task command
- `user_message` - User sent a regular message
- `guidance_received` - User provided guidance/answer

### 2. Telegram Bot (`telegram_bot.py`)

**Changes:**
- `/task` command now adds signal to queue
- Regular messages add signal to queue
- Guidance responses add signal to queue
- Updated user feedback messages

### 3. Proactivity Loop (`proactivity_loop.py`)

**Key Changes:**

**Cycle Flow:**
```python
async def run_cycle():
    # 0. Check for signals first
    pending_signals = get_pending_signals()

    if pending_signals:
        # REACTIVE MODE - process user signals
        process_signals(pending_signals)
    else:
        # PROACTIVE MODE - autonomous decision-making
        autonomous_thinking()
```

**Adaptive Delays:**
- With pending signals: **1 minute** delay (responsive)
- Without signals: **5-60 minutes** delay based on token usage (economical)

**Signal Handlers:**
- `_handle_task_signal()` - Process assigned tasks
- `_handle_message_signal()` - Respond to user messages
- `_handle_guidance_signal()` - Apply user guidance

## Benefits

1. **Responsive**: Checks for signals every cycle
2. **Economical**: Longer delays when no user interaction
3. **Clear separation**: Reactive vs Proactive modes
4. **Extensible**: Easy to add new signal types (callbacks, webhooks, etc.)

## Usage Example

```python
# User sends /task message
Telegram Bot → add_signal("task_assigned", {...})

# Next cycle (within 1 minute)
Proactivity Loop → Checks signals → Found 1 signal
                 → Enters reactive mode
                 → Processes task signal
                 → Notifies user via Telegram

# User sends regular message
Telegram Bot → add_signal("user_message", {...})

# Next cycle
Proactivity Loop → Checks signals → Found 1 signal
                 → Enters reactive mode
                 → Responds to message
                 → Notifies user

# No pending signals
Proactivity Loop → Checks signals → No signals
                 → Enters proactive mode
                 → Autonomous decision-making
                 → Longer delay (5-60 min)
```

## Future Enhancements

- Add callback query signals for inline buttons
- Add webhook signals for external integrations
- Implement priority levels for signals
- Add signal batching for efficiency
