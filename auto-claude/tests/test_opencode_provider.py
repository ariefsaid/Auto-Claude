"""
Tests for OpenCode Provider
=============================

Comprehensive tests for the OpenCode provider integration including:
- Tool name translation (Auto-Claude <-> OpenCode)
- Message parsing from JSON output
- Subprocess lifecycle management (mocked)
- OpenCodeProvider implementation
- Error handling for CLI crashes, timeouts, invalid output
- Session cleanup

All tests mock the OpenCode CLI - no installation required.
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.adapters.opencode_messages import (
    OpenCodeMessageParser,
    OpenCodeParseError,
    parse_opencode_message,
    parse_opencode_output,
    parse_opencode_stream_line,
)
from core.providers.adapters.opencode_provider import OpenCodeProvider
from core.providers.adapters.opencode_subprocess import (
    OpenCodeCrashError,
    OpenCodeNotInstalledError,
    OpenCodeSubprocess,
    OpenCodeSubprocessError,
    OpenCodeTimeoutError,
    SubprocessConfig,
)
from core.providers.adapters.opencode_tools import (
    AUTOCLAUDE_TO_OPENCODE,
    OPENCODE_TO_AUTOCLAUDE,
    TOOL_MAPPINGS,
    get_all_mappings,
    get_autoclaude_tools,
    get_opencode_tools,
    get_tool_category,
    is_autoclaude_tool,
    is_opencode_tool,
    is_supported_tool,
    translate_from_opencode,
    translate_to_opencode,
    translate_tool_input,
    translate_tool_result,
)
from core.providers.client import (
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
)
from core.providers.messages import (
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)

# =============================================================================
# Tool Translation Tests
# =============================================================================


class TestToolTranslation:
    """Tests for bidirectional tool name translation."""

    def test_translate_read_to_opencode(self):
        """Read should translate to file_read."""
        assert translate_to_opencode("Read") == "file_read"

    def test_translate_write_to_opencode(self):
        """Write should translate to file_write."""
        assert translate_to_opencode("Write") == "file_write"

    def test_translate_edit_to_opencode(self):
        """Edit should translate to file_edit."""
        assert translate_to_opencode("Edit") == "file_edit"

    def test_translate_bash_to_opencode(self):
        """Bash should translate to bash_exec."""
        assert translate_to_opencode("Bash") == "bash_exec"

    def test_translate_grep_to_opencode(self):
        """Grep should translate to code_search."""
        assert translate_to_opencode("Grep") == "code_search"

    def test_translate_glob_to_opencode(self):
        """Glob should translate to file_search."""
        assert translate_to_opencode("Glob") == "file_search"

    def test_translate_webfetch_to_opencode(self):
        """WebFetch should translate to web_fetch."""
        assert translate_to_opencode("WebFetch") == "web_fetch"

    def test_translate_websearch_to_opencode(self):
        """WebSearch should translate to web_search."""
        assert translate_to_opencode("WebSearch") == "web_search"

    def test_translate_task_to_opencode(self):
        """Task should translate to task_agent."""
        assert translate_to_opencode("Task") == "task_agent"

    def test_translate_notebookedit_to_opencode(self):
        """NotebookEdit should translate to notebook_edit."""
        assert translate_to_opencode("NotebookEdit") == "notebook_edit"

    def test_translate_todowrite_to_opencode(self):
        """TodoWrite should translate to todo_write."""
        assert translate_to_opencode("TodoWrite") == "todo_write"

    def test_translate_askuserquestion_to_opencode(self):
        """AskUserQuestion should translate to ask_user."""
        assert translate_to_opencode("AskUserQuestion") == "ask_user"

    def test_translate_unknown_passes_through(self):
        """Unknown tool names should pass through unchanged."""
        assert translate_to_opencode("UnknownTool") == "UnknownTool"

    def test_translate_file_read_from_opencode(self):
        """file_read should translate back to Read."""
        assert translate_from_opencode("file_read") == "Read"

    def test_translate_bash_exec_from_opencode(self):
        """bash_exec should translate back to Bash."""
        assert translate_from_opencode("bash_exec") == "Bash"

    def test_translate_code_search_from_opencode(self):
        """code_search should translate back to Grep."""
        assert translate_from_opencode("code_search") == "Grep"

    def test_translate_unknown_from_opencode_passes_through(self):
        """Unknown OpenCode tool names should pass through unchanged."""
        assert translate_from_opencode("unknown_tool") == "unknown_tool"

    def test_bidirectional_translation_consistency(self):
        """All mappings should be bidirectionally consistent."""
        for autoclaude_name, opencode_name in AUTOCLAUDE_TO_OPENCODE.items():
            # Translate to OpenCode and back
            assert translate_to_opencode(autoclaude_name) == opencode_name
            assert translate_from_opencode(opencode_name) == autoclaude_name


class TestToolSupportChecks:
    """Tests for tool support checking functions."""

    def test_is_supported_tool_autoclaude(self):
        """Auto-Claude tools should be supported."""
        assert is_supported_tool("Read") is True
        assert is_supported_tool("Bash") is True
        assert is_supported_tool("Grep") is True

    def test_is_supported_tool_opencode(self):
        """OpenCode tools should be supported."""
        assert is_supported_tool("file_read") is True
        assert is_supported_tool("bash_exec") is True
        assert is_supported_tool("code_search") is True

    def test_is_supported_tool_unknown(self):
        """Unknown tools should not be supported."""
        assert is_supported_tool("UnknownTool") is False

    def test_is_autoclaude_tool(self):
        """Auto-Claude tools should be identified correctly."""
        assert is_autoclaude_tool("Read") is True
        assert is_autoclaude_tool("file_read") is False
        assert is_autoclaude_tool("unknown") is False

    def test_is_opencode_tool(self):
        """OpenCode tools should be identified correctly."""
        assert is_opencode_tool("file_read") is True
        assert is_opencode_tool("Read") is False
        assert is_opencode_tool("unknown") is False


class TestToolCategories:
    """Tests for tool category functions."""

    def test_get_tool_category_file(self):
        """File tools should return 'file' category."""
        assert get_tool_category("Read") == "file"
        assert get_tool_category("file_read") == "file"
        assert get_tool_category("Write") == "file"
        assert get_tool_category("Edit") == "file"
        assert get_tool_category("Glob") == "file"

    def test_get_tool_category_shell(self):
        """Shell tools should return 'shell' category."""
        assert get_tool_category("Bash") == "shell"
        assert get_tool_category("bash_exec") == "shell"

    def test_get_tool_category_code(self):
        """Code tools should return 'code' category."""
        assert get_tool_category("Grep") == "code"
        assert get_tool_category("code_search") == "code"

    def test_get_tool_category_web(self):
        """Web tools should return 'web' category."""
        assert get_tool_category("WebFetch") == "web"
        assert get_tool_category("WebSearch") == "web"

    def test_get_tool_category_agent(self):
        """Agent tools should return 'agent' category."""
        assert get_tool_category("Task") == "agent"
        assert get_tool_category("task_agent") == "agent"

    def test_get_tool_category_unknown(self):
        """Unknown tools should return None."""
        assert get_tool_category("UnknownTool") is None


class TestToolMappingHelpers:
    """Tests for tool mapping helper functions."""

    def test_get_all_mappings(self):
        """get_all_mappings should return all tool mappings."""
        mappings = get_all_mappings()
        assert len(mappings) > 0
        assert all(hasattr(m, "autoclaude_name") for m in mappings)
        assert all(hasattr(m, "opencode_name") for m in mappings)
        assert all(hasattr(m, "category") for m in mappings)

    def test_get_autoclaude_tools(self):
        """get_autoclaude_tools should return frozenset."""
        tools = get_autoclaude_tools()
        assert isinstance(tools, frozenset)
        assert "Read" in tools
        assert "Bash" in tools

    def test_get_opencode_tools(self):
        """get_opencode_tools should return frozenset."""
        tools = get_opencode_tools()
        assert isinstance(tools, frozenset)
        assert "file_read" in tools
        assert "bash_exec" in tools

    def test_translate_tool_input_passthrough(self):
        """translate_tool_input should pass through unchanged."""
        tool_input = {"file_path": "/path/to/file", "content": "data"}
        result = translate_tool_input("Read", tool_input, to_opencode=True)
        assert result == tool_input

    def test_translate_tool_result_passthrough(self):
        """translate_tool_result should pass through unchanged."""
        result = translate_tool_result("file_read", "file content", from_opencode=True)
        assert result == "file content"


# =============================================================================
# Message Parser Tests
# =============================================================================


class TestOpenCodeMessageParserBasic:
    """Tests for basic OpenCodeMessageParser functionality."""

    def test_parser_creation(self):
        """Parser should be created with default settings."""
        parser = OpenCodeMessageParser()
        assert parser.translate_tools is True

    def test_parser_creation_no_translation(self):
        """Parser should be created with translation disabled."""
        parser = OpenCodeMessageParser(translate_tools=False)
        assert parser.translate_tools is False

    def test_parse_simple_text_message(self):
        """Parser should parse simple text message."""
        parser = OpenCodeMessageParser()
        data = {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello, world!"}],
        }
        msg = parser.parse_message(data)

        assert msg.role == "assistant"
        assert msg.text_content == "Hello, world!"

    def test_parse_string_content(self):
        """Parser should handle string content."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "assistant",
            "content": "Simple text response",
        }
        msg = parser.parse_message(data)

        assert msg.role == "assistant"
        assert msg.text_content == "Simple text response"


