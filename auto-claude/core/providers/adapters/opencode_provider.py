"""
OpenCode Provider
=================

OpenCodeProvider wraps OpenCodeSubprocess and implements the AgentClient Protocol.
Enables provider-agnostic agent usage via OpenCode CLI subprocess communication.

This module provides:
- OpenCodeProvider: AgentClient implementation for OpenCode CLI
- Subprocess-based communication with OpenCode
- Message parsing via OpenCodeMessageParser
- Streaming response support

The OpenCodeProvider manages:
- OpenCode CLI subprocess lifecycle
- JSON message serialization/deserialization
- Streaming output parsing
- Timeout and error handling

Note on capabilities:
OpenCode does NOT support the same features as Claude Code:
- No hooks (commands validated pre-execution instead)
- No sandboxing (security handled at command validation level)
- Streaming IS supported via subprocess stdout
- No MCP (OpenCode has its own tool integration)
- No extended thinking

Usage:
    from auto_claude.core.providers.adapters.opencode_provider import OpenCodeProvider
    from auto_claude.core.providers.adapters.opencode_subprocess import SubprocessConfig

    # Create provider from configuration
    config = SubprocessConfig(
        provider="openai",
        model="gpt-4o",
        api_key="sk-...",
    )
    provider = OpenCodeProvider.from_config(config)

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
from typing import Any

from ..client import (
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
)
from ..messages import TextContent, UniversalMessage
from .opencode_messages import OpenCodeMessageParser, OpenCodeParseError
from .opencode_subprocess import (
    OpenCodeCrashError,
    OpenCodeNotInstalledError,
    OpenCodeSubprocess,
    OpenCodeSubprocessError,
    OpenCodeTimeoutError,
    SubprocessConfig,
)


@dataclass
class OpenCodeProvider:
    """
    AgentClient implementation wrapping OpenCodeSubprocess.

    Provides a provider-agnostic interface to OpenCode CLI while managing
    subprocess lifecycle and message conversion.

    Unlike ClaudeProvider, OpenCodeProvider:
    - Communicates via CLI subprocess (stdin/stdout)
    - Does NOT support hooks (uses pre-execution validation instead)
    - Does NOT support sandboxing directly
    - Does NOT support MCP (uses OpenCode's built-in tools)
    - Does NOT support extended thinking

    The provider uses OpenCodeMessageParser for parsing CLI JSON output
    to UniversalMessage format.

    Attributes:
        subprocess: The underlying OpenCodeSubprocess manager
        parser: Message parser for JSON output conversion
        _is_connected: Connection state tracking
        _conversation_context: Current conversation state

    Example:
        config = SubprocessConfig(provider="openai", model="gpt-4o")
        provider = OpenCodeProvider.from_config(config)

        async with provider:
            response = await provider.query(message)
            print(response.text_content)
    """

    subprocess: OpenCodeSubprocess
    parser: OpenCodeMessageParser = field(default_factory=OpenCodeMessageParser)
    _is_connected: bool = field(default=False, init=False)
    _conversation_context: ConversationContext = field(
        default_factory=ConversationContext, init=False
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        """
        Get provider capability flags for OpenCode CLI.

        OpenCode CLI has different capabilities than Claude Code:
        - No hook support (pre-execution validation instead)
        - No sandbox support (security at validation level)
        - Streaming IS supported via stdout
        - No MCP support (built-in tools instead)
        - No extended thinking support

        Returns:
            ProviderCapabilities with OpenCode features
        """
        return ProviderCapabilities(
            supports_hooks=False,
            supports_sandbox=False,
            supports_streaming=True,
            supports_mcp=False,
            supports_extended_thinking=False,
        )

    @property
    def provider_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            "OpenCode" as the provider identifier
        """
        return "OpenCode"

    @property
    def is_connected(self) -> bool:
        """
        Check if the provider is connected and ready.

        Returns:
            True if the subprocess is running and ready
        """
        return self._is_connected and self.subprocess.is_running

    async def query(
        self,
        message: UniversalMessage,
        context: ConversationContext | None = None,
    ) -> UniversalMessage:
        """
        Send a query and get a complete response.

        Extracts text content from UniversalMessage, sends to subprocess,
        and parses the complete response.

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

        try:
            # Extract text content for the query
            text_content = self._extract_text_content(message)

            # Send query via subprocess
            await self.subprocess.send_query(text_content)

            # Read complete output
            output = await self.subprocess.read_output()

            # Parse output to messages
            messages = self.parser.parse_output(output)

            # Return last assistant message or empty response
            for msg in reversed(messages):
                if msg.role == "assistant":
                    # Add to conversation context
                    if context:
                        context.add_message(message)
                        context.add_message(msg)
                    self._conversation_context.add_message(message)
                    self._conversation_context.add_message(msg)
                    return msg

            # Return empty response if no assistant messages
            empty_response = UniversalMessage(
                role="assistant",
                content=[TextContent(text="")],
            )
            return empty_response

        except OpenCodeNotInstalledError as e:
            raise ProviderConnectionError(
                self.provider_name,
                "OpenCode CLI not installed. Please install from https://opencode.ai",
            ) from e
        except OpenCodeTimeoutError as e:
            raise ProviderError(
                self.provider_name,
                f"Query timed out: {e!s}",
                {"timeout_seconds": e.timeout_seconds},
            ) from e
        except OpenCodeCrashError as e:
            raise ProviderError(
                self.provider_name,
                f"OpenCode CLI crashed: {e!s}",
                {"exit_code": e.exit_code, "stderr": e.stderr},
            ) from e
        except OpenCodeParseError as e:
            raise ProviderError(
                self.provider_name,
                f"Failed to parse OpenCode response: {e!s}",
                {"raw_data": str(e.raw_data)[:500] if e.raw_data else None},
            ) from e
        except OpenCodeSubprocessError as e:
            raise ProviderError(
                self.provider_name,
                f"Subprocess error: {e!s}",
                {"stderr": e.stderr},
            ) from e
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

        Extracts text content from UniversalMessage, sends to subprocess,
        and streams parsed response messages as they arrive.

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

        try:
            # Extract text content for the query
            text_content = self._extract_text_content(message)

            # Send query via subprocess
            await self.subprocess.send_query(text_content)

            # Track last message for context
            last_message: UniversalMessage | None = None

            # Stream responses via subprocess stdout
            async for line in self.subprocess.read_output_stream():
                # Parse each line as potential message
                parsed_msg = self.parser.parse_streaming_line(line)
                if parsed_msg and parsed_msg.role == "assistant":
                    last_message = parsed_msg
                    yield parsed_msg

            # Add to conversation context
            if last_message:
                if context:
                    context.add_message(message)
                    context.add_message(last_message)
                self._conversation_context.add_message(message)
                self._conversation_context.add_message(last_message)

        except OpenCodeNotInstalledError as e:
            raise ProviderConnectionError(
                self.provider_name,
                "OpenCode CLI not installed. Please install from https://opencode.ai",
            ) from e
        except OpenCodeTimeoutError as e:
            raise ProviderError(
                self.provider_name,
                f"Stream query timed out: {e!s}",
                {"timeout_seconds": e.timeout_seconds},
            ) from e
        except OpenCodeCrashError as e:
            raise ProviderError(
                self.provider_name,
                f"OpenCode CLI crashed: {e!s}",
                {"exit_code": e.exit_code, "stderr": e.stderr},
            ) from e
        except OpenCodeSubprocessError as e:
            raise ProviderError(
                self.provider_name,
                f"Stream subprocess error: {e!s}",
                {"stderr": e.stderr},
            ) from e
        except Exception as e:
            raise ProviderError(
                self.provider_name,
                f"Stream query failed: {e!s}",
                {"original_error": str(e)},
            ) from e

    async def receive_response(self) -> AsyncIterator[UniversalMessage]:
        """
        Receive streaming responses from an ongoing conversation.

        Streams parsed UniversalMessage objects as they become available
        from the subprocess stdout.

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

        # Stream responses via subprocess stdout
        async for line in self.subprocess.read_output_stream():
            # Parse each line as potential message
            parsed_msg = self.parser.parse_streaming_line(line)
            if parsed_msg:
                yield parsed_msg

    async def close(self) -> None:
        """
        Close the provider connection and clean up resources.

        Stops the subprocess gracefully. This method should be called
        when the provider is no longer needed. It is automatically
        called when exiting an async context manager.
        """
        self._is_connected = False
        await self.subprocess.stop()

    async def __aenter__(self) -> "OpenCodeProvider":
        """
        Enter async context manager.

        Starts the subprocess and initializes the connection.

        Returns:
            The provider instance for use within the context

        Raises:
            ProviderConnectionError: If subprocess fails to start
        """
        try:
            await self.subprocess.start()
            self._is_connected = True
            return self
        except OpenCodeNotInstalledError as e:
            raise ProviderConnectionError(
                self.provider_name,
                "OpenCode CLI not installed. Please install from https://opencode.ai",
            ) from e
        except OpenCodeSubprocessError as e:
            raise ProviderConnectionError(
                self.provider_name,
                f"Failed to start OpenCode subprocess: {e!s}",
            ) from e

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

    def _extract_text_content(self, message: UniversalMessage) -> str:
        """
        Extract text content from a UniversalMessage.

        Args:
            message: The message to extract text from

        Returns:
            Extracted text content string
        """
        text_parts: list[str] = []
        for block in message.content:
            if isinstance(block, TextContent):
                text_parts.append(block.text)
            elif hasattr(block, "text"):
                text_parts.append(str(getattr(block, "text", "")))

        return "\n".join(text_parts)

    @classmethod
    def from_subprocess(
        cls,
        subprocess: OpenCodeSubprocess,
    ) -> "OpenCodeProvider":
        """
        Create an OpenCodeProvider from an existing OpenCodeSubprocess.

        This is the primary factory method for creating an OpenCodeProvider
        when you already have a configured subprocess manager.

        Args:
            subprocess: A configured OpenCodeSubprocess instance

        Returns:
            OpenCodeProvider wrapping the subprocess
        """
        return cls(
            subprocess=subprocess,
            parser=OpenCodeMessageParser(),
        )

    @classmethod
    def from_config(
        cls,
        config: SubprocessConfig,
    ) -> "OpenCodeProvider":
        """
        Create an OpenCodeProvider from SubprocessConfig.

        Creates the underlying OpenCodeSubprocess using the provided
        configuration.

        Args:
            config: Subprocess configuration with provider, model, etc.

        Returns:
            OpenCodeProvider ready for use

        Example:
            config = SubprocessConfig(
                provider="openai",
                model="gpt-4o",
                api_key="sk-...",
            )
            provider = OpenCodeProvider.from_config(config)

            async with provider:
                response = await provider.query(message)
        """
        subprocess = OpenCodeSubprocess(config=config)
        return cls(
            subprocess=subprocess,
            parser=OpenCodeMessageParser(),
        )

    @classmethod
    def from_parameters(
        cls,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        working_dir: Path | None = None,
        timeout: float = 300.0,
    ) -> "OpenCodeProvider":
        """
        Create an OpenCodeProvider from individual parameters.

        Convenience factory method that creates the SubprocessConfig
        and OpenCodeSubprocess internally.

        Args:
            provider: AI provider to use (openai, anthropic, google, etc.)
            model: Model name to use (gpt-4o, claude-3-5-sonnet, etc.)
            api_key: API key for the provider (optional, can use env var)
            working_dir: Working directory for the subprocess
            timeout: Default timeout for operations in seconds

        Returns:
            OpenCodeProvider ready for use

        Example:
            provider = OpenCodeProvider.from_parameters(
                provider="openai",
                model="gpt-4o",
            )

            async with provider:
                response = await provider.query(message)
        """
        config = SubprocessConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            working_dir=working_dir,
            timeout=timeout,
        )
        return cls.from_config(config)

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

    @staticmethod
    def is_available() -> bool:
        """
        Check if OpenCode CLI is available on this system.

        Returns:
            True if OpenCode CLI is installed and accessible
        """
        return OpenCodeSubprocess.is_installed()

    async def get_version(self) -> str | None:
        """
        Get the OpenCode CLI version.

        Returns:
            Version string or None if cannot be determined
        """
        return await self.subprocess.get_version()


# Re-export for convenience
__all__ = [
    "OpenCodeProvider",
]
