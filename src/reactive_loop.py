"""
Reactive Loop - Handles external signals and executes tasks continuously

This loop processes signals from external sources (Telegram messages, task assignments)
and executes them without meditation breaks, providing step-by-step progress updates.
"""
import os
import json
import asyncio
import logging
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ReactiveLoop:
    """
    Reactive system - processes external signals without delays.

    Key differences from ProactivityLoop:
    - NO meditation/delays during task execution
    - Continuous signal processing
    - Step-by-step progress reporting
    - Responds to "стоп" command
    """

    def __init__(self, state_manager, telegram_bot, action_executor):
        from claude_client import ClaudeClient

        self.state_manager = state_manager
        self.telegram_bot = telegram_bot
        self.executor = action_executor

        # Claude access: prefer Claude Code CLI authenticated via Claude Max subscription.
        # Pay-as-you-go API is disabled by default.
        self.claude = ClaudeClient()

        self.running = False
        self._stop_flag = asyncio.Event()  # For detecting "стоп" command

    async def start(self):
        """Start the reactive loop - continuous signal processing"""
        self.running = True
        logger.info("=== ReactiveLoop started - processing signals ===")

        while self.running:
            try:
                # Check for pending signals
                signals = self.state_manager.get_pending_signals()

                if not signals:
                    # No signals - wait 1 second and check again
                    await asyncio.sleep(1)
                    continue

                # Process each signal
                for signal in signals:
                    try:
                        signal_type = signal.get('type')
                        signal_data = signal.get('data', {})

                        logger.info(f"ReactiveLoop: Processing signal type={signal_type}")

                        if signal_type == 'user_message':
                            await self._handle_user_message(signal_data)
                        elif signal_type == 'task_assigned':
                            await self._handle_task_assigned(signal_data)
                        elif signal_type == 'guidance_received':
                            await self._handle_guidance(signal_data)
                        else:
                            logger.warning(f"Unknown signal type: {signal_type}")

                        # Mark signal as processed
                        self.state_manager.mark_signal_processed_by_id(signal.get('id'))

                    except Exception as e:
                        logger.error(f"Error processing signal: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error in reactive loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause on error

    def stop(self):
        """Stop the reactive loop"""
        logger.info("ReactiveLoop: Stopping...")
        self.running = False

    async def _handle_user_message(self, data: Dict[str, Any]):
        """Handle user message signal"""
        message = data.get('message', '')
        chat_id = data.get('chat_id')

        logger.info(f"ReactiveLoop: Handling user message: {message[:50]}...")

        # Classify message intent
        intent = await self._classify_intent(message)

        logger.info(f"ReactiveLoop: Message classified as: {intent}")

        if intent == 'task_execution':
            # Execute task continuously with progress updates
            await self._execute_task_continuously(message, chat_id)
        elif intent == 'question':
            # Answer question using Claude
            await self._answer_question(message, chat_id)
        elif intent == 'conversation':
            # Casual conversation
            await self._handle_conversation(message, chat_id)
        else:
            # Default: treat as conversation
            await self._handle_conversation(message, chat_id)

    async def _handle_task_assigned(self, data: Dict[str, Any]):
        """Handle task assignment signal (from /task command)"""
        task_description = data.get('description', '')
        chat_id = self.telegram_bot.master_chat_id  # Task assignments go to master

        logger.info(f"ReactiveLoop: Task assigned: {task_description}")

        # Execute task continuously
        await self._execute_task_continuously(task_description, chat_id)

    def _parse_token_limit_from_text(self, text: str) -> int | None:
        """Parse token limit like '5 млн', '5000000', '5,000,000' from Russian/English text."""
        if not text:
            return None

        t = text.lower().replace("_", " ")

        # Pattern: '5 млн', '5m', '5 million'
        m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(млн|миллион|million|m)\b", t)
        if m:
            raw_num = m.group(1).replace(",", ".")
            try:
                base = float(raw_num)
                return int(base * 1_000_000)
            except Exception:
                return None

        # Pattern: plain integer possibly with spaces/commas
        m2 = re.search(r"\b(\d[\d\s.,]{4,})\b", t)
        if m2:
            digits = re.sub(r"[^0-9]", "", m2.group(1))
            try:
                val = int(digits)
                if val >= 100_000:
                    return val
            except Exception:
                return None

        return None

    def _msk_midnight_iso(self) -> str:
        """Return ISO timestamp for upcoming midnight in Europe/Moscow."""
        if ZoneInfo is None:
            # Fallback: treat server local time as MSK (best-effort)
            now = datetime.now()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return midnight.isoformat()

        tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(tz)
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.isoformat()

    async def _handle_guidance(self, data: Dict[str, Any]):
        """Handle guidance received from Master"""
        question = data.get('question', '')
        answer = data.get('answer', '')

        logger.info(f"ReactiveLoop: Guidance received for question: {question[:80]}...")
        logger.info(f"ReactiveLoop: Guidance answer: {answer[:120]}...")

        # 1) Store guidance in context for future reference
        context = self.state_manager.load_context()
        if 'guidance_history' not in context['long_term_memory']:
            context['long_term_memory']['guidance_history'] = []

        context['long_term_memory']['guidance_history'].append({
            'question': question,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        })

        # Keep last 50 guidance entries
        context['long_term_memory']['guidance_history'] = \
            context['long_term_memory']['guidance_history'][-50:]

        self.state_manager.save_context(context)

        # 2) Apply runtime config overrides if guidance looks like a config change
        try:
            q = (question or "").lower()
            a = (answer or "").lower()
            if "token" in q or "токен" in q or "лимит" in a:
                parsed = self._parse_token_limit_from_text(answer)
                if parsed:
                    expires_at = self._msk_midnight_iso()
                    self.state_manager.set_config_override("DAILY_TOKEN_LIMIT", int(parsed), expires_at=expires_at)
                    logger.info(
                        f"ReactiveLoop: Applied override DAILY_TOKEN_LIMIT={parsed} until {expires_at}"
                    )
                    # Notify Master explicitly so it's visible in chat
                    await self.telegram_bot.notify_master(
                        f"<b>✅ Applied temporary override</b>\n\n"
                        f"DAILY_TOKEN_LIMIT = {parsed:,} (until {expires_at})"
                    )
        except Exception as e:
            logger.error(f"ReactiveLoop: Failed to apply overrides from guidance: {e}", exc_info=True)

    async def _classify_intent(self, message: str) -> str:
        """
        Classify message intent using keywords and patterns.

        Returns:
            'task_execution' - clear command to do something
            'question' - asking for information
            'conversation' - casual chat
        """
        message_lower = message.lower()

        # Task execution keywords (Russian)
        task_keywords = [
            'сделай', 'выполни', 'создай', 'напиши', 'реализуй',
            'исправь', 'обнови', 'добавь', 'удали', 'проверь',
            'запусти', 'останови', 'перезапусти', 'установи',
            'скачай', 'загрузи', 'отправь', 'найди и ',
        ]

        # Question keywords (Russian)
        question_keywords = [
            'что', 'как', 'почему', 'когда', 'где', 'кто',
            'какой', 'какая', 'какое', 'сколько',
            'можешь ли', 'умеешь ли'
        ]

        # Check for task execution
        for keyword in task_keywords:
            if keyword in message_lower:
                return 'task_execution'

        # Check for questions
        for keyword in question_keywords:
            if message_lower.startswith(keyword) or f" {keyword}" in message_lower:
                return 'question'

        # Default to conversation
        return 'conversation'

    async def _execute_task_continuously(self, task_description: str, chat_id: int):
        """
        Execute a task continuously with step-by-step progress updates.

        This is the core method for reactive task execution:
        1. Break down task into steps using Claude
        2. Execute each step
        3. Report progress after each step (one short sentence)
        4. Continue until task is complete or "стоп" command received
        """
        logger.info(f"ReactiveLoop: Starting continuous task execution: {task_description}")

        try:
            # Clear stop flag
            self._stop_flag.clear()

            # Step 1: Break down task into executable steps
            steps = await self._plan_task_steps(task_description)

            if not steps:
                await self.telegram_bot.application.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось разбить задачу на шаги",
                    parse_mode="HTML"
                )
                return

            logger.info(f"ReactiveLoop: Task broken into {len(steps)} steps")

            # Step 2: Execute each step with progress reporting
            for i, step in enumerate(steps, 1):
                # Check for stop command
                if await self._check_for_stop_command():
                    await self.telegram_bot.application.bot.send_message(
                        chat_id=chat_id,
                        text="⏸️ Выполнение остановлено по команде",
                        parse_mode="HTML"
                    )
                    break

                logger.info(f"ReactiveLoop: Executing step {i}/{len(steps)}: {step.get('description', '')}")

                # Execute the step
                result = await self._execute_step(step)

                # Verify step result
                success = result.get('success', False)

                if success:
                    # Send brief progress update (one sentence)
                    progress_message = result.get('brief_description', f"✅ Шаг {i}/{len(steps)} выполнен")
                    await self.telegram_bot.application.bot.send_message(
                        chat_id=chat_id,
                        text=progress_message,
                        parse_mode="HTML"
                    )
                else:
                    # Report failure and ask what to do
                    error_message = result.get('error', 'Неизвестная ошибка')
                    await self.telegram_bot.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Ошибка на шаге {i}/{len(steps)}: {error_message}\n\nПродолжить выполнение?",
                        parse_mode="HTML"
                    )
                    # For now, stop on error (can be made configurable)
                    break

            # Task complete
            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text="✅ Задача выполнена полностью",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error during task execution: {e}", exc_info=True)
            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка при выполнении задачи: {str(e)}",
                parse_mode="HTML"
            )

    async def _plan_task_steps(self, task_description: str) -> List[Dict[str, Any]]:
        """
        Use Claude to break down task into executable steps.

        Returns list of steps with format:
        [
            {
                'description': 'Step description',
                'action_type': 'bash_command' | 'file_edit' | 'api_call',
                'details': {...}  # Action-specific details
            },
            ...
        ]
        """
        try:
            prompt = f"""Разбей следующую задачу на конкретные выполнимые шаги:

"{task_description}"

Верни ответ СТРОГО в формате JSON (без markdown, без комментариев):
{{
  "steps": [
    {{
      "description": "Краткое описание шага",
      "action_type": "bash_command|file_edit|api_call|thinking",
      "command": "команда для выполнения (если bash_command)",
      "brief_result": "что будет сделано одним предложением"
    }}
  ]
}}

Важно:
- Каждый шаг должен быть конкретным и выполнимым
- Для каждого шага укажи brief_result - как кратко отчитаться после выполнения
- Используй только действия, которые можно автоматизировать
- Если задача требует человеческого решения - укажи это отдельным шагом"""

            response = await self._call_claude(prompt, max_tokens=2500)

            # Parse JSON response
            try:
                # Extract JSON from response (may be wrapped in markdown)
                response_text = response.strip()
                if response_text.startswith('```'):
                    # Remove markdown code block
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text

                result = json.loads(response_text)
                steps = result.get('steps', [])

                logger.info(f"ReactiveLoop: Parsed {len(steps)} steps from Claude response")
                return steps

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Claude response: {e}")
                logger.error(f"Response was: {response[:500]}")
                return []

        except Exception as e:
            logger.error(f"Error planning task steps: {e}", exc_info=True)
            return []

    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step and return result.

        Returns:
            {
                'success': True/False,
                'brief_description': 'One sentence description of what was done',
                'error': 'Error message if failed'
            }
        """
        action_type = step.get('action_type', 'thinking')
        description = step.get('description', '')

        try:
            if action_type == 'bash_command':
                command = step.get('command', '')

                # Execute bash command
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60  # 1 minute timeout
                )

                if result.returncode == 0:
                    return {
                        'success': True,
                        'brief_description': step.get('brief_result', f"✅ {description}")
                    }
                else:
                    return {
                        'success': False,
                        'error': result.stderr[:200]  # First 200 chars of error
                    }

            elif action_type == 'file_edit':
                # Use executor's file editing capabilities
                file_path = step.get('file_path', '')
                changes = step.get('changes', '')

                # This would use action_executor's capabilities
                # For now, return success with description
                return {
                    'success': True,
                    'brief_description': step.get('brief_result', f"✅ {description}")
                }

            elif action_type == 'thinking':
                # No action needed, just return description
                return {
                    'success': True,
                    'brief_description': step.get('brief_result', f"💭 {description}")
                }

            else:
                # Unknown action type
                return {
                    'success': False,
                    'error': f'Unknown action type: {action_type}'
                }

        except Exception as e:
            logger.error(f"Error executing step: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _check_for_stop_command(self) -> bool:
        """Check if user sent 'стоп' command"""
        # Check recent signals for stop command
        signals = self.state_manager.get_pending_signals()

        for signal in signals:
            if signal.get('type') == 'user_message':
                message = signal.get('data', {}).get('message', '').lower()
                if message in ['стоп', 'stop', 'останови']:
                    # Mark signal as processed
                    self.state_manager.mark_signal_processed_by_id(signal.get('id'))
                    return True

        return False

    async def _answer_question(self, question: str, chat_id: int):
        """Answer a question using Claude"""
        try:
            # Get context
            context = self.state_manager.load_context()

            # Build prompt with context
            prompt = f"""Ответь на вопрос пользователя.

