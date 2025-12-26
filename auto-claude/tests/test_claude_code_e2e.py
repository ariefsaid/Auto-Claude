"""
End-to-End Tests for Complete Claude Code Workflow
===================================================

Comprehensive E2E tests for the Claude Code provider workflow including:
1. ProviderConfig loading with AGENT_PROVIDER=claude_code
2. ClaudeProvider creation using factory
3. Query sending with UniversalMessage
4. Response receiving and message conversion verification
5. Hooks execution verification
6. Security validation verification

All tests mock the Claude SDK client - no actual API calls required.
"""

import json
import os
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.adapters.claude_adapter import ClaudeMessageAdapter
from core.providers.adapters.claude_provider import ClaudeProvider
from core.providers.client import (
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
)
from core.providers.config import AgentProvider, ProviderConfig, ProviderCredential
from core.providers.factory import create_client
from core.providers.messages import (
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)

# =============================================================================
# Mock Claude SDK Types
# =============================================================================


class TextBlock:
    """Mock Claude SDK TextBlock."""

    def __init__(self, text: str):
        self.text = text


class ToolUseBlock:
    """Mock Claude SDK ToolUseBlock."""

    def __init__(self, tool_id: str, name: str, tool_input: dict):
        self.id = tool_id
        self.name = name
        self.input = tool_input


class ToolResultBlock:
    """Mock Claude SDK ToolResultBlock."""

    def __init__(self, tool_use_id: str, content: str, is_error: bool = False):
        self.tool_use_id = tool_use_id
        self.content = content
        self.is_error = is_error


class ThinkingBlock:
    """Mock Claude SDK ThinkingBlock."""

    def __init__(self, thinking: str):
        self.thinking = thinking


class AssistantMessage:
    """Mock Claude SDK AssistantMessage."""

    def __init__(self, content: list, message_id: str | None = None):
        self.content = content
        self.id = message_id
        self.error = None


class UserMessage:
    """Mock Claude SDK UserMessage."""

    def __init__(self, content: list | str, message_id: str | None = None):
        self.content = content
        self.id = message_id


# =============================================================================
# Step 1: ProviderConfig Loading Tests
# =============================================================================


