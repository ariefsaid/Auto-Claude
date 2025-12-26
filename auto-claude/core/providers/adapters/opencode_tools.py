"""
OpenCode Tool Translation
=========================

Bidirectional tool name translation between Auto-Claude and OpenCode formats.
OpenCode uses different tool names than Auto-Claude/Claude Code, requiring
translation when sending commands and receiving results.

Tool Mapping:
    Auto-Claude    OpenCode
    -----------    --------
    Read        -> file_read
    Write       -> file_write
    Edit        -> file_edit
    Bash        -> bash_exec
    Grep        -> code_search
    Glob        -> file_search
    WebFetch    -> web_fetch
    WebSearch   -> web_search
    Task        -> task_agent
    NotebookEdit -> notebook_edit

Usage:
    from auto_claude.core.providers.adapters.opencode_tools import (
        translate_to_opencode,
        translate_from_opencode,
        is_supported_tool,
        get_all_mappings,
    )

    # Translate Auto-Claude tool name to OpenCode
    opencode_name = translate_to_opencode('Read')  # Returns 'file_read'

    # Translate OpenCode tool name back to Auto-Claude
    autoclaude_name = translate_from_opencode('file_read')  # Returns 'Read'

    # Check if a tool is supported
    if is_supported_tool('Read'):
        ...
"""

from dataclasses import dataclass
from typing import Literal

# Type aliases for clarity
AutoClaudeToolName = str
OpenCodeToolName = str

# Auto-Claude to OpenCode tool name mapping
# Based on OpenCode CLI tool naming conventions
AUTOCLAUDE_TO_OPENCODE: dict[AutoClaudeToolName, OpenCodeToolName] = {
    # File operations
    "Read": "file_read",
    "Write": "file_write",
    "Edit": "file_edit",
    "Glob": "file_search",
    # Code operations
    "Grep": "code_search",
    # Shell operations
    "Bash": "bash_exec",
    # Web operations
    "WebFetch": "web_fetch",
    "WebSearch": "web_search",
    # Agent operations
    "Task": "task_agent",
    # Notebook operations
    "NotebookEdit": "notebook_edit",
    # Todo operations
    "TodoWrite": "todo_write",
    # Question operations
    "AskUserQuestion": "ask_user",
}

# Reverse mapping: OpenCode to Auto-Claude
OPENCODE_TO_AUTOCLAUDE: dict[OpenCodeToolName, AutoClaudeToolName] = {
    v: k for k, v in AUTOCLAUDE_TO_OPENCODE.items()
}

# Set of all supported Auto-Claude tool names
SUPPORTED_AUTOCLAUDE_TOOLS: frozenset[str] = frozenset(AUTOCLAUDE_TO_OPENCODE.keys())

# Set of all supported OpenCode tool names
SUPPORTED_OPENCODE_TOOLS: frozenset[str] = frozenset(OPENCODE_TO_AUTOCLAUDE.keys())


@dataclass(frozen=True)
class ToolMapping:
    """
    Represents a tool name mapping between Auto-Claude and OpenCode.

    Attributes:
        autoclaude_name: The Auto-Claude/Claude Code tool name
        opencode_name: The corresponding OpenCode tool name
        category: Tool category for grouping (file, code, shell, web, agent)
    """

    autoclaude_name: str
    opencode_name: str
    category: Literal[
        "file", "code", "shell", "web", "agent", "notebook", "todo", "user"
    ]


# Categorized tool mappings for documentation and validation
TOOL_MAPPINGS: tuple[ToolMapping, ...] = (
    # File operations
    ToolMapping("Read", "file_read", "file"),
    ToolMapping("Write", "file_write", "file"),
    ToolMapping("Edit", "file_edit", "file"),
    ToolMapping("Glob", "file_search", "file"),
    # Code operations
    ToolMapping("Grep", "code_search", "code"),
    # Shell operations
    ToolMapping("Bash", "bash_exec", "shell"),
    # Web operations
    ToolMapping("WebFetch", "web_fetch", "web"),
    ToolMapping("WebSearch", "web_search", "web"),
    # Agent operations
    ToolMapping("Task", "task_agent", "agent"),
    # Notebook operations
    ToolMapping("NotebookEdit", "notebook_edit", "notebook"),
    # Todo operations
    ToolMapping("TodoWrite", "todo_write", "todo"),
    # User interaction operations
    ToolMapping("AskUserQuestion", "ask_user", "user"),
)


def translate_to_opencode(autoclaude_name: str) -> str:
    """
    Translate an Auto-Claude tool name to OpenCode format.

    If the tool name is not in the mapping, returns the original name unchanged.
    This allows pass-through of any tools that might be OpenCode-specific
    or have identical names in both systems.

    Args:
        autoclaude_name: The Auto-Claude/Claude Code tool name (e.g., 'Read')

    Returns:
        The OpenCode tool name (e.g., 'file_read')

    Example:
        >>> translate_to_opencode('Read')
        'file_read'
        >>> translate_to_opencode('Bash')
        'bash_exec'
        >>> translate_to_opencode('unknown_tool')
        'unknown_tool'
    """
    return AUTOCLAUDE_TO_OPENCODE.get(autoclaude_name, autoclaude_name)


