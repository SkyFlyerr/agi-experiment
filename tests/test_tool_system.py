"""
Tests for tool system (registry, execution, approval flow).
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from app.tools.registry import ToolRegistry, ToolSafety, ToolDefinition
from app.tools.approval import (
    create_approval_request,
    approve_request,
    reject_request,
    get_approval_status,
    ApprovalStatus,
)


class TestToolRegistry:
    """Tests for tool registry"""

    def test_registry_initialization(self):
        """Test that registry initializes with standard tools"""
        registry = ToolRegistry()

        # Check that standard tools are registered
        all_tools = registry.get_all_tools()
        assert len(all_tools) > 0

        tool_names = [tool.name for tool in all_tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "run_bash" in tool_names
        assert "send_telegram_message" in tool_names

    def test_get_tool_definition(self):
        """Test getting tool definition by name"""
        registry = ToolRegistry()

        # Get existing tool
        read_file = registry.get_tool_definition("read_file")
        assert read_file is not None
        assert read_file.name == "read_file"
        assert read_file.safety_level == ToolSafety.SAFE

        # Get non-existent tool
        unknown = registry.get_tool_definition("unknown_tool")
        assert unknown is None

    def test_tools_for_claude_format(self):
        """Test conversion to Anthropic API format"""
        registry = ToolRegistry()

        tools = registry.get_tools_for_claude()
        assert isinstance(tools, list)
        assert len(tools) > 0

        # Check first tool has required fields
        tool = tools[0]
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool

    @pytest.mark.asyncio
    async def test_execute_read_file_safe(self):
        """Test that read_file executes safely"""
        registry = ToolRegistry()

        # Mock file operation
        with patch("app.tools.executor.execute_file_operation") as mock_exec:
            mock_exec.return_value = {
                "status": "success",
                "result": "file contents"
            }

            result = await registry.execute_tool(
                "read_file",
                {"path": "/tmp/test.txt"}
            )

            assert result["status"] == "success"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test that unknown tool returns error"""
        registry = ToolRegistry()

        result = await registry.execute_tool(
            "unknown_tool",
            {}
        )

        assert result["status"] == "error"
        assert "Unknown tool" in result["error"]


class TestToolSafety:
    """Tests for tool safety levels"""

    def test_safe_tools(self):
        """Test that safe tools are marked correctly"""
        registry = ToolRegistry()

        safe_tools = [
            "read_file",
            "list_directory",
            "search_code",
            "recall",
            "send_telegram_message",
            "remember",
        ]

        for tool_name in safe_tools:
            tool = registry.get_tool_definition(tool_name)
            assert tool is not None
            assert tool.safety_level == ToolSafety.SAFE

    def test_requires_approval_tools(self):
        """Test that sensitive tools require approval"""
        registry = ToolRegistry()

        approval_tools = [
            "write_file",
            "run_bash",
            "http_request",
        ]

        for tool_name in approval_tools:
            tool = registry.get_tool_definition(tool_name)
            assert tool is not None
            assert tool.safety_level == ToolSafety.REQUIRES_APPROVAL


class TestApprovalFlow:
    """Tests for approval system"""

    @pytest.mark.asyncio
    async def test_create_approval_request(self):
        """Test creating approval request"""
        with patch("app.tools.approval.get_db") as mock_db:
            mock_db.return_value.execute = AsyncMock()

            with patch("app.tools.approval.send_message") as mock_send:
                mock_send.return_value = "12345"

                request_id = await create_approval_request(
                    tool_name="write_file",
                    tool_input={"path": "/tmp/test.txt", "content": "test"},
                    reasoning="Testing file write"
                )

                assert request_id is not None
                assert len(request_id) == 36  # UUID length
                mock_db.return_value.execute.assert_called_once()
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_request(self):
        """Test approving a pending request"""
        with patch("app.tools.approval.get_db") as mock_db:
            mock_db.return_value.execute = AsyncMock(return_value=True)

            result = await approve_request(
                request_id="test-uuid",
                response="Approved by Master"
            )

            assert result is True
            mock_db.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_request(self):
        """Test rejecting a pending request"""
        with patch("app.tools.approval.get_db") as mock_db:
            mock_db.return_value.execute = AsyncMock(return_value=True)

            result = await reject_request(
                request_id="test-uuid",
                response="Rejected - too risky"
            )

            assert result is True
            mock_db.return_value.execute.assert_called_once()


class TestToolExecutionSafety:
    """Tests for safe tool execution"""

    @pytest.mark.asyncio
    async def test_destructive_command_blocked(self):
        """Test that destructive commands are blocked"""
        from app.tools.executor import execute_bash

        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda",
            "shutdown -h now",
        ]

        for cmd in dangerous_commands:
            result = await execute_bash(cmd)
            assert result["status"] == "error"
            assert "Blocked" in result["error"]

    @pytest.mark.asyncio
    async def test_safe_command_allowed(self):
        """Test that safe commands are allowed"""
        from app.tools.executor import execute_bash

        safe_commands = [
            "ls -la",
            "pwd",
            "echo 'test'",
            "whoami",
        ]

        for cmd in safe_commands:
            result = await execute_bash(cmd)
            # Should execute (may succeed or fail, but not blocked)
            assert result["status"] in ["success", "error"]
            if result["status"] == "error":
                assert "Blocked" not in result.get("error", "")

    @pytest.mark.asyncio
    async def test_sensitive_file_blocked(self):
        """Test that operations on sensitive files are blocked"""
        from app.tools.executor import execute_file_operation

        sensitive_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/.ssh/id_rsa",
        ]

        for path in sensitive_paths:
            result = await execute_file_operation(
                action="read",
                path=path
            )
            assert result["status"] == "error"
            assert "Blocked" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