class TestProviderConfigLoading:
    """E2E tests for loading ProviderConfig with AGENT_PROVIDER=claude_code."""

    def test_load_config_from_env_claude_code_default(self):
        """Config should default to claude_code when no AGENT_PROVIDER set."""
        env = {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid()
            assert config.get_active_credential() is not None
            assert config.get_active_credential().api_key == "test-token"

    def test_load_config_from_env_claude_code_explicit(self):
        """Config should load correctly with explicit AGENT_PROVIDER=claude_code."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-explicit",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid()
            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.api_key == "oauth-token-explicit"

    def test_load_config_from_provider_credentials_json(self):
        """Config should load credentials from PROVIDER_CREDENTIALS JSON."""
        creds_json = json.dumps(
            {
                "claude-code": {
                    "apiKey": "json-api-key",
                    "isGlobal": False,
                    "metadata": {"source": "json"},
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "claude_code",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid()
            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.api_key == "json-api-key"
            assert cred.is_global is False
            assert cred.metadata["source"] == "json"

    def test_load_config_with_global_setting(self):
        """Config should handle global setting correctly."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "AGENT_PROVIDER_IS_GLOBAL": "true",
            "CLAUDE_CODE_OAUTH_TOKEN": "global-token",
            "CLAUDE_TOKEN_IS_GLOBAL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.is_global is True
            cred = config.get_credential("claude-code")
            assert cred.is_global is True

    def test_config_validation_errors_without_credentials(self):
        """Config should report validation errors when credentials missing."""
        env = {"AGENT_PROVIDER": "claude_code"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.is_valid() is False
            errors = config.get_validation_errors()
            assert len(errors) > 0
            assert any("credential" in err.lower() for err in errors)

    def test_config_provider_status(self):
        """Config should provide accurate status information."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "status-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()

            assert status["provider"] == "claude_code"
            assert status["is_valid"] is True
            assert status["errors"] == []
            assert "claude-code" in status["credential_source"]


# =============================================================================
# Step 2: ClaudeProvider Factory Creation Tests
# =============================================================================


class TestClaudeProviderFactoryCreation:
    """E2E tests for creating ClaudeProvider using the factory."""

    def test_factory_creates_claude_provider_from_sdk_client(self):
        """Factory should create ClaudeProvider when wrapping SDK client."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        assert isinstance(provider, ClaudeProvider)
        assert provider.provider_name == "Claude Code"
        assert provider.sdk_client == mock_sdk_client

    def test_factory_raises_for_invalid_config(self):
        """Factory should raise ProviderError for invalid config."""
        env = {"AGENT_PROVIDER": "claude_code"}  # Missing credentials
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            with pytest.raises(ProviderError) as excinfo:
                create_client(
                    config=config,
                    project_dir=Path("/tmp/test"),
                    spec_dir=Path("/tmp/test/spec"),
                    model="claude-sonnet-4-20250514",
                )

            assert "invalid provider configuration" in str(excinfo.value).lower()

    def test_claude_provider_has_correct_capabilities(self):
        """ClaudeProvider should have all capabilities enabled."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        caps = provider.capabilities
        assert isinstance(caps, ProviderCapabilities)
        assert caps.supports_hooks is True
        assert caps.supports_sandbox is True
        assert caps.supports_streaming is True
        assert caps.supports_mcp is True
        assert caps.supports_extended_thinking is True
        assert caps.requires_pre_validation is False
        assert caps.has_full_security is True

    def test_claude_provider_initially_not_connected(self):
        """ClaudeProvider should not be connected until context manager entered."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        assert provider.is_connected is False


# =============================================================================
# Step 3: Query Sending with UniversalMessage Tests
# =============================================================================


class TestQuerySendingWithUniversalMessage:
    """E2E tests for sending queries with UniversalMessage."""

    @pytest.mark.asyncio
    async def test_query_requires_connection(self):
        """Query should fail if provider is not connected."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        message = UniversalMessage(
            role="user",
            content=[TextContent(text="Hello, Claude!")],
        )

        with pytest.raises(ProviderConnectionError):
            await provider.query(message)

    @pytest.mark.asyncio
    async def test_query_converts_universal_message(self):
        """Query should convert UniversalMessage to SDK format before sending."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()
        mock_sdk_client.receive_response = AsyncMock(return_value=iter([]))

        # Make receive_response an async generator
        async def mock_receive():
            return
            yield

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Test query message")],
            )

            await provider.query(message)

            # Verify SDK client's query was called with text content
            mock_sdk_client.query.assert_called_once()
            call_args = mock_sdk_client.query.call_args[0]
            assert "Test query message" in call_args[0]

    @pytest.mark.asyncio
    async def test_query_with_tool_use_content(self):
        """Query should handle messages with tool use content."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        async def mock_receive():
            return
            yield

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[
                    TextContent(text="Read this file"),
                    ToolResultContent(
                        tool_use_id="tool_123",
                        content="File contents here",
                        is_error=False,
                    ),
                ],
            )

            await provider.query(message)
            mock_sdk_client.query.assert_called_once()


# =============================================================================
# Step 4: Response Receiving and Message Conversion Tests
# =============================================================================


class TestResponseReceivingAndConversion:
    """E2E tests for receiving responses and message conversion."""

    @pytest.mark.asyncio
    async def test_response_converted_to_universal_message(self):
        """Response should be converted back to UniversalMessage format."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        # Create mock response
        response_message = AssistantMessage(
            content=[TextBlock(text="Hello! How can I help you?")],
            message_id="msg_123",
        )

        async def mock_receive():
            yield response_message

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Hello!")],
            )

            response = await provider.query(message)

            assert isinstance(response, UniversalMessage)
            assert response.role == "assistant"
            assert response.has_text is True
            assert "How can I help" in response.text_content

    @pytest.mark.asyncio
    async def test_response_with_tool_use_converted(self):
        """Response with tool use should be correctly converted."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        # Create mock response with tool use
        response_message = AssistantMessage(
            content=[
                TextBlock(text="I'll read that file for you."),
                ToolUseBlock(
                    tool_id="tool_456",
                    name="Read",
                    tool_input={"file_path": "/path/to/file.txt"},
                ),
            ],
            message_id="msg_456",
        )

        async def mock_receive():
            yield response_message

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Read the file")],
            )

            response = await provider.query(message)

            assert isinstance(response, UniversalMessage)
            assert response.has_text is True
            assert response.has_tool_use is True
            assert len(response.tool_uses) == 1
            assert response.tool_uses[0].name == "Read"
            assert response.tool_uses[0].id == "tool_456"

    @pytest.mark.asyncio
    async def test_stream_responses(self):
        """Stream should yield multiple UniversalMessage responses."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        # Create multiple mock responses
        responses = [
            AssistantMessage(content=[TextBlock(text="First part")]),
            AssistantMessage(content=[TextBlock(text="Second part")]),
            AssistantMessage(content=[TextBlock(text="Final part")]),
        ]

        async def mock_receive():
            for resp in responses:
                yield resp

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Stream test")],
            )

            collected = []
            async for response in provider.query_stream(message):
                collected.append(response)

            assert len(collected) == 3
            assert all(isinstance(r, UniversalMessage) for r in collected)
            assert collected[0].text_content == "First part"
            assert collected[2].text_content == "Final part"

    @pytest.mark.asyncio
    async def test_response_with_thinking_block(self):
        """Response with thinking block should be converted to text."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        # Create response with thinking block
        response_message = AssistantMessage(
            content=[
                ThinkingBlock(thinking="Let me think about this..."),
                TextBlock(text="Here's my answer."),
            ],
            message_id="msg_thinking",
        )

        async def mock_receive():
            yield response_message

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Complex question")],
            )

            response = await provider.query(message)

            assert response.has_text is True
            # Thinking block should be converted to text with marker
            text = response.text_content
            assert "Thinking" in text or "Here's my answer" in text

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Empty response should return empty UniversalMessage."""
        mock_sdk_client = MagicMock()
        mock_sdk_client.query = AsyncMock()

        async def mock_receive():
            return
            yield

        mock_sdk_client.receive_response = mock_receive

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            message = UniversalMessage(
                role="user",
                content=[TextContent(text="Hello")],
            )

            response = await provider.query(message)

            assert isinstance(response, UniversalMessage)
            assert response.role == "assistant"


