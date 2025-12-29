"""
Claude Provider
================

ClaudeProvider wraps ClaudeSDKClient and implements the AgentClient Protocol.
Enables provider-agnostic agent usage while preserving all Claude SDK functionality.

This module provides:
- ClaudeProvider: AgentClient implementation for Claude Code
- Full preservation of hooks, MCP, security, and extended thinking
- Bidirectional message conversion via ClaudeMessageAdapter
- Streaming response support

The ClaudeProvider maintains:
- All security layers (sandbox, permissions, bash validation)
- MCP server integration (Context7, Linear, Graphiti, etc.)
- Extended thinking support with token budgets
- Pre/post tool use hooks

Usage:
    from auto_claude.core.providers.adapters.claude_provider import ClaudeProvider
    from auto_claude.core.providers.config import ProviderConfig

    # Create provider from configuration
    config = ProviderConfig.from_env()
    provider = ClaudeProvider.from_config(config, project_dir, spec_dir, model)

    # Use as async context manager
    async with provider as client:
        # Send a query
        response = await client.query(universal_message)

        # Or stream responses
        async for msg in client.query_stream(message):
            process(msg)
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..client import (
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
)
from ..messages import TextContent, UniversalMessage
from .claude_adapter import ClaudeMessageAdapter

# Use TYPE_CHECKING to avoid import issues during testing
if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient


@dataclass
class ClaudeProvider:
    """
    AgentClient implementation wrapping ClaudeSDKClient.

    Provides a provider-agnostic interface to Claude Code while preserving
    all existing functionality including:
    - Security layers (sandbox, permissions, bash validation)
    - MCP server integration
    - Extended thinking support
    - Pre/post tool use hooks

    The provider uses ClaudeMessageAdapter for bidirectional conversion
    between UniversalMessage format and Claude SDK message types.

    Attributes:
        sdk_client: The underlying ClaudeSDKClient instance
        adapter: Message adapter for format conversion
        _is_connected: Connection state tracking
        _conversation_context: Current conversation state

    Example:
        config = ProviderConfig.from_env()
        provider = ClaudeProvider.from_config(config, project_dir, spec_dir, model)

        async with provider:
            response = await provider.query(message)
            print(response.text_content)
    """

    sdk_client: Any  # ClaudeSDKClient (Any for testing flexibility)
    adapter: ClaudeMessageAdapter = field(default_factory=ClaudeMessageAdapter)
    _is_connected: bool = field(default=False, init=False)
    _conversation_context: ConversationContext = field(
        default_factory=ConversationContext, init=False
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        """
        Get provider capability flags for Claude Code.

        Claude Code supports:
        - Security hooks (pre/post tool use)
        - Sandboxed execution
        - Streaming responses
        - MCP server integration
        - Extended thinking with token budgets

        Returns:
            ProviderCapabilities with all Claude Code features enabled
        """
        return ProviderCapabilities(
            supports_hooks=True,
            supports_sandbox=True,
            supports_streaming=True,
            supports_mcp=True,
            supports_extended_thinking=True,
        )

    @property
    def provider_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            "Claude Code" as the provider identifier
        """
        return "Claude Code"

    @property
    def is_connected(self) -> bool:
        """
        Check if the provider is connected and ready.

        Returns:
            True if the SDK client is initialized and ready
        """
        return self._is_connected and self.sdk_client is not None

    async def query(
        self,
        message: UniversalMessage,
        context: ConversationContext | None = None,
    ) -> UniversalMessage:
        """
        Send a query and get a complete response.

        Converts the UniversalMessage to Claude SDK format, sends the query,
        and converts the response back to UniversalMessage format.

        Args:
            message: The query message in universal format
            context: Optional conversation context for multi-turn conversations

        Returns:
            Complete response message in universal format

        Raises:
            ProviderConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
        """
        if not self.is_connected:
            raise ProviderConnectionError(
                self.provider_name,
                "Provider not connected. Use 'async with provider:' context manager.",
            )

        # Convert universal message to Claude SDK format
        claude_message = self.adapter.from_universal(message)

        # Send query via SDK
        try:
            # Extract text content for the query
            text_content = ""
            for block in claude_message.get("content", []):
                if block.get("type") == "text":
                    text_content = block.get("text", "")
                    break

            # Use SDK's query method
            await self.sdk_client.query(text_content)

            # Collect the complete response
            response_blocks: list[Any] = []
            async for sdk_message in self.sdk_client.receive_response():
                response_blocks.append(sdk_message)

            # Convert last message to universal format
            if response_blocks:
                return self.adapter.to_universal(response_blocks[-1])

            # Return empty response if no messages
            return UniversalMessage(
                role="assistant",
                content=[TextContent(text="")],
            )

        except Exception as e:
            raise ProviderError(
                self.provider_name,
                f"Query failed: {e!s}",
                {"original_error": str(e)},
            ) from e

    async def query_stream(
        self,
        message: UniversalMessage,
        context: ConversationContext | None = None,
    ) -> AsyncIterator[UniversalMessage]:
        """
        Send a query and stream response chunks.

        Converts the UniversalMessage to Claude SDK format, sends the query,
        and streams converted response messages as they arrive.

        Args:
            message: The query message in universal format
            context: Optional conversation context for multi-turn conversations

        Yields:
            Response message chunks in universal format

        Raises:
            ProviderConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
        """
        if not self.is_connected:
            raise ProviderConnectionError(
                self.provider_name,
                "Provider not connected. Use 'async with provider:' context manager.",
            )

        # Convert universal message to Claude SDK format
        claude_message = self.adapter.from_universal(message)

        # Send query via SDK
        try:
            # Extract text content for the query
            text_content = ""
            for block in claude_message.get("content", []):
                if block.get("type") == "text":
                    text_content = block.get("text", "")
                    break

            # Use SDK's query method
            await self.sdk_client.query(text_content)

            # Stream responses via adapter
            async for universal_msg in self.adapter.to_universal_stream(
                self.sdk_client.receive_response()
            ):
                yield universal_msg

        except Exception as e:
            raise ProviderError(
                self.provider_name,
                f"Stream query failed: {e!s}",
                {"original_error": str(e)},
            ) from e

    async def receive_response(self) -> AsyncIterator[UniversalMessage]:
        """
        Receive streaming responses from an ongoing conversation.

        Streams converted UniversalMessage objects as they become available
        from the Claude SDK client.

        Yields:
            Response messages in universal format

        Raises:
            ProviderConnectionError: If not connected to the provider
        """
        if not self.is_connected:
            raise ProviderConnectionError(
                self.provider_name,
                "Provider not connected. Use 'async with provider:' context manager.",
            )

        # Stream responses via adapter
        async for universal_msg in self.adapter.to_universal_stream(
            self.sdk_client.receive_response()
        ):
            yield universal_msg

    async def close(self) -> None:
        """
        Close the provider connection and clean up resources.

        This method should be called when the provider is no longer needed.
        It is automatically called when exiting an async context manager.
        """
        self._is_connected = False
        # SDK client cleanup is handled by context manager exit
        # No explicit close method on ClaudeSDKClient

    async def __aenter__(self) -> "ClaudeProvider":
        """
        Enter async context manager.

        Initializes the provider connection.

        Returns:
            The provider instance for use within the context
        """
        self._is_connected = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        """
        Exit async context manager.

        Ensures close() is called when exiting the context,
        even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate exceptions
        """
        await self.close()
        return False

    @classmethod
    def from_sdk_client(
        cls,
        sdk_client: "ClaudeSDKClient",
    ) -> "ClaudeProvider":
        """
        Create a ClaudeProvider from an existing ClaudeSDKClient.

        This is the primary factory method for creating a ClaudeProvider
        when you already have a configured ClaudeSDKClient.

        Args:
            sdk_client: A configured ClaudeSDKClient instance

        Returns:
            ClaudeProvider wrapping the SDK client
        """
        return cls(
            sdk_client=sdk_client,
            adapter=ClaudeMessageAdapter(),
        )

    @classmethod
    def from_config(
        cls,
        project_dir: Path,
        spec_dir: Path,
        model: str,
        agent_type: str = "coder",
        max_thinking_tokens: int | None = None,
    ) -> "ClaudeProvider":
        """
        Create a ClaudeProvider from configuration parameters.

        Creates the underlying ClaudeSDKClient using the core/client.py
        create_client() function, preserving all security layers and
        MCP server configurations.

        Args:
            project_dir: Root directory for the project (working directory)
            spec_dir: Directory containing the spec (for settings file)
            model: Claude model to use
            agent_type: Type of agent - 'planner', 'coder', 'qa_reviewer', or 'qa_fixer'
            max_thinking_tokens: Token budget for extended thinking (None = disabled)

        Returns:
            ClaudeProvider ready for use

        Example:
            provider = ClaudeProvider.from_config(
                project_dir=Path("/path/to/project"),
                spec_dir=Path("/path/to/spec"),
                model="claude-sonnet-4-20250514",
                agent_type="coder",
            )

            async with provider:
                response = await provider.query(message)
        """
        # Import here to avoid circular imports
        from core.client import create_client

        # Create SDK client using existing infrastructure
        sdk_client = create_client(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            agent_type=agent_type,
            max_thinking_tokens=max_thinking_tokens,
        )

        return cls(
            sdk_client=sdk_client,
            adapter=ClaudeMessageAdapter(),
        )

    def get_conversation_context(self) -> ConversationContext:
        """
        Get the current conversation context.

        Returns:
            The active ConversationContext with message history
        """
        return self._conversation_context

    def clear_conversation(self) -> None:
        """
        Clear the conversation context and history.

        Useful for starting a fresh conversation without creating
        a new provider instance.
        """
        self._conversation_context.clear()
