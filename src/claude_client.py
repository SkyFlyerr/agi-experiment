"""src/claude_client.py

Claude client abstraction.

Goal: Prefer Claude Code CLI authenticated via Claude Max subscription (OAuth token)
so we do NOT spend pay-as-you-go Anthropic API tokens.

This module intentionally defaults to CLI mode and will refuse to use the
Anthropic API unless explicitly allowed via env.

Requirements reference:
- Claude Code CLI in headless mode: /usr/bin/claude --print --no-session-persistence
- Subprocess integration with timeout handling
- JSON response parsing and token usage extraction

"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ClaudeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_input_tokens


@dataclass(frozen=True)
class ClaudeResponse:
    text: str
    usage: ClaudeUsage
    raw: Dict[str, Any]


class ClaudeClientError(RuntimeError):
    pass


class ClaudeClient:
    """A minimal client that calls Claude either via Claude Code CLI (preferred) or API.

    By default, API calls are disabled to avoid pay-as-you-go spend.
    """

    def __init__(
        self,
        *,
        cli_path: Optional[str] = None,
        oauth_token: Optional[str] = None,
        allow_payg_api: Optional[bool] = None,
    ):
        self.cli_path = cli_path or os.getenv("CLAUDE_CLI_PATH", "/usr/bin/claude")

        # OAuth token should come from Claude Max setup-token flow.
        self.oauth_token = oauth_token or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")

        # Explicit opt-in required for API usage.
        if allow_payg_api is None:
            allow_payg_api = os.getenv("ALLOW_PAYG_API", "false").lower() in {"1", "true", "yes"}
        self.allow_payg_api = bool(allow_payg_api)

        # API key might exist, but we treat it as pay-as-you-go unless explicitly allowed.
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    def _build_cli_env(self) -> Dict[str, str]:
        env = os.environ.copy()

        # CRITICAL: If ANTHROPIC_API_KEY contains an OAuth token (sk-ant-oat...),
        # Claude Code CLI can prioritize it and break auth semantics.
        if env.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-oat"):
            env.pop("ANTHROPIC_API_KEY", None)

        if self.oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = self.oauth_token

        return env

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 4000,
        timeout_s: int = 120,
        output_format: str = "json",
    ) -> ClaudeResponse:
        """Run a completion.

        Prefers CLI (Claude Max). API is used only if ALLOW_PAYG_API=true.
        """

        if self.oauth_token:
            return await self._complete_via_cli(
                prompt,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                output_format=output_format,
            )

        if not self.allow_payg_api:
            raise ClaudeClientError(
                "Claude OAuth token not configured (CLAUDE_CODE_OAUTH_TOKEN). "
                "Pay-as-you-go API is disabled (ALLOW_PAYG_API=false)."
            )

        return await self._complete_via_api(prompt, max_tokens=max_tokens, timeout_s=timeout_s)

    async def _complete_via_cli(
        self,
        prompt: str,
        *,
        max_tokens: int,
        timeout_s: int,
        output_format: str,
    ) -> ClaudeResponse:
        # NOTE: Some Claude Code CLI builds do not support --max-tokens.
        # We attempt with --max-tokens first, then retry without it if needed.
        args = [
            self.cli_path,
            "--print",
            "--no-session-persistence",
            "--max-tokens",
            str(max_tokens),
        ]

        # For parsing usage reliably.
        if output_format:
            args += ["--output-format", output_format]

        env = self._build_cli_env()

        async def _run(cli_args: list[str]) -> tuple[int, str, str]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cli_args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(prompt.encode("utf-8")),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError as e:
                raise ClaudeClientError(f"Claude CLI timeout after {timeout_s}s") from e

            stdout = stdout_b.decode("utf-8", errors="replace").strip()
            stderr = stderr_b.decode("utf-8", errors="replace").strip()
            return proc.returncode or 0, stdout, stderr

        code, stdout, stderr = await _run(args)

        if code != 0 and "unknown option '--max-tokens'" in (stderr or ""):
            # Retry without --max-tokens for older/alternate CLI builds.
            args_no_max = [a for a in args if a not in {"--max-tokens", str(max_tokens)}]
            code, stdout, stderr = await _run(args_no_max)

        if code != 0:
            raise ClaudeClientError(f"Claude CLI failed (code {code}). stderr={stderr[:400]}")

        if output_format == "json":
            try:
                raw = json.loads(stdout)
            except json.JSONDecodeError as e:
                raise ClaudeClientError(f"Claude CLI returned non-JSON output: {stdout[:400]}") from e

            text = str(raw.get("result", "")).strip()
            usage_raw = raw.get("usage", {}) or {}
            usage = ClaudeUsage(
                input_tokens=int(usage_raw.get("input_tokens", 0) or 0),
                output_tokens=int(usage_raw.get("output_tokens", 0) or 0),
                cache_read_input_tokens=int(usage_raw.get("cache_read_input_tokens", 0) or 0),
            )
            return ClaudeResponse(text=text, usage=usage, raw=raw)

        return ClaudeResponse(text=stdout, usage=ClaudeUsage(), raw={"stdout": stdout, "stderr": stderr})

    async def _complete_via_api(self, prompt: str, *, max_tokens: int, timeout_s: int) -> ClaudeResponse:
        """Pay-as-you-go Anthropic API path (explicit opt-in only)."""

        if not self.anthropic_api_key:
            raise ClaudeClientError("ANTHROPIC_API_KEY not configured")

        # Import lazily to keep CLI-only installs working.
        from anthropic import Anthropic  # type: ignore

        client = Anthropic(api_key=self.anthropic_api_key)

        # NOTE: This is blocking; we wrap it to avoid blocking the event loop.
        def _call_sync():
            return client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_call_sync), timeout=timeout_s)
        except asyncio.TimeoutError as e:
            raise ClaudeClientError(f"Anthropic API timeout after {timeout_s}s") from e

        text = resp.content[0].text
        usage = ClaudeUsage(
            input_tokens=int(resp.usage.input_tokens),
            output_tokens=int(resp.usage.output_tokens),
            cache_read_input_tokens=0,
        )
        return ClaudeResponse(text=text, usage=usage, raw={"api": True})