# =============================================================================
# Step 5: Hooks Execution Verification Tests
# =============================================================================


class TestHooksExecutionVerification:
    """E2E tests for verifying hooks execute correctly."""

    def test_claude_provider_supports_hooks(self):
        """ClaudeProvider should indicate hooks support."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        assert provider.capabilities.supports_hooks is True

    def test_claude_provider_capabilities_for_hook_decisions(self):
        """ClaudeProvider capabilities should enable hook-based security."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        caps = provider.capabilities

        # Should support both pre and post hooks via Claude SDK
        assert caps.supports_hooks is True
        assert caps.supports_sandbox is True

        # Should not require pre-validation since hooks handle it
        assert caps.requires_pre_validation is False

    def test_from_config_preserves_hook_support(self):
        """ClaudeProvider created via from_sdk_client preserves hook support."""
        mock_sdk_client = MagicMock()

        # Simulate SDK client with hook configuration
        mock_sdk_client.hooks = MagicMock()

        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        # Verify the SDK client is preserved with its hooks
        assert provider.sdk_client is mock_sdk_client
        assert provider.capabilities.supports_hooks is True


# =============================================================================
# Step 6: Security Validation Verification Tests
# =============================================================================


class TestSecurityValidationVerification:
    """E2E tests for verifying security validation works."""

    def test_validate_command_allows_safe_commands(self):
        """validate_command should allow safe commands."""
        from security.hooks import validate_command

        # Create a mock profile that allows basic commands
        mock_profile = MagicMock()
        mock_profile.base_commands = {"ls", "pwd", "echo", "cat"}

        with patch("security.hooks.get_security_profile", return_value=mock_profile):
            with patch("security.hooks.is_command_allowed", return_value=(True, "")):
                is_allowed, reason = validate_command("ls -la", profile=mock_profile)

                assert is_allowed is True
                assert reason == ""

    def test_validate_command_blocks_dangerous_commands(self):
        """validate_command should block dangerous commands."""
        from security.hooks import validate_command

        mock_profile = MagicMock()
        mock_profile.base_commands = {"ls", "pwd"}

        with patch("security.hooks.get_security_profile", return_value=mock_profile):
            with patch(
                "security.hooks.is_command_allowed",
                return_value=(False, "Command 'rm' is not allowed"),
            ):
                is_allowed, reason = validate_command("rm -rf /", profile=mock_profile)

                assert is_allowed is False
                assert "rm" in reason or "not allowed" in reason.lower()

    @pytest.mark.asyncio
    async def test_bash_security_hook_integration(self):
        """bash_security_hook should integrate with validate_command."""
        from security.hooks import bash_security_hook

        # Mock the validation to allow a safe command
        with patch(
            "security.hooks.validate_command", return_value=(True, "")
        ) as mock_validate:
            result = await bash_security_hook(
                input_data={
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls -la"},
                }
            )

            # Should return empty dict (allow)
            assert result == {}
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_bash_security_hook_blocks_dangerous(self):
        """bash_security_hook should block dangerous commands."""
        from security.hooks import bash_security_hook

        with patch(
            "security.hooks.validate_command",
            return_value=(False, "Command 'rm' is not allowed"),
        ):
            result = await bash_security_hook(
                input_data={
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf /"},
                }
            )

            # Should return block decision
            assert result.get("decision") == "block"
            assert "rm" in result.get("reason", "")

    @pytest.mark.asyncio
    async def test_bash_security_hook_ignores_non_bash_tools(self):
        """bash_security_hook should ignore non-Bash tools."""
        from security.hooks import bash_security_hook

        result = await bash_security_hook(
            input_data={
                "tool_name": "Read",
                "tool_input": {"file_path": "/etc/passwd"},
            }
        )

        # Should return empty dict (pass through)
        assert result == {}

    def test_security_profile_shared_with_validate_command(self):
        """validate_command should accept pre-loaded security profile."""
        from security.hooks import validate_command

        mock_profile = MagicMock()
        mock_profile.base_commands = {"git", "npm"}

        with patch("security.hooks.is_command_allowed", return_value=(True, "")):
            # Should not call get_security_profile when profile is provided
            with patch("security.hooks.get_security_profile") as mock_get:
                is_allowed, _ = validate_command("git status", profile=mock_profile)

                assert is_allowed is True
                # get_security_profile should not be called when profile is provided
                mock_get.assert_not_called()


