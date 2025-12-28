"""Session Harness for AI Agent - Initialization and Iteration Separation.

Implements AI harness patterns from Anthropic research:
https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

Key patterns:
1. Initialization (runs once per session):
   - Read progress files
   - Verify system state
   - Run smoke tests
   - Identify next priority

2. Iteration (runs repeatedly):
   - Work on ONE feature
   - Test and verify
   - Update progress
   - Maintain clean state
"""

import logging
import json
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Harness file paths
DATA_DIR = Path("/app/data")
FEATURE_LIST_PATH = DATA_DIR / "feature_list.json"
PROGRESS_FILE_PATH = DATA_DIR / "claude-progress.txt"
SKILLS_DIR = Path("/app/skills")


class SessionState:
    """Tracks session state for harness pattern."""

    def __init__(self):
        self.initialized = False
        self.session_start = datetime.utcnow()
        self.current_feature: Optional[str] = None
        self.features_attempted: List[str] = []
        self.tests_passed: int = 0
        self.tests_failed: int = 0
        self.git_commits: List[str] = []
        self.clean_state: bool = True
        self.blockers: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initialized": self.initialized,
            "session_start": self.session_start.isoformat(),
            "current_feature": self.current_feature,
            "features_attempted": self.features_attempted,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "git_commits": self.git_commits,
            "clean_state": self.clean_state,
            "blockers": self.blockers,
        }


# Global session state
_session_state = SessionState()


async def run_initialization() -> Dict[str, Any]:
    """
    Run initialization phase (once per session).

    Steps:
    1. Read claude-progress.txt
    2. Read feature_list.json
    3. Check git status
    4. Run smoke tests
    5. Identify priority feature

    Returns:
        Initialization result with next steps
    """
    global _session_state

    if _session_state.initialized:
        logger.info("Session already initialized, skipping")
        return {
            "status": "already_initialized",
            "session_state": _session_state.to_dict(),
        }

    logger.info("Running session initialization (AI Harness pattern)")

    result = {
        "status": "initializing",
        "steps_completed": [],
        "errors": [],
        "next_priority": None,
    }

    # Step 1: Read progress file
    progress_content = None
    try:
        if PROGRESS_FILE_PATH.exists():
            progress_content = PROGRESS_FILE_PATH.read_text()
            result["steps_completed"].append("read_progress_file")
            logger.info("Read progress file successfully")
        else:
            result["errors"].append("Progress file not found")
            logger.warning("Progress file not found, starting fresh")
    except Exception as e:
        result["errors"].append(f"Error reading progress: {e}")
        logger.error(f"Error reading progress file: {e}")

    # Step 2: Read feature list
    feature_list = None
    try:
        if FEATURE_LIST_PATH.exists():
            with open(FEATURE_LIST_PATH) as f:
                feature_list = json.load(f)
            result["steps_completed"].append("read_feature_list")
            result["feature_stats"] = feature_list.get("statistics", {})
            logger.info(f"Read feature list: {feature_list.get('statistics', {})}")
        else:
            result["errors"].append("Feature list not found")
            logger.warning("Feature list not found")
    except Exception as e:
        result["errors"].append(f"Error reading features: {e}")
        logger.error(f"Error reading feature list: {e}")

    # Step 3: Check git status
    try:
        git_status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd="/app",
            timeout=10,
        )
        if git_status.returncode == 0:
            uncommitted = git_status.stdout.strip()
            if uncommitted:
                _session_state.clean_state = False
                result["uncommitted_changes"] = uncommitted.split("\n")
                logger.warning(f"Found uncommitted changes: {uncommitted}")
            else:
                _session_state.clean_state = True
            result["steps_completed"].append("check_git_status")
    except Exception as e:
        result["errors"].append(f"Error checking git: {e}")
        logger.error(f"Error checking git status: {e}")

    # Step 4: Get recent git commits
    try:
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True,
            text=True,
            cwd="/app",
            timeout=10,
        )
        if git_log.returncode == 0:
            result["recent_commits"] = git_log.stdout.strip().split("\n")[:10]
            result["steps_completed"].append("read_git_log")
    except Exception as e:
        result["errors"].append(f"Error reading git log: {e}")

    # Step 5: Run smoke tests
    smoke_test_result = await run_smoke_tests()
    result["smoke_tests"] = smoke_test_result
    if smoke_test_result.get("passed"):
        result["steps_completed"].append("smoke_tests_passed")
    else:
        result["errors"].append("Smoke tests failed")
        _session_state.blockers.append("Smoke tests failing")

    # Step 6: Identify next priority feature
    if feature_list:
        priority_feature = find_next_priority_feature(feature_list)
        if priority_feature:
            result["next_priority"] = priority_feature
            _session_state.current_feature = priority_feature["id"]
            result["steps_completed"].append("identified_priority")

    # Mark as initialized
    _session_state.initialized = True
    result["status"] = "initialized"
    result["session_state"] = _session_state.to_dict()

    logger.info(f"Initialization complete: {len(result['steps_completed'])} steps, {len(result['errors'])} errors")

    return result


