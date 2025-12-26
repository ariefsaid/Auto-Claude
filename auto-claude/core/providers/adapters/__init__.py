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

# Adapters will be imported here as they are implemented in subsequent subtasks.
# The following imports will be added:
#
# from .claude_adapter import ClaudeMessageAdapter
# from .claude_provider import ClaudeProvider
# from .opencode_provider import OpenCodeProvider
# from .opencode_messages import parse_opencode_response
# from .opencode_tools import translate_tool_name
# from .opencode_subprocess import OpenCodeSubprocess
# from .opencode_security import validate_opencode_command

__all__ = [
    # Claude adapters (to be implemented)
    # "ClaudeMessageAdapter",
    # "ClaudeProvider",
    # OpenCode adapters (to be implemented)
    # "OpenCodeProvider",
    # "parse_opencode_response",
    # "translate_tool_name",
    # "OpenCodeSubprocess",
    # "validate_opencode_command",
]