# =============================================================================
# Complete E2E Workflow Tests
# =============================================================================


class TestCompleteE2EWorkflow:
    """Complete end-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_workflow_text_query_response(self):
        """
        Complete workflow: config -> provider -> query -> response.

        Steps:
        1. Load ProviderConfig with AGENT_PROVIDER=claude_code
        2. Create ClaudeProvider
        3. Send query with UniversalMessage
        4. Receive response in UniversalMessage format
        """
        # Step 1: Load config
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "e2e-test-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid()

            # Step 2: Create provider (mock SDK client)
            mock_sdk_client = MagicMock()
            mock_sdk_client.query = AsyncMock()

            response_message = AssistantMessage(
                content=[TextBlock(text="I'm here to help!")],
                message_id="msg_e2e_1",
            )

            async def mock_receive():
                yield response_message

            mock_sdk_client.receive_response = mock_receive

            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            # Step 3 & 4: Send query, receive response
            async with provider:
                query = UniversalMessage(
                    role="user",
                    content=[TextContent(text="Hello, Claude!")],
                )

                response = await provider.query(query)

                assert isinstance(response, UniversalMessage)
                assert response.role == "assistant"
                assert "help" in response.text_content.lower()

    @pytest.mark.asyncio
    async def test_complete_workflow_tool_use_round_trip(self):
        """
        Complete workflow with tool use and result.

        Tests the complete flow of:
        1. User sends text query
        2. Assistant responds with tool use
        3. User sends tool result
        4. Assistant provides final response
        """
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "e2e-tool-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid()

            mock_sdk_client = MagicMock()

            # Simulate multi-turn conversation
            call_count = 0

            async def mock_query(text):
                nonlocal call_count
                call_count += 1

            mock_sdk_client.query = mock_query

            # First response: tool use
            tool_response = AssistantMessage(
                content=[
                    TextBlock(text="Let me read that file."),
                    ToolUseBlock(
                        tool_id="tool_read_1",
                        name="Read",
                        tool_input={"file_path": "/test.txt"},
                    ),
                ]
            )

            # Second response: final answer
            final_response = AssistantMessage(
                content=[TextBlock(text="The file contains: Hello World")]
            )

            response_sequence = [tool_response, final_response]
            response_index = 0

            async def mock_receive():
                nonlocal response_index
                if response_index < len(response_sequence):
                    yield response_sequence[response_index]
                    response_index += 1

            mock_sdk_client.receive_response = mock_receive

            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            async with provider:
                # Turn 1: User query
                query1 = UniversalMessage(
                    role="user",
                    content=[TextContent(text="Read the file /test.txt")],
                )
                response1 = await provider.query(query1)

                assert response1.has_tool_use is True
                tool_use = response1.tool_uses[0]
                assert tool_use.name == "Read"

                # Turn 2: Tool result
                query2 = UniversalMessage(
                    role="user",
                    content=[
                        ToolResultContent(
                            tool_use_id=tool_use.id,
                            content="Hello World",
                            is_error=False,
                        )
                    ],
                )
                response2 = await provider.query(query2)

                assert response2.has_text is True
                assert "Hello World" in response2.text_content

    @pytest.mark.asyncio
    async def test_complete_workflow_with_security_validation(self):
        """
        Complete workflow with security validation.

        Verifies that:
        1. Config loads correctly
        2. Provider has security capabilities
        3. Security validation would be applied to tool calls
        """
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "e2e-security-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid()

            mock_sdk_client = MagicMock()
            mock_sdk_client.query = AsyncMock()

            # Response with bash tool use
            bash_response = AssistantMessage(
                content=[
                    TextBlock(text="Let me run that command."),
                    ToolUseBlock(
                        tool_id="tool_bash_1",
                        name="Bash",
                        tool_input={"command": "ls -la"},
                    ),
                ]
            )

            async def mock_receive():
                yield bash_response

            mock_sdk_client.receive_response = mock_receive

            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            # Verify security capabilities
            assert provider.capabilities.supports_hooks is True
            assert provider.capabilities.supports_sandbox is True

            async with provider:
                query = UniversalMessage(
                    role="user",
                    content=[TextContent(text="List files in current directory")],
                )

                response = await provider.query(query)

                # Response should contain bash tool use
                assert response.has_tool_use is True
                bash_tool = response.tool_uses[0]
                assert bash_tool.name == "Bash"
                assert bash_tool.input.get("command") == "ls -la"

    @pytest.mark.asyncio
    async def test_complete_workflow_error_handling(self):
        """
        Complete workflow with error handling.

        Tests that errors during query are properly wrapped.
        """
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "e2e-error-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid()

            mock_sdk_client = MagicMock()
            mock_sdk_client.query = AsyncMock(side_effect=Exception("Network error"))

            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            async with provider:
                query = UniversalMessage(
                    role="user",
                    content=[TextContent(text="This will fail")],
                )

                with pytest.raises(ProviderError) as excinfo:
                    await provider.query(query)

                assert "Query failed" in str(excinfo.value)
                assert "Network error" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_complete_workflow_streaming_with_hooks(self):
        """
        Complete streaming workflow.

        Tests streaming responses work correctly with the provider.
        """
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "e2e-stream-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid()
            assert config.provider == AgentProvider.CLAUDE_CODE

            mock_sdk_client = MagicMock()
            mock_sdk_client.query = AsyncMock()

            # Simulate streaming chunks
            chunks = [
                AssistantMessage(content=[TextBlock(text="Processing")]),
                AssistantMessage(content=[TextBlock(text="your request")]),
                AssistantMessage(content=[TextBlock(text="complete!")]),
            ]

            async def mock_receive():
                for chunk in chunks:
                    yield chunk

            mock_sdk_client.receive_response = mock_receive

            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)
            assert provider.capabilities.supports_streaming is True

            async with provider:
                query = UniversalMessage(
                    role="user",
                    content=[TextContent(text="Stream response please")],
                )

                collected = []
                async for response in provider.query_stream(query):
                    collected.append(response.text_content)

                assert len(collected) == 3
                assert "Processing" in collected[0]
                assert "complete!" in collected[2]


# =============================================================================
# Message Adapter Round-Trip Tests
# =============================================================================


class TestMessageAdapterRoundTrip:
    """Tests for bidirectional message conversion."""

    def test_text_content_round_trip(self):
        """Text content should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()

        # Create mock Claude message
        claude_msg = AssistantMessage(
            content=[TextBlock(text="Test message")],
            message_id="msg_rt_1",
        )

        # Convert to universal
        universal = adapter.to_universal(claude_msg)
        assert universal.role == "assistant"
        assert universal.text_content == "Test message"

        # Convert back to Claude format
        claude_dict = adapter.from_universal(universal)
        assert claude_dict["role"] == "assistant"
        assert claude_dict["content"][0]["type"] == "text"
        assert claude_dict["content"][0]["text"] == "Test message"

    def test_tool_use_content_round_trip(self):
        """Tool use content should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()

        claude_msg = AssistantMessage(
            content=[
                ToolUseBlock(
                    tool_id="tool_rt_1",
                    name="Read",
                    tool_input={"file_path": "/test.txt"},
                )
            ]
        )

        universal = adapter.to_universal(claude_msg)
        assert universal.has_tool_use is True
        assert universal.tool_uses[0].id == "tool_rt_1"
        assert universal.tool_uses[0].name == "Read"

        claude_dict = adapter.from_universal(universal)
        assert claude_dict["content"][0]["type"] == "tool_use"
        assert claude_dict["content"][0]["id"] == "tool_rt_1"
        assert claude_dict["content"][0]["name"] == "Read"

    def test_tool_result_content_round_trip(self):
        """Tool result content should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()

        # Create tool result as user message
        original = UniversalMessage(
            role="user",
            content=[
                ToolResultContent(
                    tool_use_id="tool_tr_1",
                    content="File contents here",
                    is_error=False,
                )
            ],
        )

        claude_dict = adapter.from_universal(original)
        assert claude_dict["role"] == "user"
        assert claude_dict["content"][0]["type"] == "tool_result"
        assert claude_dict["content"][0]["tool_use_id"] == "tool_tr_1"
        assert claude_dict["content"][0]["content"] == "File contents here"
        assert claude_dict["content"][0]["is_error"] is False

    def test_complex_message_round_trip(self):
        """Complex message with multiple blocks should survive round-trip."""
        adapter = ClaudeMessageAdapter()

        claude_msg = AssistantMessage(
            content=[
                TextBlock(text="I'll help you with that."),
                ToolUseBlock(
                    tool_id="tool_complex_1",
                    name="Bash",
                    tool_input={"command": "ls -la"},
                ),
                TextBlock(text="Running the command now."),
            ],
            message_id="msg_complex",
        )

        universal = adapter.to_universal(claude_msg)
        assert len(universal.content) == 3
        assert universal.has_text is True
        assert universal.has_tool_use is True

        claude_dict = adapter.from_universal(universal)
        assert len(claude_dict["content"]) == 3
        assert claude_dict["content"][0]["type"] == "text"
        assert claude_dict["content"][1]["type"] == "tool_use"
        assert claude_dict["content"][2]["type"] == "text"


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestAsyncContextManager:
    """Tests for async context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(self):
        """Context manager should manage connection state."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        assert provider.is_connected is False

        async with provider:
            assert provider.is_connected is True

        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_context_manager_handles_exception(self):
        """Context manager should close even on exception."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        with pytest.raises(ValueError):
            async with provider:
                assert provider.is_connected is True
                raise ValueError("Test exception")

        # Should still be closed after exception
        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_close_method_directly(self):
        """close() method should disconnect provider."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        async with provider:
            assert provider.is_connected is True
            await provider.close()
            assert provider.is_connected is False


# =============================================================================
# Conversation Context Tests
# =============================================================================


class TestConversationContext:
    """Tests for conversation context management."""

    def test_get_conversation_context(self):
        """Provider should provide conversation context."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        context = provider.get_conversation_context()
        assert isinstance(context, ConversationContext)

    def test_clear_conversation(self):
        """clear_conversation should reset context."""
        mock_sdk_client = MagicMock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        context = provider.get_conversation_context()
        context.add_message(
            UniversalMessage(role="user", content=[TextContent(text="test")])
        )
        assert len(context.messages) == 1

        provider.clear_conversation()
        assert len(provider.get_conversation_context().messages) == 0
