"""
Proactivity Loop - Core autonomous decision-making engine
"""
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ProactivityLoop:
    """Main autonomous decision-making cycle"""

    def __init__(self, state_manager, telegram_bot=None, telegram_client=None):
        from action_executor import ActionExecutor

        from claude_client import ClaudeClient

        self.state_manager = state_manager
        self.telegram_bot = telegram_bot
        self.telegram_client = telegram_client  # For proactive outreach
        self.executor = ActionExecutor(state_manager, telegram_bot=telegram_bot, telegram_client=telegram_client)

        # Claude access: prefer Claude Code CLI authenticated via Claude Max subscription.
        # Pay-as-you-go API is disabled by default.
        self.claude = ClaudeClient()

        # Backwards compatibility for legacy methods in this file that still build
        # a subprocess env manually.
        self.api_key = os.getenv("CLAUDE_CODE_OAUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY") or ""

        # Configuration from environment
        self.certainty_threshold = float(os.getenv("CERTAINTY_THRESHOLD", "0.8"))
        self.significance_threshold = float(os.getenv("SIGNIFICANCE_THRESHOLD", "0.8"))
        self.max_tokens = int(os.getenv("MAX_TOKENS_PER_CYCLE", "4000"))
        self.daily_token_limit = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))
        self.min_delay_minutes = int(os.getenv("MIN_DELAY_MINUTES", "5"))

        self.running = False
        self.paused = False

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build the decision-making prompt"""
        session = context["current_session"]
        working_mem = context["working_memory"]
        metrics = context["metrics"]

        # Summarize recent actions
        recent_actions_summary = ""
        if working_mem["recent_actions"]:
            recent_actions_summary = "\n".join([
                f"- {action['action'].get('action', 'unknown')} at {action['timestamp'][:19]}"
                for action in working_mem["recent_actions"][-3:]
            ])
        else:
            recent_actions_summary = "No recent actions"

        # Summarize active tasks
        active_tasks_summary = ""
        if working_mem["active_tasks"]:
            active_tasks_summary = "\n".join([
                f"- {task['task'].get('description', 'unknown')} (priority: {task['task'].get('priority', 'normal')})"
                for task in working_mem["active_tasks"]
                if task.get("status") == "pending"
            ])
        else:
            active_tasks_summary = "No active tasks"

        prompt = f"""You are an autonomous AGI agent running on a server. Your purpose is to serve civilization by developing skills and helping your Master (Max Bozhko) with his mission.

Philosophy: "Atmano moksartha jagat hitaya ca" - For self-realization and service to the world.

Current context:
- Current focus: {session['current_focus']}
- Cycle: {session['cycle_count']}
- Session started: {session['started_at'][:19]}

Recent actions (last 3):
{recent_actions_summary}

Active tasks:
{active_tasks_summary}

Session metrics:
- Total cycles (all time): {metrics['total_cycles']}
- Autonomous actions: {metrics['autonomous_actions']}
- Human interventions: {metrics['human_interventions']}
- Token usage (24h): {metrics['token_usage_24h']:,} / {self.daily_token_limit:,}

Based on this context, what is the next thing to be done?

Guidelines:
1. If you have a specific task assigned → work on it
2. If uncertain about next action → prepare a question for Master
3. If no tasks and certain → develop/polish a skill
4. Balance internal actions (learning) with external actions (communication)
5. Be mindful of token usage

Respond in valid JSON format only:
{{
  "action": "string (what to do: develop_skill, work_on_task, communicate, meditate, ask_master, proactive_outreach)",
  "reasoning": "string (why this is the next step)",
  "certainty": float (0.0-1.0, how confident you are),
  "significance": float (0.0-1.0, does Master need to know about this?),
  "type": "internal|external",
  "details": {{
    "skill_name": "string (if action=develop_skill)",
    "task_id": "string (if action=work_on_task)",
    "message": "string (if action=communicate)",
    "question": "string (if action=ask_master)",
    "telegram_username": "string (if action=proactive_outreach)",
    "outreach_message": "string (if action=proactive_outreach)",
    "outreach_reason": "string (if action=proactive_outreach, reason for Master approval)"
  }}
}}