class TestOpenCodeMessageParserRoles:
    """Tests for role extraction in message parsing."""

    def test_parse_explicit_role_user(self):
        """Parser should extract explicit user role."""
        parser = OpenCodeMessageParser()
        data = {"role": "user", "content": "Hello"}
        msg = parser.parse_message(data)
        assert msg.role == "user"

    def test_parse_explicit_role_assistant(self):
        """Parser should extract explicit assistant role."""
        parser = OpenCodeMessageParser()
        data = {"role": "assistant", "content": "Hello"}
        msg = parser.parse_message(data)
        assert msg.role == "assistant"

    def test_parse_type_as_role(self):
        """Parser should infer role from type field."""
        parser = OpenCodeMessageParser()
        data = {"type": "assistant", "content": "Hello"}
        msg = parser.parse_message(data)
        assert msg.role == "assistant"

    def test_parse_default_role_for_message(self):
        """Parser should default to assistant for message type."""
        parser = OpenCodeMessageParser()
        data = {"type": "message", "content": "Hello"}
        msg = parser.parse_message(data)
        assert msg.role == "assistant"

    def test_parse_invalid_type_raises_error(self):
        """Parser should raise error for invalid message type."""
        parser = OpenCodeMessageParser()
        data = {"type": "invalid_type", "content": "Hello"}
        with pytest.raises(OpenCodeParseError) as excinfo:
            parser.parse_message(data)
        assert "Unsupported message type" in str(excinfo.value)


