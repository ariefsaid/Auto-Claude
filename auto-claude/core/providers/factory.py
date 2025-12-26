"""
Provider Factory Functions
===========================

Factory functions for creating provider clients based on configuration.
Enables provider-agnostic client instantiation for the multi-provider backend.

This module provides:
- create_client(): Factory function to create the appropriate provider client
- Provider selection based on ProviderConfig settings
- Error handling for unknown or unsupported providers

Usage:
    from auto_claude.core.providers.factory import create_client
    from auto_claude.core.providers.config import ProviderConfig

    # Load configuration from environment
    config = ProviderConfig.from_env()

    # Create the appropriate provider client
    provider = create_client(
        config=config,
        project_dir=Path("/path/to/project"),
        spec_dir=Path("/path/to/spec"),
        model="claude-sonnet-4-20250514",
    )

    # Use the provider
    async with provider:
        response = await provider.query(message)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .client import AgentClient, ProviderError, ProviderNotFoundError
from .config import AgentProvider, ProviderConfig

if TYPE_CHECKING:
    from .adapters.claude_provider import ClaudeProvider

logger = logging.getLogger(__name__)


def create_client(
    config: ProviderConfig,
    project_dir: Path,
    spec_dir: Path,
    model: str,
    agent_type: str = "coder",
    max_thinking_tokens: int | None = None,
) -> AgentClient:
    """
    Create a provider client based on the configured provider.

    Factory function that instantiates the appropriate provider implementation
    based on the ProviderConfig settings. Supports Claude Code and OpenCode
    providers with extensibility for future providers.

    Args:
        config: ProviderConfig with provider settings and credentials
        project_dir: Root directory for the project (working directory)
        spec_dir: Directory containing the spec (for settings file)
        model: Model to use (provider-specific format)
        agent_type: Type of agent - 'planner', 'coder', 'qa_reviewer', or 'qa_fixer'
        max_thinking_tokens: Token budget for extended thinking (None = disabled)

    Returns:
        AgentClient implementation for the configured provider

    Raises:
        ProviderNotFoundError: If the requested provider is not available
        ProviderError: If client creation fails

    Example:
        config = ProviderConfig.from_env()

        # Create Claude Code provider
        provider = create_client(
            config=config,
            project_dir=Path("/project"),
            spec_dir=Path("/project/.auto-claude/specs/001"),
            model="claude-sonnet-4-20250514",
        )

        async with provider:
            response = await provider.query(message)
    """
    provider = config.provider

    logger.info(f"Creating client for provider: {provider.value}")

    # Validate configuration before creating client
    if not config.is_valid():
        errors = config.get_validation_errors()
        error_msg = "; ".join(errors)
        raise ProviderError(
            provider=provider.value,
            message=f"Invalid provider configuration: {error_msg}",
            details={"validation_errors": errors},
        )

    if provider == AgentProvider.CLAUDE_CODE:
        return _create_claude_provider(
            config=config,
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            agent_type=agent_type,
            max_thinking_tokens=max_thinking_tokens,
        )
    elif provider == AgentProvider.OPENCODE:
        return _create_opencode_provider(
            config=config,
            project_dir=project_dir,
            model=model,
        )
    else:
        available = [p.value for p in AgentProvider]
        raise ProviderNotFoundError(provider.value, available)


def _create_claude_provider(
    config: ProviderConfig,
    project_dir: Path,
    spec_dir: Path,
    model: str,
    agent_type: str = "coder",
    max_thinking_tokens: int | None = None,
) -> "ClaudeProvider":
    """
    Create a ClaudeProvider instance.

    Args:
        config: ProviderConfig with Claude Code settings
        project_dir: Root directory for the project
        spec_dir: Directory containing the spec
        model: Claude model to use
        agent_type: Type of agent
        max_thinking_tokens: Token budget for extended thinking

    Returns:
        ClaudeProvider instance ready for use

    Raises:
        ProviderError: If client creation fails
    """
    from .adapters.claude_provider import ClaudeProvider

    logger.info(f"Creating Claude Code provider with model: {model}")

    try:
        return ClaudeProvider.from_config(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            agent_type=agent_type,
            max_thinking_tokens=max_thinking_tokens,
        )
    except Exception as e:
        raise ProviderError(
            provider="claude_code",
            message=f"Failed to create Claude Code provider: {e!s}",
            details={"original_error": str(e)},
        ) from e


def _create_opencode_provider(
    config: ProviderConfig,
    project_dir: Path,
    model: str,
) -> Any:
    """
    Create an OpenCodeProvider instance.

    Note: OpenCodeProvider is implemented in a subsequent subtask.
    This function provides the factory integration point.

    Args:
        config: ProviderConfig with OpenCode settings
        project_dir: Root directory for the project
        model: Model to use with OpenCode

    Returns:
        OpenCodeProvider instance ready for use

    Raises:
        ProviderError: If OpenCode provider is not yet implemented or creation fails
    """
    logger.info(
        f"Creating OpenCode provider with provider: {config.opencode_provider}, "
        f"model: {config.opencode_model or model}"
    )

    try:
        # Import OpenCodeProvider when it's implemented
        from .adapters.opencode_provider import OpenCodeProvider

        # Get credential for the LLM provider
        credential = config.get_credential(config.opencode_provider)
        api_key = credential.api_key if credential else ""

        return OpenCodeProvider(
            project_dir=project_dir,
            provider=config.opencode_provider,
            model=config.opencode_model or model,
            api_key=api_key,
        )
    except ImportError:
        raise ProviderError(
            provider="opencode",
            message=(
                "OpenCode provider is not yet implemented. "
                "This will be available in a future update."
            ),
            details={"status": "not_implemented"},
        )
    except Exception as e:
        raise ProviderError(
            provider="opencode",
            message=f"Failed to create OpenCode provider: {e!s}",
            details={"original_error": str(e)},
        ) from e


def get_available_providers() -> list[str]:
    """
    Get list of available provider names.

    Returns:
        List of provider value strings
    """
    return [provider.value for provider in AgentProvider]


def is_provider_available(provider_name: str) -> bool:
    """
    Check if a provider is available.

    Args:
        provider_name: Provider name to check

    Returns:
        True if provider is available
    """
    try:
        AgentProvider.from_string(provider_name)
        return True
    except ValueError:
        return False
