# Telegram Account Setup for Proactive Messaging

## Overview

The agent can now send proactive messages through a Telegram user account (not just bot). This allows the agent to:
- Message users/channels directly
- Participate in conversations naturally
- **Always ask Master for permission first** before messaging anyone

## Setup Instructions

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Navigate to "API Development Tools"
4. Create a new application:
   - App title: "Server-Agent"
   - Short name: "server-agent"
   - Platform: Other
5. Copy the following credentials:
   - **API ID** (integer)
   - **API Hash** (long string)

### 2. Add to .env File

Add these variables to `/opt/server-agent/.env` on the server:

```bash
# Telegram User Account (for proactive messaging)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
AGENT_TELEGRAM_PHONE=+1234567890  # Agent's phone number
```

### 3. First-Time Authorization

The first time the agent starts with these credentials, it will:
1. Send a code to the phone number via Telegram
2. **You need to manually authorize** by entering the code

**Manual authorization process:**

```bash
# SSH to server
ssh -p 58504 -i ~/.ssh/frankfurt2_ed25519 root@92.246.136.186

# Stop the service
systemctl stop server-agent

# Run manually to authorize
cd /opt/server-agent
source venv/bin/activate
python src/telegram_client.py

# Enter the code when prompted
# After success, restart service
systemctl start server-agent
```

### 4. Install Dependencies

```bash
# On server
cd /opt/server-agent
./venv/bin/pip install -r requirements.txt
```

## How Permission System Works

### Agent Behavior

1. **Agent decides to message someone** → Analyzes situation and determines if outreach needed
2. **Checks if approved** → Looks in state for pre-approved contacts
3. **If NOT approved** → Sends permission request to Master via bot
4. **Waits for Master approval** → Does NOT send message until approved
5. **After approval** → Can message that contact freely in future

### Master Commands

**Approve a contact:**
```
/approve username
```

**Deny a contact:**
```
/deny username
```

### Permission Request Format

When agent wants to message someone, Master receives:

```
🤖 Permission Request

Contact: @username
Reason: [Agent's reasoning for messaging this person]

Reply with:
✅ /approve username
❌ /deny username
```

## Agent Decision Making

The agent can choose `proactive_outreach` action when:
- It has valuable information to share
- It needs to coordinate with someone
- It wants to follow up on a conversation

**Important:** The agent is explicitly instructed to:
- **Always ask Master first**
- Never message anyone without approval
- Provide clear reasoning for why the message is important

## Example Workflow

1. Agent completes a task related to a project
2. Agent realizes it should update the project stakeholder
3. Agent chooses action: `proactive_outreach`
   ```json
   {
     "action": "proactive_outreach",
     "reasoning": "Task completed, stakeholder should be informed",
     "details": {
       "telegram_username": "project_owner",
       "outreach_message": "Hi! I've completed the API integration...",
       "outreach_reason": "Inform stakeholder about completed task"
     }
   }
   ```
4. Master receives permission request via bot
5. Master approves: `/approve project_owner`
6. Agent sends message
7. Future messages to `@project_owner` don't need approval

## Checking Approved Contacts

Approved contacts are stored in `data/context.json`:

```json
{
  "long_term_memory": {
    "master_preferences": {
      "approved_telegram_contacts": [
        "username1",
        "username2"
      ]
    }
  }
}
```

## Security Considerations

- Agent session file stored at `/opt/server-agent/agent_session.session`
- Only Master can approve contacts
- All outreach attempts are logged
- Master receives notifications for all permission requests

## Troubleshooting

**Agent can't authorize:**
- Run `python src/telegram_client.py` manually to debug
- Check phone number format (+country_code_number)
- Ensure API credentials are correct

**Permission requests not showing:**
- Check bot is running: `systemctl status server-agent`
- Verify MASTER_MAX_TELEGRAM_CHAT_ID is correct

**Messages not sending:**
- Check approved contacts list in context.json
- Verify Telegram client started (check logs)
- Ensure session file exists
