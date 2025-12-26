"""
Provider Infrastructure Package
===============================

Core provider infrastructure for multi-provider backend abstraction.
Supports dynamic credential system for ANY provider without code changes.

This package provides:
- Provider ID normalization for consistent identification
- Provider configuration and credential management
- Universal message format for cross-provider communication
- Provider client interface and factory

Usage:
    from auto_claude.core.providers import (
        normalize_provider_id,
        AgentProvider,
        ProviderCredential,
        ProviderConfig,
        UniversalMessage,
        TextContent,
        ToolUseContent,
        ToolResultContent,
    )

    # Normalize provider names to consistent IDs
    provider_id = normalize_provider_id("AWS Bedrock")  # Returns "aws-bedrock"

    # Get agent provider enum
    provider = AgentProvider.CLAUDE_CODE

    # Create provider credential
    credential = ProviderCredential(
        provider="openai",
        api_key="sk-...",
        default_model="gpt-4o",
    )

    # Load configuration from environment
    config = ProviderConfig.from_env()

    # Create universal messages
    msg = UniversalMessage(
        role="assistant",
        content=[TextContent(text="Hello, world!")],
    )
"""

from .client import (
    AgentClient,
    ConversationContext,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderTimeoutError,
)
from .config import AgentProvider, ProviderConfig, ProviderCredential
from .factory import create_client, get_available_providers, is_provider_available
from .messages import (
    ContentBlock,
    TextContent,
    ToolResultContent,
    ToolUseContent,
    UniversalMessage,
)
from .utils import normalize_provider_id

__all__ = [
    # Core classes
    "AgentProvider",
    "ProviderConfig",
    "ProviderCredential",
    # Client protocol and types
    "AgentClient",
    "ProviderCapabilities",
    "ConversationContext",
    # Exceptions
    "ProviderError",
    "ProviderNotFoundError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    # Message types
    "UniversalMessage",
    "TextContent",
    "ToolUseContent",
    "ToolResultContent",
    "ContentBlock",
    # Factory functions
    "create_client",
    "get_available_providers",
    "is_provider_available",
    # Utility functions
    "normalize_provider_id",
]
