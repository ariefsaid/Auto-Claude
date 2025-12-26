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
"""

from .config import AgentProvider, ProviderConfig, ProviderCredential
from .utils import normalize_provider_id

__all__ = [
    # Core classes
    "AgentProvider",
    "ProviderConfig",
    "ProviderCredential",
    # Utility functions
    "normalize_provider_id",
]