def translate_from_opencode(opencode_name: str) -> str:
    """
    Translate an OpenCode tool name to Auto-Claude format.

    If the tool name is not in the mapping, returns the original name unchanged.
    This allows pass-through of any tools that might be Auto-Claude-specific
    or have identical names in both systems.

    Args:
        opencode_name: The OpenCode tool name (e.g., 'file_read')

    Returns:
        The Auto-Claude tool name (e.g., 'Read')

    Example:
        >>> translate_from_opencode('file_read')
        'Read'
        >>> translate_from_opencode('bash_exec')
        'Bash'
        >>> translate_from_opencode('unknown_tool')
        'unknown_tool'
    """
    return OPENCODE_TO_AUTOCLAUDE.get(opencode_name, opencode_name)


def is_supported_tool(tool_name: str) -> bool:
    """
    Check if a tool name is supported for translation.

    Returns True if the tool name is a known Auto-Claude or OpenCode tool name.

    Args:
        tool_name: Tool name to check (can be either format)

    Returns:
        True if the tool is supported, False otherwise

    Example:
        >>> is_supported_tool('Read')
        True
        >>> is_supported_tool('file_read')
        True
        >>> is_supported_tool('unknown_tool')
        False
    """
    return (
        tool_name in SUPPORTED_AUTOCLAUDE_TOOLS or tool_name in SUPPORTED_OPENCODE_TOOLS
    )


def is_autoclaude_tool(tool_name: str) -> bool:
    """
    Check if a tool name is in Auto-Claude format.

    Args:
        tool_name: Tool name to check

    Returns:
        True if it's an Auto-Claude tool name

    Example:
        >>> is_autoclaude_tool('Read')
        True
        >>> is_autoclaude_tool('file_read')
        False
    """
    return tool_name in SUPPORTED_AUTOCLAUDE_TOOLS


def is_opencode_tool(tool_name: str) -> bool:
    """
    Check if a tool name is in OpenCode format.

    Args:
        tool_name: Tool name to check

    Returns:
        True if it's an OpenCode tool name

    Example:
        >>> is_opencode_tool('file_read')
        True
        >>> is_opencode_tool('Read')
        False
    """
    return tool_name in SUPPORTED_OPENCODE_TOOLS


def get_tool_category(tool_name: str) -> str | None:
    """
    Get the category of a tool by its name.

    Works with both Auto-Claude and OpenCode tool names.

    Args:
        tool_name: Tool name in either format

    Returns:
        Category string or None if not found

    Example:
        >>> get_tool_category('Read')
        'file'
        >>> get_tool_category('file_read')
        'file'
        >>> get_tool_category('Bash')
        'shell'
    """
    for mapping in TOOL_MAPPINGS:
        if tool_name == mapping.autoclaude_name or tool_name == mapping.opencode_name:
            return mapping.category
    return None


def get_all_mappings() -> tuple[ToolMapping, ...]:
    """
    Get all tool mappings as ToolMapping objects.

    Returns:
        Tuple of all ToolMapping objects

    Example:
        >>> mappings = get_all_mappings()
        >>> for m in mappings:
        ...     print(f"{m.autoclaude_name} -> {m.opencode_name} ({m.category})")
    """
    return TOOL_MAPPINGS


def get_autoclaude_tools() -> frozenset[str]:
    """
    Get all supported Auto-Claude tool names.

    Returns:
        Frozen set of Auto-Claude tool names
    """
    return SUPPORTED_AUTOCLAUDE_TOOLS


def get_opencode_tools() -> frozenset[str]:
    """
    Get all supported OpenCode tool names.

    Returns:
        Frozen set of OpenCode tool names
    """
    return SUPPORTED_OPENCODE_TOOLS


def translate_tool_input(
    tool_name: str, tool_input: dict, *, to_opencode: bool = True
) -> dict:
    """
    Translate tool input parameters between formats.

    Some tools may have different parameter names or structures between
    Auto-Claude and OpenCode. This function handles those translations.

    Currently, most parameter names are identical, so this is largely
    a pass-through. Future versions may handle more complex translations.

    Args:
        tool_name: The tool name (in either format)
        tool_input: The tool input parameters
        to_opencode: If True, translate to OpenCode format; otherwise to Auto-Claude

    Returns:
        Translated tool input dictionary

    Example:
        >>> translate_tool_input('Read', {'file_path': '/path'}, to_opencode=True)
        {'file_path': '/path'}
    """
    # For now, most parameter names are identical between systems
    # Future translations can be added here
    return dict(tool_input)


def translate_tool_result(
    tool_name: str, tool_result: str | dict, *, from_opencode: bool = True
) -> str | dict:
    """
    Translate tool result between formats.

    Some tools may return results in different formats between providers.
    This function normalizes results to a consistent format.

    Args:
        tool_name: The tool name (in source format)
        tool_result: The tool result from the source provider
        from_opencode: If True, result is from OpenCode; otherwise from Auto-Claude

    Returns:
        Translated tool result

    Example:
        >>> translate_tool_result('file_read', 'content', from_opencode=True)
        'content'
    """
    # For now, results are passed through unchanged
    # Future translations can be added here
    return tool_result
