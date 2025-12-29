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
- Integrated security validation for bash commands

The OpenCodeProvider manages:
- OpenCode CLI subprocess lifecycle
- JSON message serialization/deserialization
- Streaming output parsing
- Timeout and error handling
- Pre-execution security validation for bash commands

Note on capabilities:
OpenCode does NOT support the same features as Claude Code:
- No hooks (commands validated pre-execution instead)
- No sandboxing (security handled at command validation level)
- Streaming IS supported via subprocess stdout
- No MCP (OpenCode has its own tool integration)
- No extended thinking

Security Integration:
Because OpenCode lacks hook support, security validation happens BEFORE
commands are sent to the subprocess. The same security profile from
.auto-claude-security.json applies to both Claude Code and OpenCode.

Usage:
    from auto_claude.core.providers.adapters.opencode_provider import OpenCodeProvider
    from auto_claude.core.providers.adapters.opencode_subprocess import SubprocessConfig

    # Create provider from configuration with security enabled
    config = SubprocessConfig(
        provider="openai",
        model="gpt-4o",
        api_key="sk-...",
    )
    provider = OpenCodeProvider.from_config(config, enable_security=True)

    # Use as async context manager
    async with provider as client:
        # Send a query - bash commands will be validated before execution
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
    SecurityBlockedError,
)
from ..messages import TextContent, ToolUseContent, UniversalMessage
from .opencode_messages import OpenCodeMessageParser, OpenCodeParseError
from .opencode_security import (
    OpenCodeSecurityValidator,
    ValidationResult,
    create_security_wrapper,
)
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
    subprocess lifecycle, message conversion, and security validation.

    Unlike ClaudeProvider, OpenCodeProvider:
    - Communicates via CLI subprocess (stdin/stdout)
    - Does NOT support hooks (uses pre-execution validation instead)
    - Does NOT support sandboxing directly
    - Does NOT support MCP (uses OpenCode's built-in tools)
    - Does NOT support extended thinking
    - Includes optional pre-execution security validation for bash commands

    The provider uses OpenCodeMessageParser for parsing CLI JSON output
    to UniversalMessage format, and OpenCodeSecurityValidator for
    pre-execution command validation.

    Attributes:
        subprocess: The underlying OpenCodeSubprocess manager
        parser: Message parser for JSON output conversion
        security_validator: Optional security validator for bash commands
        _is_connected: Connection state tracking
        _conversation_context: Current conversation state

    Example:
        config = SubprocessConfig(provider="openai", model="gpt-4o")
        provider = OpenCodeProvider.from_config(config, enable_security=True)

        async with provider:
            response = await provider.query(message)
            print(response.text_content)
    """

    subprocess: OpenCodeSubprocess
    parser: OpenCodeMessageParser = field(default_factory=OpenCodeMessageParser)
    security_validator: OpenCodeSecurityValidator | None = None
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
            True if the provider has been initialized (subprocess may not be running yet)
        """
        # We only need to check _is_connected, not subprocess.is_running
        # because send_query() handles starting/restarting the subprocess
        return self._is_connected

    @property
    def is_security_enabled(self) -> bool:
        """
        Check if security validation is enabled for this provider.

        Returns:
            True if a security validator is configured
        """
        return self.security_validator is not None

    def _validate_message(self, message: UniversalMessage) -> ValidationResult | None:
        """
        Validate tool calls in a message for security.

        Checks all ToolUseContent blocks in the message for Bash commands
        and validates them against the security profile.

        Args:
            message: The message containing potential tool calls

        Returns:
            ValidationResult if a command was blocked, None if all allowed

        Note:
            Only validates if security_validator is configured.
            Non-Bash tool calls pass through without validation.
        """
        if not self.is_security_enabled:
            return None

        # Check all tool use blocks in the message
        for block in message.content:
            if isinstance(block, ToolUseContent):
                result = self.security_validator.validate_tool_call(
                    tool_name=block.name,
                    tool_input=block.input,
                )
                if result.is_blocked:
                    return result

        return None

    def _raise_if_blocked(self, result: ValidationResult) -> None:
        """
        Raise SecurityBlockedError if validation result indicates blocked.

        Args:
            result: ValidationResult from security validation

        Raises:
            SecurityBlockedError: If the result indicates command was blocked
        """
        if result.is_blocked:
            raise SecurityBlockedError(
                provider=self.provider_name,
                command=result.command,
                reason=result.reason,
                tool_name=result.tool_name,
            )

    async def query(
        self,
        message: UniversalMessage | str,
        context: ConversationContext | None = None,
    ) -> UniversalMessage:
        """
        Send a query and get a complete response.

        Accepts both UniversalMessage objects and raw strings for compatibility
        with different calling patterns. Sends to subprocess and parses the
        complete response. Validates any bash tool calls against the security
        profile before returning.

        Args:
            message: The query message in universal format
            context: Optional conversation context for multi-turn conversations

        Returns:
            Complete response message in universal format

        Raises:
            ProviderConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
            SecurityBlockedError: If a bash command is blocked by security
        """
        if not self.is_connected:
            raise ProviderConnectionError(
                self.provider_name,
                "Provider not connected. Use 'async with provider:' context manager.",
            )

        try:
            # Handle both string and UniversalMessage input
            # The session layer passes strings, so we need to handle both formats
            if isinstance(message, str):
                text_content = message
            else:
                # Extract text content from UniversalMessage
                text_content = self._extract_text_content(message)

            # Send query via subprocess
            await self.subprocess.send_query(text_content)

            # Read complete output
            output = await self.subprocess.read_output()

            # Parse output to messages
            messages = self.parser.parse_output(output)

            # Return last assistant message with content, or empty response
            for msg in reversed(messages):
                if msg.role == "assistant" and msg.content:
                    # Skip messages with empty content (like step markers)
                    has_content = any(
                        (hasattr(block, "text") and block.text)
                        or hasattr(block, "name")  # Tool use has content
                        for block in msg.content
                    )
                    if not has_content:
                        continue

                    # Validate tool calls for security before returning
                    blocked = self._validate_message(msg)
                    if blocked:
                        self._raise_if_blocked(blocked)

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
        and streams parsed response messages as they arrive. Validates
        each message for bash tool calls against the security profile.

        Args:
            message: The query message in universal format
            context: Optional conversation context for multi-turn conversations

        Yields:
            Response message chunks in universal format

        Raises:
            ProviderConnectionError: If not connected to the provider
            ProviderError: If the provider returns an error
            SecurityBlockedError: If a bash command is blocked by security
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
                    # Validate tool calls for security before yielding
                    blocked = self._validate_message(parsed_msg)
                    if blocked:
                        self._raise_if_blocked(blocked)

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

        Initializes the provider for use. The subprocess is started lazily
        when the first query is sent (via send_query).

        Returns:
            The provider instance for use within the context
        """
        # Don't start subprocess here - it will be started in send_query()
        # when we have an actual query to run
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
        enable_security: bool = False,
        project_dir: Path | None = None,
    ) -> "OpenCodeProvider":
        """
        Create an OpenCodeProvider from an existing OpenCodeSubprocess.

        This is the primary factory method for creating an OpenCodeProvider
        when you already have a configured subprocess manager.

        Args:
            subprocess: A configured OpenCodeSubprocess instance
            enable_security: Whether to enable security validation for bash commands
            project_dir: Project directory for security profile. Uses subprocess
                         working_dir or cwd if not provided.

        Returns:
            OpenCodeProvider wrapping the subprocess with optional security
        """
        security_validator = None
        if enable_security:
            # Use project_dir, or fall back to subprocess working dir, or cwd
            sec_dir = project_dir or subprocess.config.working_dir or Path.cwd()
            security_validator = create_security_wrapper(sec_dir)

        return cls(
            subprocess=subprocess,
            parser=OpenCodeMessageParser(),
            security_validator=security_validator,
        )

    @classmethod
    def from_config(
        cls,
        config: SubprocessConfig,
        enable_security: bool = False,
        project_dir: Path | None = None,
    ) -> "OpenCodeProvider":
        """
        Create an OpenCodeProvider from SubprocessConfig.

        Creates the underlying OpenCodeSubprocess using the provided
        configuration.

        Args:
            config: Subprocess configuration with provider, model, etc.
            enable_security: Whether to enable security validation for bash commands
            project_dir: Project directory for security profile. Uses config
                         working_dir or cwd if not provided.

        Returns:
            OpenCodeProvider ready for use with optional security

        Example:
            config = SubprocessConfig(
                provider="openai",
                model="gpt-4o",
                api_key="sk-...",
            )
            provider = OpenCodeProvider.from_config(config, enable_security=True)

            async with provider:
                response = await provider.query(message)
        """
        subprocess = OpenCodeSubprocess(config=config)
        return cls.from_subprocess(
            subprocess=subprocess,
            enable_security=enable_security,
            project_dir=project_dir or config.working_dir,
        )

    @classmethod
    def from_parameters(
        cls,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        working_dir: Path | None = None,
        timeout: float = 300.0,
        enable_security: bool = False,
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
            enable_security: Whether to enable security validation for bash commands

        Returns:
            OpenCodeProvider ready for use with optional security

        Example:
            provider = OpenCodeProvider.from_parameters(
                provider="openai",
                model="gpt-4o",
                enable_security=True,
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
        return cls.from_config(config, enable_security=enable_security)

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