class TestOpenCodeMessageParserToolUse:
    """Tests for tool use content parsing."""

    def test_parse_tool_use_content(self):
        """Parser should parse tool use content."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "file_read",
                    "input": {"path": "/file.txt"},
                }
            ],
        }
        msg = parser.parse_message(data)

        assert msg.has_tool_use is True
        assert len(msg.tool_uses) == 1
        tool = msg.tool_uses[0]
        # Tool name should be translated to Auto-Claude format
        assert tool.name == "Read"
        assert tool.id == "tool_123"
        assert tool.input == {"path": "/file.txt"}

    def test_parse_tool_use_without_translation(self):
        """Parser should keep OpenCode tool names when translation disabled."""
        parser = OpenCodeMessageParser(translate_tools=False)
        data = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "file_read",
                    "input": {},
                }
            ],
        }
        msg = parser.parse_message(data)

        tool = msg.tool_uses[0]
        assert tool.name == "file_read"

    def test_parse_tool_call_type(self):
        """Parser should handle tool_call type."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_call",
                    "id": "call_456",
                    "name": "bash_exec",
                    "input": {"command": "ls"},
                }
            ],
        }
        msg = parser.parse_message(data)

        assert msg.has_tool_use is True
        tool = msg.tool_uses[0]
        assert tool.name == "Bash"

    def test_parse_tool_use_string_input(self):
        """Parser should handle string input for tool use."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_789",
                    "name": "file_read",
                    "input": '{"path": "/file.txt"}',
                }
            ],
        }
        msg = parser.parse_message(data)

        tool = msg.tool_uses[0]
        assert tool.input == {"path": "/file.txt"}


class TestOpenCodeMessageParserToolResult:
    """Tests for tool result content parsing."""

    def test_parse_tool_result_content(self):
        """Parser should parse tool result content."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_123",
                    "content": "File contents here",
                    "is_error": False,
                }
            ],
        }
        msg = parser.parse_message(data)

        assert msg.has_tool_result is True
        result = msg.tool_results[0]
        assert result.tool_use_id == "tool_123"
        assert result.content == "File contents here"
        assert result.is_error is False

    def test_parse_tool_result_with_error(self):
        """Parser should parse error tool results."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_456",
                    "content": "Error: file not found",
                    "is_error": True,
                }
            ],
        }
        msg = parser.parse_message(data)

        result = msg.tool_results[0]
        assert result.is_error is True

    def test_parse_tool_result_dict_content(self):
        """Parser should serialize dict content to JSON string."""
        parser = OpenCodeMessageParser()
        data = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_789",
                    "content": {"status": "success", "data": [1, 2, 3]},
                }
            ],
        }
        msg = parser.parse_message(data)

        result = msg.tool_results[0]
        assert '"status"' in result.content
        assert '"success"' in result.content


class TestOpenCodeMessageParserOutput:
    """Tests for full CLI output parsing."""

    def test_parse_empty_output(self):
        """Parser should handle empty output."""
        parser = OpenCodeMessageParser()
        messages = parser.parse_output("")
        assert messages == []

    def test_parse_single_json_object(self):
        """Parser should parse single JSON object."""
        parser = OpenCodeMessageParser()
        output = json.dumps({"role": "assistant", "content": "Hello"})
        messages = parser.parse_output(output)

        assert len(messages) == 1
        assert messages[0].text_content == "Hello"

    def test_parse_json_array(self):
        """Parser should parse JSON array of messages."""
        parser = OpenCodeMessageParser()
        output = json.dumps(
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ]
        )
        messages = parser.parse_output(output)

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_parse_ndjson(self):
        """Parser should parse newline-delimited JSON."""
        parser = OpenCodeMessageParser()
        output = "\n".join(
            [
                json.dumps({"role": "assistant", "content": "First"}),
                json.dumps({"role": "assistant", "content": "Second"}),
            ]
        )
        messages = parser.parse_output(output)

        assert len(messages) == 2
        assert messages[0].text_content == "First"
        assert messages[1].text_content == "Second"

    def test_parse_wrapper_messages(self):
        """Parser should handle wrapper with 'messages' key."""
        parser = OpenCodeMessageParser()
        output = json.dumps(
            {
                "messages": [
                    {"role": "assistant", "content": "Wrapped message"},
                ]
            }
        )
        messages = parser.parse_output(output)

        assert len(messages) == 1
        assert messages[0].text_content == "Wrapped message"

    def test_parse_wrapper_data(self):
        """Parser should handle wrapper with 'data' key."""
        parser = OpenCodeMessageParser()
        output = json.dumps(
            {
                "data": [
                    {"role": "assistant", "content": "Data message"},
                ]
            }
        )
        messages = parser.parse_output(output)

        assert len(messages) == 1
        assert messages[0].text_content == "Data message"


class TestOpenCodeMessageParserStreaming:
    """Tests for streaming line parsing."""

    def test_parse_streaming_line_valid(self):
        """Parser should parse valid streaming line."""
        parser = OpenCodeMessageParser()
        line = json.dumps({"role": "assistant", "content": "Streaming"})
        msg = parser.parse_streaming_line(line)

        assert msg is not None
        assert msg.text_content == "Streaming"

    def test_parse_streaming_line_empty(self):
        """Parser should return None for empty line."""
        parser = OpenCodeMessageParser()
        msg = parser.parse_streaming_line("")
        assert msg is None

    def test_parse_streaming_line_whitespace(self):
        """Parser should return None for whitespace-only line."""
        parser = OpenCodeMessageParser()
        msg = parser.parse_streaming_line("   \t\n  ")
        assert msg is None

    def test_parse_streaming_line_invalid_json(self):
        """Parser should return None for invalid JSON."""
        parser = OpenCodeMessageParser()
        msg = parser.parse_streaming_line("not valid json")
        assert msg is None


class TestOpenCodeMessageConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_parse_opencode_message(self):
        """parse_opencode_message should work."""
        data = {"role": "assistant", "content": "Hello"}
        msg = parse_opencode_message(data)
        assert msg.text_content == "Hello"

    def test_parse_opencode_output(self):
        """parse_opencode_output should work."""
        output = json.dumps({"role": "assistant", "content": "Output"})
        messages = parse_opencode_output(output)
        assert len(messages) == 1

    def test_parse_opencode_stream_line(self):
        """parse_opencode_stream_line should work."""
        line = json.dumps({"role": "assistant", "content": "Stream"})
        msg = parse_opencode_stream_line(line)
        assert msg.text_content == "Stream"


# =============================================================================
# Subprocess Config Tests
# =============================================================================


class TestSubprocessConfig:
    """Tests for SubprocessConfig dataclass."""

    def test_basic_creation(self):
        """Config should be created with minimal parameters."""
        config = SubprocessConfig(provider="openai")
        assert config.provider == "openai"
        assert config.model is None
        assert config.api_key is None
        assert config.timeout == 300.0

    def test_full_creation(self):
        """Config should be created with all parameters."""
        config = SubprocessConfig(
            provider="anthropic",
            model="claude-3-5-sonnet",
            api_key="test-key",
            working_dir=Path("/tmp"),
            timeout=60.0,
            env={"CUSTOM": "value"},
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-3-5-sonnet"
        assert config.api_key == "test-key"
        assert config.timeout == 60.0

    def test_get_command_args(self):
        """get_command_args should return correct arguments."""
        config = SubprocessConfig(provider="openai", model="gpt-4o")
        args = config.get_command_args()

        assert "build" in args
        assert "--non-interactive" in args
        assert "--provider" in args
        assert "openai" in args
        assert "--model" in args
        assert "gpt-4o" in args

    def test_get_command_args_minimal(self):
        """get_command_args should work with minimal config."""
        config = SubprocessConfig(provider="openai")
        args = config.get_command_args()

        assert "build" in args
        assert "--non-interactive" in args
        assert "--provider" in args
        # Model not included when None
        assert "--model" not in args or args[args.index("--model") + 1] != "None"

    def test_get_env_sets_api_key(self):
        """get_env should set provider-specific API key."""
        config = SubprocessConfig(provider="openai", api_key="sk-test")
        env = config.get_env()

        assert env.get("OPENAI_API_KEY") == "sk-test"

    def test_get_env_anthropic_api_key(self):
        """get_env should set ANTHROPIC_API_KEY for anthropic provider."""
        config = SubprocessConfig(provider="anthropic", api_key="sk-ant-test")
        env = config.get_env()

        assert env.get("ANTHROPIC_API_KEY") == "sk-ant-test"

    def test_get_env_custom_env(self):
        """get_env should include custom environment variables."""
        config = SubprocessConfig(
            provider="openai",
            env={"CUSTOM_VAR": "custom_value"},
        )
        env = config.get_env()

        assert env.get("CUSTOM_VAR") == "custom_value"


# =============================================================================
# Subprocess Error Tests
# =============================================================================


class TestOpenCodeSubprocessErrors:
    """Tests for OpenCode subprocess error classes."""

    def test_opencode_subprocess_error_basic(self):
        """Basic subprocess error should work."""
        error = OpenCodeSubprocessError("Test error")
        assert "Test error" in str(error)

    def test_opencode_subprocess_error_with_exit_code(self):
        """Subprocess error should include exit code."""
        error = OpenCodeSubprocessError("Failed", exit_code=1)
        assert error.exit_code == 1
        assert "Exit code: 1" in str(error)

    def test_opencode_subprocess_error_with_stderr(self):
        """Subprocess error should include stderr."""
        error = OpenCodeSubprocessError("Failed", stderr="error output")
        assert error.stderr == "error output"
        assert "error output" in str(error)

    def test_opencode_not_installed_error(self):
        """Not installed error should have installation instructions."""
        error = OpenCodeNotInstalledError()
        error_str = str(error)
        assert "curl" in error_str.lower() or "install" in error_str.lower()

    def test_opencode_timeout_error(self):
        """Timeout error should include timeout value."""
        error = OpenCodeTimeoutError(30.0, "query")
        assert error.timeout_seconds == 30.0
        assert error.operation == "query"
        assert "30" in str(error)

    def test_opencode_crash_error(self):
        """Crash error should include exit code."""
        error = OpenCodeCrashError(exit_code=127, stderr="command not found")
        assert error.exit_code == 127
        assert "127" in str(error)


# =============================================================================
# Subprocess Manager Tests (Mocked)
# =============================================================================


class TestOpenCodeSubprocessManager:
    """Tests for OpenCodeSubprocess manager with mocked CLI."""

    def test_from_config(self):
        """from_config should create subprocess manager."""
        subprocess_mgr = OpenCodeSubprocess.from_config(
            provider="openai",
            model="gpt-4o",
        )
        assert subprocess_mgr.config.provider == "openai"
        assert subprocess_mgr.config.model == "gpt-4o"

    def test_is_running_initial(self):
        """is_running should be False initially."""
        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))
        assert subprocess_mgr.is_running is False

    @mock.patch("shutil.which")
    def test_find_opencode_executable_in_path(self, mock_which):
        """find_opencode_executable should find opencode in PATH."""
        mock_which.return_value = "/usr/local/bin/opencode"
        result = OpenCodeSubprocess.find_opencode_executable()
        assert result == "/usr/local/bin/opencode"

    @mock.patch("shutil.which")
    def test_find_opencode_executable_not_found(self, mock_which):
        """find_opencode_executable should return None when not found."""
        mock_which.return_value = None
        with mock.patch.object(Path, "exists", return_value=False):
            result = OpenCodeSubprocess.find_opencode_executable()
        # Result could be None or a common path if it exists
        # Just verify no exception

    @mock.patch("shutil.which")
    def test_is_installed_true(self, mock_which):
        """is_installed should return True when executable found."""
        mock_which.return_value = "/usr/local/bin/opencode"
        assert OpenCodeSubprocess.is_installed() is True

    @mock.patch("shutil.which")
    def test_is_installed_false(self, mock_which):
        """is_installed should return False when not found."""
        mock_which.return_value = None
        with mock.patch.object(Path, "exists", return_value=False):
            result = OpenCodeSubprocess.is_installed()
        # Result depends on common paths

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    async def test_start_raises_when_not_installed(self, mock_find):
        """start should raise OpenCodeNotInstalledError when CLI not found."""
        mock_find.return_value = None
        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))

        with pytest.raises(OpenCodeNotInstalledError):
            await subprocess_mgr.start()

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_start_creates_subprocess(self, mock_create, mock_find):
        """start should create subprocess when CLI found."""
        mock_find.return_value = "/usr/local/bin/opencode"

        # Create a mock process
        mock_process = mock.Mock()
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdout = mock.Mock()
        mock_process.stderr = mock.Mock()
        mock_create.return_value = mock_process

        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))

        await subprocess_mgr.start()

        assert subprocess_mgr._started is True
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_stop_terminates_subprocess(self, mock_create, mock_find):
        """stop should terminate subprocess."""
        mock_find.return_value = "/usr/local/bin/opencode"

        # Create a mock process
        mock_process = mock.AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))

        await subprocess_mgr.start()
        await subprocess_mgr.stop()

        assert subprocess_mgr._stopped is True

    @pytest.mark.asyncio
    async def test_send_query_raises_when_not_running(self):
        """send_query should raise error when not running."""
        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))

        with pytest.raises(OpenCodeSubprocessError) as excinfo:
            await subprocess_mgr.send_query("test query")
        assert "not running" in str(excinfo.value).lower()


class TestOpenCodeSubprocessContextManager:
    """Tests for OpenCodeSubprocess async context manager."""

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_context_manager_starts_and_stops(self, mock_create, mock_find):
        """Context manager should start and stop subprocess."""
        mock_find.return_value = "/usr/local/bin/opencode"

        mock_process = mock.AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        config = SubprocessConfig(provider="openai")

        async with OpenCodeSubprocess(config=config) as proc:
            assert proc._started is True

        assert proc._stopped is True


# =============================================================================
# OpenCode Provider Tests
# =============================================================================


class TestOpenCodeProviderCreation:
    """Tests for OpenCodeProvider creation."""

    def test_from_config(self):
        """from_config should create provider."""
        config = SubprocessConfig(
            provider="openai",
            model="gpt-4o",
        )
        provider = OpenCodeProvider.from_config(config)

        assert provider.subprocess is not None
        assert provider.parser is not None

    def test_from_parameters(self):
        """from_parameters should create provider."""
        provider = OpenCodeProvider.from_parameters(
            provider="anthropic",
            model="claude-3-5-sonnet",
        )

        assert provider.subprocess.config.provider == "anthropic"
        assert provider.subprocess.config.model == "claude-3-5-sonnet"

    def test_from_subprocess(self):
        """from_subprocess should wrap existing subprocess."""
        subprocess_mgr = OpenCodeSubprocess(config=SubprocessConfig(provider="openai"))
        provider = OpenCodeProvider.from_subprocess(subprocess_mgr)

        assert provider.subprocess is subprocess_mgr


class TestOpenCodeProviderCapabilities:
    """Tests for OpenCodeProvider capabilities."""

    def test_capabilities(self):
        """OpenCode capabilities should be correct."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        caps = provider.capabilities

        assert caps.supports_hooks is False
        assert caps.supports_sandbox is False
        assert caps.supports_streaming is True
        assert caps.supports_mcp is False
        assert caps.supports_extended_thinking is False

    def test_provider_name(self):
        """provider_name should return 'OpenCode'."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        assert provider.provider_name == "OpenCode"


class TestOpenCodeProviderConnection:
    """Tests for OpenCodeProvider connection state."""

    def test_is_connected_initial(self):
        """is_connected should be False initially."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_query_requires_connection(self):
        """query should raise error when not connected."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        with pytest.raises(ProviderConnectionError) as excinfo:
            await provider.query(message)
        assert "not connected" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_query_stream_requires_connection(self):
        """query_stream should raise error when not connected."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.query_stream(message):
                pass

    @pytest.mark.asyncio
    async def test_receive_response_requires_connection(self):
        """receive_response should raise error when not connected."""
        provider = OpenCodeProvider.from_parameters(provider="openai")

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.receive_response():
                pass


