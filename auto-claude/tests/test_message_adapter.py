"""
Tests for Message Adapter
==========================

Comprehensive tests for ClaudeMessageAdapter and UniversalMessage dataclasses.

Test Coverage:
- TextContent, ToolUseContent, ToolResultContent dataclass creation and validation
- UniversalMessage creation with various content combinations
- ClaudeMessageAdapter.to_universal() conversion from Claude SDK types
- ClaudeMessageAdapter.from_universal() conversion to Claude SDK format
- Round-trip conversion (Claude -> Universal -> Claude) preserving all data
- Batch and stream conversions
- Edge cases: empty content, multiple blocks, error states, thinking blocks
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.adapters.claude_adapter import ClaudeMessageAdapter
from core.providers.messages import (
    ContentBlock,
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)

# =============================================================================
# Mock Claude SDK Types for Testing
# =============================================================================
# Note: Class names MUST match exactly what the adapter expects
# (TextBlock, ToolUseBlock, etc.) because the adapter uses type(block).__name__


@dataclass
class TextBlock:
    """Mock Claude SDK TextBlock."""

    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    """Mock Claude SDK ToolUseBlock."""

    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class ToolResultBlock:
    """Mock Claude SDK ToolResultBlock."""

    tool_use_id: str
    content: str = ""
    is_error: bool = False
    type: str = "tool_result"


@dataclass
class ThinkingBlock:
    """Mock Claude SDK ThinkingBlock."""

    thinking: str
    type: str = "thinking"


@dataclass
class AssistantMessage:
    """Mock Claude SDK AssistantMessage."""

    content: list[Any]
    id: str | None = None
    role: str = "assistant"


@dataclass
class UserMessage:
    """Mock Claude SDK UserMessage."""

    content: list[Any]
    id: str | None = None
    role: str = "user"


@dataclass
class UnknownMessage:
    """Mock unknown message type for testing unsupported types."""

    content: list[Any]
    id: str | None = None


@dataclass
class UnknownBlock:
    """Mock unknown block type for testing unsupported types."""

    data: str
    type: str = "unknown"


# =============================================================================
# TextContent Tests
# =============================================================================


class TestTextContent:
    """Tests for the TextContent dataclass."""

    def test_basic_creation(self):
        """Basic text content creation should work."""
        content = TextContent(text="Hello, world!")
        assert content.text == "Hello, world!"
        assert content.type == "text"

    def test_empty_text(self):
        """Empty text should be allowed."""
        content = TextContent(text="")
        assert content.text == ""

    def test_none_text_converted_to_empty(self):
        """None text should be converted to empty string."""
        content = TextContent(text=None)
        assert content.text == ""

    def test_non_string_converted_to_string(self):
        """Non-string text should be converted to string."""
        content = TextContent(text=123)
        assert content.text == "123"

        content = TextContent(text=3.14)
        assert content.text == "3.14"

    def test_multiline_text(self):
        """Multiline text should be preserved."""
        text = "Line 1\nLine 2\nLine 3"
        content = TextContent(text=text)
        assert content.text == text

    def test_unicode_text(self):
        """Unicode text should be handled correctly."""
        text = "Hello, \u4e16\u754c! \U0001f600"
        content = TextContent(text=text)
        assert content.text == text

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        content = TextContent(text="Hello")
        result = content.to_dict()
        assert result == {"type": "text", "text": "Hello"}

    def test_from_dict(self):
        """from_dict should create correct TextContent."""
        data = {"type": "text", "text": "Hello"}
        content = TextContent.from_dict(data)
        assert content.text == "Hello"
        assert content.type == "text"

    def test_from_dict_missing_text(self):
        """from_dict with missing text should use empty string."""
        content = TextContent.from_dict({})
        assert content.text == ""


# =============================================================================
# ToolUseContent Tests
# =============================================================================


class TestToolUseContent:
    """Tests for the ToolUseContent dataclass."""

    def test_basic_creation(self):
        """Basic tool use content creation should work."""
        content = ToolUseContent(
            id="tool_123", name="Read", input={"file_path": "/test.txt"}
        )
        assert content.id == "tool_123"
        assert content.name == "Read"
        assert content.input == {"file_path": "/test.txt"}
        assert content.type == "tool_use"

    def test_empty_input(self):
        """Tool use with empty input should work."""
        content = ToolUseContent(id="tool_123", name="GetTime", input={})
        assert content.input == {}

    def test_none_input_converted_to_dict(self):
        """None input should be converted to empty dict."""
        content = ToolUseContent(id="tool_123", name="Read", input=None)
        assert content.input == {}

    def test_complex_input(self):
        """Complex nested input should be preserved."""
        complex_input = {
            "file_path": "/test.txt",
            "options": {"encoding": "utf-8", "binary": False},
            "limits": [100, 200, 300],
        }
        content = ToolUseContent(id="tool_123", name="Read", input=complex_input)
        assert content.input == complex_input

    def test_empty_id_raises_error(self):
        """Empty ID should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolUseContent(id="", name="Read", input={})
        assert "id" in str(excinfo.value).lower()

    def test_empty_name_raises_error(self):
        """Empty name should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolUseContent(id="tool_123", name="", input={})
        assert "name" in str(excinfo.value).lower()

    def test_non_dict_input_raises_error(self):
        """Non-dict input should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolUseContent(id="tool_123", name="Read", input="not a dict")
        assert "dictionary" in str(excinfo.value).lower()

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        content = ToolUseContent(id="tool_123", name="Read", input={"path": "/test"})
        result = content.to_dict()
        assert result == {
            "type": "tool_use",
            "id": "tool_123",
            "name": "Read",
            "input": {"path": "/test"},
        }

    def test_from_dict(self):
        """from_dict should create correct ToolUseContent."""
        data = {"id": "tool_123", "name": "Read", "input": {"path": "/test"}}
        content = ToolUseContent.from_dict(data)
        assert content.id == "tool_123"
        assert content.name == "Read"
        assert content.input == {"path": "/test"}

    def test_from_dict_missing_id_raises_error(self):
        """from_dict with missing ID should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolUseContent.from_dict({"name": "Read"})
        assert "id" in str(excinfo.value).lower()

    def test_from_dict_missing_name_raises_error(self):
        """from_dict with missing name should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolUseContent.from_dict({"id": "tool_123"})
        assert "name" in str(excinfo.value).lower()


