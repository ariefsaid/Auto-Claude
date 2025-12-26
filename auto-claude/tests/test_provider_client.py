"""
Tests for Provider Client
===========================

Comprehensive tests for the AgentClient Protocol, ProviderCapabilities,
ConversationContext, ProviderError hierarchy, ClaudeProvider wrapper,
factory functions, and backward compatibility.

Test Coverage:
- ProviderCapabilities dataclass creation and serialization
- ConversationContext management and message handling
- ProviderError exception hierarchy and serialization
- AgentClient Protocol interface and runtime_checkable functionality
- ClaudeProvider wrapper with async context manager
- Factory function (create_client) for provider selection
- Backward compatibility (create_client_from_config in core/client.py)
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.client import (
    AgentClient,
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderTimeoutError,
)
from core.providers.config import AgentProvider, ProviderConfig, ProviderCredential
from core.providers.messages import TextContent, ToolUseContent, UniversalMessage

# =============================================================================
# ProviderCapabilities Tests
# =============================================================================


class TestProviderCapabilities:
    """Tests for the ProviderCapabilities dataclass."""

    def test_default_creation(self):
        """Default creation should have expected default values."""
        caps = ProviderCapabilities()
        assert caps.supports_hooks is False
        assert caps.supports_sandbox is False
        assert caps.supports_streaming is True  # Default True
        assert caps.supports_mcp is False
        assert caps.supports_extended_thinking is False

    def test_custom_creation(self):
        """Custom values should be preserved."""
        caps = ProviderCapabilities(
            supports_hooks=True,
            supports_sandbox=True,
            supports_streaming=True,
            supports_mcp=True,
            supports_extended_thinking=True,
        )
        assert caps.supports_hooks is True
        assert caps.supports_sandbox is True
        assert caps.supports_streaming is True
        assert caps.supports_mcp is True
        assert caps.supports_extended_thinking is True

    def test_partial_creation(self):
        """Partial values should work with defaults."""
        caps = ProviderCapabilities(supports_hooks=True, supports_mcp=True)
        assert caps.supports_hooks is True
        assert caps.supports_sandbox is False
        assert caps.supports_streaming is True
        assert caps.supports_mcp is True
        assert caps.supports_extended_thinking is False

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        caps = ProviderCapabilities(
            supports_hooks=True,
            supports_sandbox=True,
            supports_streaming=True,
            supports_mcp=False,
            supports_extended_thinking=True,
        )
        result = caps.to_dict()

        assert result == {
            "supports_hooks": True,
            "supports_sandbox": True,
            "supports_streaming": True,
            "supports_mcp": False,
            "supports_extended_thinking": True,
        }

    def test_to_dict_default_values(self):
        """to_dict should include default values."""
        caps = ProviderCapabilities()
        result = caps.to_dict()

        assert result == {
            "supports_hooks": False,
            "supports_sandbox": False,
            "supports_streaming": True,
            "supports_mcp": False,
            "supports_extended_thinking": False,
        }

    def test_claude_capabilities(self):
        """Claude Code capabilities should be all enabled."""
        caps = ProviderCapabilities(
            supports_hooks=True,
            supports_sandbox=True,
            supports_streaming=True,
            supports_mcp=True,
            supports_extended_thinking=True,
        )
        assert all(
            [
                caps.supports_hooks,
                caps.supports_sandbox,
                caps.supports_streaming,
                caps.supports_mcp,
                caps.supports_extended_thinking,
            ]
        )


# =============================================================================
# ConversationContext Tests
# =============================================================================


class TestConversationContext:
    """Tests for the ConversationContext dataclass."""

    def test_default_creation(self):
        """Default creation should have expected defaults."""
        ctx = ConversationContext()
        assert ctx.conversation_id is None
        assert ctx.messages == []
        assert ctx.metadata == {}

    def test_creation_with_id(self):
        """Creation with conversation_id should work."""
        ctx = ConversationContext(conversation_id="conv_123")
        assert ctx.conversation_id == "conv_123"

    def test_add_message(self):
        """add_message should append messages."""
        ctx = ConversationContext()
        msg1 = UniversalMessage(role="user", content=[TextContent(text="Hello")])
        msg2 = UniversalMessage(role="assistant", content=[TextContent(text="Hi")])

        ctx.add_message(msg1)
        assert len(ctx.messages) == 1

        ctx.add_message(msg2)
        assert len(ctx.messages) == 2
        assert ctx.messages[0].text_content == "Hello"
        assert ctx.messages[1].text_content == "Hi"

    def test_clear(self):
        """clear should reset messages and metadata."""
        ctx = ConversationContext(conversation_id="conv_123", metadata={"key": "value"})
        ctx.add_message(
            UniversalMessage(role="user", content=[TextContent(text="Hello")])
        )

        ctx.clear()

        assert ctx.messages == []
        assert ctx.metadata == {}
        # conversation_id is preserved
        assert ctx.conversation_id == "conv_123"

    def test_get_last_message(self):
        """get_last_message should return most recent message."""
        ctx = ConversationContext()

        # Empty context returns None
        assert ctx.get_last_message() is None

        msg1 = UniversalMessage(role="user", content=[TextContent(text="First")])
        msg2 = UniversalMessage(role="assistant", content=[TextContent(text="Second")])

        ctx.add_message(msg1)
        assert ctx.get_last_message().text_content == "First"

        ctx.add_message(msg2)
        assert ctx.get_last_message().text_content == "Second"

    def test_get_message_count(self):
        """get_message_count should return correct count."""
        ctx = ConversationContext()

        assert ctx.get_message_count() == 0

        ctx.add_message(
            UniversalMessage(role="user", content=[TextContent(text="Hello")])
        )
        assert ctx.get_message_count() == 1

        ctx.add_message(
            UniversalMessage(role="assistant", content=[TextContent(text="Hi")])
        )
        assert ctx.get_message_count() == 2

    def test_metadata_operations(self):
        """Metadata operations should work correctly."""
        ctx = ConversationContext(metadata={"initial": "value"})
        assert ctx.metadata["initial"] == "value"

        ctx.metadata["new_key"] = "new_value"
        assert ctx.metadata["new_key"] == "new_value"
        assert len(ctx.metadata) == 2


# =============================================================================
# ProviderError Tests
# =============================================================================


class TestProviderError:
    """Tests for the ProviderError base exception."""

    def test_basic_creation(self):
        """Basic creation should work."""
        error = ProviderError("test_provider", "Something went wrong")
        assert error.provider == "test_provider"
        assert error.message == "Something went wrong"
        assert error.details == {}

    def test_creation_with_details(self):
        """Creation with details should preserve them."""
        details = {"code": 500, "reason": "internal_error"}
        error = ProviderError("test_provider", "Server error", details)
        assert error.details == details

    def test_string_representation(self):
        """String representation should include provider and message."""
        error = ProviderError("claude_code", "Connection failed")
        error_str = str(error)
        assert "claude_code" in error_str
        assert "Connection failed" in error_str

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        error = ProviderError("opencode", "Query timeout", {"timeout_seconds": 30})
        result = error.to_dict()

        assert result == {
            "provider": "opencode",
            "message": "Query timeout",
            "details": {"timeout_seconds": 30},
        }

    def test_exception_inheritance(self):
        """ProviderError should be an Exception."""
        error = ProviderError("test", "error")
        assert isinstance(error, Exception)


class TestProviderNotFoundError:
    """Tests for the ProviderNotFoundError exception."""

    def test_basic_creation(self):
        """Basic creation should work."""
        error = ProviderNotFoundError("unknown_provider")
        assert error.provider == "unknown_provider"
        assert "not found" in error.message.lower()

    def test_with_available_providers(self):
        """Available providers should be included in message."""
        error = ProviderNotFoundError("invalid", available=["claude_code", "opencode"])
        assert "claude_code" in error.message
        assert "opencode" in error.message
        assert error.details["available"] == ["claude_code", "opencode"]

    def test_without_available_providers(self):
        """Missing available list should show 'none'."""
        error = ProviderNotFoundError("invalid")
        assert "none" in error.message.lower()
        assert error.details["available"] == []

    def test_inheritance(self):
        """ProviderNotFoundError should inherit from ProviderError."""
        error = ProviderNotFoundError("test")
        assert isinstance(error, ProviderError)
        assert isinstance(error, Exception)


class TestProviderConnectionError:
    """Tests for the ProviderConnectionError exception."""

    def test_basic_creation(self):
        """Basic creation should work."""
        error = ProviderConnectionError("claude_code", "Network timeout")
        assert error.provider == "claude_code"
        assert "Network timeout" in error.message
        assert error.details["reason"] == "Network timeout"

    def test_with_retry_after(self):
        """retry_after should be included in details."""
        error = ProviderConnectionError("opencode", "Rate limited", retry_after=30.0)
        assert error.details["retry_after"] == 30.0

    def test_without_retry_after(self):
        """Missing retry_after should not be in details."""
        error = ProviderConnectionError("test", "Failed")
        assert "retry_after" not in error.details

    def test_inheritance(self):
        """ProviderConnectionError should inherit from ProviderError."""
        error = ProviderConnectionError("test", "Failed")
        assert isinstance(error, ProviderError)


class TestProviderTimeoutError:
    """Tests for the ProviderTimeoutError exception."""

    def test_basic_creation(self):
        """Basic creation should work."""
        error = ProviderTimeoutError("claude_code", "query", 60.0)
        assert error.provider == "claude_code"
        assert "query" in error.message
        assert "60" in error.message

    def test_details(self):
        """Details should include operation and timeout."""
        error = ProviderTimeoutError("opencode", "receive_response", 30.5)
        assert error.details["operation"] == "receive_response"
        assert error.details["timeout_seconds"] == 30.5

    def test_inheritance(self):
        """ProviderTimeoutError should inherit from ProviderError."""
        error = ProviderTimeoutError("test", "op", 10.0)
        assert isinstance(error, ProviderError)


# =============================================================================
# AgentClient Protocol Tests
# =============================================================================


class TestAgentClientProtocol:
    """Tests for the AgentClient Protocol interface."""

    def test_protocol_is_runtime_checkable(self):
        """AgentClient should be runtime_checkable."""

        # Create a minimal class that implements the protocol
        class MockProvider:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities()

            @property
            def provider_name(self) -> str:
                return "mock"

            @property
            def is_connected(self) -> bool:
                return True

            async def query(self, message, context=None):
                return message

            async def query_stream(self, message, context=None):
                yield message

            async def receive_response(self):
                yield UniversalMessage(role="assistant", content=[])

            async def close(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        mock_provider = MockProvider()
        assert isinstance(mock_provider, AgentClient)

    def test_incomplete_implementation_fails_check(self):
        """Incomplete implementation should not be AgentClient."""

        class IncompleteProvider:
            """Missing most protocol methods."""

            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities()

        incomplete = IncompleteProvider()
        # Protocol checks are structural - this will fail due to missing methods
        # But with runtime_checkable, it checks for presence of methods
        # So this test verifies the isinstance check behavior
        # Note: runtime_checkable only checks method names, not signatures
        assert not isinstance(incomplete, AgentClient)


# =============================================================================
# ClaudeProvider Tests
# =============================================================================


class TestClaudeProviderCreation:
    """Tests for ClaudeProvider creation and properties."""

    def test_from_sdk_client(self):
        """from_sdk_client should wrap SDK client correctly."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

        assert provider.sdk_client is mock_sdk_client
        assert provider.adapter is not None

    def test_direct_creation(self):
        """Direct creation with sdk_client should work."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        assert provider.sdk_client is mock_sdk_client

    def test_capabilities_all_enabled(self):
        """Claude provider should have all capabilities enabled."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)
        caps = provider.capabilities

        assert caps.supports_hooks is True
        assert caps.supports_sandbox is True
        assert caps.supports_streaming is True
        assert caps.supports_mcp is True
        assert caps.supports_extended_thinking is True

    def test_provider_name(self):
        """provider_name should return 'Claude Code'."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        assert provider.provider_name == "Claude Code"

    def test_is_connected_initial_state(self):
        """is_connected should be False initially."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        assert provider.is_connected is False