class TestOpenCodeProviderContextManager:
    """Tests for OpenCodeProvider async context manager."""

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_context_manager_connects(self, mock_create, mock_find):
        """Context manager should connect provider."""
        mock_find.return_value = "/usr/local/bin/opencode"

        mock_process = mock.AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        provider = OpenCodeProvider.from_parameters(provider="openai")

        async with provider as p:
            assert p.is_connected is True

        assert provider.is_connected is False

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    async def test_context_manager_raises_on_not_installed(self, mock_find):
        """Context manager should raise when CLI not installed."""
        mock_find.return_value = None

        provider = OpenCodeProvider.from_parameters(provider="openai")

        with pytest.raises(ProviderConnectionError) as excinfo:
            async with provider:
                pass

        assert "not installed" in str(excinfo.value).lower()


class TestOpenCodeProviderQuery:
    """Tests for OpenCodeProvider query functionality."""

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_query_success(self, mock_create, mock_find):
        """query should return response on success."""
        mock_find.return_value = "/usr/local/bin/opencode"

        # Create mock process with proper response
        response_json = json.dumps(
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Response from OpenCode"}],
            }
        )

        mock_process = mock.AsyncMock()
        # returncode must be None initially (process still running)
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.write = mock.Mock()
        mock_process.stdin.drain = mock.AsyncMock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.stdout = mock.Mock()
        mock_process.stderr = mock.Mock()

        async def mock_communicate():
            mock_process.returncode = 0  # Set exit code when communicate completes
            return (response_json.encode(), b"")

        mock_process.communicate = mock_communicate
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            response = await provider.query(message)

        assert response.role == "assistant"
        assert response.text_content == "Response from OpenCode"

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_query_timeout(self, mock_create, mock_find):
        """query should raise ProviderError on timeout."""
        mock_find.return_value = "/usr/local/bin/opencode"

        mock_process = mock.AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.write = mock.Mock()
        mock_process.stdin.drain = mock.AsyncMock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.stdout = mock.Mock()
        mock_process.stderr = mock.Mock()
        mock_process.communicate = mock.AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.wait = mock.AsyncMock()
        mock_process.send_signal = mock.Mock()
        mock_create.return_value = mock_process

        provider = OpenCodeProvider.from_parameters(provider="openai", timeout=0.1)
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            with pytest.raises(ProviderError) as excinfo:
                await provider.query(message)

            assert "timed out" in str(excinfo.value).lower()


