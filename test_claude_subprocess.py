#!/usr/bin/env python3
"""Test Claude CLI subprocess with OAuth token"""
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

env = os.environ.copy()
print(f"CLAUDE_CODE_OAUTH_TOKEN in env: {'YES' if 'CLAUDE_CODE_OAUTH_TOKEN' in env else 'NO'}")
print(f"Value starts with: {env.get('CLAUDE_CODE_OAUTH_TOKEN', 'NONE')[:20]}...")

result = subprocess.run(
    ["/usr/bin/claude", "--print", "test"],
    capture_output=True,
    text=True,
    env=env
)

print(f"\nReturn code: {result.returncode}")
print(f"Output: {result.stdout[:200]}")
print(f"Stderr: {result.stderr[:200]}")