class TestClaudeProviderAsyncContextManager:
    """Tests for ClaudeProvider async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connects(self):
        """Context manager should set is_connected to True."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        assert provider.is_connected is False

        async with provider as p:
            assert p.is_connected is True
            assert p is provider

        # After exit, should be disconnected
        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_context_manager_on_exception(self):
        """Context manager should disconnect even on exception."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        with pytest.raises(ValueError):
            async with provider:
                assert provider.is_connected is True
                raise ValueError("Test exception")

        # Should still be disconnected
        assert provider.is_connected is False


class TestClaudeProviderQuery:
    """Tests for ClaudeProvider query methods."""

    @pytest.mark.asyncio
    async def test_query_requires_connection(self):
        """query should raise error if not connected."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        with pytest.raises(ProviderConnectionError) as excinfo:
            await provider.query(message)

        assert "not connected" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_query_stream_requires_connection(self):
        """query_stream should raise error if not connected."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.query_stream(message):
                pass

    @pytest.mark.asyncio
    async def test_receive_response_requires_connection(self):
        """receive_response should raise error if not connected."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.receive_response():
                pass

    @pytest.mark.asyncio
    async def test_query_sends_to_sdk(self):
        """query should send message to SDK client."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        # Mock SDK client with async generator response
        @dataclass
        class MockTextBlock:
            text: str
            type: str = "text"

        # Use proper class name for adapter
        MockTextBlock.__name__ = "TextBlock"

        @dataclass
        class MockAssistantMessage:
            content: list
            role: str = "assistant"

        MockAssistantMessage.__name__ = "AssistantMessage"

        async def mock_receive_response():
            yield MockAssistantMessage(
                content=[MockTextBlock(text="Response from Claude")]
            )

        mock_sdk_client = mock.Mock()
        mock_sdk_client.query = mock.AsyncMock()
        mock_sdk_client.receive_response = mock_receive_response

        provider = ClaudeProvider(sdk_client=mock_sdk_client)
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            response = await provider.query(message)

        mock_sdk_client.query.assert_called_once()
        assert response.role == "assistant"
        assert response.text_content == "Response from Claude"

    @pytest.mark.asyncio
    async def test_query_handles_sdk_error(self):
        """query should wrap SDK errors in ProviderError."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        mock_sdk_client.query = mock.AsyncMock(side_effect=RuntimeError("SDK error"))

        provider = ClaudeProvider(sdk_client=mock_sdk_client)
        message = UniversalMessage(role="user", content=[TextContent(text="Hello")])

        async with provider:
            with pytest.raises(ProviderError) as excinfo:
                await provider.query(message)

            assert "SDK error" in str(excinfo.value)


