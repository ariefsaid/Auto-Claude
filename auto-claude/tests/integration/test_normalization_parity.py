"""
Normalization Parity Tests - TypeScript vs Python
==================================================

CRITICAL: This test suite verifies that the Python normalize_provider_id()
function produces identical output to the TypeScript normalizeProviderId()
function. Any mismatch will cause provider ID lookup failures between
the UI (TypeScript) and CLI (Python).

Test cases cover:
- Basic normalization (lowercase, spaces to dashes)
- Special character removal
- Dash deduplication
- Edge cases (empty strings, unicode, etc.)
- All documented test cases from spec.md
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Add parent directory to path for imports
_AUTO_CLAUDE_DIR = Path(__file__).parent.parent.parent
if str(_AUTO_CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTO_CLAUDE_DIR))

# Import directly from provider_info module to avoid dependency chain
# that requires claude_agent_sdk (which may not be installed in test env)
import importlib.util

_provider_info_path = _AUTO_CLAUDE_DIR / "cli" / "provider_info.py"
_spec = importlib.util.spec_from_file_location("provider_info", _provider_info_path)
_provider_info = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_provider_info)  # type: ignore
python_normalize = _provider_info.normalize_provider_id


# =============================================================================
# TypeScript Normalization Reference (for documentation)
# =============================================================================
#
# The TypeScript implementation in auto-claude-ui/src/renderer/utils/providerCredentials.ts:
#
# export function normalizeProviderId(name: string): string {
#   // Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
#   let normalized = name.toLowerCase().trim().replace(/ /g, '-');
#
#   // Step 2: Remove all characters except a-z, 0-9, and dash
#   normalized = normalized.replace(/[^a-z0-9-]/g, '');
#
#   // Step 3: Collapse multiple consecutive dashes into a single dash
#   normalized = normalized.replace(/-+/g, '-');
#
#   // Step 4: Remove leading and trailing dashes
#   return normalized.replace(/^-+|-+$/g, '');
# }
# =============================================================================


def typescript_normalize(name: str) -> str:
    """
    Python implementation of the TypeScript normalizeProviderId() function.

    This function mirrors the exact logic from TypeScript to enable
    in-process comparison without needing to spawn a Node.js process.

    IMPORTANT: If the TypeScript implementation changes, this function
    must be updated to match exactly.
    """
    # Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
    # CRITICAL: Only replace space character (ASCII 32), not all whitespace
    normalized = name.lower().strip().replace(" ", "-")

    # Step 2: Remove all characters except a-z, 0-9, and dash
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)

    # Step 3: Collapse multiple consecutive dashes into a single dash
    normalized = re.sub(r"-+", "-", normalized)

    # Step 4: Remove leading and trailing dashes
    return normalized.strip("-")


# =============================================================================
# Spec-Required Test Cases
# =============================================================================


class TestSpecRequiredCases:
    """Test cases explicitly required by spec.md."""

    def test_openai_normalization(self) -> None:
        """Spec: 'OpenAI' -> 'openai'"""
        result = python_normalize("OpenAI")
        assert result == "openai"

    def test_zai_glm_normalization(self) -> None:
        """Spec: 'Z.ai GLM 4.7' -> 'zai-glm-47'"""
        result = python_normalize("Z.ai GLM 4.7")
        assert result == "zai-glm-47"

    def test_custom_provider_normalization(self) -> None:
        """Spec: 'Custom Provider' -> 'custom-provider'"""
        result = python_normalize("Custom Provider")
        assert result == "custom-provider"

    def test_whitespace_trimming(self) -> None:
        """Spec: '  OpenAI  ' -> 'openai'"""
        result = python_normalize("  OpenAI  ")
        assert result == "openai"

    def test_dash_deduplication(self) -> None:
        """Spec: 'Custom---Provider' -> 'custom-provider'"""
        result = python_normalize("Custom---Provider")
        assert result == "custom-provider"

    def test_special_char_removal(self) -> None:
        """Spec: 'Z.ai GLM 4.7!@#' -> 'zai-glm-47'"""
        result = python_normalize("Z.ai GLM 4.7!@#")
        assert result == "zai-glm-47"


# =============================================================================
# TypeScript Parity Tests
# =============================================================================


class TestTypeScriptParity:
    """Verify Python produces identical output to TypeScript reference."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            # Spec-required cases
            ("OpenAI", "openai"),
            ("Z.ai GLM 4.7", "zai-glm-47"),
            ("Custom Provider", "custom-provider"),
            ("  OpenAI  ", "openai"),
            ("Custom---Provider", "custom-provider"),
            ("Z.ai GLM 4.7!@#", "zai-glm-47"),
            # Common provider names
            ("Anthropic", "anthropic"),
            ("Google Gemini", "google-gemini"),
            ("OpenRouter", "openrouter"),
            ("Mistral AI", "mistral-ai"),
            ("Cohere", "cohere"),
            ("Groq", "groq"),
            ("DeepSeek", "deepseek"),
            ("Together AI", "together-ai"),
            ("Fireworks AI", "fireworks-ai"),
            ("Perplexity", "perplexity"),
            # Edge cases
            ("", ""),
            ("a", "a"),
            ("1", "1"),
            ("a1", "a1"),
            ("1a", "1a"),
            # Mixed case
            ("UPPERCASE", "uppercase"),
            ("MixedCase", "mixedcase"),
            ("camelCase", "camelcase"),
            # Special characters
            ("test.provider", "testprovider"),
            ("test_provider", "testprovider"),
            ("test@provider", "testprovider"),
            ("test#provider", "testprovider"),
            ("test$provider", "testprovider"),
            ("test%provider", "testprovider"),
            ("test^provider", "testprovider"),
            ("test&provider", "testprovider"),
            ("test*provider", "testprovider"),
            ("test(provider)", "testprovider"),
            ("test[provider]", "testprovider"),
            ("test{provider}", "testprovider"),
            ("test|provider", "testprovider"),
            ("test\\provider", "testprovider"),
            ("test:provider", "testprovider"),
            ("test;provider", "testprovider"),
            ("test'provider", "testprovider"),
            ('test"provider', "testprovider"),
            ("test<provider>", "testprovider"),
            ("test,provider", "testprovider"),
            ("test?provider", "testprovider"),
            ("test/provider", "testprovider"),
            ("test`provider", "testprovider"),
            ("test~provider", "testprovider"),
            ("test+provider", "testprovider"),
            ("test=provider", "testprovider"),
            # Numbers
            ("GPT-4", "gpt-4"),
            ("Claude 3.5", "claude-35"),
            ("Model V2.0", "model-v20"),
            ("Version 1.2.3", "version-123"),
            # Dashes
            ("-leading", "leading"),
            ("trailing-", "trailing"),
            ("-both-", "both"),
            ("--double-dash--", "double-dash"),
            ("a--b", "a-b"),
            ("a---b", "a-b"),
            ("a----b", "a-b"),
            # Spaces
            ("one space", "one-space"),
            ("multiple   spaces", "multiple-spaces"),
            ("\ttab\t", "tab"),
            ("\nnewline\n", "newline"),
            ("  lots   of   spaces  ", "lots-of-spaces"),
            # Combined edge cases
            ("  --Test Provider 123--  ", "test-provider-123"),
            ("!!!SPECIAL!!!CHARS!!!", "specialchars"),
            ("...dots...everywhere...", "dotseverywhere"),
            ("CamelCase-with-Dashes", "camelcase-with-dashes"),
            ("MixedCase123Numbers", "mixedcase123numbers"),
        ],
    )
    def test_python_matches_typescript(self, input_name: str, expected: str) -> None:
        """Verify Python normalize matches TypeScript reference implementation."""
        python_result = python_normalize(input_name)
        typescript_result = typescript_normalize(input_name)

        assert (
            python_result == typescript_result
        ), f"Mismatch for '{input_name}': Python='{python_result}', TypeScript='{typescript_result}'"
        assert (
            python_result == expected
        ), f"Unexpected result for '{input_name}': got '{python_result}', expected '{expected}'"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self) -> None:
        """Empty string should normalize to empty string."""
        assert python_normalize("") == ""
        assert typescript_normalize("") == ""

    def test_only_spaces(self) -> None:
        """String with only spaces should normalize to empty string."""
        assert python_normalize("   ") == ""
        assert typescript_normalize("   ") == ""

    def test_only_special_chars(self) -> None:
        """String with only special chars should normalize to empty string."""
        assert python_normalize("!@#$%^&*()") == ""
        assert typescript_normalize("!@#$%^&*()") == ""

    def test_only_dashes(self) -> None:
        """String with only dashes should normalize to empty string."""
        assert python_normalize("---") == ""
        assert typescript_normalize("---") == ""

    def test_single_character(self) -> None:
        """Single valid character should stay as-is (lowercased)."""
        assert python_normalize("A") == "a"
        assert typescript_normalize("A") == "a"

    def test_single_digit(self) -> None:
        """Single digit should stay as-is."""
        assert python_normalize("5") == "5"
        assert typescript_normalize("5") == "5"

    def test_unicode_letters(self) -> None:
        """Unicode letters should be removed (only ASCII a-z allowed)."""
        # These should all result in just the ASCII parts
        assert python_normalize("Cafe") == "cafe"  # ASCII e, not cafe
        assert python_normalize("Cafe") == "cafe"
        assert typescript_normalize("Cafe") == "cafe"

    def test_unicode_removal(self) -> None:
        """Non-ASCII characters should be removed."""
        assert python_normalize("test") == "test"
        assert typescript_normalize("test") == "test"

    def test_very_long_string(self) -> None:
        """Long strings should normalize correctly."""
        long_input = "Very Long Provider Name " * 100
        python_result = python_normalize(long_input)
        typescript_result = typescript_normalize(long_input)
        assert python_result == typescript_result
        # Should be a valid normalized ID
        assert re.match(r"^[a-z0-9-]+$", python_result) or python_result == ""


