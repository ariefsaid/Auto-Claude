"""
OpenCode Message Parser
=======================

Parse OpenCode CLI JSON output to UniversalMessage format.
Enables conversion of OpenCode responses to the provider-agnostic
message format used throughout Auto-Claude.

OpenCode CLI outputs JSON messages in a specific format. This module
parses that output and converts it to UniversalMessage objects,
translating tool names in the process.

Expected OpenCode JSON Message Format:
{
    "type": "message",
    "role": "assistant" | "user",
    "id": "msg_xxx",  // optional
    "content": [
        {
            "type": "text",
            "text": "Hello, world!"
        },
        {
            "type": "tool_use",
            "id": "tool_xxx",
            "name": "file_read",  // OpenCode tool name
            "input": {"path": "/file.txt"}
        },
        {
            "type": "tool_result",
            "tool_use_id": "tool_xxx",
            "output": "File contents...",
            "error": false
        }
    ]
}

Usage:
    from auto_claude.core.providers.adapters.opencode_messages import (
        parse_opencode_message,
        parse_opencode_output,
        OpenCodeMessageParser,
    )

    # Parse a single message from JSON dict
    universal_msg = parse_opencode_message(json_dict)

    # Parse full CLI output (may contain multiple messages)
    messages = parse_opencode_output(cli_output_string)
"""

import json
from dataclasses import dataclass, field
from typing import Any

from ..messages import (
    ContentBlock,
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)
from .opencode_tools import translate_from_opencode


class OpenCodeParseError(Exception):
    """
    Exception raised when OpenCode message parsing fails.

    Attributes:
        message: Error description
        raw_data: The raw data that failed to parse (if available)
    """

    def __init__(self, message: str, raw_data: Any = None):
        super().__init__(message)
        self.raw_data = raw_data


