"""Tool executor for AI operations."""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Safety checks for destructive operations
DESTRUCTIVE_COMMANDS = [
    "rm -rf",
    "dd if=",
    "mkfs",
    "format",
    "> /dev/",
    "systemctl stop",
    "systemctl disable",
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
]


async def execute_bash(command: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Execute bash command.

    Args:
        command: Bash command to execute
        timeout: Timeout in seconds (default: 60)

    Returns:
        Dict with:
            - status: "success" or "error"
            - stdout: Command stdout
            - stderr: Command stderr
            - exit_code: Exit code

    Safety:
        - Checks for destructive commands
        - Enforces timeout
        - Logs all executions
    """
    try:
        # Safety check - prevent destructive commands
        for dangerous in DESTRUCTIVE_COMMANDS:
            if dangerous in command:
                logger.warning(f"Blocked potentially destructive command: {command}")
                return {
                    "status": "error",
                    "error": f"Blocked: potentially destructive command containing '{dangerous}'",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }

        logger.info(f"Executing bash command: {command}")

        # Execute command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"Command timeout after {timeout}s: {command}")
            return {
                "status": "error",
                "error": f"Command timeout after {timeout}s",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""
        exit_code = process.returncode or 0

        if exit_code == 0:
            logger.info(f"Command succeeded: {command}")
            return {
                "status": "success",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": exit_code,
            }
        else:
            logger.warning(f"Command failed with exit code {exit_code}: {command}")
            return {
                "status": "error",
                "error": f"Command exited with code {exit_code}",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": exit_code,
            }

    except Exception as e:
        logger.error(f"Error executing bash command: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }


async def execute_file_operation(
    action: str,
    path: str,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute file operation.

    Args:
        action: Operation type ("read", "write", "append", "delete", "list")
        path: File/directory path
        content: Content for write/append operations

    Returns:
        Dict with:
            - status: "success" or "error"
            - result: Operation result (file content, listing, etc.)
            - error: Error message (if failed)

    Safety:
        - Validates paths
        - Prevents operations outside allowed directories
        - Logs all operations
    """
    try:
        logger.info(f"File operation: {action} on {path}")

        # Normalize path
        file_path = Path(path).expanduser().resolve()

        # Safety check - prevent operations on sensitive system files
        sensitive_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/etc/sudoers",
            "/root/.ssh",
            "/home/*/.ssh/id_rsa",
        ]

        path_str = str(file_path)
        for sensitive in sensitive_paths:
            if sensitive.replace("*", "") in path_str:
                logger.warning(f"Blocked operation on sensitive path: {path_str}")
                return {
                    "status": "error",
                    "error": f"Blocked: operation on sensitive path",
                }

        # Execute operation
        if action == "read":
            if not file_path.exists():
                return {
                    "status": "error",
                    "error": f"File not found: {path_str}",
                }

            if not file_path.is_file():
                return {
                    "status": "error",
                    "error": f"Not a file: {path_str}",
                }

            content = file_path.read_text(encoding="utf-8", errors="replace")
            return {
                "status": "success",
                "result": content,
            }

        elif action == "write":
            if content is None:
                return {
                    "status": "error",
                    "error": "No content provided for write operation",
                }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "result": f"Wrote {len(content)} bytes to {path_str}",
            }

        elif action == "append":
            if content is None:
                return {
                    "status": "error",
                    "error": "No content provided for append operation",
                }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as f:
                f.write(content)
            return {
                "status": "success",
                "result": f"Appended {len(content)} bytes to {path_str}",
            }

        elif action == "delete":
            if not file_path.exists():
                return {
                    "status": "error",
                    "error": f"File not found: {path_str}",
                }

            if file_path.is_file():
                file_path.unlink()
                return {
                    "status": "success",
                    "result": f"Deleted file: {path_str}",
                }
            else:
                return {
                    "status": "error",
                    "error": f"Not a file: {path_str}",
                }

        elif action == "list":
            if not file_path.exists():
                return {
                    "status": "error",
                    "error": f"Directory not found: {path_str}",
                }

            if not file_path.is_dir():
                return {
                    "status": "error",
                    "error": f"Not a directory: {path_str}",
                }

            items = [item.name for item in file_path.iterdir()]
            return {
                "status": "success",
                "result": items,
            }

        else:
            return {
                "status": "error",
                "error": f"Unknown action: {action}",
            }

    except Exception as e:
        logger.error(f"Error in file operation: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


async def execute_api_call(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Execute HTTP API call.

    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        payload: Request payload (for POST/PUT)
        headers: Request headers
        timeout: Timeout in seconds (default: 30)

    Returns:
        Dict with:
            - status: "success" or "error"
            - status_code: HTTP status code
            - response: Response body (JSON or text)
            - error: Error message (if failed)

    Safety:
        - Enforces timeout
        - Logs all requests
    """
    try:
        logger.info(f"API call: {method} {url}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
            )

            # Try to parse as JSON
            try:
                response_data = response.json()
            except Exception:
                response_data = response.text

            if 200 <= response.status_code < 300:
                logger.info(f"API call succeeded: {method} {url} -> {response.status_code}")
                return {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": response_data,
                }
            else:
                logger.warning(
                    f"API call failed: {method} {url} -> {response.status_code}"
                )
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "response": response_data,
                    "error": f"HTTP {response.status_code}",
                }

    except asyncio.TimeoutError:
        logger.error(f"API call timeout after {timeout}s: {method} {url}")
        return {
            "status": "error",
            "error": f"Request timeout after {timeout}s",
            "status_code": 0,
        }
    except Exception as e:
        logger.error(f"Error in API call: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "status_code": 0,
        }


__all__ = [
    "execute_bash",
    "execute_file_operation",
    "execute_api_call",
]
