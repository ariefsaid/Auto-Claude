"""
AgentClient Protocol
====================

Provider-agnostic client interface for agent implementations.
Defines the standard interface that all provider implementations must follow.

This module provides:
- AgentClient Protocol: Standard interface for all providers
- ProviderCapabilities: Capability flags for provider features
- ConversationContext: Context for multi-turn conversations

The AgentClient Protocol enables:
- Unified query interface across providers
- Streaming response support via async generators
- Async context manager for resource management
- Provider capability detection for feature gating

Usage:
    from auto_claude.core.providers.client import AgentClient, ProviderCapabilities

    class MyProvider:
        '''Provider implementing AgentClient Protocol.'''

        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(
                supports_hooks=True,
                supports_sandbox=True,
                supports_streaming=True,
            )

        async def query(self, message: UniversalMessage) -> UniversalMessage:
            # Send query and return response
            ...

        async def receive_response(self) -> AsyncIterator[UniversalMessage]:
            # Stream responses
            ...

        async def close(self) -> None:
            # Clean up resources
            ...

        async def __aenter__(self) -> 'MyProvider':
            return self

        async def __aexit__(self, *args) -> None:
            await self.close()
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .messages import UniversalMessage


@dataclass
class ProviderCapabilities:
    """
    Capability flags for provider features.

    Providers have different capabilities based on their underlying
    implementation. These flags enable feature gating and appropriate
    fallback behavior.

    Attributes:
        supports_hooks: Whether the provider supports pre/post tool use hooks.
            Claude Code supports hooks via the Claude SDK.
            OpenCode does NOT support hooks (commands validated pre-execution).
        supports_sandbox: Whether the provider supports sandboxed execution.
            Claude Code supports sandbox mode via the Claude SDK.
            OpenCode does NOT support sandboxing directly.
        supports_streaming: Whether the provider supports streaming responses.
            Most providers support streaming, but some may only support
            complete responses.
        supports_mcp: Whether the provider supports MCP (Model Context Protocol).
            Claude Code supports MCP servers.
            OpenCode has its own tool integration.
        supports_extended_thinking: Whether the provider supports extended thinking.
            Claude Code supports extended thinking with token budgets.
            Other providers may not support this feature.
    """

    supports_hooks: bool = False
    supports_sandbox: bool = False
    supports_streaming: bool = True
    supports_mcp: bool = False
    supports_extended_thinking: bool = False

    def to_dict(self) -> dict[str, bool]:
        """
        Convert capabilities to dictionary format.

        Returns:
            Dictionary with capability flags
        """
        return {
            "supports_hooks": self.supports_hooks,
            "supports_sandbox": self.supports_sandbox,
            "supports_streaming": self.supports_streaming,
            "supports_mcp": self.supports_mcp,
            "supports_extended_thinking": self.supports_extended_thinking,
        }


@dataclass
class ConversationContext:
    """
    Context for multi-turn conversations.

    Maintains state across multiple query/response cycles within
    a conversation. Providers may use this to track conversation
    history, session IDs, or other stateful information.

    Attributes:
        conversation_id: Unique identifier for the conversation
        messages: History of messages in the conversation
        metadata: Provider-specific metadata
    """

    conversation_id: str | None = None
    messages: list[UniversalMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: UniversalMessage) -> None:
        """
        Add a message to the conversation history.

        Args:
            message: Message to add to history
        """
        self.messages.append(message)

    def clear(self) -> None:
        """Clear conversation history and metadata."""
        self.messages.clear()
        self.metadata.clear()

    def get_last_message(self) -> UniversalMessage | None:
        """
        Get the most recent message in the conversation.

        Returns:
            Last message or None if conversation is empty
        """
        return self.messages[-1] if self.messages else None

    def get_message_count(self) -> int:
        """
        Get the number of messages in the conversation.

        Returns:
            Count of messages
        """
        return len(self.messages)


@runtime_checkable
class AgentClient(Protocol):
    """
    Protocol defining the standard interface for agent providers.

    All provider implementations must conform to this protocol to ensure
    consistent behavior across different backends (Claude Code, OpenCode, etc.).

    The protocol supports:
    - Query/response pattern for single-turn interactions
    - Streaming responses via async iterators
    - Async context manager for resource management
    - Capability detection for feature gating

    Example:
        async with provider as client:
            # Send a query
            response = await client.query(message)

            # Or stream responses
            async for msg in client.receive_response():
                process(msg)

    Note:
        This is a Protocol class (duck typing), not an abstract base class.
        Implementations don't need to explicitly inherit from AgentClient.
    """

    @property
    def capabilities(self) -> ProviderCapabilities:
        """
        Get provider capability flags.

        Returns:
            ProviderCapabilities indicating what features this provider supports

        Example:
            if provider.capabilities.supports_hooks:
                # Register security hooks
                pass
        """
        ...

    @property
    def provider_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            Provider name (e.g., "Claude Code", "OpenCode")
        """
        ...

    @property
    def is_connected(self) -> bool:
        """
        Check if the client is connected and ready.

        Returns:
            True if connected and ready to accept queries
        """
        ...

    async def query(
        self,
        message: UniversalMessage,
        context: ConversationContext | None = None,
    ) -> UniversalMessage:
        """
        Send a query and get a complete response.

        This is the primary method for single-turn interactions.
        For streaming responses, use receive_response() instead.

        Args:
            message: The query message to send
            context: Optional conversation context for multi-turn conversations

        Returns:
            Complete response message from the provider

        Raises:
            ConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
            TimeoutError: If the query times out
        """
        ...

    async def query_stream(
        self,
        message: UniversalMessage,
        context: ConversationContext | None = None,
    ) -> AsyncIterator[UniversalMessage]:
        """
        Send a query and stream response chunks.

        Use this for streaming responses where partial results are
        available before the complete response is ready.

        Args:
            message: The query message to send
            context: Optional conversation context for multi-turn conversations

        Yields:
            Response message chunks as they become available

        Raises:
            ConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
            TimeoutError: If the stream times out
        """
        ...

    async def receive_response(self) -> AsyncIterator[UniversalMessage]:
        """
        Receive streaming responses from an ongoing conversation.

        This async iterator yields messages as they become available
        from the provider. Use after query_stream() or for long-running
        conversations.

        Yields:
            Response messages as they become available

        Raises:
            ConnectionError: If not connected to the provider
            StopAsyncIteration: When no more messages are available
        """
        ...

    async def close(self) -> None:
        """
        Close the client connection and clean up resources.

        This method should be called when the client is no longer needed.
        It is automatically called when exiting an async context manager.

        After calling close(), the client should not be used for queries.
        Attempting to query a closed client may raise ConnectionError.
        """
        ...

    async def __aenter__(self) -> "AgentClient":
        """
        Enter async context manager.

        Returns:
            The client instance for use within the context
        """
        ...

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
            False to propagate exceptions, True to suppress
        """
        ...


class ProviderError(Exception):
    """
    Exception raised when a provider encounters an error.

    Attributes:
        provider: Name of the provider that raised the error
        message: Human-readable error message
        details: Optional additional error details
    """

    def __init__(
        self,
        provider: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a ProviderError.

        Args:
            provider: Name of the provider
            message: Error message
            details: Optional additional details
        """
        self.provider = provider
        self.message = message
        self.details = details or {}
        super().__init__(f"[{provider}] {message}")

    def to_dict(self) -> dict[str, Any]:
        """
        Convert error to dictionary format.

        Returns:
            Dictionary representation of the error
        """
        return {
            "provider": self.provider,
            "message": self.message,
            "details": self.details,
        }