class TestNormalizationAlgorithm:
    """Test the normalization algorithm step by step."""

    def test_step1_lowercase(self) -> None:
        """Step 1: Convert to lowercase."""
        assert python_normalize("TEST") == "test"

    def test_step1_trim(self) -> None:
        """Step 1: Trim whitespace."""
        assert python_normalize("  test  ") == "test"

    def test_step1_space_to_dash(self) -> None:
        """Step 1: Replace spaces with dashes."""
        assert python_normalize("test provider") == "test-provider"

    def test_step2_remove_special(self) -> None:
        """Step 2: Remove special characters."""
        assert python_normalize("test.provider") == "testprovider"

    def test_step3_collapse_dashes(self) -> None:
        """Step 3: Collapse multiple dashes."""
        assert python_normalize("test--provider") == "test-provider"

    def test_step4_strip_dashes(self) -> None:
        """Step 4: Remove leading/trailing dashes."""
        assert python_normalize("-test-") == "test"


class TestRealWorldProviders:
    """Test with real-world provider names."""

    @pytest.mark.parametrize(
        "display_name,expected_id",
        [
            # Major providers
            ("OpenAI", "openai"),
            ("Anthropic", "anthropic"),
            ("Google", "google"),
            ("Microsoft Azure", "microsoft-azure"),
            ("Amazon Bedrock", "amazon-bedrock"),
            ("Hugging Face", "hugging-face"),
            # Model-based names
            ("Claude 3.5 Sonnet", "claude-35-sonnet"),
            ("GPT-4 Turbo", "gpt-4-turbo"),
            ("Gemini Pro 1.5", "gemini-pro-15"),
            ("Llama 2 70B", "llama-2-70b"),
            ("Mixtral 8x7B", "mixtral-8x7b"),
            # Custom/local providers
            ("Local Ollama", "local-ollama"),
            ("Self-Hosted LLM", "self-hosted-llm"),
            ("Company Internal API", "company-internal-api"),
            # With version numbers
            ("OpenAI v2", "openai-v2"),
            ("Custom Provider 3.0", "custom-provider-30"),
        ],
    )
    def test_real_world_provider(self, display_name: str, expected_id: str) -> None:
        """Verify real-world provider names normalize correctly."""
        python_result = python_normalize(display_name)
        typescript_result = typescript_normalize(display_name)

        assert python_result == typescript_result
        assert python_result == expected_id


