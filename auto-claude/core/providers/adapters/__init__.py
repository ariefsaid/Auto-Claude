"""
Provider Adapters Package
=========================

Adapters for converting between provider-specific formats and the universal message format.
This package contains message adapters and provider implementations.

This package provides:
- ClaudeMessageAdapter: Bidirectional Claude SDK <-> UniversalMessage conversion
- ClaudeProvider: Wraps ClaudeSDKClient, implements AgentClient Protocol
- OpenCodeProvider: Implements AgentClient via CLI subprocess
- OpenCode message parsing, tool translation, and subprocess management
- Pre-execution security validation for OpenCode

Usage:
    from auto_claude.core.providers.adapters import (
        ClaudeMessageAdapter,
        ClaudeProvider,
        OpenCodeProvider,
    )

    # Convert Claude SDK messages to universal format
    adapter = ClaudeMessageAdapter()
    universal_msg = adapter.to_universal(claude_message)
    claude_msg = adapter.from_universal(universal_msg)

    # Create Claude provider
    provider = ClaudeProvider(config)
    async with provider:
        response = await provider.query(universal_msg)

    # Create OpenCode provider
    provider = OpenCodeProvider(config)
    async with provider:
        response = await provider.query(universal_msg)
"""

# Claude adapters
from .claude_adapter import ClaudeMessageAdapter
from .claude_provider import ClaudeProvider

# OpenCode message parsing
from .opencode_messages import (
    OpenCodeMessageParser,
    OpenCodeParseError,
    parse_opencode_message,
    parse_opencode_output,
    parse_opencode_stream_line,
)

# OpenCode tool translation
from .opencode_tools import (
    ToolMapping,
    get_all_mappings,
    get_tool_category,
    is_supported_tool,
    translate_from_opencode,
    translate_to_opencode,
)

# The following imports will be added as they are implemented in subsequent subtasks:
# from .opencode_provider import OpenCodeProvider
# from .opencode_subprocess import OpenCodeSubprocess
# from .opencode_security import validate_opencode_command

__all__ = [
    # Claude adapters
    "ClaudeMessageAdapter",
    "ClaudeProvider",
    # OpenCode tool translation
    "translate_to_opencode",
    "translate_from_opencode",
    "is_supported_tool",
    "get_all_mappings",
    "get_tool_category",
    "ToolMapping",
    # OpenCode message parsing
    "OpenCodeMessageParser",
    "OpenCodeParseError",
    "parse_opencode_message",
    "parse_opencode_output",
    "parse_opencode_stream_line",
    # OpenCode adapters (to be implemented)
    # "OpenCodeProvider",
    # "OpenCodeSubprocess",
    # "validate_opencode_command",
]