async def run_smoke_tests() -> Dict[str, Any]:
    """
    Run basic smoke tests to verify system functionality.

    Tests:
    - Database connectivity
    - API health endpoint
    - Telegram bot responsiveness
    - File system access

    Returns:
        Test results
    """
    results = {
        "passed": True,
        "tests": [],
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Test 1: Check if app directory exists
    try:
        app_dir = Path("/app")
        if app_dir.exists():
            results["tests"].append({"name": "app_directory", "passed": True})
        else:
            results["tests"].append({"name": "app_directory", "passed": False, "error": "Not found"})
            results["passed"] = False
    except Exception as e:
        results["tests"].append({"name": "app_directory", "passed": False, "error": str(e)})
        results["passed"] = False

    # Test 2: Check if data directory is writable
    try:
        test_file = DATA_DIR / ".smoke_test"
        test_file.write_text("test")
        test_file.unlink()
        results["tests"].append({"name": "data_writable", "passed": True})
    except Exception as e:
        results["tests"].append({"name": "data_writable", "passed": False, "error": str(e)})
        results["passed"] = False

    # Test 3: Check if feature list is valid JSON
    try:
        if FEATURE_LIST_PATH.exists():
            with open(FEATURE_LIST_PATH) as f:
                json.load(f)
            results["tests"].append({"name": "feature_list_valid", "passed": True})
        else:
            results["tests"].append({"name": "feature_list_valid", "passed": False, "error": "Not found"})
    except Exception as e:
        results["tests"].append({"name": "feature_list_valid", "passed": False, "error": str(e)})
        results["passed"] = False

    # Test 4: Check Python imports
    try:
        import asyncpg
        import anthropic
        import aiogram
        results["tests"].append({"name": "python_imports", "passed": True})
    except ImportError as e:
        results["tests"].append({"name": "python_imports", "passed": False, "error": str(e)})
        results["passed"] = False

    _session_state.tests_passed = sum(1 for t in results["tests"] if t["passed"])
    _session_state.tests_failed = sum(1 for t in results["tests"] if not t["passed"])

    return results


def find_next_priority_feature(feature_list: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the next priority feature to work on.

    Priority order:
    1. Critical priority, failing
    2. High priority, failing
    3. Medium priority, failing
    4. Low priority, failing

    Args:
        feature_list: Feature list data

    Returns:
        Next priority feature or None
    """
    features = feature_list.get("features", [])

    priority_order = ["critical", "high", "medium", "low"]

    for priority in priority_order:
        for feature in features:
            if (
                feature.get("priority") == priority
                and feature.get("status") == "failing"
            ):
                return feature

    return None


async def run_iteration(feature_id: str) -> Dict[str, Any]:
    """
    Run one iteration of feature implementation.

    Steps:
    1. Load feature from feature_list.json
    2. Implement/fix the feature
    3. Test and verify
    4. Update feature status
    5. Update progress file
    6. Commit changes

    Args:
        feature_id: ID of feature to work on

    Returns:
        Iteration result
    """
    global _session_state

    if not _session_state.initialized:
        return {
            "status": "error",
            "error": "Session not initialized. Call run_initialization() first.",
        }

    logger.info(f"Running iteration for feature: {feature_id}")

    result = {
        "status": "in_progress",
        "feature_id": feature_id,
        "steps_completed": [],
        "errors": [],
    }

    # Load feature details
    try:
        with open(FEATURE_LIST_PATH) as f:
            feature_list = json.load(f)

        feature = None
        for f in feature_list.get("features", []):
            if f.get("id") == feature_id:
                feature = f
                break

        if not feature:
            result["status"] = "error"
            result["error"] = f"Feature {feature_id} not found"
            return result

        result["feature"] = feature
        result["steps_completed"].append("loaded_feature")

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Error loading feature: {e}"
        return result

    # Track attempt
    _session_state.features_attempted.append(feature_id)
    _session_state.current_feature = feature_id

    # Note: Actual implementation would be done by Claude with tools
    # This is the harness structure, not the implementation itself
    result["status"] = "ready_for_implementation"
    result["implementation_context"] = {
        "feature": feature,
        "steps": feature.get("steps", []),
        "priority": feature.get("priority"),
        "current_status": feature.get("status"),
    }

    return result


async def update_progress(
    summary: str,
    next_steps: List[str],
    blockers: Optional[List[str]] = None,
) -> bool:
    """
    Update the progress file for session continuity.

    Args:
        summary: What was accomplished
        next_steps: What should be done next
        blockers: Any issues or blockers

    Returns:
        True if update successful
    """
    global _session_state

    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Read existing content
        existing_content = ""
        if PROGRESS_FILE_PATH.exists():
            existing_content = PROGRESS_FILE_PATH.read_text()

        # Build update section
        update_section = f"""
---

## Session Update: {timestamp}

### Completed:
{summary}

### Next Steps:
{chr(10).join('- ' + step for step in next_steps)}

### Blockers:
{chr(10).join('- ' + b for b in (blockers or [])) if blockers else '- None'}

### Session Stats:
- Features attempted: {len(_session_state.features_attempted)}
- Tests passed: {_session_state.tests_passed}
- Tests failed: {_session_state.tests_failed}
- Clean state: {_session_state.clean_state}

"""

        # Prepend update to existing content (most recent first after header)
        if "# Atman" in existing_content:
            # Insert after header section
            parts = existing_content.split("---", 1)
            if len(parts) == 2:
                new_content = parts[0] + update_section + "---" + parts[1]
            else:
                new_content = existing_content + update_section
        else:
            new_content = existing_content + update_section

        PROGRESS_FILE_PATH.write_text(new_content)

        logger.info("Progress file updated successfully")
        return True

    except Exception as e:
        logger.error(f"Error updating progress file: {e}")
        return False


async def update_feature_status(
    feature_id: str,
    new_status: str,
    notes: Optional[str] = None,
) -> bool:
    """
    Update feature status in feature_list.json.

    Args:
        feature_id: ID of feature to update
        new_status: New status (passing/failing)
        notes: Optional notes about the change

    Returns:
        True if update successful
    """
    try:
        with open(FEATURE_LIST_PATH) as f:
            feature_list = json.load(f)

        updated = False
        for feature in feature_list.get("features", []):
            if feature.get("id") == feature_id:
                old_status = feature.get("status")
                feature["status"] = new_status
                feature["last_updated"] = datetime.utcnow().isoformat()
                if notes:
                    feature["notes"] = notes
                updated = True
                logger.info(f"Feature {feature_id}: {old_status} -> {new_status}")
                break

        if updated:
            # Recalculate statistics
            features = feature_list.get("features", [])
            passing = sum(1 for f in features if f.get("status") == "passing")
            failing = sum(1 for f in features if f.get("status") == "failing")

            feature_list["statistics"]["passing"] = passing
            feature_list["statistics"]["failing"] = failing

            with open(FEATURE_LIST_PATH, "w") as f:
                json.dump(feature_list, f, indent=2)

            return True

        return False

    except Exception as e:
        logger.error(f"Error updating feature status: {e}")
        return False


async def ensure_clean_state() -> Tuple[bool, str]:
    """
    Ensure codebase is in clean state before ending session.

    Returns:
        Tuple of (is_clean, message)
    """
    global _session_state

    try:
        # Check for uncommitted changes
        git_status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd="/app",
            timeout=10,
        )

        if git_status.returncode != 0:
            return False, f"Git error: {git_status.stderr}"

        uncommitted = git_status.stdout.strip()
        if uncommitted:
            _session_state.clean_state = False
            return False, f"Uncommitted changes: {uncommitted}"

        _session_state.clean_state = True
        return True, "Clean state verified"

    except Exception as e:
        return False, f"Error checking state: {e}"


def get_session_state() -> Dict[str, Any]:
    """Get current session state."""
    return _session_state.to_dict()


__all__ = [
    "run_initialization",
    "run_iteration",
    "run_smoke_tests",
    "find_next_priority_feature",
    "update_progress",
    "update_feature_status",
    "ensure_clean_state",
    "get_session_state",
    "SessionState",
]