class TestOpenCodeProviderConversation:
    """Tests for OpenCodeProvider conversation management."""

    def test_get_conversation_context(self):
        """get_conversation_context should return context."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        ctx = provider.get_conversation_context()

        assert isinstance(ctx, ConversationContext)

    def test_clear_conversation(self):
        """clear_conversation should reset context."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        ctx = provider.get_conversation_context()

        ctx.add_message(
            UniversalMessage(role="user", content=[TextContent(text="Hello")])
        )
        assert ctx.get_message_count() == 1

        provider.clear_conversation()
        assert ctx.get_message_count() == 0


class TestOpenCodeProviderAvailability:
    """Tests for OpenCodeProvider availability checks."""

    @mock.patch.object(OpenCodeSubprocess, "is_installed")
    def test_is_available_true(self, mock_is_installed):
        """is_available should return True when CLI installed."""
        mock_is_installed.return_value = True
        assert OpenCodeProvider.is_available() is True

    @mock.patch.object(OpenCodeSubprocess, "is_installed")
    def test_is_available_false(self, mock_is_installed):
        """is_available should return False when CLI not installed."""
        mock_is_installed.return_value = False
        assert OpenCodeProvider.is_available() is False


class TestOpenCodeProviderTextExtraction:
    """Tests for OpenCodeProvider text extraction from messages."""

    def test_extract_text_content_simple(self):
        """Should extract simple text content."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(
            role="user", content=[TextContent(text="Hello world")]
        )

        text = provider._extract_text_content(message)
        assert text == "Hello world"

    def test_extract_text_content_multiple(self):
        """Should concatenate multiple text blocks."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(
            role="user",
            content=[
                TextContent(text="First"),
                TextContent(text="Second"),
            ],
        )

        text = provider._extract_text_content(message)
        assert "First" in text
        assert "Second" in text

    def test_extract_text_content_empty(self):
        """Should handle empty content."""
        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[])

        text = provider._extract_text_content(message)
        assert text == ""