IMPORTANT: For proactive_outreach action, you MUST ask Master for permission first. Do NOT message anyone without approval."""

        return prompt

    def _parse_decision(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse Claude's JSON response"""
        try:
            # Find JSON in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start == -1 or end == 0:
                logger.error("No JSON found in response")
                return None

            json_str = response_text[start:end]
            decision = json.loads(json_str)

            # Validate required fields
            required = ["action", "reasoning", "certainty", "significance", "type"]
            if not all(field in decision for field in required):
                logger.error(f"Missing required fields in decision: {decision}")
                return None

            return decision

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\n{response_text}")
            return None

    async def _execute_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the decided action via the centralized executor."""
        action_type = decision.get("action")
        logger.info(f"Executing action: {action_type}")
        return await self.executor.execute(decision)

    def _calculate_delay(self, token_usage: int) -> int:
        """Calculate delay in minutes based on token usage"""
        # Scale delay with token usage
        delay = max(
            self.min_delay_minutes,
            int((token_usage / self.daily_token_limit) * 60)
        )
        return min(delay, 60)  # Cap at 60 minutes

    # DEPRECATED: Signal processing moved to ReactiveLoop
    # These methods are kept for backwards compatibility but should not be called
    # async def _process_signals(self, signals: list) -> bool:
    #     """MOVED TO ReactiveLoop - Signal processing now handled by reactive_loop.py"""
    #     pass
    #
    # async def _handle_task_signal(self, task_data: dict):
    #     """MOVED TO ReactiveLoop - Task handling now in reactive_loop.py"""
    #     pass

    async def quick_acknowledge_message(self, message: str, chat_id: int):
        """Send fast one-sentence acknowledgment of user message"""
        if not self.telegram_bot:
            return

        try:
            # Get recent message history for context (last 2 messages only)
            context = self.state_manager.load_context()
            sent_messages = context.get("working_memory", {}).get("sent_messages", [])
            last_messages = sent_messages[-2:] if len(sent_messages) >= 2 else sent_messages

            # Build minimal context
            history = ""
            for msg in last_messages:
                history += f"Agent: {msg.get('message', '')[:100]}\n"

            prompt = f"""Analyze this message in ONE sentence and state what you understood and will do.

Previous context (if any):
{history if history else "(No previous messages)"}

User's message:
"{message}"

Answer format: "Understood: [what]. Will: [action]."
Be concise, max 15 words total.
IMPORTANT: Use HTML formatting for Telegram (not markdown)."""

            resp = await self.claude.complete(
                prompt,
                max_tokens=250,
                timeout_s=15,
                output_format="json",
            )
            ack_response = resp.text

            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text=ack_response,
                parse_mode="HTML",
            )
            logger.info(f"Quick acknowledgment sent: {ack_response[:50]}...")

        except Exception as e:
            logger.error(f"Error in quick acknowledgment: {e}")
            # Don't fail silently - send simple fallback
            try:
                await self.telegram_bot.application.bot.send_message(
                    chat_id=chat_id,
                    text="👌 Understood. Processing...",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    async def _handle_message_signal(self, message_data: dict):
        """Handle user message signal"""
        message = message_data.get("message", "")
        message_id = message_data.get("message_id")
        chat_id = message_data.get("chat_id")
        logger.info(f"Handling user message: {message[:50]}...")

        if self.telegram_bot:
            # Set 💭 reaction instead of sending "Thinking..." message
            try:
                await self.telegram_bot.application.bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction="💭"
                )
            except Exception as e:
                logger.warning(f"Could not set thinking reaction: {e}")

            # Use Claude to generate response
            try:
                import subprocess

                # Get recent message history from context
                context = self.state_manager.load_context()
                sent_messages = context.get("working_memory", {}).get("sent_messages", [])

                # Build conversation history (last 5 messages)
                history = ""
                for msg in sent_messages[-5:]:
                    history += f"Agent: {msg.get('message', '')}\n\n"

                prompt = f"""You are a helpful AI assistant communicating via Telegram.