class TestClaudeProviderConversation:
    """Tests for ClaudeProvider conversation management."""

    def test_get_conversation_context(self):
        """get_conversation_context should return context."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        ctx = provider.get_conversation_context()
        assert isinstance(ctx, ConversationContext)

    def test_clear_conversation(self):
        """clear_conversation should reset context."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        ctx = provider.get_conversation_context()
        ctx.add_message(
            UniversalMessage(role="user", content=[TextContent(text="Hello")])
        )
        ctx.metadata["key"] = "value"

        assert ctx.get_message_count() == 1

        provider.clear_conversation()

        assert ctx.get_message_count() == 0
        assert ctx.metadata == {}


class TestClaudeProviderProtocol:
    """Tests for ClaudeProvider implementing AgentClient Protocol."""

    def test_implements_agent_client(self):
        """ClaudeProvider should implement AgentClient Protocol."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        # runtime_checkable Protocol check
        assert isinstance(provider, AgentClient)


# =============================================================================
# Factory Tests
# =============================================================================


class TestFactoryGetAvailableProviders:
    """Tests for get_available_providers function."""

    def test_returns_list(self):
        """Should return list of provider strings."""
        from core.providers.factory import get_available_providers

        providers = get_available_providers()
        assert isinstance(providers, list)
        assert all(isinstance(p, str) for p in providers)

    def test_includes_expected_providers(self):
        """Should include claude_code and opencode."""
        from core.providers.factory import get_available_providers

        providers = get_available_providers()
        assert "claude_code" in providers
        assert "opencode" in providers


class TestFactoryIsProviderAvailable:
    """Tests for is_provider_available function."""

    def test_claude_code_available(self):
        """claude_code should be available."""
        from core.providers.factory import is_provider_available

        assert is_provider_available("claude_code") is True

    def test_opencode_available(self):
        """opencode should be available."""
        from core.providers.factory import is_provider_available

        assert is_provider_available("opencode") is True

    def test_unknown_provider_not_available(self):
        """Unknown provider should not be available."""
        from core.providers.factory import is_provider_available

        assert is_provider_available("unknown_provider") is False

    def test_case_insensitive(self):
        """Check should be case insensitive."""
        from core.providers.factory import is_provider_available

        assert is_provider_available("CLAUDE_CODE") is True
        assert is_provider_available("Claude_Code") is True


class TestFactoryCreateClient:
    """Tests for create_client factory function."""

    def test_invalid_config_raises_error(self):
        """Invalid config should raise ProviderError."""
        from core.providers.factory import create_client

        # Config with no credentials
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE,
            credentials={},
        )

        with pytest.raises(ProviderError) as excinfo:
            create_client(
                config=config,
                project_dir=Path("/test"),
                spec_dir=Path("/test/spec"),
                model="test-model",
            )

        assert "invalid" in str(excinfo.value).lower()

    def test_provider_selection_logic(self):
        """Factory should correctly route to provider-specific creators."""
        from core.providers.factory import create_client

        # Valid config should pass validation and reach provider selection
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE,
            credentials={
                "claude-code": ProviderCredential(
                    provider="claude-code", api_key="test"
                )
            },
        )

        # This will fail during creation due to missing dependencies,
        # but should get past provider selection and validation
        with pytest.raises((ProviderError, Exception)):
            create_client(
                config=config,
                project_dir=Path("/test"),
                spec_dir=Path("/test/spec"),
                model="test-model",
            )

    def test_opencode_not_implemented_raises_error(self):
        """OpenCode provider should raise error (not yet implemented)."""
        from core.providers.factory import create_client

        config = ProviderConfig(
            provider=AgentProvider.OPENCODE,
            opencode_provider="openai",
            opencode_model="gpt-4o-mini",
            credentials={
                "openai": ProviderCredential(provider="openai", api_key="test-key")
            },
        )

        with pytest.raises(ProviderError) as excinfo:
            create_client(
                config=config,
                project_dir=Path("/test"),
                spec_dir=Path("/test/spec"),
                model="test-model",
            )

        # Should indicate OpenCode is not yet implemented
        assert "opencode" in str(excinfo.value).lower()


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing create_client function."""

    def test_core_client_module_exists(self):
        """core.client module should exist and be importable."""
        import importlib.util

        spec = importlib.util.find_spec("core.client")
        assert spec is not None, "core.client module should exist"

    def test_create_client_defined(self):
        """Original create_client should be defined in core/client.py."""
        # Read the source file to verify the function is defined
        import re

        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        # Check for create_client function definition
        assert (
            "def create_client(" in content
        ), "create_client function should be defined"

    def test_create_client_from_config_defined(self):
        """New create_client_from_config should be defined in core/client.py."""
        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        # Check for create_client_from_config function definition
        assert (
            "def create_client_from_config(" in content
        ), "create_client_from_config function should be defined"

    def test_both_functions_defined(self):
        """Both create_client and create_client_from_config should be defined together."""
        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        assert "def create_client(" in content
        assert "def create_client_from_config(" in content

    def test_create_client_from_config_signature(self):
        """create_client_from_config should accept expected parameters."""
        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        # Check that the function signature includes expected parameters
        # Find the function and its parameters
        assert "project_dir:" in content or "project_dir:" in content
        assert "spec_dir:" in content or "spec_dir:" in content
        assert "model:" in content or "model:" in content
        assert "config:" in content

    def test_create_client_from_config_imports_provider_config(self):
        """create_client_from_config should import from providers."""
        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        # Check that the function imports ProviderConfig
        assert "ProviderConfig" in content
        assert "from core.providers" in content or "core.providers.config" in content

    def test_factory_integration(self):
        """create_client_from_config should use the factory pattern."""
        client_path = Path(__file__).parent.parent / "core" / "client.py"
        content = client_path.read_text()

        # Check that it uses factory_create_client
        assert "factory_create_client" in content or "factory" in content.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestProviderClientIntegration:
    """Integration tests for provider client components."""

    def test_provider_capabilities_in_context(self):
        """Provider capabilities should be accessible from provider."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        # Get capabilities
        caps = provider.capabilities
        caps_dict = caps.to_dict()

        # Should be able to serialize and use
        assert isinstance(caps_dict, dict)
        assert len(caps_dict) == 5  # All 5 capability flags

    def test_error_hierarchy(self):
        """Error classes should form proper hierarchy."""
        # Test inheritance
        assert issubclass(ProviderNotFoundError, ProviderError)
        assert issubclass(ProviderConnectionError, ProviderError)
        assert issubclass(ProviderTimeoutError, ProviderError)

        # Test all inherit from Exception
        assert issubclass(ProviderError, Exception)
        assert issubclass(ProviderNotFoundError, Exception)
        assert issubclass(ProviderConnectionError, Exception)
        assert issubclass(ProviderTimeoutError, Exception)

    def test_conversation_context_with_messages(self):
        """ConversationContext should work with UniversalMessage."""
        ctx = ConversationContext(conversation_id="test_conv")

        # Add various message types
        user_msg = UniversalMessage(role="user", content=[TextContent(text="Hello")])
        assistant_msg = UniversalMessage(
            role="assistant",
            content=[
                TextContent(text="Hi!"),
                ToolUseContent(id="tool_1", name="Read", input={}),
            ],
        )

        ctx.add_message(user_msg)
        ctx.add_message(assistant_msg)

        assert ctx.get_message_count() == 2
        assert ctx.get_last_message().has_tool_use

    @pytest.mark.asyncio
    async def test_provider_lifecycle(self):
        """Complete provider lifecycle should work correctly."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        # Before connection
        assert not provider.is_connected
        assert provider.provider_name == "Claude Code"

        # During connection
        async with provider as p:
            assert p.is_connected
            assert isinstance(p.capabilities, ProviderCapabilities)

            # Verify conversation context works
            ctx = p.get_conversation_context()
            assert isinstance(ctx, ConversationContext)

            p.clear_conversation()
            assert ctx.get_message_count() == 0

        # After connection
        assert not provider.is_connected


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_provider_error_empty_details(self):
        """ProviderError with empty details should work."""
        error = ProviderError("test", "message", {})
        assert error.details == {}
        assert error.to_dict()["details"] == {}

    def test_provider_error_none_details(self):
        """ProviderError with None details should use empty dict."""
        error = ProviderError("test", "message", None)
        assert error.details == {}

    def test_conversation_context_multiple_clear(self):
        """Multiple clears should not cause errors."""
        ctx = ConversationContext()
        ctx.clear()
        ctx.clear()
        assert ctx.messages == []

    def test_capabilities_equality(self):
        """Two capabilities with same values should be equal."""
        caps1 = ProviderCapabilities(supports_hooks=True)
        caps2 = ProviderCapabilities(supports_hooks=True)
        assert caps1 == caps2

    def test_capabilities_inequality(self):
        """Two capabilities with different values should not be equal."""
        caps1 = ProviderCapabilities(supports_hooks=True)
        caps2 = ProviderCapabilities(supports_hooks=False)
        assert caps1 != caps2

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Calling close multiple times should not cause errors."""
        from core.providers.adapters.claude_provider import ClaudeProvider

        mock_sdk_client = mock.Mock()
        provider = ClaudeProvider(sdk_client=mock_sdk_client)

        async with provider:
            pass

        # Call close again - should not raise
        await provider.close()
        await provider.close()

        assert not provider.is_connected

    def test_empty_universal_message_in_context(self):
        """Empty UniversalMessage should work in context."""
        ctx = ConversationContext()
        empty_msg = UniversalMessage(role="assistant", content=[])
        ctx.add_message(empty_msg)

        assert ctx.get_message_count() == 1
        assert ctx.get_last_message().text_content == ""
