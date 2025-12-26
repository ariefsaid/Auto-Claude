"""
Auto Claude CLI Package
=======================

Command-line interface for the Auto Claude autonomous coding framework.

This package provides a modular CLI structure:
- main.py: Argument parsing and command routing
- spec_commands.py: Spec listing and management
- build_commands.py: Build execution and follow-up tasks
- workspace_commands.py: Workspace management (merge, review, discard)
- qa_commands.py: QA validation commands
- provider_info.py: Provider configuration and validation utilities
- utils.py: Shared utilities and configuration
"""

from .main import get_provider_config, main

__all__ = ["main", "get_provider_config"]
