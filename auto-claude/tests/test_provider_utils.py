"""
Tests for Provider Utilities
=============================

Comprehensive tests for normalize_provider_id() and other utility functions
in the provider utils module.

Test Coverage:
- Standard provider names (single word, lowercase)
- Multi-word provider names with spaces
- Special characters removal
- Edge cases (consecutive hyphens, whitespace, empty strings)
- TypeScript frontend compatibility verification
"""

import sys
from pathlib import Path

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.utils import normalize_provider_id


class TestNormalizeProviderId:
    """Tests for the normalize_provider_id function."""

    # ==========================================================================
    # Standard Provider Names
    # ==========================================================================

    def test_lowercase_single_word(self):
        """Simple lowercase names should remain unchanged."""
        assert normalize_provider_id("openai") == "openai"
        assert normalize_provider_id("anthropic") == "anthropic"
        assert normalize_provider_id("google") == "google"

    def test_uppercase_conversion(self):
        """Uppercase names should be converted to lowercase."""
        assert normalize_provider_id("OpenAI") == "openai"
        assert normalize_provider_id("OPENAI") == "openai"
        assert normalize_provider_id("Anthropic") == "anthropic"
        assert normalize_provider_id("ANTHROPIC") == "anthropic"

    def test_mixed_case(self):
        """Mixed case names should be converted to lowercase."""
        assert normalize_provider_id("OpenRouter") == "openrouter"
        assert normalize_provider_id("DeepSeek") == "deepseek"
        assert normalize_provider_id("TogetherAI") == "togetherai"

    # ==========================================================================
    # Multi-Word Provider Names
    # ==========================================================================

    def test_space_to_hyphen(self):
        """Spaces should be converted to hyphens."""
        assert normalize_provider_id("AWS Bedrock") == "aws-bedrock"
        assert normalize_provider_id("Azure OpenAI") == "azure-openai"
        assert normalize_provider_id("Google AI") == "google-ai"

    def test_multiple_spaces(self):
        """Multiple consecutive spaces should be collapsed to single hyphen."""
        assert normalize_provider_id("AWS   Bedrock") == "aws-bedrock"
        assert normalize_provider_id("Azure  OpenAI") == "azure-openai"

    def test_three_word_names(self):
        """Names with three or more words should work correctly."""
        assert normalize_provider_id("Google Cloud AI") == "google-cloud-ai"
        assert normalize_provider_id("AWS Machine Learning") == "aws-machine-learning"

    # ==========================================================================
    # Special Characters
    # ==========================================================================

    def test_period_removal(self):
        """Periods should be removed."""
        assert normalize_provider_id("Z.ai") == "zai"
        assert normalize_provider_id("Z.ai GLM") == "zai-glm"
        assert normalize_provider_id("a.b.c") == "abc"

    def test_underscore_removal(self):
        """Underscores should be removed."""
        assert normalize_provider_id("test_provider") == "testprovider"
        assert normalize_provider_id("my_custom_ai") == "mycustomai"

    def test_other_special_chars(self):
        """Other special characters should be removed."""
        assert normalize_provider_id("test@provider") == "testprovider"
        assert normalize_provider_id("test#provider") == "testprovider"
        assert normalize_provider_id("test!provider") == "testprovider"
        assert normalize_provider_id("test$provider") == "testprovider"
        assert normalize_provider_id("test%provider") == "testprovider"
        assert normalize_provider_id("test&provider") == "testprovider"
        assert normalize_provider_id("test*provider") == "testprovider"
        assert normalize_provider_id("test+provider") == "testprovider"
        assert normalize_provider_id("test=provider") == "testprovider"

    def test_parentheses_brackets(self):
        """Parentheses and brackets should be removed."""
        assert normalize_provider_id("Provider (Beta)") == "provider-beta"
        assert normalize_provider_id("Provider [v2]") == "provider-v2"
        assert normalize_provider_id("Provider {test}") == "provider-test"

    def test_preserve_hyphens(self):
        """Existing hyphens should be preserved."""
        assert normalize_provider_id("claude-code") == "claude-code"
        assert normalize_provider_id("gpt-4-turbo") == "gpt-4-turbo"
        assert normalize_provider_id("AWS-Bedrock") == "aws-bedrock"

    def test_numbers_preserved(self):
        """Numbers should be preserved."""
        assert normalize_provider_id("GPT4") == "gpt4"
        assert normalize_provider_id("Claude 3.5") == "claude-35"
        assert normalize_provider_id("v2Provider") == "v2provider"

    # ==========================================================================
    # Edge Cases - Consecutive Hyphens
    # ==========================================================================

    def test_consecutive_hyphens(self):
        """Consecutive hyphens should be collapsed to single hyphen."""
        assert normalize_provider_id("My--Provider") == "my-provider"
        assert normalize_provider_id("Test---AI") == "test-ai"
        assert normalize_provider_id("a----b") == "a-b"

    def test_special_chars_creating_consecutive_hyphens(self):
        """Special chars that create consecutive hyphens should be handled."""
        # Period and space combo
        assert normalize_provider_id("Z. ai") == "z-ai"
        # Multiple special chars together
        assert normalize_provider_id("Test..AI") == "testai"
        # Mix of removals and spaces
        assert normalize_provider_id("Test. .AI") == "test-ai"

    # ==========================================================================
    # Edge Cases - Whitespace
    # ==========================================================================

    def test_leading_trailing_whitespace(self):
        """Leading and trailing whitespace should be trimmed."""
        assert normalize_provider_id("  OpenAI  ") == "openai"
        assert normalize_provider_id("  AWS Bedrock  ") == "aws-bedrock"
        assert normalize_provider_id("\t\nOpenAI\t\n") == "openai"

    def test_leading_trailing_hyphens(self):
        """Leading and trailing hyphens should be removed."""
        assert normalize_provider_id("-OpenAI-") == "openai"
        assert normalize_provider_id("--Provider--") == "provider"
        # Caused by special chars at ends
        assert normalize_provider_id(".OpenAI.") == "openai"

    # ==========================================================================
    # Edge Cases - Empty and Invalid
    # ==========================================================================

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert normalize_provider_id("") == ""

    def test_none_like_empty(self):
        """Whitespace-only strings should return empty string."""
        assert normalize_provider_id("   ") == ""
        assert normalize_provider_id("\t\n") == ""

    def test_only_special_chars(self):
        """String with only special chars should return empty string."""
        assert normalize_provider_id("...") == ""
        assert normalize_provider_id("@#$%") == ""
        assert normalize_provider_id("---") == ""

    def test_only_hyphens(self):
        """String with only hyphens should return empty string."""
        assert normalize_provider_id("-") == ""
        assert normalize_provider_id("---") == ""

    # ==========================================================================
    # Real-World Provider Names (Critical for TypeScript sync)
    # ==========================================================================

    def test_real_provider_openai(self):
        """OpenAI variations should normalize correctly."""
        assert normalize_provider_id("OpenAI") == "openai"
        assert normalize_provider_id("openai") == "openai"
        assert normalize_provider_id("OPENAI") == "openai"
        assert normalize_provider_id("Open AI") == "open-ai"  # With space = different

    def test_real_provider_anthropic(self):
        """Anthropic variations should normalize correctly."""
        assert normalize_provider_id("Anthropic") == "anthropic"
        assert normalize_provider_id("anthropic") == "anthropic"
        assert normalize_provider_id("ANTHROPIC") == "anthropic"

    def test_real_provider_aws_bedrock(self):
        """AWS Bedrock variations should normalize correctly."""
        assert normalize_provider_id("AWS Bedrock") == "aws-bedrock"
        assert normalize_provider_id("aws-bedrock") == "aws-bedrock"
        assert normalize_provider_id("AWSBedrock") == "awsbedrock"
        assert (
            normalize_provider_id("AWS_Bedrock") == "awsbedrock"
        )  # Underscore removed

    def test_real_provider_azure(self):
        """Azure OpenAI variations should normalize correctly."""
        assert normalize_provider_id("Azure OpenAI") == "azure-openai"
        assert normalize_provider_id("azure-openai") == "azure-openai"
        assert normalize_provider_id("Azure-OpenAI") == "azure-openai"

    def test_real_provider_google(self):
        """Google AI variations should normalize correctly."""
        assert normalize_provider_id("Google") == "google"
        assert normalize_provider_id("Google AI") == "google-ai"
        assert normalize_provider_id("Vertex AI") == "vertex-ai"
        assert normalize_provider_id("Google Cloud AI") == "google-cloud-ai"

    def test_real_provider_zai(self):
        """Z.ai variations should normalize correctly (with periods)."""
        assert normalize_provider_id("Z.ai") == "zai"
        assert normalize_provider_id("Z.ai GLM") == "zai-glm"
        assert normalize_provider_id("zai") == "zai"

    def test_real_provider_openrouter(self):
        """OpenRouter variations should normalize correctly."""
        assert normalize_provider_id("OpenRouter") == "openrouter"
        assert normalize_provider_id("openrouter") == "openrouter"
        assert normalize_provider_id("Open Router") == "open-router"  # With space

    def test_real_provider_groq(self):
        """Groq variations should normalize correctly."""
        assert normalize_provider_id("Groq") == "groq"
        assert normalize_provider_id("groq") == "groq"
        assert normalize_provider_id("GROQ") == "groq"

    def test_real_provider_ollama(self):
        """Ollama variations should normalize correctly."""
        assert normalize_provider_id("Ollama") == "ollama"
        assert normalize_provider_id("ollama") == "ollama"
        assert normalize_provider_id("OLLAMA") == "ollama"

    def test_real_provider_claude_code(self):
        """Claude Code variations should normalize correctly."""
        assert normalize_provider_id("claude-code") == "claude-code"
        assert normalize_provider_id("Claude Code") == "claude-code"
        assert (
            normalize_provider_id("ClaudeCode") == "claudecode"
        )  # No space = no hyphen

    # ==========================================================================
    # Idempotency
    # ==========================================================================

    def test_idempotency(self):
        """Normalizing an already-normalized ID should return the same result."""
        test_cases = [
            "openai",
            "aws-bedrock",
            "azure-openai",
            "claude-code",
            "zai-glm",
        ]
        for normalized in test_cases:
            assert normalize_provider_id(normalized) == normalized
            # Double normalization should also work
            assert (
                normalize_provider_id(normalize_provider_id(normalized)) == normalized
            )


class TestNormalizeProviderIdDocstrings:
    """Test cases from the function docstring."""

    def test_docstring_example_openai(self):
        """>>> normalize_provider_id("OpenAI") -> 'openai'"""
        assert normalize_provider_id("OpenAI") == "openai"

    def test_docstring_example_aws_bedrock(self):
        """>>> normalize_provider_id("AWS Bedrock") -> 'aws-bedrock'"""
        assert normalize_provider_id("AWS Bedrock") == "aws-bedrock"

    def test_docstring_example_zai_glm(self):
        """>>> normalize_provider_id("Z.ai GLM") -> 'zai-glm'"""
        assert normalize_provider_id("Z.ai GLM") == "zai-glm"

    def test_docstring_example_consecutive_hyphens(self):
        """>>> normalize_provider_id("My--Provider") -> 'my-provider'"""
        assert normalize_provider_id("My--Provider") == "my-provider"

    def test_docstring_example_whitespace(self):
        """>>> normalize_provider_id("  Test Provider  ") -> 'test-provider'"""
        assert normalize_provider_id("  Test Provider  ") == "test-provider"
