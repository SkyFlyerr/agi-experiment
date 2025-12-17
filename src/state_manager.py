"""src/state_manager.py

State Manager - Handles persistent memory and context for the agent
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


class StateManager:
    """Manages agent state, working memory, and long-term memory"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.context_file = self.data_dir / "context.json"
        self.history_dir = self.data_dir / "history"
        self.history_dir.mkdir(exist_ok=True)
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(exist_ok=True)

        # Event for immediate signal notification
        self.signal_event = asyncio.Event()

        # Initialize context if not exists
        if not self.context_file.exists():
            self._initialize_context()

    def _initialize_context(self):
        """Create initial context structure"""
        initial_context = {
            "current_session": {
                "session_id": datetime.now().isoformat(),
                "started_at": datetime.now().isoformat(),
                "cycle_count": 0,
                "current_focus": "initialization",
                "certainty_level": 0.0
            },
            "working_memory": {
                "recent_actions": [],
                "active_tasks": [],
                "pending_questions": [],
                "incoming_signals": []  # User messages, callbacks, external triggers
            },
            "long_term_memory": {
                "skills_learned": [],
                "master_preferences": {},
                "successful_patterns": [],
                "failed_patterns": [],
                # Runtime overrides for configuration knobs (e.g., DAILY_TOKEN_LIMIT).
                # Each entry: {"value": <any>, "expires_at": <iso str or None>, "set_at": <iso str>}
                "config_overrides": {},
            },
            "metrics": {
                "total_cycles": 0,
                "autonomous_actions": 0,
                "human_interventions": 0,
                "token_usage_24h": 0,
                "earnings_total": "0.00 BTC"
            }
        }
        self._save_json(self.context_file, initial_context)

    def _save_json(self, filepath: Path, data: Dict):
        """Save JSON data to file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_json(self, filepath: Path) -> Dict:
        """Load JSON data from file"""
        with open(filepath, 'r') as f:
            return json.load(f)

    def load_context(self) -> Dict[str, Any]:
        """Load current context for decision making"""
        context = self._load_json(self.context_file)

        # Migration: Add incoming_signals if not present
        if "incoming_signals" not in context.get("working_memory", {}):
            context.setdefault("working_memory", {})["incoming_signals"] = []

        # Migration: Add config_overrides if not present
        ltm = context.setdefault("long_term_memory", {})
        if "config_overrides" not in ltm:
            ltm["config_overrides"] = {}

        self.save_context(context)
        return context

    def save_context(self, context: Dict[str, Any]):
        """Save updated context"""
        self._save_json(self.context_file, context)

    def record_action(self, action: Dict[str, Any], result: Dict[str, Any]):
        """Record an executed action with its result"""
        context = self.load_context()

        action_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "result": result,
            "cycle": context["current_session"]["cycle_count"]
        }

        # Add to recent actions (keep last 10)
        context["working_memory"]["recent_actions"].append(action_record)
        if len(context["working_memory"]["recent_actions"]) > 10:
            context["working_memory"]["recent_actions"].pop(0)

        # Update metrics
        context["metrics"]["total_cycles"] = context["current_session"]["cycle_count"]
        if action.get("autonomous", False):
            context["metrics"]["autonomous_actions"] += 1
        else:
            context["metrics"]["human_interventions"] += 1

        # Save to history
        history_file = self.history_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(history_file, 'a') as f:
            f.write(json.dumps(action_record) + '\n')

        self.save_context(context)

    def record_guidance(self, question: str, guidance: str):
        """Record Master's guidance on a question"""
        context = self.load_context()

        guidance_record = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "guidance": guidance,
            "cycle": context["current_session"]["cycle_count"]
        }

        # Add to master preferences
        if "guidance_history" not in context["long_term_memory"]["master_preferences"]:
            context["long_term_memory"]["master_preferences"]["guidance_history"] = []

        context["long_term_memory"]["master_preferences"]["guidance_history"].append(guidance_record)

        self.save_context(context)

    def increment_cycle(self):
        """Increment the cycle counter"""
        context = self.load_context()
        context["current_session"]["cycle_count"] += 1
        self.save_context(context)

    def update_focus(self, focus: str, certainty: float):
        """Update current focus and certainty level"""
        context = self.load_context()
        context["current_session"]["current_focus"] = focus
        context["current_session"]["certainty_level"] = certainty
        self.save_context(context)

    def add_task(self, task: Dict[str, Any]):
        """Add a task to active tasks"""
        context = self.load_context()
        context["working_memory"]["active_tasks"].append({
            "task": task,
            "added_at": datetime.now().isoformat(),
            "status": "pending"
        })
        self.save_context(context)

    def complete_task(self, task_id: str):
        """Mark a task as completed."""
        context = self.load_context()
        for task_entry in context["working_memory"]["active_tasks"]:
            task = task_entry.get("task", {})
            if task.get("id") == task_id:
                task_entry["status"] = "completed"
                task_entry["completed_at"] = datetime.now().isoformat()
        self.save_context(context)

    def add_skill(self, skill_name: str, skill_data: Dict[str, Any]):
        """Record a newly learned skill"""
        context = self.load_context()

        skill_record = {
            "name": skill_name,
            "learned_at": datetime.now().isoformat(),
            "data": skill_data
        }

        context["long_term_memory"]["skills_learned"].append(skill_record)

        # Save skill details to separate file
        skill_file = self.skills_dir / f"{skill_name}.json"
        self._save_json(skill_file, skill_data)

        self.save_context(context)

    def get_session_summary(self) -> Dict[str, Any]:
        """Generate summary of current session"""
        context = self.load_context()
        return {
            "session_id": context["current_session"]["session_id"],
            "started_at": context["current_session"]["started_at"],
            "cycles": context["current_session"]["cycle_count"],
            "current_focus": context["current_session"]["current_focus"],
            "certainty": context["current_session"]["certainty_level"],
            "recent_actions": len(context["working_memory"]["recent_actions"]),
            "active_tasks": len(context["working_memory"]["active_tasks"]),
            "total_cycles_all_time": context["metrics"]["total_cycles"],
            "autonomous_ratio": (
                context["metrics"]["autonomous_actions"] /
                max(context["metrics"]["total_cycles"], 1)
            ),
            "token_usage_24h": context["metrics"]["token_usage_24h"]
        }

    def update_token_usage(self, tokens: int):
        """Update 24h token usage"""
        context = self.load_context()
        context["metrics"]["token_usage_24h"] += tokens
        self.save_context(context)

    def reset_daily_metrics(self):
        """Reset daily metrics (call this once per day)"""
        context = self.load_context()
        context["metrics"]["token_usage_24h"] = 0
        self.save_context(context)

    def add_signal(self, signal_type: str, signal_data: Dict[str, Any]) -> str:
        """Add an incoming signal (user message, task, callback, etc.).

        Returns:
            signal_id: Stable identifier that can be used to mark it processed.
        """
        context = self.load_context()

        signal_id = uuid4().hex
        signal = {
            "id": signal_id,
            "type": signal_type,  # "user_message", "task_assigned", "callback", etc.
            "data": signal_data,
            "received_at": datetime.now().isoformat(),
            "processed": False,
        }

        context["working_memory"]["incoming_signals"].append(signal)
        self.save_context(context)

        # Notify waiting loops about new signal (wake up from meditation)
        self.signal_event.set()
        return signal_id

    def get_pending_signals(self) -> List[Dict[str, Any]]:
        """Get all unprocessed signals"""
        context = self.load_context()
        return [s for s in context["working_memory"]["incoming_signals"] if not s.get("processed", False)]

    def mark_signal_processed(self, signal_index: int):
        """Mark a signal as processed by index (legacy).

        Prefer [`StateManager.mark_signal_processed_by_id()`](src/state_manager.py:??) for stability.
        """
        context = self.load_context()
        if signal_index < len(context["working_memory"]["incoming_signals"]):
            context["working_memory"]["incoming_signals"][signal_index]["processed"] = True
            context["working_memory"]["incoming_signals"][signal_index]["processed_at"] = datetime.now().isoformat()
        self.save_context(context)

    def mark_signal_processed_by_id(self, signal_id: str) -> bool:
        """Mark a signal as processed by stable id."""
        context = self.load_context()
        for s in context["working_memory"]["incoming_signals"]:
            if s.get("id") == signal_id:
                s["processed"] = True
                s["processed_at"] = datetime.now().isoformat()
                self.save_context(context)
                return True
        return False

    def clear_processed_signals(self):
        """Remove processed signals (keep last 10 for history)"""
        context = self.load_context()
        unprocessed = [s for s in context["working_memory"]["incoming_signals"] if not s.get("processed", False)]
        processed = [s for s in context["working_memory"]["incoming_signals"] if s.get("processed", False)]

        # Keep last 10 processed signals for history
        context["working_memory"]["incoming_signals"] = unprocessed + processed[-10:]
        self.save_context(context)

    def set_config_override(self, key: str, value: Any, *, expires_at: str | None = None) -> None:
        """Set a runtime configuration override stored in persistent context."""
        context = self.load_context()
        overrides = context.setdefault("long_term_memory", {}).setdefault("config_overrides", {})
        overrides[key] = {
            "value": value,
            "expires_at": expires_at,
            "set_at": datetime.now().isoformat(),
        }
        self.save_context(context)

    def get_config_override(self, key: str) -> Any | None:
        """Get override if present and not expired, otherwise None."""
        context = self.load_context()
        overrides = context.get("long_term_memory", {}).get("config_overrides", {}) or {}
        item = overrides.get(key)
        if not item:
            return None

        expires_at = item.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if datetime.now(exp.tzinfo) >= exp:
                    # Expired: clean up
                    overrides.pop(key, None)
                    self.save_context(context)
                    return None
            except Exception:
                # If parsing fails, treat as expired to be safe
                overrides.pop(key, None)
                self.save_context(context)
                return None

        return item.get("value")