# =============================================================================
# ToolResultContent Tests
# =============================================================================


class TestToolResultContent:
    """Tests for the ToolResultContent dataclass."""

    def test_basic_creation(self):
        """Basic tool result content creation should work."""
        content = ToolResultContent(
            tool_use_id="tool_123", content="File contents here"
        )
        assert content.tool_use_id == "tool_123"
        assert content.content == "File contents here"
        assert content.is_error is False
        assert content.type == "tool_result"

    def test_error_result(self):
        """Tool result with error should work."""
        content = ToolResultContent(
            tool_use_id="tool_123", content="File not found", is_error=True
        )
        assert content.is_error is True

    def test_empty_content(self):
        """Empty content should be allowed."""
        content = ToolResultContent(tool_use_id="tool_123", content="")
        assert content.content == ""

    def test_none_content_converted_to_empty(self):
        """None content should be converted to empty string."""
        content = ToolResultContent(tool_use_id="tool_123", content=None)
        assert content.content == ""

    def test_non_string_content_converted(self):
        """Non-string content should be converted to string."""
        content = ToolResultContent(tool_use_id="tool_123", content=42)
        assert content.content == "42"

    def test_empty_tool_use_id_raises_error(self):
        """Empty tool_use_id should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolResultContent(tool_use_id="", content="result")
        assert "tool_use_id" in str(excinfo.value).lower()

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        content = ToolResultContent(
            tool_use_id="tool_123", content="result", is_error=False
        )
        result = content.to_dict()
        assert result == {
            "type": "tool_result",
            "tool_use_id": "tool_123",
            "content": "result",
            "is_error": False,
        }

    def test_to_dict_with_error(self):
        """to_dict with error should include is_error=True."""
        content = ToolResultContent(
            tool_use_id="tool_123", content="error msg", is_error=True
        )
        result = content.to_dict()
        assert result["is_error"] is True

    def test_from_dict(self):
        """from_dict should create correct ToolResultContent."""
        data = {"tool_use_id": "tool_123", "content": "result", "is_error": False}
        content = ToolResultContent.from_dict(data)
        assert content.tool_use_id == "tool_123"
        assert content.content == "result"
        assert content.is_error is False

    def test_from_dict_with_error(self):
        """from_dict with error should set is_error=True."""
        data = {"tool_use_id": "tool_123", "is_error": True}
        content = ToolResultContent.from_dict(data)
        assert content.is_error is True

    def test_from_dict_missing_tool_use_id_raises_error(self):
        """from_dict with missing tool_use_id should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            ToolResultContent.from_dict({"content": "result"})
        assert "tool_use_id" in str(excinfo.value).lower()


# =============================================================================
# UniversalMessage Tests
# =============================================================================


