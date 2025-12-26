"""
Security Hooks
==============

Pre-tool-use hooks that validate bash commands for security.
Main enforcement point for the security system.

This module provides:
- validate_command: Core validation function usable by any provider
- bash_security_hook: Claude SDK hook wrapper for bash validation
"""

import os
from pathlib import Path
from typing import Any

from project_analyzer import BASE_COMMANDS, SecurityProfile, is_command_allowed

from .parser import extract_commands, get_command_for_validation, split_command_segments
from .profile import get_security_profile
from .validator import VALIDATORS


def validate_command(
    command: str,
    project_dir: Path | None = None,
    profile: SecurityProfile | None = None,
) -> tuple[bool, str]:
    """
    Validate a bash command string against the security profile.

    This is the core validation function that can be used by any provider
    (Claude, OpenCode, etc.) to validate bash commands before execution.

    The function:
    1. Extracts command names from the command string
    2. Checks each command against the project's security profile
    3. Runs additional validation for sensitive commands (git, curl, etc.)

    Args:
        command: Full command string to validate (e.g., "ls -la && git status")
        project_dir: Optional project directory for loading security profile.
                     Uses current working directory if not provided.
        profile: Optional pre-loaded SecurityProfile. If provided, project_dir
                 is ignored. Useful when profile is already loaded or for testing.

    Returns:
        Tuple of (is_allowed, reason):
        - (True, "") if command is allowed
        - (False, "reason message") if command is blocked
    """
    # Get security profile if not provided
    if profile is None:
        if project_dir is None:
            project_dir = Path.cwd()
        profile = get_security_profile(project_dir)

    # Extract all commands from the command string
    commands = extract_commands(command)

    if not commands:
        return False, f"Could not parse command for security validation: {command}"

    # Split into segments for per-command validation
    segments = split_command_segments(command)

    # Check each command against the allowlist
    for cmd in commands:
        # Check if command is allowed
        is_allowed_result, reason = is_command_allowed(cmd, profile)
        if not is_allowed_result:
            return False, reason

        # Additional validation for sensitive commands
        if cmd in VALIDATORS:
            cmd_segment = get_command_for_validation(cmd, segments)
            if not cmd_segment:
                cmd_segment = command

            validator = VALIDATORS[cmd]
            allowed, reason = validator(cmd_segment)
            if not allowed:
                return False, reason

    return True, ""


async def bash_security_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None = None,
    context: Any | None = None,
) -> dict[str, Any]:
    """
    Pre-tool-use hook that validates bash commands using dynamic allowlist.

    This is the main security enforcement point for Claude SDK. It wraps
    validate_command() for use with the Claude SDK hook system.

    The hook:
    1. Extracts the command from tool input
    2. Determines the working directory from context
    3. Calls validate_command() for actual validation
    4. Returns block decision if validation fails

    Args:
        input_data: Dict containing tool_name and tool_input
        tool_use_id: Optional tool use ID (not used currently)
        context: Optional context with cwd attribute

    Returns:
        Empty dict to allow, or {"decision": "block", "reason": "..."} to block
    """
    # Only validate Bash tool
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    # Get the working directory from context or use current directory
    cwd = os.getcwd()
    if context and hasattr(context, "cwd"):
        cwd = context.cwd

    # Get or create security profile with fallback
    try:
        profile = get_security_profile(Path(cwd))
    except Exception:
        # If profile creation fails, fall back to base commands only
        profile = SecurityProfile()
        profile.base_commands = BASE_COMMANDS.copy()

    # Use the core validation function
    is_allowed, reason = validate_command(command, profile=profile)

    if not is_allowed:
        return {
            "decision": "block",
            "reason": reason,
        }

    return {}
