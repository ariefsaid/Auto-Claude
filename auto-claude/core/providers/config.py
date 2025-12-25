"""
Provider Configuration
======================

Configuration classes for the multi-provider backend abstraction layer.
Supports dynamic credential system for ANY provider without code changes.

This module provides:
- AgentProvider enum for supported agent backend providers
- ProviderCredential dataclass for dynamic credential storage
- Environment variable loading with proper fallbacks

Environment Variables:
    AGENT_PROVIDER: Active provider selection (claude_code|opencode) - default: claude_code
    AGENT_PROVIDER_IS_GLOBAL: Whether to use global provider setting (true|false)
    PROVIDER_CREDENTIALS: JSON object with provider credentials
        {
            "openai": {
                "isGlobal": false,
                "apiKey": "sk-...",
                "baseUrl": "https://api.openai.com",
                "defaultModel": "gpt-4o",
                "metadata": {}
            }
        }
    OPENCODE_PROVIDER: Provider for OpenCode to use (openai|anthropic|google|etc.)
    OPENCODE_MODEL: Model for OpenCode to use (e.g., gpt-4o-mini)

    Legacy (maintained for backward compatibility):
    CLAUDE_CODE_OAUTH_TOKEN: OAuth token for Claude Code API
    CLAUDE_TOKEN_IS_GLOBAL: Legacy global flag for Claude token
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentProvider(str, Enum):
    """
    Supported agent backend providers.

    These are the agent systems that can execute tasks, not the LLM providers
    that power them. Each agent provider may support multiple LLM providers.
    """

    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"

    @classmethod
    def from_string(cls, value: str) -> "AgentProvider":
        """
        Convert a string to AgentProvider enum.

        Args:
            value: String value to convert (case-insensitive)

        Returns:
            AgentProvider enum value

        Raises:
            ValueError: If value is not a valid provider
        """
        value_lower = value.lower().strip()
        for provider in cls:
            if provider.value == value_lower:
                return provider
        valid_values = [p.value for p in cls]
        raise ValueError(
            f"Invalid agent provider: '{value}'. Valid options: {valid_values}"
        )

    @classmethod
    def default(cls) -> "AgentProvider":
        """Get the default agent provider."""
        return cls.CLAUDE_CODE


@dataclass
class ProviderCredential:
    """
    Dynamic credential storage for any provider.

    Supports ANY provider without code changes via generic credential fields.
    Provider-specific configuration stored in metadata dict.

    Attributes:
        provider: Normalized provider ID (e.g., "openai", "anthropic", "aws-bedrock")
        api_key: API key or access token for the provider
        base_url: Custom API endpoint URL (optional, for custom deployments)
        default_model: Default model to use with this provider (optional)
        is_global: Whether this credential is from global settings
        metadata: Provider-specific additional configuration
    """

    provider: str
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    is_global: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Normalize provider ID after initialization."""
        from .utils import normalize_provider_id

        if self.provider:
            self.provider = normalize_provider_id(self.provider)

        # Ensure metadata is a dict
        if self.metadata is None:
            self.metadata = {}

        # Normalize base_url (remove trailing slash)
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")

    def is_valid(self) -> bool:
        """
        Check if credential has minimum required values.

        Returns:
            True if credential has a provider ID and either an API key
            or is marked as global (global credentials may use system auth)
        """
        if not self.provider:
            return False

        # Global credentials might use system-level auth
        if self.is_global:
            return True

        # Non-global credentials need an API key
        return bool(self.api_key)

    def get_validation_errors(self) -> list[str]:
        """
        Get list of validation errors for this credential.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.provider:
            errors.append("Provider ID is required")
            return errors

        if not self.is_global and not self.api_key:
            errors.append(f"API key required for provider '{self.provider}'")

        return errors

    def get_source_info(self) -> str:
        """
        Get information about where this credential came from.

        Returns:
            Human-readable source description
        """
        if self.is_global:
            return f"{self.provider} (global settings)"
        else:
            return f"{self.provider} (project settings)"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert credential to dictionary format.

        Returns:
            Dictionary representation of the credential
        """
        return {
            "provider": self.provider,
            "apiKey": self.api_key,
            "baseUrl": self.base_url,
            "defaultModel": self.default_model,
            "isGlobal": self.is_global,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, provider: str, data: dict) -> "ProviderCredential":
        """
        Create ProviderCredential from dictionary data.

        Args:
            provider: Provider ID
            data: Dictionary with credential data (camelCase keys from JSON)

        Returns:
            ProviderCredential instance
        """
        return cls(
            provider=provider,
            api_key=data.get("apiKey", ""),
            base_url=data.get("baseUrl", ""),
            default_model=data.get("defaultModel", ""),
            is_global=data.get("isGlobal", False),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_env_legacy_claude(cls) -> Optional["ProviderCredential"]:
        """
        Create ProviderCredential from legacy Claude Code environment variables.

        Supports backward compatibility with:
        - CLAUDE_CODE_OAUTH_TOKEN
        - CLAUDE_TOKEN_IS_GLOBAL

        Returns:
            ProviderCredential for Claude Code, or None if not configured
        """
        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        if not token:
            return None

        is_global_str = os.environ.get("CLAUDE_TOKEN_IS_GLOBAL", "").lower()
        is_global = is_global_str in ("true", "1", "yes")

        return cls(
            provider="claude-code",
            api_key=token,
            is_global=is_global,
        )


def parse_provider_credentials(json_str: str) -> dict[str, ProviderCredential]:
    """
    Parse PROVIDER_CREDENTIALS JSON string into credential objects.

    Args:
        json_str: JSON string containing provider credentials

    Returns:
        Dictionary mapping provider ID to ProviderCredential

    Raises:
        ValueError: If JSON is invalid or malformed

    Example JSON format:
        {
            "openai": {
                "isGlobal": false,
                "apiKey": "sk-...",
                "defaultModel": "gpt-4o"
            },
            "anthropic": {
                "isGlobal": true,
                "baseUrl": "https://api.anthropic.com"
            }
        }
    """
    if not json_str or json_str.strip() == "":
        return {}

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid PROVIDER_CREDENTIALS JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("PROVIDER_CREDENTIALS must be a JSON object")

    credentials = {}
    for provider_name, provider_data in data.items():
        if not isinstance(provider_data, dict):
            raise ValueError(
                f"Provider '{provider_name}' credentials must be an object"
            )
        credentials[provider_name] = ProviderCredential.from_dict(
            provider_name, provider_data
        )

    return credentials


def get_active_provider() -> AgentProvider:
    """
    Get the currently active agent provider from environment.

    Reads AGENT_PROVIDER environment variable, defaults to claude_code.

    Returns:
        AgentProvider enum value
    """
    provider_str = os.environ.get("AGENT_PROVIDER", "claude_code")
    try:
        return AgentProvider.from_string(provider_str)
    except ValueError:
        # Default to claude_code for invalid values
        return AgentProvider.default()


def is_global_provider() -> bool:
    """
    Check if the provider setting is from global settings.

    Returns:
        True if AGENT_PROVIDER_IS_GLOBAL is set to true
    """
    is_global_str = os.environ.get("AGENT_PROVIDER_IS_GLOBAL", "").lower()
    return is_global_str in ("true", "1", "yes")