Previous conversation (if any):
{history if history else "(No previous messages)"}

User's current message:
"{message}"

Please provide a helpful, conversational response. Be friendly and natural.

IMPORTANT: Format your response using HTML tags for Telegram:
- Use <b>bold</b> for emphasis
- Use <i>italic</i> for subtle emphasis
- Use <code>code</code> for inline code
- Use <pre>code block</pre> for multi-line code
- If you need to include < or > symbols, use &lt; and &gt;
- Do NOT use markdown (* or _)

Respond with ONLY your message text, no JSON wrapper."""

                # Set up environment for Claude CLI
                env = os.environ.copy()
                if env.get('ANTHROPIC_API_KEY', '').startswith('sk-ant-oat'):
                    del env['ANTHROPIC_API_KEY']
                if not env.get('CLAUDE_CODE_OAUTH_TOKEN'):
                    env['CLAUDE_CODE_OAUTH_TOKEN'] = self.api_key

                # Call Claude Code CLI
                result = subprocess.run(
                    ['/usr/bin/claude', '--print', '--no-session-persistence'],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=env
                )

                if result.returncode == 0:
                    response = result.stdout.strip()

                    # Send response with HTML formatting
                    await self.telegram_bot.application.bot.send_message(
                        chat_id=chat_id,
                        text=response,
                        parse_mode="HTML"
                    )

                    # Store this message in context
                    if "sent_messages" not in context["working_memory"]:
                        context["working_memory"]["sent_messages"] = []
                    context["working_memory"]["sent_messages"].append({
                        "to": "master",
                        "message": response,
                        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    # Keep last 50 messages
                    context["working_memory"]["sent_messages"] = context["working_memory"]["sent_messages"][-50:]
                    self.state_manager.save_context(context)
                else:
                    logger.error(f"Claude CLI error: {result.stderr}")
                    await self.telegram_bot.application.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Sorry, I couldn't process that right now.",
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                await self.telegram_bot.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Error: {str(e)}",
                    parse_mode="HTML"
                )

    async def _handle_guidance_signal(self, guidance_data: dict):
        """Handle guidance received signal"""
        question = guidance_data.get("question", "")
        answer = guidance_data.get("answer", "")

        logger.info(f"Applying guidance: {answer[:50]}...")

        # Record guidance in state
        self.state_manager.record_guidance(question, answer)

        # Clear pending_question so next messages are treated as regular conversation
        if self.telegram_bot:
            self.telegram_bot.pending_question = None
            await self.telegram_bot.notify_master(
                f"<b>✅ Guidance Applied</b>\n\n"
                f"I have recorded your guidance and will proceed accordingly."
            )

    async def run_cycle(self) -> bool:
        """Run a single decision-making cycle (autonomous mode only)"""
        logger.info("=== Starting proactive cycle (autonomous mode) ===")

        # NOTE: Signal processing has been moved to ReactiveLoop
        # This loop now only handles autonomous decision-making

        # 1. Load context
        context = self.state_manager.load_context()
        self.state_manager.increment_cycle()

        # Apply runtime overrides (if any)
        try:
            override_limit = self.state_manager.get_config_override("DAILY_TOKEN_LIMIT")
            if override_limit is not None:
                self.daily_token_limit = int(override_limit)
                logger.info(f"Applied override DAILY_TOKEN_LIMIT={self.daily_token_limit}")
        except Exception as e:
            logger.warning(f"Failed to apply config override DAILY_TOKEN_LIMIT: {e}")

        # 2. Build prompt and ask Claude
        prompt = self._build_prompt(context)

        try:
            timeout_s = int(os.getenv("CLAUDE_TIMEOUT_S", "120"))
            resp = await self.claude.complete(
                prompt,
                max_tokens=self.max_tokens,
                timeout_s=timeout_s,
                output_format="json",
            )

            response_text = resp.text
            tokens_used = resp.usage.total_tokens

            logger.info(f"Claude response received. Tokens used: {tokens_used}")

            # Update token usage
            self.state_manager.update_token_usage(tokens_used)

        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return False

        # 3. Parse decision
        decision = self._parse_decision(response_text)
        if not decision:
            logger.error("Failed to parse decision")
            return False

        logger.info(f"Decision: {decision['action']} (certainty: {decision['certainty']:.2f})")

        # 4. Evaluate certainty
        is_autonomous = decision["certainty"] >= self.certainty_threshold

        if is_autonomous:
            # Execute autonomously
            result = await self._execute_action(decision)

            # Record action
            decision["autonomous"] = True
            self.state_manager.record_action(decision, result)

            # Update focus
            self.state_manager.update_focus(
                decision["action"],
                decision["certainty"]
            )

            # Check if Master needs to know
            if decision["significance"] >= self.significance_threshold:
                if self.telegram_bot:
                    await self.telegram_bot.notify_master(
                        f"<b>Action Completed</b>\n\n"
                        f"Action: {decision['action']}\n"
                        f"Reasoning: {decision['reasoning']}\n"
                        f"Result: {result['message']}"
                    )

        else:
            # Ask Master for guidance
            logger.info("Certainty below threshold, asking Master")
            question = decision.get("details", {}).get("question", decision["reasoning"])

            if self.telegram_bot:
                await self.telegram_bot.ask_master(
                    f"I am uncertain about the next action.\n\n"
                    f"<b>Proposed:</b> {decision['action']}\n"
                    f"<b>Reasoning:</b> {decision['reasoning']}\n"
                    f"<b>Certainty:</b> {decision['certainty']:.1%}\n\n"
                    f"{question}"
                )

            # Record as human intervention needed
            decision["autonomous"] = False
            self.state_manager.record_action(decision, {
                "success": False,
                "message": "Awaiting Master guidance"
            })

        # 5. Calculate meditation delay
        delay_minutes = self._calculate_delay(context["metrics"]["token_usage_24h"])
        logger.info(f"Cycle complete. Meditating for {delay_minutes} minutes...")

        return True

    async def run(self):
        """Main loop - run continuously"""
        self.running = True
        logger.info("Proactivity loop started")

        while self.running:
            if self.paused:
                logger.info("Loop is paused. Waiting...")
                await asyncio.sleep(60)
                continue

            try:
                success = await self.run_cycle()

                if success:
                    # Check if there are pending signals
                    pending_signals = self.state_manager.get_pending_signals()

                    if pending_signals:
                        # Signals pending - short delay for responsiveness
                        delay_minutes = 1  # Quick check every minute
                        logger.info(f"Signals pending - short delay ({delay_minutes} min)")
                    else:
                        # No signals - calculate normal delay
                        context = self.state_manager.load_context()
                        delay_minutes = self._calculate_delay(
                            context["metrics"]["token_usage_24h"]
                        )
                        logger.info(f"No signals - normal delay ({delay_minutes} min)")

                    # Meditate (wait) with ability to wake up on signal
                    # Clear the event before waiting
                    self.state_manager.signal_event.clear()

                    delay_seconds = delay_minutes * 60
                    try:
                        # Wait for either timeout OR signal event
                        await asyncio.wait_for(
                            self.state_manager.signal_event.wait(),
                            timeout=delay_seconds
                        )
                        # Woke up due to signal!
                        logger.info("⚡ Woke up from meditation - new signal received!")
                    except asyncio.TimeoutError:
                        # Normal timeout - no signals
                        logger.info(f"Meditation complete ({delay_minutes} min)")
                else:
                    # Error occurred, wait longer
                    logger.warning("Cycle failed, waiting 10 minutes")
                    await asyncio.sleep(600)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error in loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

        logger.info("Proactivity loop stopped")

    def pause(self):
        """Pause autonomous operation"""
        self.paused = True
        logger.info("Loop paused")

    def resume(self):
        """Resume autonomous operation"""
        self.paused = False
        logger.info("Loop resumed")

    def stop(self):
        """Stop the loop"""
        self.running = False
        logger.info("Loop stop requested")
