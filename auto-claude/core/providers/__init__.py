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
    from auto_claude.core.providers import normalize_provider_id

    # Normalize provider names to consistent IDs
    provider_id = normalize_provider_id("AWS Bedrock")  # Returns "aws-bedrock"
"""

from .utils import normalize_provider_id

__all__ = [
    "normalize_provider_id",
]
