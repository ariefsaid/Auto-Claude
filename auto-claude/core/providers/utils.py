"""
Provider Utilities
==================

Utility functions for provider ID normalization and common operations.
"""

import re


def normalize_provider_id(display_name: str) -> str:
    """
    Normalize a provider display name to a consistent provider ID.

    This function converts any provider display name to a consistent format:
    - Lowercase
    - Spaces converted to hyphens
    - Special characters (except hyphens) removed
    - Consecutive hyphens collapsed to single hyphen
    - Leading/trailing hyphens removed

    This is critical for matching TypeScript frontend normalization rules.

    Args:
        display_name: The provider display name (e.g., "OpenAI", "AWS Bedrock", "Z.ai GLM")

    Returns:
        Normalized provider ID (e.g., "openai", "aws-bedrock", "zai-glm")

    Examples:
        >>> normalize_provider_id("OpenAI")
        'openai'
        >>> normalize_provider_id("AWS Bedrock")
        'aws-bedrock'
        >>> normalize_provider_id("Z.ai GLM")
        'zai-glm'
        >>> normalize_provider_id("My--Provider")
        'my-provider'
        >>> normalize_provider_id("  Test Provider  ")
        'test-provider'
    """
    if not display_name:
        return ""

    # Strip leading/trailing whitespace
    normalized = display_name.strip()

    # Convert to lowercase
    normalized = normalized.lower()

    # Replace spaces with hyphens
    normalized = normalized.replace(" ", "-")

    # Remove all characters except alphanumeric and hyphens
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)

    # Collapse consecutive hyphens to single hyphen
    normalized = re.sub(r"-+", "-", normalized)

    # Remove leading and trailing hyphens
    normalized = normalized.strip("-")

    return normalized