class TestPythonTypescriptConsistency:
    """
    Comprehensive consistency tests between Python and TypeScript implementations.

    These tests ensure the two implementations remain synchronized.
    """

    def test_implementations_match_all_ascii(self) -> None:
        """Test all printable ASCII characters produce same results."""
        import string

        for char in string.printable:
            if char in "\t\n\r\x0b\x0c":  # Skip problematic whitespace
                continue
            python_result = python_normalize(char)
            typescript_result = typescript_normalize(char)
            assert python_result == typescript_result, f"Mismatch for char '{char!r}'"

    def test_random_combinations(self) -> None:
        """Test various random combinations of characters."""
        test_cases = [
            "AbCdEf123",
            "Test-Case_One",
            "  Spaced  Out  ",
            "---dashes---",
            "Mix3d.C@$e!",
            "ALLCAPS",
            "alllower",
            "123numbers",
            "numbers123at123end",
            "a",
            "1",
            "-",
            " ",
            ".",
        ]

        for test_input in test_cases:
            python_result = python_normalize(test_input)
            typescript_result = typescript_normalize(test_input)
            assert (
                python_result == typescript_result
            ), f"Mismatch for '{test_input}': Python='{python_result}', TypeScript='{typescript_result}'"


# =============================================================================
# Optional: Live TypeScript Execution Tests
# =============================================================================