Вопрос: {question}

Контекст:
- Текущий фокус: {context['working_memory']['current_focus']}
- Недавние действия: {len(context['working_memory']['recent_actions'])}

Дай краткий и полезный ответ."""

            response = await self._call_claude(prompt, max_tokens=1200)

            # Send answer
            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text=response,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error answering question: {e}", exc_info=True)
            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка при ответе на вопрос: {str(e)}",
                parse_mode="HTML"
            )

    async def _handle_conversation(self, message: str, chat_id: int):
        """Handle casual conversation"""
        try:
            # Simple conversational response
            prompt = f"""Ответь на сообщение пользователя в дружелюбном тоне.

Сообщение: {message}

Дай короткий естественный ответ (1-2 предложения)."""

            response = await self._call_claude(prompt, max_tokens=800)

            # Send response
            await self.telegram_bot.application.bot.send_message(
                chat_id=chat_id,
                text=response,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Error in conversation: {e}", exc_info=True)

    async def _call_claude(self, prompt: str, *, max_tokens: int, timeout_s: int | None = None) -> str:
        """Call Claude via ClaudeClient (prefers Claude Code CLI / Max subscription)."""

        if timeout_s is None:
            timeout_s = int(os.getenv("CLAUDE_TIMEOUT_S", "120"))

        resp = await self.claude.complete(
            prompt,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            output_format="json",
        )

        # Track token usage centrally.
        if resp.usage.total_tokens:
            self.state_manager.update_token_usage(resp.usage.total_tokens)

        return resp.text