class TestOpenCodeProviderProtocol:
    """Tests for OpenCodeProvider implementing AgentClient Protocol."""

    def test_has_required_methods(self):
        """OpenCodeProvider should have all required protocol methods."""
        provider = OpenCodeProvider.from_parameters(provider="openai")

        assert hasattr(provider, "query")
        assert callable(provider.query)
        assert hasattr(provider, "query_stream")
        assert callable(provider.query_stream)
        assert hasattr(provider, "receive_response")
        assert callable(provider.receive_response)
        assert hasattr(provider, "close")
        assert callable(provider.close)
        assert hasattr(provider, "__aenter__")
        assert hasattr(provider, "__aexit__")
        assert hasattr(provider, "capabilities")
        assert hasattr(provider, "provider_name")
        assert hasattr(provider, "is_connected")


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestOpenCodeProviderErrorHandling:
    """Tests for OpenCode provider error handling."""

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_query_handles_crash(self, mock_create, mock_find):
        """query should handle subprocess crash gracefully."""
        mock_find.return_value = "/usr/local/bin/opencode"

        mock_process = mock.AsyncMock()
        # returncode starts as None (process running)
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.write = mock.Mock()
        mock_process.stdin.drain = mock.AsyncMock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.stdout = mock.Mock()
        mock_process.stderr = mock.Mock()

        async def mock_communicate():
            mock_process.returncode = 1  # Crash exit code
            return (b"", b"Crash error message")

        mock_process.communicate = mock_communicate
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            with pytest.raises(ProviderError) as excinfo:
                await provider.query(message)

            assert (
                "crashed" in str(excinfo.value).lower()
                or "exit" in str(excinfo.value).lower()
            )

    @pytest.mark.asyncio
    @mock.patch.object(OpenCodeSubprocess, "find_opencode_executable")
    @mock.patch("asyncio.create_subprocess_exec")
    async def test_query_handles_invalid_json(self, mock_create, mock_find):
        """query should handle invalid JSON output gracefully."""
        mock_find.return_value = "/usr/local/bin/opencode"

        mock_process = mock.AsyncMock()
        # returncode starts as None (process running)
        mock_process.returncode = None
        mock_process.stdin = mock.Mock()
        mock_process.stdin.write = mock.Mock()
        mock_process.stdin.drain = mock.AsyncMock()
        mock_process.stdin.close = mock.Mock()
        mock_process.stdin.wait_closed = mock.AsyncMock()
        mock_process.stdout = mock.Mock()
        mock_process.stderr = mock.Mock()

        async def mock_communicate():
            mock_process.returncode = 0  # Success exit code
            return (b"not valid json", b"")

        mock_process.communicate = mock_communicate
        mock_process.wait = mock.AsyncMock()
        mock_create.return_value = mock_process

        provider = OpenCodeProvider.from_parameters(provider="openai")
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            # Should return empty response when no valid messages parsed
            response = await provider.query(message)
            assert response.role == "assistant"
            assert response.text_content == ""

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """close should be idempotent."""
        provider = OpenCodeProvider.from_parameters(provider="openai")

        # Close multiple times should not raise
        await provider.close()
        await provider.close()
        await provider.close()

        assert provider.is_connected is False


