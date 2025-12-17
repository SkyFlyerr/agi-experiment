#!/usr/bin/env python3
"""
Test script for Server-Agent components
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from state_manager import StateManager


def test_state_manager():
    """Test StateManager component"""
    print("🧪 Testing State Manager...")
    print("-" * 50)

    # Create state manager
    sm = StateManager(data_dir="data")

    # Test 1: Load initial context
    print("\n1. Loading initial context...")
    context = sm.load_context()
    print(f"   ✅ Context loaded: {context['current_session']['session_id']}")

    # Test 2: Record action
    print("\n2. Recording test action...")
    action = {
        "action": "test_action",
        "reasoning": "Testing the state manager",
        "certainty": 0.95,
        "significance": 0.3,
        "type": "internal",
        "autonomous": True
    }
    result = {
        "success": True,
        "message": "Test action completed successfully"
    }
    sm.record_action(action, result)
    print("   ✅ Action recorded")

    # Test 3: Add skill
    print("\n3. Adding test skill...")
    sm.add_skill("test_skill", {
        "description": "A test skill for validation",
        "status": "completed"
    })
    print("   ✅ Skill added")

    # Test 4: Get session summary
    print("\n4. Getting session summary...")
    summary = sm.get_session_summary()
    print(f"   Session ID: {summary['session_id']}")
    print(f"   Cycles: {summary['cycles']}")
    print(f"   Focus: {summary['current_focus']}")
    print(f"   Recent actions: {summary['recent_actions']}")
    print(f"   ✅ Summary generated")

    # Test 5: Verify persistence
    print("\n5. Verifying persistence...")
    context_file = Path("data/context.json")
    if context_file.exists():
        with open(context_file) as f:
            saved_context = json.load(f)
        print(f"   ✅ Context persisted to {context_file}")
        print(f"   Working memory actions: {len(saved_context['working_memory']['recent_actions'])}")
        print(f"   Skills learned: {len(saved_context['long_term_memory']['skills_learned'])}")
    else:
        print("   ❌ Context file not found")
        return False

    print("\n" + "=" * 50)
    print("✅ All State Manager tests passed!\n")
    return True


def test_file_structure():
    """Test that required directories exist"""
    print("🧪 Testing File Structure...")
    print("-" * 50)

    required_dirs = [
        "data",
        "data/history",
        "data/skills",
        "logs",
        "src"
    ]

    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"   ✅ {dir_path}/")
        else:
            print(f"   ❌ {dir_path}/ - MISSING")
            all_exist = False

    required_files = [
        "src/main.py",
        "src/state_manager.py",
        "src/telegram_bot.py",
        "src/proactivity_loop.py",
        "requirements.txt",
        ".env.example",
        "README.md",
        "ARCHITECTURE.md",
        "CLAUDE.md"
    ]

    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            all_exist = False

    print("\n" + "=" * 50)
    if all_exist:
        print("✅ All required files and directories exist!\n")
    else:
        print("❌ Some files or directories are missing\n")

    return all_exist


def test_env_file():
    """Test .env file configuration"""
    print("🧪 Testing Environment Configuration...")
    print("-" * 50)

    env_file = Path(".env")
    if not env_file.exists():
        print("   ⚠️  .env file not found")
        print("   ℹ️  Copy .env.example to .env and configure it")
        return False

    from dotenv import load_dotenv
    import os

    load_dotenv()

    required_vars = [
        "TELEGRAM_API_TOKEN",
        "TELEGRAM_BOT_NAME",
        "MASTER_MAX_TELEGRAM_CHAT_ID",
        "ANTHROPIC_API_KEY"
    ]

    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value and value != f"your_{var.lower()}":
            print(f"   ✅ {var} is set")
        else:
            print(f"   ❌ {var} is NOT set or still has placeholder value")
            all_set = False

    print("\n" + "=" * 50)
    if all_set:
        print("✅ Environment is properly configured!\n")
    else:
        print("⚠️  Please configure .env file with actual values\n")

    return all_set


def main():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("🤖 Server-Agent Component Tests")
    print("=" * 50 + "\n")

    tests = [
        ("File Structure", test_file_structure),
        ("State Manager", test_state_manager),
        ("Environment Config", test_env_file)
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} test failed with error: {e}\n")
            results[name] = False

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)

    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")

    all_passed = all(results.values())

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! The agent is ready to run.")
        print("\nNext steps:")
        print("1. Configure .env if not already done")
        print("2. Run: python src/main.py")
        print("3. Test Telegram commands: /start, /status")
    else:
        print("⚠️  Some tests failed. Please fix issues above.")
        print("\nCommon fixes:")
        print("- Run ./setup.sh to create missing directories")
        print("- Copy .env.example to .env and configure")
        print("- Ensure all dependencies are installed: pip install -r requirements.txt")

    print("=" * 50 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