class TestUniversalMessage:
    """Tests for the UniversalMessage dataclass."""

    # -------------------------------------------------------------------------
    # Creation and Validation
    # -------------------------------------------------------------------------

    def test_basic_creation_assistant(self):
        """Basic assistant message creation should work."""
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])
        assert msg.role == "assistant"
        assert len(msg.content) == 1
        assert msg.id is None

    def test_basic_creation_user(self):
        """Basic user message creation should work."""
        msg = UniversalMessage(role="user", content=[TextContent(text="Hi")])
        assert msg.role == "user"

    def test_with_message_id(self):
        """Message with ID should preserve it."""
        msg = UniversalMessage(
            role="assistant", content=[TextContent(text="Hello")], id="msg_123"
        )
        assert msg.id == "msg_123"

    def test_empty_content(self):
        """Empty content list should be allowed."""
        msg = UniversalMessage(role="assistant", content=[])
        assert msg.content == []

    def test_none_content_converted_to_list(self):
        """None content should be converted to empty list."""
        msg = UniversalMessage(role="assistant", content=None)
        assert msg.content == []

    def test_single_content_wrapped_in_list(self):
        """Single content block should be wrapped in list."""
        content = TextContent(text="Hello")
        msg = UniversalMessage(role="assistant", content=content)
        assert len(msg.content) == 1
        assert msg.content[0].text == "Hello"

    def test_invalid_role_raises_error(self):
        """Invalid role should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            UniversalMessage(role="system", content=[])
        assert "role" in str(excinfo.value).lower()
        assert "system" in str(excinfo.value)

    def test_invalid_content_block_raises_error(self):
        """Invalid content block type should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            UniversalMessage(role="assistant", content=["invalid"])
        assert "content block" in str(excinfo.value).lower()

    # -------------------------------------------------------------------------
    # Multiple Content Blocks
    # -------------------------------------------------------------------------

    def test_multiple_text_blocks(self):
        """Message with multiple text blocks should work."""
        msg = UniversalMessage(
            role="assistant",
            content=[TextContent(text="First"), TextContent(text="Second")],
        )
        assert len(msg.content) == 2

    def test_mixed_content_blocks(self):
        """Message with mixed content blocks should work."""
        msg = UniversalMessage(
            role="assistant",
            content=[
                TextContent(text="Let me read that file"),
                ToolUseContent(
                    id="tool_123", name="Read", input={"file_path": "/test.txt"}
                ),
            ],
        )
        assert len(msg.content) == 2
        assert isinstance(msg.content[0], TextContent)
        assert isinstance(msg.content[1], ToolUseContent)

    def test_tool_result_message(self):
        """Message with tool result should work."""
        msg = UniversalMessage(
            role="user",
            content=[
                ToolResultContent(
                    tool_use_id="tool_123", content="File contents", is_error=False
                )
            ],
        )
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], ToolResultContent)

    # -------------------------------------------------------------------------
    # Helper Properties
    # -------------------------------------------------------------------------

    def test_has_text_true(self):
        """has_text should return True when text content exists."""
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])
        assert msg.has_text is True

    def test_has_text_false(self):
        """has_text should return False when no text content."""
        msg = UniversalMessage(
            role="assistant",
            content=[ToolUseContent(id="tool_123", name="Read", input={})],
        )
        assert msg.has_text is False

    def test_has_tool_use_true(self):
        """has_tool_use should return True when tool use exists."""
        msg = UniversalMessage(
            role="assistant",
            content=[ToolUseContent(id="tool_123", name="Read", input={})],
        )
        assert msg.has_tool_use is True

    def test_has_tool_use_false(self):
        """has_tool_use should return False when no tool use."""
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])
        assert msg.has_tool_use is False

    def test_has_tool_result_true(self):
        """has_tool_result should return True when tool result exists."""
        msg = UniversalMessage(
            role="user",
            content=[ToolResultContent(tool_use_id="tool_123", content="result")],
        )
        assert msg.has_tool_result is True

    def test_has_tool_result_false(self):
        """has_tool_result should return False when no tool result."""
        msg = UniversalMessage(role="user", content=[TextContent(text="Hello")])
        assert msg.has_tool_result is False

    def test_text_content_single(self):
        """text_content should return text from single block."""
        msg = UniversalMessage(
            role="assistant", content=[TextContent(text="Hello, world!")]
        )
        assert msg.text_content == "Hello, world!"

    def test_text_content_multiple(self):
        """text_content should concatenate multiple text blocks."""
        msg = UniversalMessage(
            role="assistant",
            content=[TextContent(text="Line 1"), TextContent(text="Line 2")],
        )
        assert msg.text_content == "Line 1\nLine 2"

    def test_text_content_empty(self):
        """text_content should return empty string when no text blocks."""
        msg = UniversalMessage(
            role="assistant",
            content=[ToolUseContent(id="tool_123", name="Read", input={})],
        )
        assert msg.text_content == ""

    def test_tool_uses_property(self):
        """tool_uses should return all tool use blocks."""
        msg = UniversalMessage(
            role="assistant",
            content=[
                TextContent(text="Doing two things"),
                ToolUseContent(id="tool_1", name="Read", input={}),
                ToolUseContent(id="tool_2", name="Write", input={}),
            ],
        )
        tool_uses = msg.tool_uses
        assert len(tool_uses) == 2
        assert tool_uses[0].id == "tool_1"
        assert tool_uses[1].id == "tool_2"

    def test_tool_results_property(self):
        """tool_results should return all tool result blocks."""
        msg = UniversalMessage(
            role="user",
            content=[
                ToolResultContent(tool_use_id="tool_1", content="result 1"),
                ToolResultContent(tool_use_id="tool_2", content="result 2"),
            ],
        )
        results = msg.tool_results
        assert len(results) == 2
        assert results[0].tool_use_id == "tool_1"
        assert results[1].tool_use_id == "tool_2"

    def test_get_tool_use_by_id(self):
        """get_tool_use_by_id should find correct tool use."""
        msg = UniversalMessage(
            role="assistant",
            content=[
                ToolUseContent(id="tool_1", name="Read", input={}),
                ToolUseContent(id="tool_2", name="Write", input={}),
            ],
        )
        tool = msg.get_tool_use_by_id("tool_2")
        assert tool is not None
        assert tool.name == "Write"

    def test_get_tool_use_by_id_not_found(self):
        """get_tool_use_by_id should return None when not found."""
        msg = UniversalMessage(
            role="assistant",
            content=[ToolUseContent(id="tool_1", name="Read", input={})],
        )
        assert msg.get_tool_use_by_id("nonexistent") is None

    def test_get_tool_result_by_id(self):
        """get_tool_result_by_id should find correct tool result."""
        msg = UniversalMessage(
            role="user",
            content=[
                ToolResultContent(tool_use_id="tool_1", content="result 1"),
                ToolResultContent(tool_use_id="tool_2", content="result 2"),
            ],
        )
        result = msg.get_tool_result_by_id("tool_2")
        assert result is not None
        assert result.content == "result 2"

    def test_get_tool_result_by_id_not_found(self):
        """get_tool_result_by_id should return None when not found."""
        msg = UniversalMessage(
            role="user",
            content=[ToolResultContent(tool_use_id="tool_1", content="result")],
        )
        assert msg.get_tool_result_by_id("nonexistent") is None

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        msg = UniversalMessage(
            role="assistant",
            content=[
                TextContent(text="Hello"),
                ToolUseContent(id="tool_123", name="Read", input={"path": "/test"}),
            ],
            id="msg_123",
        )
        result = msg.to_dict()
        assert result["role"] == "assistant"
        assert result["id"] == "msg_123"
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"

    def test_to_dict_no_id(self):
        """to_dict without ID should not include id key."""
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])
        result = msg.to_dict()
        assert "id" not in result

    def test_from_dict(self):
        """from_dict should create correct UniversalMessage."""
        data = {
            "role": "assistant",
            "id": "msg_123",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "id": "tool_123", "name": "Read", "input": {}},
            ],
        }
        msg = UniversalMessage.from_dict(data)
        assert msg.role == "assistant"
        assert msg.id == "msg_123"
        assert len(msg.content) == 2
        assert isinstance(msg.content[0], TextContent)
        assert isinstance(msg.content[1], ToolUseContent)

    def test_from_dict_invalid_role(self):
        """from_dict with invalid role should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            UniversalMessage.from_dict({"role": "invalid", "content": []})
        assert "role" in str(excinfo.value).lower()

    def test_from_dict_unknown_content_type_skipped(self):
        """from_dict should skip unknown content types."""
        data = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "unknown", "data": "ignored"},
            ],
        }
        msg = UniversalMessage.from_dict(data)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextContent)

    # -------------------------------------------------------------------------
    # Repr
    # -------------------------------------------------------------------------

    def test_repr_text(self):
        """Repr should show text preview."""
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])
        repr_str = repr(msg)
        assert "assistant" in repr_str
        assert "Text" in repr_str
        assert "Hello" in repr_str

    def test_repr_tool_use(self):
        """Repr should show tool name."""
        msg = UniversalMessage(
            role="assistant",
            content=[ToolUseContent(id="tool_123", name="Read", input={})],
        )
        repr_str = repr(msg)
        assert "ToolUse(Read)" in repr_str

    def test_repr_with_id(self):
        """Repr should include message ID."""
        msg = UniversalMessage(
            role="assistant", content=[TextContent(text="Hello")], id="msg_123"
        )
        repr_str = repr(msg)
        assert "msg_123" in repr_str


# =============================================================================
# ClaudeMessageAdapter Tests
# =============================================================================


class TestClaudeMessageAdapterCreation:
    """Tests for ClaudeMessageAdapter creation."""

    def test_adapter_creation(self):
        """Adapter should be created successfully."""
        adapter = ClaudeMessageAdapter()
        assert adapter is not None

    def test_adapter_is_stateless(self):
        """Adapter should be stateless and reusable."""
        adapter = ClaudeMessageAdapter()
        # Should be able to convert multiple messages with same adapter
        msg1 = AssistantMessage(content=[TextBlock(text="Hello")])
        msg2 = AssistantMessage(content=[TextBlock(text="World")])

        result1 = adapter.to_universal(msg1)
        result2 = adapter.to_universal(msg2)

        assert result1.text_content == "Hello"
        assert result2.text_content == "World"


class TestClaudeMessageAdapterToUniversal:
    """Tests for ClaudeMessageAdapter.to_universal() method."""

    # -------------------------------------------------------------------------
    # Message Type Conversion
    # -------------------------------------------------------------------------

    def test_assistant_message(self):
        """AssistantMessage should be converted to role='assistant'."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[TextBlock(text="Hello")])

        result = adapter.to_universal(claude_msg)

        assert result.role == "assistant"
        assert result.text_content == "Hello"

    def test_user_message(self):
        """UserMessage should be converted to role='user'."""
        adapter = ClaudeMessageAdapter()
        claude_msg = UserMessage(content=[TextBlock(text="Hi")])

        result = adapter.to_universal(claude_msg)

        assert result.role == "user"
        assert result.text_content == "Hi"

    def test_message_with_id(self):
        """Message ID should be preserved."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[TextBlock(text="Hello")], id="msg_123")

        result = adapter.to_universal(claude_msg)

        assert result.id == "msg_123"

    def test_message_without_id(self):
        """Message without ID should have None ID."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[TextBlock(text="Hello")])

        result = adapter.to_universal(claude_msg)

        assert result.id is None

    def test_unsupported_message_type_raises_error(self):
        """Unsupported message type should raise ValueError."""
        adapter = ClaudeMessageAdapter()
        unknown_msg = UnknownMessage(content=[])

        with pytest.raises(ValueError) as excinfo:
            adapter.to_universal(unknown_msg)
        assert "unsupported" in str(excinfo.value).lower()

    def test_message_with_role_attribute(self):
        """Message with role attribute should use that role."""
        adapter = ClaudeMessageAdapter()

        @dataclass
        class MessageWithRole:
            role: str
            content: list[Any]

        msg = MessageWithRole(role="assistant", content=[TextBlock(text="Hello")])
        result = adapter.to_universal(msg)
        assert result.role == "assistant"

    # -------------------------------------------------------------------------
    # Content Block Conversion
    # -------------------------------------------------------------------------

    def test_text_block_conversion(self):
        """TextBlock should be converted to TextContent."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[TextBlock(text="Hello, world!")])

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == "Hello, world!"

    def test_tool_use_block_conversion(self):
        """ToolUseBlock should be converted to ToolUseContent."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool_123", name="Read", input={"file_path": "/test.txt"}
                )
            ]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        tool_use = result.content[0]
        assert isinstance(tool_use, ToolUseContent)
        assert tool_use.id == "tool_123"
        assert tool_use.name == "Read"
        assert tool_use.input == {"file_path": "/test.txt"}

    def test_tool_result_block_conversion(self):
        """ToolResultBlock should be converted to ToolResultContent."""
        adapter = ClaudeMessageAdapter()
        claude_msg = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_123", content="File contents", is_error=False
                )
            ]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        tool_result = result.content[0]
        assert isinstance(tool_result, ToolResultContent)
        assert tool_result.tool_use_id == "tool_123"
        assert tool_result.content == "File contents"
        assert tool_result.is_error is False

    def test_tool_result_with_error(self):
        """ToolResultBlock with error should preserve is_error=True."""
        adapter = ClaudeMessageAdapter()
        claude_msg = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_123", content="Error message", is_error=True
                )
            ]
        )

        result = adapter.to_universal(claude_msg)

        tool_result = result.content[0]
        assert tool_result.is_error is True

    def test_thinking_block_conversion(self):
        """ThinkingBlock should be converted to TextContent with marker."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(
            content=[ThinkingBlock(thinking="Let me think about this...")]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert "[Thinking]" in result.content[0].text
        assert "Let me think about this" in result.content[0].text

    def test_empty_thinking_block_skipped(self):
        """Empty ThinkingBlock should be skipped."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[ThinkingBlock(thinking="")])

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 0

    def test_unknown_block_skipped(self):
        """Unknown block type should be skipped."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(
            content=[
                TextBlock(text="Hello"),
                UnknownBlock(data="ignored"),
            ]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        assert result.text_content == "Hello"

    # -------------------------------------------------------------------------
    # Multiple Content Blocks
    # -------------------------------------------------------------------------

    def test_multiple_text_blocks(self):
        """Multiple text blocks should be preserved."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(
            content=[TextBlock(text="First"), TextBlock(text="Second")]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 2
        assert result.content[0].text == "First"
        assert result.content[1].text == "Second"

    def test_mixed_content_blocks(self):
        """Mixed content blocks should be preserved in order."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(
            content=[
                TextBlock(text="Let me read the file"),
                ToolUseBlock(id="tool_1", name="Read", input={"path": "/test"}),
                TextBlock(text="And write to another"),
                ToolUseBlock(id="tool_2", name="Write", input={"path": "/out"}),
            ]
        )

        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 4
        assert isinstance(result.content[0], TextContent)
        assert isinstance(result.content[1], ToolUseContent)
        assert isinstance(result.content[2], TextContent)
        assert isinstance(result.content[3], ToolUseContent)

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_content(self):
        """Message with empty content should have empty content list."""
        adapter = ClaudeMessageAdapter()
        claude_msg = AssistantMessage(content=[])

        result = adapter.to_universal(claude_msg)

        assert result.content == []

    def test_none_content(self):
        """Message with None content should have empty content list."""
        adapter = ClaudeMessageAdapter()

        @dataclass
        class MessageWithNoneContent:
            content: None
            role: str = "assistant"

        claude_msg = MessageWithNoneContent(content=None)
        result = adapter.to_universal(claude_msg)
        assert result.content == []

    def test_string_content(self):
        """Message with string content should be converted to TextContent."""
        adapter = ClaudeMessageAdapter()

        @dataclass
        class MessageWithStringContent:
            content: str
            role: str = "assistant"

        claude_msg = MessageWithStringContent(content="Simple string message")
        result = adapter.to_universal(claude_msg)

        assert len(result.content) == 1
        assert result.content[0].text == "Simple string message"

    def test_message_without_content_attribute(self):
        """Message without content attribute should have empty content."""
        adapter = ClaudeMessageAdapter()

        @dataclass
        class MessageWithoutContent:
            role: str = "assistant"

        claude_msg = MessageWithoutContent()
        result = adapter.to_universal(claude_msg)
        assert result.content == []

    def test_tool_use_with_non_dict_input(self):
        """ToolUseBlock with non-dict input should use empty dict."""
        adapter = ClaudeMessageAdapter()

        # Create a mock ToolUseBlock with invalid input type
        # We need the class name to be exactly "ToolUseBlock" for the adapter to recognize it
        class ToolUseBlockBadInput:
            """Mock ToolUseBlock with non-dict input."""

            def __init__(self):
                self.id = "tool_1"
                self.name = "Read"
                self.input = "not a dict"  # Wrong type

        # Override class name to match what adapter expects
        ToolUseBlockBadInput.__name__ = "ToolUseBlock"

        claude_msg = AssistantMessage(content=[ToolUseBlockBadInput()])
        result = adapter.to_universal(claude_msg)

        assert result.content[0].input == {}

    def test_tool_result_with_non_string_content(self):
        """ToolResultBlock with non-string content should convert to string."""
        adapter = ClaudeMessageAdapter()

        # Create a mock ToolResultBlock with int content
        # We need the class name to be exactly "ToolResultBlock" for the adapter to recognize it
        class ToolResultBlockIntContent:
            """Mock ToolResultBlock with int content."""

            def __init__(self):
                self.tool_use_id = "tool_1"
                self.content = 42  # Wrong type - should be string
                self.is_error = False

        # Override class name to match what adapter expects
        ToolResultBlockIntContent.__name__ = "ToolResultBlock"

        claude_msg = UserMessage(content=[ToolResultBlockIntContent()])
        result = adapter.to_universal(claude_msg)

        assert result.content[0].content == "42"


class TestClaudeMessageAdapterFromUniversal:
    """Tests for ClaudeMessageAdapter.from_universal() method."""

    def test_text_content_conversion(self):
        """TextContent should be converted to text block dict."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(
            role="assistant", content=[TextContent(text="Hello, world!")]
        )

        result = adapter.from_universal(msg)

        assert result["role"] == "assistant"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello, world!"

    def test_tool_use_content_conversion(self):
        """ToolUseContent should be converted to tool_use block dict."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(
            role="assistant",
            content=[
                ToolUseContent(
                    id="tool_123", name="Read", input={"file_path": "/test.txt"}
                )
            ],
        )

        result = adapter.from_universal(msg)

        assert len(result["content"]) == 1
        block = result["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "tool_123"
        assert block["name"] == "Read"
        assert block["input"] == {"file_path": "/test.txt"}

    def test_tool_result_content_conversion(self):
        """ToolResultContent should be converted to tool_result block dict."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(
            role="user",
            content=[
                ToolResultContent(
                    tool_use_id="tool_123", content="File contents", is_error=False
                )
            ],
        )

        result = adapter.from_universal(msg)

        assert len(result["content"]) == 1
        block = result["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tool_123"
        assert block["content"] == "File contents"
        assert block["is_error"] is False

    def test_message_id_preserved(self):
        """Message ID should be preserved in output."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(
            role="assistant", content=[TextContent(text="Hello")], id="msg_123"
        )

        result = adapter.from_universal(msg)

        assert result["id"] == "msg_123"

    def test_message_without_id(self):
        """Message without ID should not include id key."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(role="assistant", content=[TextContent(text="Hello")])

        result = adapter.from_universal(msg)

        assert "id" not in result

    def test_multiple_content_blocks(self):
        """Multiple content blocks should be preserved."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(
            role="assistant",
            content=[
                TextContent(text="Doing stuff"),
                ToolUseContent(id="tool_1", name="Read", input={}),
                ToolUseContent(id="tool_2", name="Write", input={}),
            ],
        )

        result = adapter.from_universal(msg)

        assert len(result["content"]) == 3
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"
        assert result["content"][2]["type"] == "tool_use"

    def test_empty_content(self):
        """Empty content should produce empty content list."""
        adapter = ClaudeMessageAdapter()
        msg = UniversalMessage(role="assistant", content=[])

        result = adapter.from_universal(msg)

        assert result["content"] == []


# =============================================================================
# Round-Trip Conversion Tests
# =============================================================================


class TestRoundTripConversion:
    """Tests for round-trip conversion (Claude -> Universal -> Claude)."""

    def test_text_block_round_trip(self):
        """Text block should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()
        original = AssistantMessage(
            content=[TextBlock(text="Hello, world!")], id="msg_123"
        )

        result = adapter.round_trip(original)

        assert result["role"] == "assistant"
        assert result["id"] == "msg_123"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello, world!"

    def test_tool_use_block_round_trip(self):
        """Tool use block should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()
        original = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool_123",
                    name="Read",
                    input={"file_path": "/test.txt", "encoding": "utf-8"},
                )
            ]
        )

        result = adapter.round_trip(original)

        block = result["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "tool_123"
        assert block["name"] == "Read"
        assert block["input"] == {"file_path": "/test.txt", "encoding": "utf-8"}

    def test_tool_result_block_round_trip(self):
        """Tool result block should survive round-trip conversion."""
        adapter = ClaudeMessageAdapter()
        original = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_123", content="File contents here", is_error=False
                )
            ]
        )

        result = adapter.round_trip(original)

        block = result["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tool_123"
        assert block["content"] == "File contents here"
        assert block["is_error"] is False

    def test_tool_result_error_round_trip(self):
        """Tool result with error should preserve error state."""
        adapter = ClaudeMessageAdapter()
        original = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_123", content="Error message", is_error=True
                )
            ]
        )

        result = adapter.round_trip(original)

        block = result["content"][0]
        assert block["is_error"] is True

    def test_multiple_blocks_round_trip(self):
        """Multiple mixed blocks should survive round-trip."""
        adapter = ClaudeMessageAdapter()
        original = AssistantMessage(
            content=[
                TextBlock(text="Let me read that file"),
                ToolUseBlock(id="tool_1", name="Read", input={"path": "/a.txt"}),
                TextBlock(text="And also this one"),
                ToolUseBlock(id="tool_2", name="Read", input={"path": "/b.txt"}),
            ],
            id="msg_complex",
        )

        result = adapter.round_trip(original)

        assert result["id"] == "msg_complex"
        assert len(result["content"]) == 4
        assert result["content"][0]["text"] == "Let me read that file"
        assert result["content"][1]["id"] == "tool_1"
        assert result["content"][2]["text"] == "And also this one"
        assert result["content"][3]["id"] == "tool_2"

    def test_tool_correlation_preserved(self):
        """Tool use ID and tool result tool_use_id should match."""
        adapter = ClaudeMessageAdapter()

        # Create tool use message
        tool_use_msg = AssistantMessage(
            content=[ToolUseBlock(id="tool_abc123", name="Read", input={})]
        )

        # Create corresponding tool result message
        tool_result_msg = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_abc123", content="result", is_error=False
                )
            ]
        )

        # Convert and verify correlation
        tool_use_result = adapter.round_trip(tool_use_msg)
        tool_result_result = adapter.round_trip(tool_result_msg)

        tool_use_id = tool_use_result["content"][0]["id"]
        tool_result_id = tool_result_result["content"][0]["tool_use_id"]
        assert tool_use_id == tool_result_id == "tool_abc123"


# =============================================================================
# Batch Conversion Tests
# =============================================================================


class TestBatchConversion:
    """Tests for batch conversion methods."""

    def test_to_universal_batch(self):
        """to_universal_batch should convert multiple messages."""
        adapter = ClaudeMessageAdapter()
        messages = [
            AssistantMessage(content=[TextBlock(text="Hello")]),
            UserMessage(content=[TextBlock(text="Hi")]),
            AssistantMessage(content=[TextBlock(text="How can I help?")]),
        ]

        results = adapter.to_universal_batch(messages)

        assert len(results) == 3
        assert results[0].role == "assistant"
        assert results[0].text_content == "Hello"
        assert results[1].role == "user"
        assert results[2].text_content == "How can I help?"

    def test_to_universal_batch_skips_unsupported(self):
        """to_universal_batch should skip unsupported message types."""
        adapter = ClaudeMessageAdapter()
        messages = [
            AssistantMessage(content=[TextBlock(text="Hello")]),
            UnknownMessage(content=[]),  # Should be skipped
            UserMessage(content=[TextBlock(text="Hi")]),
        ]

        results = adapter.to_universal_batch(messages)

        assert len(results) == 2
        assert results[0].text_content == "Hello"
        assert results[1].text_content == "Hi"

    def test_to_universal_batch_empty(self):
        """to_universal_batch with empty list should return empty list."""
        adapter = ClaudeMessageAdapter()
        results = adapter.to_universal_batch([])
        assert results == []

    def test_from_universal_batch(self):
        """from_universal_batch should convert multiple messages."""
        adapter = ClaudeMessageAdapter()
        messages = [
            UniversalMessage(role="assistant", content=[TextContent(text="Hello")]),
            UniversalMessage(role="user", content=[TextContent(text="Hi")]),
        ]

        results = adapter.from_universal_batch(messages)

        assert len(results) == 2
        assert results[0]["role"] == "assistant"
        assert results[0]["content"][0]["text"] == "Hello"
        assert results[1]["role"] == "user"

    def test_from_universal_batch_empty(self):
        """from_universal_batch with empty list should return empty list."""
        adapter = ClaudeMessageAdapter()
        results = adapter.from_universal_batch([])
        assert results == []


# =============================================================================
# Stream Conversion Tests
# =============================================================================


class TestStreamConversion:
    """Tests for stream conversion methods."""

    @pytest.mark.asyncio
    async def test_to_universal_stream(self):
        """to_universal_stream should convert streaming messages."""
        adapter = ClaudeMessageAdapter()

        async def mock_stream():
            yield AssistantMessage(content=[TextBlock(text="Hello")])
            yield AssistantMessage(content=[TextBlock(text="World")])

        results = []
        async for msg in adapter.to_universal_stream(mock_stream()):
            results.append(msg)

        assert len(results) == 2
        assert results[0].text_content == "Hello"
        assert results[1].text_content == "World"

    @pytest.mark.asyncio
    async def test_to_universal_stream_skips_unsupported(self):
        """to_universal_stream should skip unsupported message types."""
        adapter = ClaudeMessageAdapter()

        async def mock_stream():
            yield AssistantMessage(content=[TextBlock(text="Hello")])
            yield UnknownMessage(content=[])  # Should be skipped
            yield AssistantMessage(content=[TextBlock(text="World")])

        results = []
        async for msg in adapter.to_universal_stream(mock_stream()):
            results.append(msg)

        assert len(results) == 2
        assert results[0].text_content == "Hello"
        assert results[1].text_content == "World"

    @pytest.mark.asyncio
    async def test_to_universal_stream_empty(self):
        """to_universal_stream with empty stream should yield nothing."""
        adapter = ClaudeMessageAdapter()

        async def mock_empty_stream():
            return
            yield  # Make it a generator

        results = []
        async for msg in adapter.to_universal_stream(mock_empty_stream()):
            results.append(msg)

        assert results == []

    @pytest.mark.asyncio
    async def test_to_universal_stream_tool_use(self):
        """to_universal_stream should handle tool use blocks."""
        adapter = ClaudeMessageAdapter()

        async def mock_stream():
            yield AssistantMessage(
                content=[
                    TextBlock(text="Let me help"),
                    ToolUseBlock(id="tool_1", name="Read", input={}),
                ]
            )

        results = []
        async for msg in adapter.to_universal_stream(mock_stream()):
            results.append(msg)

        assert len(results) == 1
        assert results[0].has_text
        assert results[0].has_tool_use
        assert results[0].tool_uses[0].id == "tool_1"


# =============================================================================
# Integration Tests
# =============================================================================


class TestMessageAdapterIntegration:
    """Integration tests for complete message adapter workflows."""

    def test_full_conversation_flow(self):
        """Complete conversation flow should work correctly."""
        adapter = ClaudeMessageAdapter()

        # User sends a message
        user_msg1 = UserMessage(content=[TextBlock(text="Read /test.txt")])
        user_universal1 = adapter.to_universal(user_msg1)
        assert user_universal1.role == "user"

        # Assistant responds with tool use
        assistant_msg1 = AssistantMessage(
            content=[
                TextBlock(text="I'll read that file for you"),
                ToolUseBlock(id="tool_1", name="Read", input={"path": "/test.txt"}),
            ],
            id="msg_1",
        )
        assistant_universal1 = adapter.to_universal(assistant_msg1)
        assert assistant_universal1.has_text
        assert assistant_universal1.has_tool_use

        # User sends tool result
        user_msg2 = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_1", content="File contents here", is_error=False
                )
            ]
        )
        user_universal2 = adapter.to_universal(user_msg2)
        assert user_universal2.has_tool_result
        assert user_universal2.get_tool_result_by_id("tool_1") is not None

        # Assistant responds with final answer
        assistant_msg2 = AssistantMessage(
            content=[TextBlock(text="The file contains: File contents here")],
            id="msg_2",
        )
        assistant_universal2 = adapter.to_universal(assistant_msg2)

        # Convert all back to Claude format
        all_messages = [
            user_universal1,
            assistant_universal1,
            user_universal2,
            assistant_universal2,
        ]
        claude_format = adapter.from_universal_batch(all_messages)

        assert len(claude_format) == 4
        assert claude_format[0]["role"] == "user"
        assert claude_format[1]["role"] == "assistant"
        assert claude_format[1]["id"] == "msg_1"
        assert claude_format[2]["role"] == "user"
        assert claude_format[3]["role"] == "assistant"

    def test_error_handling_workflow(self):
        """Error handling workflow should preserve error state."""
        adapter = ClaudeMessageAdapter()

        # Assistant requests tool use
        assistant_msg = AssistantMessage(
            content=[
                TextBlock(text="Let me try to read that"),
                ToolUseBlock(
                    id="tool_1", name="Read", input={"path": "/nonexistent.txt"}
                ),
            ]
        )
        assistant_universal = adapter.to_universal(assistant_msg)

        # Tool returns error
        error_msg = UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_1",
                    content="FileNotFoundError: /nonexistent.txt not found",
                    is_error=True,
                )
            ]
        )
        error_universal = adapter.to_universal(error_msg)

        # Verify error state preserved through round-trip
        error_dict = adapter.from_universal(error_universal)
        assert error_dict["content"][0]["is_error"] is True
        assert "FileNotFoundError" in error_dict["content"][0]["content"]

    def test_complex_tool_input_preserved(self):
        """Complex nested tool input should be preserved."""
        adapter = ClaudeMessageAdapter()

        complex_input = {
            "file_path": "/path/to/file.py",
            "options": {
                "encoding": "utf-8",
                "mode": "r",
                "settings": {"buffer_size": 4096, "flags": ["read", "binary"]},
            },
            "metadata": {
                "tags": ["python", "source"],
                "priority": 1,
                "timestamp": "2024-01-01T00:00:00Z",
            },
        }

        assistant_msg = AssistantMessage(
            content=[ToolUseBlock(id="tool_1", name="ReadComplex", input=complex_input)]
        )

        universal = adapter.to_universal(assistant_msg)
        result = adapter.from_universal(universal)

        assert result["content"][0]["input"] == complex_input