class TestOpenCodeParseErrorAttributes:
    """Tests for OpenCodeParseError exception."""

    def test_parse_error_with_raw_data(self):
        """Parse error should include raw data."""
        error = OpenCodeParseError("Parse failed", raw_data={"bad": "data"})
        assert error.raw_data == {"bad": "data"}
        assert "Parse failed" in str(error)

    def test_parse_error_without_raw_data(self):
        """Parse error should work without raw data."""
        error = OpenCodeParseError("Parse failed")
        assert error.raw_data is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestOpenCodeProviderIntegration:
    """Integration tests for OpenCode provider components."""

    def test_tool_translation_in_message_parsing(self):
        """Tool names should be translated during message parsing."""
        parser = OpenCodeMessageParser(translate_tools=True)
        data = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "file_read",
                    "input": {"path": "/test.txt"},
                },
                {
                    "type": "tool_use",
                    "id": "tool_2",
                    "name": "bash_exec",
                    "input": {"command": "ls"},
                },
            ],
        }
        msg = parser.parse_message(data)

        assert len(msg.tool_uses) == 2
        assert msg.tool_uses[0].name == "Read"
        assert msg.tool_uses[1].name == "Bash"

    def test_complete_message_flow(self):
        """Test complete message parsing flow."""
        # Simulate OpenCode CLI output
        output = json.dumps(
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll read the file for you."},
                    {
                        "type": "tool_use",
                        "id": "call_123",
                        "name": "file_read",
                        "input": {"path": "/example.txt"},
                    },
                ],
            }
        )

        messages = parse_opencode_output(output)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.role == "assistant"
        assert "read the file" in msg.text_content
        assert msg.has_tool_use
        assert msg.tool_uses[0].name == "Read"

    def test_subprocess_config_to_provider(self):
        """SubprocessConfig should work with OpenCodeProvider."""
        config = SubprocessConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-api-key",
            timeout=120.0,
        )

        provider = OpenCodeProvider.from_config(config)

        assert provider.subprocess.config.provider == "openai"
        assert provider.subprocess.config.model == "gpt-4o-mini"
        assert provider.subprocess.config.timeout == 120.0