@dataclass
class OpenCodeMessageParser:
    """
    Parser for OpenCode CLI JSON output.

    Converts OpenCode JSON messages to UniversalMessage format,
    translating tool names from OpenCode format to Auto-Claude format.

    The parser is stateless and can be reused across multiple conversions.

    Attributes:
        translate_tools: Whether to translate tool names (default: True)

    Example:
        parser = OpenCodeMessageParser()

        # Parse a single message
        universal = parser.parse_message(json_dict)

        # Parse full CLI output
        messages = parser.parse_output(cli_stdout)
    """

    translate_tools: bool = field(default=True)

    def parse_message(self, data: dict[str, Any]) -> UniversalMessage:
        """
        Parse a single OpenCode JSON message to UniversalMessage.

        Args:
            data: Dictionary containing OpenCode message data

        Returns:
            UniversalMessage with converted content blocks

        Raises:
            OpenCodeParseError: If the message format is invalid
        """
        # Validate message type
        # OpenCode uses types like: "text", "step_start", "step_finish", "tool_use", etc.
        # We accept all types and extract content from them
        msg_type = data.get("type", "message")

        # Skip non-content events (step markers, metadata)
        skip_types = ("step_start", "step-start", "step_finish", "step-finish")
        if msg_type in skip_types:
            # These are metadata events, not actual messages
            # Return empty message which will be filtered out
            return UniversalMessage(role="assistant", content=[])

        # Extract role
        role = self._extract_role(data)

        # Extract message ID if present
        message_id = data.get("id") or data.get("message_id")

        # Parse content blocks
        content_blocks = self._parse_content(data)

        return UniversalMessage(
            role=role,
            content=content_blocks,
            id=message_id,
        )

    def _extract_role(self, data: dict[str, Any]) -> str:
        """
        Extract message role from OpenCode message data.

        Args:
            data: Message data dictionary

        Returns:
            Role string ("user" or "assistant")

        Raises:
            OpenCodeParseError: If role cannot be determined
        """
        # Check explicit role field
        role = data.get("role", "")
        if role in ("user", "assistant"):
            return role

        # Check message type field
        msg_type = data.get("type", "")
        if msg_type == "assistant":
            return "assistant"
        if msg_type == "user":
            return "user"

        # Default to assistant for response-type messages
        if msg_type in ("message", "response"):
            return "assistant"

        # OpenCode content messages (text, tool_use, etc.) are from assistant
        if msg_type in ("text", "tool_use", "tool-use", "tool_result", "tool-result"):
            return "assistant"

        # If we have content but no role, assume assistant (AI response)
        if data.get("content") or data.get("text") or data.get("part", {}).get("text"):
            return "assistant"

        raise OpenCodeParseError(
            f"Cannot determine message role from data: {data!r}", raw_data=data
        )

    def _parse_content(self, data: dict[str, Any]) -> list[ContentBlock]:
        """
        Parse content blocks from OpenCode message data.

        Args:
            data: Message data dictionary

        Returns:
            List of content blocks
        """
        content_blocks: list[ContentBlock] = []

        # OpenCode wraps content in "part" field - extract it first
        if "part" in data and isinstance(data["part"], dict):
            part_data = data["part"]
            # Check for text in the part object
            if "text" in part_data and part_data["text"]:
                content_blocks.append(TextContent(text=part_data["text"]))
                return content_blocks
            # Otherwise continue parsing with part_data
            data = part_data

        # Get content from various possible locations
        content = data.get("content")

        # Handle case where content is a string (simple text message)
        if isinstance(content, str):
            if content:
                content_blocks.append(TextContent(text=content))
            return content_blocks

        # Handle case where content is a list of blocks
        if isinstance(content, list):
            for block_data in content:
                if isinstance(block_data, dict):
                    block = self._parse_content_block(block_data)
                    if block is not None:
                        content_blocks.append(block)
                elif isinstance(block_data, str):
                    # Handle string items in content list
                    if block_data:
                        content_blocks.append(TextContent(text=block_data))
            return content_blocks

        # Handle case where entire data is the content (simplified format)
        if "text" in data and data["text"]:
            content_blocks.append(TextContent(text=data["text"]))

        if "tool_use" in data or "tool_call" in data:
            tool_data = data.get("tool_use") or data.get("tool_call")
            if isinstance(tool_data, dict):
                block = self._parse_tool_use(tool_data)
                if block is not None:
                    content_blocks.append(block)

        if "tool_result" in data or "output" in data:
            result_data = data.get("tool_result")
            if isinstance(result_data, dict):
                block = self._parse_tool_result(result_data)
                if block is not None:
                    content_blocks.append(block)

        return content_blocks

    def _parse_content_block(self, block_data: dict[str, Any]) -> ContentBlock | None:
        """
        Parse a single content block from OpenCode format.

        Args:
            block_data: Dictionary containing block data

        Returns:
            ContentBlock or None if unsupported/invalid
        """
        block_type = block_data.get("type", "")

        if block_type == "text":
            return self._parse_text_block(block_data)
        elif block_type in ("tool_use", "tool_call", "function_call"):
            return self._parse_tool_use(block_data)
        elif block_type in ("tool_result", "function_result", "output"):
            return self._parse_tool_result(block_data)
        else:
            # Try to infer type from content
            if "text" in block_data and "name" not in block_data:
                return self._parse_text_block(block_data)
            if "name" in block_data and "input" in block_data:
                return self._parse_tool_use(block_data)
            if "tool_use_id" in block_data or "call_id" in block_data:
                return self._parse_tool_result(block_data)

        # Unknown block type
        return None

    def _parse_text_block(self, block_data: dict[str, Any]) -> TextContent | None:
        """
        Parse a text content block.

        Args:
            block_data: Dictionary containing text block data

        Returns:
            TextContent or None if empty
        """
        text = block_data.get("text", "")
        if not text and "content" in block_data:
            text = block_data.get("content", "")

        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        # Return None for empty text to avoid empty blocks
        if not text:
            return None

        return TextContent(text=text)

    def _parse_tool_use(self, block_data: dict[str, Any]) -> ToolUseContent | None:
        """
        Parse a tool use content block.

        Translates OpenCode tool names to Auto-Claude format.

        Args:
            block_data: Dictionary containing tool use data

        Returns:
            ToolUseContent or None if invalid
        """
        # Extract tool use ID from various possible field names
        tool_id = (
            block_data.get("id")
            or block_data.get("tool_id")
            or block_data.get("call_id")
            or ""
        )

        # Extract tool name from various possible field names
        name = (
            block_data.get("name")
            or block_data.get("tool_name")
            or block_data.get("function")
            or ""
        )

        # Extract input from various possible field names
        tool_input = (
            block_data.get("input")
            or block_data.get("arguments")
            or block_data.get("params")
            or block_data.get("parameters")
            or {}
        )

        # Validate required fields
        if not tool_id or not name:
            return None

        # Translate tool name if enabled
        if self.translate_tools:
            name = translate_from_opencode(name)

        # Ensure input is a dict
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                tool_input = {"raw": tool_input}

        if not isinstance(tool_input, dict):
            tool_input = {}

        return ToolUseContent(
            id=tool_id,
            name=name,
            input=tool_input,
        )

    def _parse_tool_result(
        self, block_data: dict[str, Any]
    ) -> ToolResultContent | None:
        """
        Parse a tool result content block.

        Args:
            block_data: Dictionary containing tool result data

        Returns:
            ToolResultContent or None if invalid
        """
        # Extract tool_use_id from various possible field names
        tool_use_id = (
            block_data.get("tool_use_id")
            or block_data.get("call_id")
            or block_data.get("id")
            or ""
        )

        # Validate required field
        if not tool_use_id:
            return None

        # Extract content from various possible field names
        content = (
            block_data.get("content")
            or block_data.get("output")
            or block_data.get("result")
            or ""
        )

        # Ensure content is a string
        if not isinstance(content, str):
            if isinstance(content, dict):
                content = json.dumps(content)
            elif content is not None:
                content = str(content)
            else:
                content = ""

        # Extract error status
        is_error = (
            block_data.get("is_error")
            or block_data.get("error")
            or block_data.get("is_failure")
            or False
        )

        # Ensure is_error is a boolean
        if not isinstance(is_error, bool):
            is_error = bool(is_error)

        return ToolResultContent(
            tool_use_id=tool_use_id,
            content=content,
            is_error=is_error,
        )

    def parse_output(self, output: str) -> list[UniversalMessage]:
        """
        Parse full OpenCode CLI output to list of UniversalMessage.

        Handles multiple message formats:
        - Single JSON object
        - JSON array of messages
        - Newline-delimited JSON (NDJSON)
        - JSON objects with "messages" or "data" wrapper

        Args:
            output: Raw CLI output string

        Returns:
            List of UniversalMessage objects

        Raises:
            OpenCodeParseError: If the output cannot be parsed
        """
        output = output.strip()
        if not output:
            return []

        messages: list[UniversalMessage] = []

        # Try parsing as JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try newline-delimited JSON
            return self._parse_ndjson(output)

        # Handle parsed JSON
        if isinstance(data, list):
            # Array of messages
            for item in data:
                if isinstance(item, dict):
                    try:
                        messages.append(self.parse_message(item))
                    except OpenCodeParseError:
                        continue
        elif isinstance(data, dict):
            # Check for wrapper objects
            if "messages" in data and isinstance(data["messages"], list):
                for item in data["messages"]:
                    if isinstance(item, dict):
                        try:
                            messages.append(self.parse_message(item))
                        except OpenCodeParseError:
                            continue
            elif "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    if isinstance(item, dict):
                        try:
                            messages.append(self.parse_message(item))
                        except OpenCodeParseError:
                            continue
            else:
                # Single message object
                try:
                    messages.append(self.parse_message(data))
                except OpenCodeParseError:
                    pass

        return messages

    def _parse_ndjson(self, output: str) -> list[UniversalMessage]:
        """
        Parse newline-delimited JSON output.

        Args:
            output: NDJSON formatted string

        Returns:
            List of UniversalMessage objects
        """
        messages: list[UniversalMessage] = []

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    messages.append(self.parse_message(data))
            except (json.JSONDecodeError, OpenCodeParseError):
                continue

        return messages

    def parse_streaming_line(self, line: str) -> UniversalMessage | None:
        """
        Parse a single line from streaming OpenCode output.

        Useful for real-time parsing of streaming CLI output.

        Args:
            line: Single line of output

        Returns:
            UniversalMessage or None if line is not a valid message
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return self.parse_message(data)
        except (json.JSONDecodeError, OpenCodeParseError):
            pass

        return None


# Module-level convenience functions


def parse_opencode_message(
    data: dict[str, Any], *, translate_tools: bool = True
) -> UniversalMessage:
    """
    Parse a single OpenCode JSON message to UniversalMessage.

    This is a convenience function that creates a parser and parses
    a single message.

    Args:
        data: Dictionary containing OpenCode message data
        translate_tools: Whether to translate tool names (default: True)

    Returns:
        UniversalMessage with converted content blocks

    Raises:
        OpenCodeParseError: If the message format is invalid

    Example:
        msg = parse_opencode_message({
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}]
        })
    """
    parser = OpenCodeMessageParser(translate_tools=translate_tools)
    return parser.parse_message(data)


def parse_opencode_output(
    output: str, *, translate_tools: bool = True
) -> list[UniversalMessage]:
    """
    Parse full OpenCode CLI output to list of UniversalMessage.

    This is a convenience function that creates a parser and parses
    full CLI output.

    Args:
        output: Raw CLI output string
        translate_tools: Whether to translate tool names (default: True)

    Returns:
        List of UniversalMessage objects

    Raises:
        OpenCodeParseError: If the output cannot be parsed

    Example:
        messages = parse_opencode_output(subprocess_stdout)
        for msg in messages:
            print(msg.text_content)
    """
    parser = OpenCodeMessageParser(translate_tools=translate_tools)
    return parser.parse_output(output)


def parse_opencode_stream_line(
    line: str, *, translate_tools: bool = True
) -> UniversalMessage | None:
    """
    Parse a single line from streaming OpenCode output.

    This is a convenience function for real-time parsing of streaming output.

    Args:
        line: Single line of output
        translate_tools: Whether to translate tool names (default: True)

    Returns:
        UniversalMessage or None if line is not a valid message

    Example:
        for line in process.stdout:
            msg = parse_opencode_stream_line(line)
            if msg:
                process_message(msg)
    """
    parser = OpenCodeMessageParser(translate_tools=translate_tools)
    return parser.parse_streaming_line(line)


# Re-export for convenience
__all__ = [
    "OpenCodeParseError",
    "OpenCodeMessageParser",
    "parse_opencode_message",
    "parse_opencode_output",
    "parse_opencode_stream_line",
]