class ProviderNotFoundError(ProviderError):
    """
    Exception raised when a requested provider is not available.

    This may occur when:
    - The provider is not installed
    - The provider is not configured
    - The provider type is not supported
    """

    def __init__(self, provider: str, available: list[str] | None = None) -> None:
        """
        Initialize a ProviderNotFoundError.

        Args:
            provider: Name of the requested provider
            available: List of available provider names
        """
        available_str = ", ".join(available) if available else "none"
        message = f"Provider not found. Available providers: {available_str}"
        super().__init__(provider, message, {"available": available or []})


class ProviderConnectionError(ProviderError):
    """
    Exception raised when connection to a provider fails.

    This may occur when:
    - The provider service is unavailable
    - Authentication fails
    - Network issues prevent connection
    """

    def __init__(
        self,
        provider: str,
        reason: str,
        retry_after: float | None = None,
    ) -> None:
        """
        Initialize a ProviderConnectionError.

        Args:
            provider: Name of the provider
            reason: Reason for connection failure
            retry_after: Optional seconds to wait before retrying
        """
        message = f"Connection failed: {reason}"
        details = {"reason": reason}
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(provider, message, details)


class ProviderTimeoutError(ProviderError):
    """
    Exception raised when a provider operation times out.

    This may occur when:
    - A query takes too long to complete
    - The provider is slow to respond
    - Network latency causes delays
    """

    def __init__(
        self,
        provider: str,
        operation: str,
        timeout_seconds: float,
    ) -> None:
        """
        Initialize a ProviderTimeoutError.

        Args:
            provider: Name of the provider
            operation: Name of the operation that timed out
            timeout_seconds: Timeout duration in seconds
        """
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        super().__init__(
            provider,
            message,
            {"operation": operation, "timeout_seconds": timeout_seconds},
        )