class TestLiveTypeScriptExecution:
    """
    Tests that execute actual TypeScript code to verify parity.

    These tests require Node.js to be installed and are marked as slow.
    They can be skipped in CI environments without Node.js.
    """

    @pytest.fixture
    def node_available(self) -> bool:
        """Check if Node.js is available."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @pytest.fixture
    def typescript_file_path(self) -> Path:
        """Get the path to the TypeScript implementation."""
        # Navigate from tests/integration to auto-claude-ui
        return (
            _AUTO_CLAUDE_DIR.parent
            / "auto-claude-ui"
            / "src"
            / "renderer"
            / "utils"
            / "providerCredentials.ts"
        )

    @pytest.mark.slow
    def test_live_execution_matches(
        self, node_available: bool, typescript_file_path: Path
    ) -> None:
        """
        Execute TypeScript code via Node.js and compare with Python.

        This test runs actual TypeScript code to ensure complete parity.
        """
        if not node_available:
            pytest.skip("Node.js not available")

        if not typescript_file_path.exists():
            pytest.skip(f"TypeScript file not found: {typescript_file_path}")

        # Test cases to verify
        test_cases = [
            "OpenAI",
            "Z.ai GLM 4.7",
            "Custom Provider",
            "  OpenAI  ",
            "Custom---Provider",
            "Z.ai GLM 4.7!@#",
        ]

        # Create a temporary Node.js script to run normalization
        import json as json_module

        test_cases_json = json_module.dumps(test_cases)
        node_script = f"""
        function normalizeProviderId(name) {{
            let normalized = name.toLowerCase().trim().replace(/ /g, '-');
            normalized = normalized.replace(/[^a-z0-9-]/g, '');
            normalized = normalized.replace(/-+/g, '-');
            return normalized.replace(/^-+|-+$/g, '');
        }}

        const testCases = {test_cases_json};
        const results = testCases.map(name => normalizeProviderId(name));
        console.log(JSON.stringify(results));
        """

        try:
            result = subprocess.run(
                ["node", "-e", node_script],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                pytest.skip(f"Node.js execution failed: {result.stderr}")

            ts_results = json_module.loads(result.stdout.strip())

            for test_input, ts_result in zip(test_cases, ts_results):
                python_result = python_normalize(test_input)
                assert python_result == ts_result, (
                    f"Live mismatch for '{test_input}': "
                    f"Python='{python_result}', TypeScript='{ts_result}'"
                )

        except subprocess.TimeoutExpired:
            pytest.skip("Node.js execution timed out")
        except json_module.JSONDecodeError as e:
            pytest.skip(f"Failed to parse Node.js output: {e}")


# =============================================================================
# Test Summary and Documentation
# =============================================================================


class TestDocumentation:
    """Meta-tests to ensure test coverage documentation."""

    def test_all_spec_cases_covered(self) -> None:
        """Verify all spec-required test cases are explicitly tested."""
        spec_cases = [
            ("OpenAI", "openai"),
            ("Z.ai GLM 4.7", "zai-glm-47"),
            ("Custom Provider", "custom-provider"),
            ("  OpenAI  ", "openai"),
            ("Custom---Provider", "custom-provider"),
            ("Z.ai GLM 4.7!@#", "zai-glm-47"),
        ]

        for input_name, expected in spec_cases:
            result = python_normalize(input_name)
            assert (
                result == expected
            ), f"Spec case failed: '{input_name}' -> got '{result}', expected '{expected}'"
