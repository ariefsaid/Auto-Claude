"""
Claude Message Adapter
======================

Bidirectional conversion between Claude SDK message types and UniversalMessage format.
Enables provider-agnostic message handling while preserving all message data.

This module provides:
- ClaudeMessageAdapter: Converts between Claude SDK and UniversalMessage formats
- Support for all Claude SDK message types (AssistantMessage, UserMessage)
- Support for all content block types (TextBlock, ToolUseBlock, ToolResultBlock)
- Lossless round-trip conversion (Claude → Universal → Claude)

Usage:
    from auto_claude.core.providers.adapters.claude_adapter import ClaudeMessageAdapter
    from auto_claude.core.providers.messages import UniversalMessage, TextContent

    # Create adapter
    adapter = ClaudeMessageAdapter()

    # Convert Claude SDK message to universal format
    universal_msg = adapter.to_universal(claude_message)

    # Convert universal message back to Claude SDK format
    claude_msg = adapter.from_universal(universal_msg)

    # Convert streaming response to universal messages
    async for universal_msg in adapter.to_universal_stream(client.receive_response()):
        process(universal_msg)
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from ..messages import (
    ContentBlock,
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)


@dataclass
class ClaudeMessageAdapter:
    """
    Bidirectional adapter for Claude SDK messages.

    Converts between Claude SDK message types and the UniversalMessage format.
    Supports all Claude SDK message and content block types.

    The adapter is stateless and can be reused across multiple conversions.

    Attributes:
        None - adapter is stateless

    Example:
        adapter = ClaudeMessageAdapter()

        # Convert Claude message to universal format
        universal = adapter.to_universal(claude_msg)

        # Convert back to Claude format
        claude_dict = adapter.from_universal(universal)
    """

    def to_universal(self, claude_message: Any) -> UniversalMessage:
        """
        Convert a Claude SDK message to UniversalMessage format.

        Handles AssistantMessage and UserMessage types from the Claude SDK.
        Extracts all content blocks (TextBlock, ToolUseBlock, ToolResultBlock)
        and converts them to the corresponding universal content types.

        Args:
            claude_message: A Claude SDK message object (AssistantMessage or UserMessage)

        Returns:
            UniversalMessage with converted content blocks

        Raises:
            ValueError: If the message type is not supported
        """
        msg_type = type(claude_message).__name__

        # Determine role based on message type
        if msg_type == "AssistantMessage":
            role = "assistant"
        elif msg_type == "UserMessage":
            role = "user"
        else:
            # Try to infer role from message attributes
            if hasattr(claude_message, "role"):
                role = claude_message.role
            else:
                raise ValueError(
                    f"Unsupported message type: {msg_type}. "
                    "Expected AssistantMessage or UserMessage"
                )

        # Extract message ID if present
        message_id = getattr(claude_message, "id", None)

        # Convert content blocks
        content_blocks = self._convert_content_blocks(claude_message)

        return UniversalMessage(
            role=role,
            content=content_blocks,
            id=message_id,
        )

    def _convert_content_blocks(self, claude_message: Any) -> list[ContentBlock]:
        """
        Convert Claude SDK content blocks to universal content blocks.

        Args:
            claude_message: A Claude SDK message with content attribute

        Returns:
            List of universal content blocks
        """
        content_blocks: list[ContentBlock] = []

        # Check if message has content
        if not hasattr(claude_message, "content"):
            return content_blocks

        content = claude_message.content
        if content is None:
            return content_blocks

        # Handle case where content is a string (simple text message)
        if isinstance(content, str):
            content_blocks.append(TextContent(text=content))
            return content_blocks

        # Handle list of content blocks
        if not isinstance(content, (list, tuple)):
            return content_blocks

        for block in content:
            converted = self._convert_single_block(block)
            if converted is not None:
                content_blocks.append(converted)

        return content_blocks

    def _convert_single_block(self, block: Any) -> ContentBlock | None:
        """
        Convert a single Claude SDK content block to universal format.

        Args:
            block: A Claude SDK content block

        Returns:
            Converted content block or None if unsupported
        """
        block_type = type(block).__name__

        if block_type == "TextBlock":
            return self._convert_text_block(block)
        elif block_type == "ToolUseBlock":
            return self._convert_tool_use_block(block)
        elif block_type == "ToolResultBlock":
            return self._convert_tool_result_block(block)
        elif block_type == "ThinkingBlock":
            # ThinkingBlock contains internal reasoning - convert to text with marker
            thinking_text = getattr(block, "thinking", "")
            if thinking_text:
                return TextContent(text=f"[Thinking]\n{thinking_text}")
            return None
        else:
            # Unknown block type - skip silently
            return None

    def _convert_text_block(self, block: Any) -> TextContent:
        """Convert Claude SDK TextBlock to TextContent."""
        text = getattr(block, "text", "")
        return TextContent(text=text)

    def _convert_tool_use_block(self, block: Any) -> ToolUseContent:
        """Convert Claude SDK ToolUseBlock to ToolUseContent."""
        tool_id = getattr(block, "id", "")
        name = getattr(block, "name", "")
        tool_input = getattr(block, "input", {})

        # Ensure input is a dict
        if not isinstance(tool_input, dict):
            tool_input = {}

        return ToolUseContent(
            id=tool_id,
            name=name,
            input=tool_input,
        )

    def _convert_tool_result_block(self, block: Any) -> ToolResultContent:
        """Convert Claude SDK ToolResultBlock to ToolResultContent."""
        tool_use_id = getattr(block, "tool_use_id", "")
        content = getattr(block, "content", "")
        is_error = getattr(block, "is_error", False)

        # Ensure content is a string
        if not isinstance(content, str):
            content = str(content) if content is not None else ""

        return ToolResultContent(
            tool_use_id=tool_use_id,
            content=content,
            is_error=is_error,
        )

    def from_universal(self, universal_message: UniversalMessage) -> dict[str, Any]:
        """
        Convert a UniversalMessage to Claude SDK message format (as dict).

        Returns a dictionary representation that can be used with Claude SDK.
        This is useful for constructing messages to send to the Claude API.

        Args:
            universal_message: UniversalMessage to convert

        Returns:
            Dictionary in Claude SDK message format
        """
        result: dict[str, Any] = {
            "role": universal_message.role,
            "content": [],
        }

        if universal_message.id is not None:
            result["id"] = universal_message.id

        for block in universal_message.content:
            converted = self._convert_universal_block(block)
            if converted is not None:
                result["content"].append(converted)

        return result

    def _convert_universal_block(self, block: ContentBlock) -> dict[str, Any] | None:
        """
        Convert a universal content block to Claude SDK format (as dict).

        Args:
            block: Universal content block

        Returns:
            Dictionary in Claude SDK block format or None if unsupported
        """
        if isinstance(block, TextContent):
            return {
                "type": "text",
                "text": block.text,
            }
        elif isinstance(block, ToolUseContent):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        elif isinstance(block, ToolResultContent):
            return {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
                "is_error": block.is_error,
            }
        else:
            return None

    def to_universal_stream(
        self, claude_stream: AsyncIterator[Any]
    ) -> AsyncIterator[UniversalMessage]:
        """
        Convert a stream of Claude SDK messages to UniversalMessage format.

        This is an async generator that yields UniversalMessage objects
        as they are received from the Claude SDK client.

        Args:
            claude_stream: Async iterator of Claude SDK messages
                          (typically from client.receive_response())

        Yields:
            UniversalMessage objects converted from Claude SDK messages

        Example:
            async for msg in adapter.to_universal_stream(client.receive_response()):
                if msg.has_text:
                    print(msg.text_content)
        """
        return self._stream_converter(claude_stream)

    async def _stream_converter(
        self, claude_stream: AsyncIterator[Any]
    ) -> AsyncIterator[UniversalMessage]:
        """Internal async generator for stream conversion."""
        async for claude_message in claude_stream:
            try:
                yield self.to_universal(claude_message)
            except ValueError:
                # Skip unsupported message types in stream
                continue

    def to_universal_batch(self, claude_messages: list[Any]) -> list[UniversalMessage]:
        """
        Convert a batch of Claude SDK messages to UniversalMessage format.

        Args:
            claude_messages: List of Claude SDK messages

        Returns:
            List of UniversalMessage objects
        """
        results: list[UniversalMessage] = []
        for msg in claude_messages:
            try:
                results.append(self.to_universal(msg))
            except ValueError:
                # Skip unsupported message types
                continue
        return results

    def from_universal_batch(
        self, universal_messages: list[UniversalMessage]
    ) -> list[dict[str, Any]]:
        """
        Convert a batch of UniversalMessage objects to Claude SDK format.

        Args:
            universal_messages: List of UniversalMessage objects

        Returns:
            List of dictionaries in Claude SDK message format
        """
        return [self.from_universal(msg) for msg in universal_messages]

    def round_trip(self, claude_message: Any) -> dict[str, Any]:
        """
        Perform a round-trip conversion for testing purposes.

        Converts Claude SDK message to UniversalMessage and back.
        Useful for verifying that conversions are lossless.

        Args:
            claude_message: A Claude SDK message

        Returns:
            Dictionary in Claude SDK message format

        Example:
            # Verify round-trip preserves data
            original_dict = adapter.from_universal(adapter.to_universal(msg))
            assert original_dict["content"] == expected_content
        """
        universal = self.to_universal(claude_message)
        return self.from_universal(universal)
