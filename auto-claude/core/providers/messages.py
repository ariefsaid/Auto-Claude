"""
Universal Message Format
========================

Provider-agnostic message format for cross-provider communication.
Enables bidirectional conversion between provider-specific message formats
without data loss.

This module provides:
- UniversalMessage: Container for message content with role designation
- TextContent: Plain text content block
- ToolUseContent: Tool invocation content block
- ToolResultContent: Tool execution result content block

The universal message format preserves:
- Message IDs for conversation tracking
- Tool call IDs for request-response correlation
- Error states in tool results
- Multiple content blocks per message

Usage:
    from auto_claude.core.providers.messages import (
        UniversalMessage,
        TextContent,
        ToolUseContent,
        ToolResultContent,
    )

    # Create a text message
    msg = UniversalMessage(
        role="assistant",
        content=[TextContent(text="Hello, world!")],
    )

    # Create a tool use message
    tool_msg = UniversalMessage(
        role="assistant",
        content=[
            TextContent(text="Let me read that file for you."),
            ToolUseContent(
                id="tool_123",
                name="Read",
                input={"file_path": "/path/to/file"},
            ),
        ],
    )

    # Create a tool result message
    result_msg = UniversalMessage(
        role="user",
        content=[
            ToolResultContent(
                tool_use_id="tool_123",
                content="File contents here...",
                is_error=False,
            ),
        ],
    )
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Union

# Content block type literals for type checking
ContentType = Literal["text", "tool_use", "tool_result"]
MessageRole = Literal["user", "assistant"]


@dataclass
class TextContent:
    """
    Plain text content block.

    Represents textual content from either the user or the assistant.
    This is the most common content type for conversational messages.

    Attributes:
        text: The text content of the message
        type: Content type identifier (always "text")
    """

    text: str
    type: ContentType = field(default="text", init=False)

    def __post_init__(self):
        """Validate text content after initialization."""
        # Ensure text is a string (convert if necessary)
        if self.text is None:
            self.text = ""
        elif not isinstance(self.text, str):
            self.text = str(self.text)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert content block to dictionary format.

        Returns:
            Dictionary representation of the content block
        """
        return {
            "type": self.type,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TextContent":
        """
        Create TextContent from dictionary data.

        Args:
            data: Dictionary with content data

        Returns:
            TextContent instance
        """
        return cls(text=data.get("text", ""))


@dataclass
class ToolUseContent:
    """
    Tool invocation content block.

    Represents a request to execute a tool. The tool name and input
    are provider-specific and may need translation between providers.

    Attributes:
        id: Unique identifier for this tool use (for correlation with results)
        name: Name of the tool to invoke
        input: Tool input parameters as a dictionary
        type: Content type identifier (always "tool_use")
    """

    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    type: ContentType = field(default="tool_use", init=False)

    def __post_init__(self):
        """Validate tool use content after initialization."""
        # Ensure id is a string
        if not self.id:
            raise ValueError("ToolUseContent requires a non-empty id")

        # Ensure name is a string
        if not self.name:
            raise ValueError("ToolUseContent requires a non-empty name")

        # Ensure input is a dict
        if self.input is None:
            self.input = {}
        elif not isinstance(self.input, dict):
            raise ValueError("ToolUseContent input must be a dictionary")

    def to_dict(self) -> dict[str, Any]:
        """
        Convert content block to dictionary format.

        Returns:
            Dictionary representation of the content block
        """
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolUseContent":
        """
        Create ToolUseContent from dictionary data.

        Args:
            data: Dictionary with content data

        Returns:
            ToolUseContent instance

        Raises:
            ValueError: If required fields are missing
        """
        tool_id = data.get("id", "")
        name = data.get("name", "")

        if not tool_id:
            raise ValueError("ToolUseContent requires 'id' field")
        if not name:
            raise ValueError("ToolUseContent requires 'name' field")

        return cls(
            id=tool_id,
            name=name,
            input=data.get("input", {}),
        )


@dataclass
class ToolResultContent:
    """
    Tool execution result content block.

    Represents the result of a tool execution. Links back to the
    original tool use via tool_use_id for request-response correlation.

    Attributes:
        tool_use_id: ID of the ToolUseContent this is responding to
        content: Result content (string, can be JSON-serialized data)
        is_error: Whether the tool execution resulted in an error
        type: Content type identifier (always "tool_result")
    """

    tool_use_id: str
    content: str = ""
    is_error: bool = False
    type: ContentType = field(default="tool_result", init=False)

    def __post_init__(self):
        """Validate tool result content after initialization."""
        # Ensure tool_use_id is a string
        if not self.tool_use_id:
            raise ValueError("ToolResultContent requires a non-empty tool_use_id")

        # Ensure content is a string (convert if necessary)
        if self.content is None:
            self.content = ""
        elif not isinstance(self.content, str):
            self.content = str(self.content)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert content block to dictionary format.

        Returns:
            Dictionary representation of the content block
        """
        return {
            "type": self.type,
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolResultContent":
        """
        Create ToolResultContent from dictionary data.

        Args:
            data: Dictionary with content data

        Returns:
            ToolResultContent instance

        Raises:
            ValueError: If required fields are missing
        """
        tool_use_id = data.get("tool_use_id", "")
        if not tool_use_id:
            raise ValueError("ToolResultContent requires 'tool_use_id' field")

        return cls(
            tool_use_id=tool_use_id,
            content=data.get("content", ""),
            is_error=data.get("is_error", False),
        )


# Union type for all content block types
ContentBlock = Union[TextContent, ToolUseContent, ToolResultContent]


@dataclass
class UniversalMessage:
    """
    Universal message format for cross-provider communication.

    A provider-agnostic message container that can hold multiple content
    blocks. Supports bidirectional conversion to/from provider-specific
    message formats without data loss.

    Attributes:
        role: Message role ("user" or "assistant")
        content: List of content blocks (text, tool_use, tool_result)
        id: Optional message ID for conversation tracking
    """

    role: MessageRole
    content: list[ContentBlock] = field(default_factory=list)
    id: str | None = None

    def __post_init__(self):
        """Validate message after initialization."""
        # Validate role
        if self.role not in ("user", "assistant"):
            raise ValueError(
                f"Invalid message role: '{self.role}'. Must be 'user' or 'assistant'"
            )

        # Ensure content is a list
        if self.content is None:
            self.content = []
        elif not isinstance(self.content, list):
            # Wrap single content block in list
            self.content = [self.content]

        # Validate content blocks
        for i, block in enumerate(self.content):
            if not isinstance(block, (TextContent, ToolUseContent, ToolResultContent)):
                raise ValueError(
                    f"Invalid content block at index {i}: {type(block).__name__}. "
                    "Must be TextContent, ToolUseContent, or ToolResultContent"
                )

    @property
    def has_text(self) -> bool:
        """Check if message contains any text content."""
        return any(isinstance(block, TextContent) for block in self.content)

    @property
    def has_tool_use(self) -> bool:
        """Check if message contains any tool use content."""
        return any(isinstance(block, ToolUseContent) for block in self.content)

    @property
    def has_tool_result(self) -> bool:
        """Check if message contains any tool result content."""
        return any(isinstance(block, ToolResultContent) for block in self.content)

    @property
    def text_content(self) -> str:
        """
        Get concatenated text content from all text blocks.

        Returns:
            Combined text from all TextContent blocks, separated by newlines
        """
        texts = [block.text for block in self.content if isinstance(block, TextContent)]
        return "\n".join(texts)

    @property
    def tool_uses(self) -> list[ToolUseContent]:
        """
        Get all tool use content blocks.

        Returns:
            List of ToolUseContent blocks in this message
        """
        return [block for block in self.content if isinstance(block, ToolUseContent)]

    @property
    def tool_results(self) -> list[ToolResultContent]:
        """
        Get all tool result content blocks.

        Returns:
            List of ToolResultContent blocks in this message
        """
        return [block for block in self.content if isinstance(block, ToolResultContent)]

    def get_tool_use_by_id(self, tool_id: str) -> ToolUseContent | None:
        """
        Get a specific tool use content block by ID.

        Args:
            tool_id: Tool use ID to find

        Returns:
            ToolUseContent with matching ID, or None if not found
        """
        for block in self.content:
            if isinstance(block, ToolUseContent) and block.id == tool_id:
                return block
        return None

    def get_tool_result_by_id(self, tool_use_id: str) -> ToolResultContent | None:
        """
        Get a specific tool result content block by tool use ID.

        Args:
            tool_use_id: Tool use ID that the result responds to

        Returns:
            ToolResultContent with matching tool_use_id, or None if not found
        """
        for block in self.content:
            if (
                isinstance(block, ToolResultContent)
                and block.tool_use_id == tool_use_id
            ):
                return block
        return None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert message to dictionary format.

        Returns:
            Dictionary representation of the message
        """
        result = {
            "role": self.role,
            "content": [block.to_dict() for block in self.content],
        }
        if self.id is not None:
            result["id"] = self.id
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "UniversalMessage":
        """
        Create UniversalMessage from dictionary data.

        Args:
            data: Dictionary with message data

        Returns:
            UniversalMessage instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        role = data.get("role", "")
        if role not in ("user", "assistant"):
            raise ValueError(
                f"Invalid message role: '{role}'. Must be 'user' or 'assistant'"
            )

        content_list = data.get("content", [])
        content_blocks = []

        for block_data in content_list:
            if not isinstance(block_data, dict):
                continue

            block_type = block_data.get("type", "")
            if block_type == "text":
                content_blocks.append(TextContent.from_dict(block_data))
            elif block_type == "tool_use":
                content_blocks.append(ToolUseContent.from_dict(block_data))
            elif block_type == "tool_result":
                content_blocks.append(ToolResultContent.from_dict(block_data))
            # Unknown types are silently skipped

        return cls(
            role=role,
            content=content_blocks,
            id=data.get("id"),
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        content_summary = []
        for block in self.content:
            if isinstance(block, TextContent):
                text_preview = (
                    block.text[:30] + "..." if len(block.text) > 30 else block.text
                )
                content_summary.append(f"Text({text_preview!r})")
            elif isinstance(block, ToolUseContent):
                content_summary.append(f"ToolUse({block.name})")
            elif isinstance(block, ToolResultContent):
                error_str = ", error=True" if block.is_error else ""
                content_summary.append(f"ToolResult({block.tool_use_id}{error_str})")

        content_str = ", ".join(content_summary) if content_summary else "empty"
        id_str = f", id={self.id!r}" if self.id else ""
        return f"UniversalMessage(role={self.role!r}, content=[{content_str}]{id_str})"
