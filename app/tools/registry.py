"""
Tool registry system for AGI agent.

Defines available tools that Claude can use, with:
- Tool definitions (for Claude API)
- Tool executors (actual implementation)
- Safety controls (approval requirements, restrictions)
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolSafety(str, Enum):
    """Safety level for tool execution"""
    SAFE = "safe"  # Can execute autonomously
    REQUIRES_APPROVAL = "requires_approval"  # Needs Master approval
    DANGEROUS = "dangerous"  # Blocked unless explicitly allowed


class ToolDefinition(BaseModel):
    """Tool definition for Claude API"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    safety_level: ToolSafety = ToolSafety.SAFE

    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic API tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """Central registry of available tools for the AGI agent"""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._executors: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize standard tool set"""

        # === File System Tools ===

        self.register_tool(
            ToolDefinition(
                name="read_file",
                description="Read contents of a file. Use this to examine code, configuration, logs, or any text file.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative path to the file"
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)",
                            "default": "utf-8"
                        }
                    },
                    "required": ["path"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_read_file
        )

        self.register_tool(
            ToolDefinition(
                name="write_file",
                description="Write content to a file. Creates parent directories if needed. Use for creating new files or completely replacing existing ones.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative path to the file"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)",
                            "default": "utf-8"
                        }
                    },
                    "required": ["path", "content"]
                },
                safety_level=ToolSafety.REQUIRES_APPROVAL
            ),
            self._execute_write_file
        )

        self.register_tool(
            ToolDefinition(
                name="list_directory",
                description="List contents of a directory. Use to explore file structure.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Whether to list recursively",
                            "default": False
                        }
                    },
                    "required": ["path"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_list_directory
        )

        # === Shell Execution Tools ===

        self.register_tool(
            ToolDefinition(
                name="run_bash",
                description="Execute a bash command. Use for running scripts, checking system status, installing packages, etc. IMPORTANT: Destructive commands require approval.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash command to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 60)",
                            "default": 60
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Working directory for command execution"
                        }
                    },
                    "required": ["command"]
                },
                safety_level=ToolSafety.REQUIRES_APPROVAL  # Will be auto-approved for safe commands
            ),
            self._execute_bash
        )

        # === Code Search Tools ===

        self.register_tool(
            ToolDefinition(
                name="search_code",
                description="Search for patterns in code using grep. Use to find function definitions, imports, usage patterns, etc.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern (supports regex)"
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search in (default: current directory)"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "File pattern to filter (e.g., '*.py', '*.ts')"
                        },
                        "case_sensitive": {
                            "type": "boolean",
                            "description": "Whether search is case-sensitive",
                            "default": True
                        }
                    },
                    "required": ["pattern"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_search_code
        )

        # === Communication Tools ===

        self.register_tool(
            ToolDefinition(
                name="send_telegram_message",
                description="Send a message to Master via Telegram. Use for reporting results, asking questions, or sharing insights.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Message text to send (supports HTML formatting)"
                        },
                        "chat_id": {
                            "type": "string",
                            "description": "Chat ID to send to (default: Master's chat)"
                        }
                    },
                    "required": ["text"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_send_telegram
        )

        # === API Tools ===

        self.register_tool(
            ToolDefinition(
                name="http_request",
                description="Make HTTP API request. Use for interacting with external services, APIs, webhooks, etc.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "API endpoint URL"
                        },
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
                            "default": "GET"
                        },
                        "payload": {
                            "type": "object",
                            "description": "Request payload (for POST/PUT)"
                        },
                        "headers": {
                            "type": "object",
                            "description": "Request headers"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30)",
                            "default": 30
                        }
                    },
                    "required": ["url"]
                },
                safety_level=ToolSafety.REQUIRES_APPROVAL
            ),
            self._execute_http_request
        )

        # === Memory Tools ===

        self.register_tool(
            ToolDefinition(
                name="remember",
                description="Store important information in long-term memory. Use for facts, patterns, insights, or anything worth remembering.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Memory key (identifier for this piece of information)"
                        },
                        "value": {
                            "type": "string",
                            "description": "Information to remember"
                        },
                        "category": {
                            "type": "string",
                            "description": "Category (skill, fact, pattern, insight, etc.)"
                        }
                    },
                    "required": ["key", "value"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_remember
        )

        self.register_tool(
            ToolDefinition(
                name="recall",
                description="Retrieve information from long-term memory. Use to access previously stored facts, patterns, or insights.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Memory key to retrieve"
                        },
                        "category": {
                            "type": "string",
                            "description": "Category filter (optional)"
                        }
                    },
                    "required": ["key"]
                },
                safety_level=ToolSafety.SAFE
            ),
            self._execute_recall
        )

        logger.info(f"Tool registry initialized with {len(self._tools)} tools")

    def register_tool(
        self,
        definition: ToolDefinition,
        executor: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ):
        """Register a new tool"""
        self._tools[definition.name] = definition
        self._executors[definition.name] = executor
        logger.debug(f"Registered tool: {definition.name} (safety: {definition.safety_level})")

    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[ToolDefinition]:
        """Get all registered tools"""
        return list(self._tools.values())

    def get_tools_for_claude(self) -> List[Dict[str, Any]]:
        """Get tools in Anthropic API format"""
        return [tool.to_anthropic_format() for tool in self._tools.values()]

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool with given arguments"""
        if name not in self._executors:
            return {
                "status": "error",
                "error": f"Unknown tool: {name}"
            }

        try:
            executor = self._executors[name]
            result = await executor(arguments)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool Executors ===

    async def _execute_read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute read_file tool"""
        from app.tools.executor import execute_file_operation

        result = await execute_file_operation(
            action="read",
            path=args["path"]
        )
        return result

    async def _execute_write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute write_file tool"""
        from app.tools.executor import execute_file_operation

        result = await execute_file_operation(
            action="write",
            path=args["path"],
            content=args["content"]
        )
        return result

    async def _execute_list_directory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute list_directory tool"""
        from app.tools.executor import execute_file_operation

        result = await execute_file_operation(
            action="list",
            path=args["path"]
        )
        return result

    async def _execute_bash(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute run_bash tool"""
        from app.tools.executor import execute_bash

        result = await execute_bash(
            command=args["command"],
            timeout=args.get("timeout", 60)
        )
        return result

    async def _execute_search_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search_code tool"""
        from app.tools.executor import execute_bash

        pattern = args["pattern"]
        path = args.get("path", ".")
        file_pattern = args.get("file_pattern", "*")
        case_sensitive = args.get("case_sensitive", True)

        # Build grep command
        grep_cmd = "grep -r"
        if not case_sensitive:
            grep_cmd += " -i"

        grep_cmd += f" '{pattern}' {path}"

        if file_pattern != "*":
            grep_cmd += f" --include='{file_pattern}'"

        result = await execute_bash(grep_cmd, timeout=30)
        return result

    async def _execute_send_telegram(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute send_telegram_message tool"""
        from app.telegram import send_message
        from app.config import settings

        chat_id = args.get("chat_id")
        if not chat_id:
            # Default to Master's chat
            master_ids = settings.master_chat_ids_list
            if not master_ids:
                return {
                    "status": "error",
                    "error": "No master chat ID configured"
                }
            chat_id = str(master_ids[0])

        try:
            message_id = await send_message(
                chat_id=chat_id,
                text=args["text"]
            )
            return {
                "status": "success",
                "message_id": message_id
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _execute_http_request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute http_request tool"""
        from app.tools.executor import execute_api_call

        result = await execute_api_call(
            url=args["url"],
            method=args.get("method", "GET"),
            payload=args.get("payload"),
            headers=args.get("headers"),
            timeout=args.get("timeout", 30)
        )
        return result

    async def _execute_remember(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute remember tool"""
        from app.db import get_db

        try:
            db = get_db()

            # Store in a simple key-value memory table
            # (You'll need to create this table in your schema)
            await db.execute(
                """
                INSERT INTO agent_memory (key, value, category, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (key) DO UPDATE
                SET value = $2, category = $3, updated_at = NOW()
                """,
                args["key"],
                args["value"],
                args.get("category", "general")
            )

            return {
                "status": "success",
                "message": f"Remembered: {args['key']}"
            }
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _execute_recall(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute recall tool"""
        from app.db import get_db

        try:
            db = get_db()

            query = "SELECT value, category, created_at FROM agent_memory WHERE key = $1"
            params = [args["key"]]

            if "category" in args:
                query += " AND category = $2"
                params.append(args["category"])

            row = await db.fetch_one(query, *params)

            if row:
                return {
                    "status": "success",
                    "value": row["value"],
                    "category": row["category"],
                    "created_at": row["created_at"].isoformat()
                }
            else:
                return {
                    "status": "error",
                    "error": f"No memory found for key: {args['key']}"
                }
        except Exception as e:
            logger.error(f"Error recalling memory: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create global tool registry"""
    global _registry

    if _registry is None:
        _registry = ToolRegistry()

    return _registry


__all__ = [
    "ToolSafety",
    "ToolDefinition",
    "ToolRegistry",
    "get_tool_registry"
]
