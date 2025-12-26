"""
Tests for Provider Configuration
=================================

Comprehensive tests for ProviderConfig, ProviderCredential, AgentProvider,
and related configuration functions.

Test Coverage:
- AgentProvider enum operations
- ProviderCredential creation, validation, and serialization
- ProviderConfig.from_env() with various environment scenarios
- Global/project credential inheritance
- Legacy CLAUDE_CODE_OAUTH_TOKEN support
- Validation methods and error messages
- Credential source tracking
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.config import (
    AgentProvider,
    ProviderConfig,
    ProviderCredential,
    get_active_provider,
    is_global_provider,
    parse_provider_credentials,
)

# =============================================================================
# AgentProvider Enum Tests
# =============================================================================


class TestAgentProvider:
    """Tests for the AgentProvider enum."""

    def test_enum_values(self):
        """AgentProvider should have correct enum values."""
        assert AgentProvider.CLAUDE_CODE.value == "claude_code"
        assert AgentProvider.OPENCODE.value == "opencode"

    def test_from_string_valid(self):
        """from_string should convert valid strings to enum."""
        assert AgentProvider.from_string("claude_code") == AgentProvider.CLAUDE_CODE
        assert AgentProvider.from_string("opencode") == AgentProvider.OPENCODE

    def test_from_string_case_insensitive(self):
        """from_string should be case-insensitive."""
        assert AgentProvider.from_string("CLAUDE_CODE") == AgentProvider.CLAUDE_CODE
        assert AgentProvider.from_string("Claude_Code") == AgentProvider.CLAUDE_CODE
        assert AgentProvider.from_string("OPENCODE") == AgentProvider.OPENCODE

    def test_from_string_with_whitespace(self):
        """from_string should handle whitespace."""
        assert AgentProvider.from_string("  claude_code  ") == AgentProvider.CLAUDE_CODE
        assert AgentProvider.from_string("\topencode\n") == AgentProvider.OPENCODE

    def test_from_string_invalid(self):
        """from_string should raise ValueError for invalid strings."""
        with pytest.raises(ValueError) as excinfo:
            AgentProvider.from_string("invalid_provider")
        assert "invalid_provider" in str(excinfo.value).lower()
        assert "claude_code" in str(excinfo.value)
        assert "opencode" in str(excinfo.value)

    def test_default(self):
        """default() should return CLAUDE_CODE."""
        assert AgentProvider.default() == AgentProvider.CLAUDE_CODE


# =============================================================================
# ProviderCredential Tests
# =============================================================================


class TestProviderCredential:
    """Tests for the ProviderCredential dataclass."""

    # -------------------------------------------------------------------------
    # Creation and Initialization
    # -------------------------------------------------------------------------

    def test_basic_creation(self):
        """Basic credential creation should work."""
        cred = ProviderCredential(provider="openai", api_key="sk-test123")
        assert cred.provider == "openai"
        assert cred.api_key == "sk-test123"
        assert cred.base_url == ""
        assert cred.default_model == ""
        assert cred.is_global is False
        assert cred.metadata == {}

    def test_full_creation(self):
        """Credential with all fields should work."""
        cred = ProviderCredential(
            provider="anthropic",
            api_key="sk-ant-test",
            base_url="https://api.anthropic.com",
            default_model="claude-3-opus",
            is_global=True,
            metadata={"custom_key": "value"},
        )
        assert cred.provider == "anthropic"
        assert cred.api_key == "sk-ant-test"
        assert cred.base_url == "https://api.anthropic.com"
        assert cred.default_model == "claude-3-opus"
        assert cred.is_global is True
        assert cred.metadata == {"custom_key": "value"}

    def test_provider_normalization(self):
        """Provider ID should be normalized on creation."""
        cred = ProviderCredential(provider="OpenAI", api_key="test")
        assert cred.provider == "openai"

        cred = ProviderCredential(provider="AWS Bedrock", api_key="test")
        assert cred.provider == "aws-bedrock"

        cred = ProviderCredential(provider="Z.ai GLM", api_key="test")
        assert cred.provider == "zai-glm"

    def test_base_url_normalization(self):
        """Base URL should have trailing slash removed."""
        cred = ProviderCredential(
            provider="openai", api_key="test", base_url="https://api.openai.com/"
        )
        assert cred.base_url == "https://api.openai.com"

        # Multiple trailing slashes
        cred = ProviderCredential(
            provider="openai", api_key="test", base_url="https://api.openai.com///"
        )
        assert cred.base_url == "https://api.openai.com"

    def test_none_metadata_handled(self):
        """None metadata should be converted to empty dict."""
        cred = ProviderCredential(provider="test", api_key="test", metadata=None)
        assert cred.metadata == {}

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def test_is_valid_with_api_key(self):
        """Credential with provider and API key should be valid."""
        cred = ProviderCredential(provider="openai", api_key="sk-test")
        assert cred.is_valid() is True

    def test_is_valid_global_without_api_key(self):
        """Global credential without API key should be valid."""
        cred = ProviderCredential(provider="openai", is_global=True)
        assert cred.is_valid() is True

    def test_is_invalid_no_api_key_not_global(self):
        """Non-global credential without API key should be invalid."""
        cred = ProviderCredential(provider="openai")
        assert cred.is_valid() is False

    def test_is_invalid_no_provider(self):
        """Credential without provider should be invalid."""
        cred = ProviderCredential(provider="", api_key="test")
        assert cred.is_valid() is False

    def test_validation_errors_no_provider(self):
        """Validation should report missing provider."""
        cred = ProviderCredential(provider="", api_key="test")
        errors = cred.get_validation_errors()
        assert len(errors) == 1
        assert "provider id is required" in errors[0].lower()

    def test_validation_errors_no_api_key(self):
        """Validation should report missing API key for non-global."""
        cred = ProviderCredential(provider="openai")
        errors = cred.get_validation_errors()
        assert len(errors) == 1
        assert "api key required" in errors[0].lower()
        assert "openai" in errors[0]

    def test_validation_errors_valid_credential(self):
        """Valid credential should have no errors."""
        cred = ProviderCredential(provider="openai", api_key="sk-test")
        assert cred.get_validation_errors() == []

    # -------------------------------------------------------------------------
    # Source Info
    # -------------------------------------------------------------------------

    def test_source_info_global(self):
        """Global credential should show global source."""
        cred = ProviderCredential(provider="openai", is_global=True)
        source = cred.get_source_info()
        assert "openai" in source
        assert "global" in source.lower()

    def test_source_info_project(self):
        """Project credential should show project source."""
        cred = ProviderCredential(provider="openai", api_key="test", is_global=False)
        source = cred.get_source_info()
        assert "openai" in source
        assert "project" in source.lower()

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def test_to_dict(self):
        """to_dict should produce correct dictionary."""
        cred = ProviderCredential(
            provider="openai",
            api_key="sk-test",
            base_url="https://api.openai.com",
            default_model="gpt-4o",
            is_global=True,
            metadata={"key": "value"},
        )
        result = cred.to_dict()
        assert result == {
            "provider": "openai",
            "apiKey": "sk-test",
            "baseUrl": "https://api.openai.com",
            "defaultModel": "gpt-4o",
            "isGlobal": True,
            "metadata": {"key": "value"},
        }

    def test_from_dict(self):
        """from_dict should create correct credential."""
        data = {
            "apiKey": "sk-test",
            "baseUrl": "https://api.openai.com",
            "defaultModel": "gpt-4o",
            "isGlobal": True,
            "metadata": {"key": "value"},
        }
        cred = ProviderCredential.from_dict("OpenAI", data)
        assert cred.provider == "openai"  # Normalized
        assert cred.api_key == "sk-test"
        assert cred.base_url == "https://api.openai.com"
        assert cred.default_model == "gpt-4o"
        assert cred.is_global is True
        assert cred.metadata == {"key": "value"}

    def test_from_dict_minimal(self):
        """from_dict with minimal data should use defaults."""
        cred = ProviderCredential.from_dict("test", {})
        assert cred.provider == "test"
        assert cred.api_key == ""
        assert cred.base_url == ""
        assert cred.default_model == ""
        assert cred.is_global is False
        assert cred.metadata == {}

    # -------------------------------------------------------------------------
    # Legacy Claude Code Support
    # -------------------------------------------------------------------------

    def test_from_env_legacy_claude_with_token(self):
        """Legacy Claude token should create credential."""
        with patch.dict(
            os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-123"}, clear=False
        ):
            cred = ProviderCredential.from_env_legacy_claude()
            assert cred is not None
            assert cred.provider == "claude-code"
            assert cred.api_key == "oauth-token-123"
            assert cred.is_global is False

    def test_from_env_legacy_claude_with_global(self):
        """Legacy Claude token with global flag should work."""
        with patch.dict(
            os.environ,
            {"CLAUDE_CODE_OAUTH_TOKEN": "token", "CLAUDE_TOKEN_IS_GLOBAL": "true"},
            clear=False,
        ):
            cred = ProviderCredential.from_env_legacy_claude()
            assert cred is not None
            assert cred.is_global is True

    def test_from_env_legacy_claude_global_variations(self):
        """Legacy global flag should accept various true values."""
        for true_value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            with patch.dict(
                os.environ,
                {
                    "CLAUDE_CODE_OAUTH_TOKEN": "token",
                    "CLAUDE_TOKEN_IS_GLOBAL": true_value,
                },
                clear=False,
            ):
                cred = ProviderCredential.from_env_legacy_claude()
                assert cred.is_global is True, f"Failed for value: {true_value}"

    def test_from_env_legacy_claude_no_token(self):
        """No legacy token should return None."""
        with patch.dict(os.environ, {}, clear=True):
            cred = ProviderCredential.from_env_legacy_claude()
            assert cred is None


# =============================================================================
# parse_provider_credentials Tests
# =============================================================================


class TestParseProviderCredentials:
    """Tests for the parse_provider_credentials function."""

    def test_valid_json_single_provider(self):
        """Should parse single provider correctly."""
        json_str = '{"openai": {"apiKey": "sk-test", "defaultModel": "gpt-4o"}}'
        result = parse_provider_credentials(json_str)
        assert len(result) == 1
        assert "openai" in result
        assert result["openai"].api_key == "sk-test"
        assert result["openai"].default_model == "gpt-4o"

    def test_valid_json_multiple_providers(self):
        """Should parse multiple providers correctly."""
        json_str = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "isGlobal": False},
                "anthropic": {"apiKey": "sk-ant", "isGlobal": True},
                "zai": {"isGlobal": True},
            }
        )
        result = parse_provider_credentials(json_str)
        assert len(result) == 3
        assert result["openai"].api_key == "sk-openai"
        assert result["openai"].is_global is False
        assert result["anthropic"].api_key == "sk-ant"
        assert result["anthropic"].is_global is True
        assert result["zai"].is_global is True

    def test_empty_string(self):
        """Empty string should return empty dict."""
        assert parse_provider_credentials("") == {}
        assert parse_provider_credentials("   ") == {}

    def test_empty_object(self):
        """Empty JSON object should return empty dict."""
        assert parse_provider_credentials("{}") == {}

    def test_invalid_json(self):
        """Invalid JSON should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            parse_provider_credentials("not valid json")
        assert "invalid" in str(excinfo.value).lower()

    def test_non_object_json(self):
        """Non-object JSON should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            parse_provider_credentials("[]")
        assert "must be a json object" in str(excinfo.value).lower()

        with pytest.raises(ValueError) as excinfo:
            parse_provider_credentials('"string"')
        assert "must be a json object" in str(excinfo.value).lower()

    def test_non_object_provider_data(self):
        """Non-object provider data should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            parse_provider_credentials('{"openai": "invalid"}')
        assert "must be an object" in str(excinfo.value).lower()
        assert "openai" in str(excinfo.value).lower()

    def test_complex_provider_data(self):
        """Should handle complex provider data with metadata."""
        json_str = json.dumps(
            {
                "custom-provider": {
                    "apiKey": "key",
                    "baseUrl": "https://custom.api.com/",
                    "defaultModel": "custom-model-v1",
                    "isGlobal": False,
                    "metadata": {"region": "us-east-1", "timeout": 30},
                }
            }
        )
        result = parse_provider_credentials(json_str)
        cred = result["custom-provider"]
        assert cred.api_key == "key"
        assert cred.base_url == "https://custom.api.com"  # Trailing slash removed
        assert cred.default_model == "custom-model-v1"
        assert cred.metadata["region"] == "us-east-1"
        assert cred.metadata["timeout"] == 30


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetActiveProvider:
    """Tests for get_active_provider helper function."""

    def test_default_provider(self):
        """Should return claude_code when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_active_provider() == AgentProvider.CLAUDE_CODE

    def test_claude_code_explicit(self):
        """Should return claude_code when explicitly set."""
        with patch.dict(os.environ, {"AGENT_PROVIDER": "claude_code"}, clear=False):
            assert get_active_provider() == AgentProvider.CLAUDE_CODE

    def test_opencode_explicit(self):
        """Should return opencode when set."""
        with patch.dict(os.environ, {"AGENT_PROVIDER": "opencode"}, clear=False):
            assert get_active_provider() == AgentProvider.OPENCODE

    def test_invalid_falls_back_to_default(self):
        """Should fallback to default for invalid provider."""
        with patch.dict(os.environ, {"AGENT_PROVIDER": "invalid"}, clear=False):
            assert get_active_provider() == AgentProvider.CLAUDE_CODE


class TestIsGlobalProvider:
    """Tests for is_global_provider helper function."""

    def test_default_false(self):
        """Should return False when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_global_provider() is False

    def test_true_values(self):
        """Should return True for various true values."""
        for true_value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            with patch.dict(
                os.environ, {"AGENT_PROVIDER_IS_GLOBAL": true_value}, clear=False
            ):
                assert is_global_provider() is True, f"Failed for value: {true_value}"

    def test_false_values(self):
        """Should return False for various false values."""
        for false_value in ["false", "False", "0", "no", "other"]:
            with patch.dict(
                os.environ, {"AGENT_PROVIDER_IS_GLOBAL": false_value}, clear=False
            ):
                assert is_global_provider() is False, f"Failed for value: {false_value}"


# =============================================================================
# ProviderConfig Tests
# =============================================================================


class TestProviderConfig:
    """Tests for the ProviderConfig dataclass."""

    # -------------------------------------------------------------------------
    # Basic Creation
    # -------------------------------------------------------------------------

    def test_default_creation(self):
        """Default creation should have sensible defaults."""
        config = ProviderConfig()
        assert config.provider == AgentProvider.CLAUDE_CODE
        assert config.is_global is False
        assert config.credentials == {}
        assert config.opencode_provider == ""
        assert config.opencode_model == ""

    # -------------------------------------------------------------------------
    # from_env Tests
    # -------------------------------------------------------------------------

    def test_from_env_defaults(self):
        """from_env with no env vars should use defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_global is False

    def test_from_env_claude_code_provider(self):
        """from_env should load claude_code provider."""
        with patch.dict(os.environ, {"AGENT_PROVIDER": "claude_code"}, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE

    def test_from_env_opencode_provider(self):
        """from_env should load opencode provider."""
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.OPENCODE
            assert config.opencode_provider == "openai"
            assert config.opencode_model == "gpt-4o-mini"

    def test_from_env_global_flag(self):
        """from_env should respect global flag."""
        env = {"AGENT_PROVIDER_IS_GLOBAL": "true"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_global is True

    def test_from_env_provider_credentials(self):
        """from_env should load PROVIDER_CREDENTIALS JSON."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "isGlobal": False},
                "anthropic": {"apiKey": "sk-ant", "isGlobal": True},
            }
        )
        env = {"PROVIDER_CREDENTIALS": creds_json}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert len(config.credentials) == 2
            assert config.credentials["openai"].api_key == "sk-openai"
            assert config.credentials["anthropic"].api_key == "sk-ant"

    def test_from_env_invalid_json_silently_ignored(self):
        """from_env should silently ignore invalid JSON."""
        env = {"PROVIDER_CREDENTIALS": "invalid json"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.credentials == {}

    def test_from_env_legacy_claude_token(self):
        """from_env should load legacy CLAUDE_CODE_OAUTH_TOKEN."""
        env = {"CLAUDE_CODE_OAUTH_TOKEN": "legacy-token"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert "claude-code" in config.credentials
            assert config.credentials["claude-code"].api_key == "legacy-token"

    def test_from_env_provider_credentials_overrides_legacy(self):
        """PROVIDER_CREDENTIALS should override legacy token."""
        creds_json = json.dumps({"claude-code": {"apiKey": "new-token"}})
        env = {
            "PROVIDER_CREDENTIALS": creds_json,
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.credentials["claude-code"].api_key == "new-token"

    def test_from_env_opencode_provider_lowercase(self):
        """OPENCODE_PROVIDER should be lowercased."""
        env = {"OPENCODE_PROVIDER": "OpenAI"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.opencode_provider == "openai"

    # -------------------------------------------------------------------------
    # get_credential Tests
    # -------------------------------------------------------------------------

    def test_get_credential_existing(self):
        """get_credential should return existing credential."""
        cred = ProviderCredential(provider="openai", api_key="test")
        config = ProviderConfig(credentials={"openai": cred})
        result = config.get_credential("openai")
        assert result is not None
        assert result.api_key == "test"

    def test_get_credential_normalized(self):
        """get_credential should normalize provider ID."""
        cred = ProviderCredential(provider="openai", api_key="test")
        config = ProviderConfig(credentials={"openai": cred})
        # Query with different case
        result = config.get_credential("OpenAI")
        assert result is not None
        assert result.api_key == "test"

    def test_get_credential_missing(self):
        """get_credential should return None for missing credential."""
        config = ProviderConfig()
        assert config.get_credential("openai") is None

    # -------------------------------------------------------------------------
    # get_active_credential Tests
    # -------------------------------------------------------------------------

    def test_get_active_credential_claude_code(self):
        """get_active_credential should return claude-code for CLAUDE_CODE provider."""
        cred = ProviderCredential(provider="claude-code", api_key="token")
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE, credentials={"claude-code": cred}
        )
        result = config.get_active_credential()
        assert result is not None
        assert result.api_key == "token"

    def test_get_active_credential_opencode(self):
        """get_active_credential should return LLM provider credential for OPENCODE."""
        cred = ProviderCredential(provider="openai", api_key="sk-test")
        config = ProviderConfig(
            provider=AgentProvider.OPENCODE,
            opencode_provider="openai",
            credentials={"openai": cred},
        )
        result = config.get_active_credential()
        assert result is not None
        assert result.api_key == "sk-test"

    def test_get_active_credential_opencode_no_provider(self):
        """get_active_credential should return None if no opencode_provider set."""
        config = ProviderConfig(provider=AgentProvider.OPENCODE)
        assert config.get_active_credential() is None

    # -------------------------------------------------------------------------
    # get_credential_source_info Tests
    # -------------------------------------------------------------------------

    def test_credential_source_info_with_credential(self):
        """get_credential_source_info should return credential source."""
        cred = ProviderCredential(
            provider="claude-code", api_key="token", is_global=True
        )
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE, credentials={"claude-code": cred}
        )
        source = config.get_credential_source_info()
        assert "claude-code" in source
        assert "global" in source.lower()

    def test_credential_source_info_no_credential(self):
        """get_credential_source_info should handle missing credential."""
        config = ProviderConfig(provider=AgentProvider.CLAUDE_CODE, is_global=True)
        source = config.get_credential_source_info()
        assert "claude_code" in source
        assert "no credential" in source.lower()

    # -------------------------------------------------------------------------
    # is_valid Tests
    # -------------------------------------------------------------------------

    def test_is_valid_claude_code_with_credential(self):
        """Claude Code with valid credential should be valid."""
        cred = ProviderCredential(provider="claude-code", api_key="token")
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE, credentials={"claude-code": cred}
        )
        assert config.is_valid() is True

    def test_is_valid_claude_code_no_credential(self):
        """Claude Code without credential should be invalid."""
        config = ProviderConfig(provider=AgentProvider.CLAUDE_CODE)
        assert config.is_valid() is False

    def test_is_valid_claude_code_invalid_credential(self):
        """Claude Code with invalid credential should be invalid."""
        # Credential without api_key and not global
        cred = ProviderCredential(provider="claude-code")
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE, credentials={"claude-code": cred}
        )
        assert config.is_valid() is False

    def test_is_valid_opencode_with_provider(self):
        """OpenCode with provider set should be valid."""
        config = ProviderConfig(
            provider=AgentProvider.OPENCODE, opencode_provider="openai"
        )
        # OpenCode can work without explicit credentials (uses env vars like OPENAI_API_KEY)
        assert config.is_valid() is True

    def test_is_valid_opencode_no_provider(self):
        """OpenCode without provider should be invalid."""
        config = ProviderConfig(provider=AgentProvider.OPENCODE)
        assert config.is_valid() is False

    def test_is_valid_opencode_with_credential(self):
        """OpenCode with valid LLM credential should be valid."""
        cred = ProviderCredential(provider="openai", api_key="sk-test")
        config = ProviderConfig(
            provider=AgentProvider.OPENCODE,
            opencode_provider="openai",
            credentials={"openai": cred},
        )
        assert config.is_valid() is True

    # -------------------------------------------------------------------------
    # get_validation_errors Tests
    # -------------------------------------------------------------------------

    def test_validation_errors_claude_code_no_credential(self):
        """Should report missing Claude Code credentials."""
        config = ProviderConfig(provider=AgentProvider.CLAUDE_CODE)
        errors = config.get_validation_errors()
        assert len(errors) == 1
        assert "claude code" in errors[0].lower() or "claude-code" in errors[0].lower()

    def test_validation_errors_opencode_no_provider(self):
        """Should report missing OpenCode provider."""
        config = ProviderConfig(provider=AgentProvider.OPENCODE)
        errors = config.get_validation_errors()
        assert len(errors) == 1
        assert "opencode_provider" in errors[0].lower()

    def test_validation_errors_valid_config(self):
        """Valid config should have no errors."""
        cred = ProviderCredential(provider="claude-code", api_key="token")
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE, credentials={"claude-code": cred}
        )
        assert config.get_validation_errors() == []

    # -------------------------------------------------------------------------
    # get_credentials_summary Tests
    # -------------------------------------------------------------------------

    def test_credentials_summary(self):
        """get_credentials_summary should return correct summary."""
        cred = ProviderCredential(
            provider="openai",
            api_key="sk-test",
            base_url="https://api.openai.com",
            default_model="gpt-4o",
            is_global=False,
        )
        config = ProviderConfig(
            provider=AgentProvider.OPENCODE,
            is_global=True,
            opencode_provider="openai",
            opencode_model="gpt-4o",
            credentials={"openai": cred},
        )
        summary = config.get_credentials_summary()

        assert summary["active_provider"] == "opencode"
        assert summary["is_global"] is True
        assert summary["opencode_provider"] == "openai"
        assert summary["opencode_model"] == "gpt-4o"
        assert "openai" in summary["credentials"]

        openai_summary = summary["credentials"]["openai"]
        assert openai_summary["is_valid"] is True
        assert openai_summary["has_api_key"] is True
        assert openai_summary["has_base_url"] is True
        assert openai_summary["default_model"] == "gpt-4o"
        assert openai_summary["is_global"] is False

    def test_credentials_summary_sensitive_data_excluded(self):
        """get_credentials_summary should not include actual API keys."""
        cred = ProviderCredential(provider="openai", api_key="sk-secret-key")
        config = ProviderConfig(credentials={"openai": cred})
        summary = config.get_credentials_summary()

        # Should have has_api_key flag but not actual key
        assert summary["credentials"]["openai"]["has_api_key"] is True
        # API key should not be in the summary at all
        assert "sk-secret-key" not in str(summary)

    # -------------------------------------------------------------------------
    # get_provider_status Tests
    # -------------------------------------------------------------------------

    def test_provider_status_valid(self):
        """get_provider_status should return correct status for valid config."""
        cred = ProviderCredential(
            provider="claude-code", api_key="token", is_global=True
        )
        config = ProviderConfig(
            provider=AgentProvider.CLAUDE_CODE,
            is_global=True,
            credentials={"claude-code": cred},
        )
        status = config.get_provider_status()

        assert status["provider"] == "claude_code"
        assert status["is_valid"] is True
        assert status["is_global"] is True
        assert "claude-code" in status["credential_source"]
        assert "global" in status["credential_source"].lower()
        assert status["errors"] == []

    def test_provider_status_invalid(self):
        """get_provider_status should include errors for invalid config."""
        config = ProviderConfig(provider=AgentProvider.CLAUDE_CODE)
        status = config.get_provider_status()

        assert status["is_valid"] is False
        assert len(status["errors"]) > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestProviderConfigIntegration:
    """Integration tests for complete configuration scenarios."""

    def test_full_claude_code_setup(self):
        """Complete Claude Code setup via environment."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-123",
            "CLAUDE_TOKEN_IS_GLOBAL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid() is True
            assert config.get_validation_errors() == []

            cred = config.get_active_credential()
            assert cred is not None
            assert cred.api_key == "oauth-token-123"
            assert cred.is_global is True

    def test_full_opencode_setup(self):
        """Complete OpenCode setup via environment."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-openai-key",
                    "defaultModel": "gpt-4o",
                    "isGlobal": False,
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "AGENT_PROVIDER_IS_GLOBAL": "false",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.OPENCODE
            assert config.is_global is False
            assert config.opencode_provider == "openai"
            assert config.opencode_model == "gpt-4o-mini"
            assert config.is_valid() is True

            cred = config.get_active_credential()
            assert cred is not None
            assert cred.api_key == "sk-openai-key"

    def test_mixed_credential_inheritance(self):
        """Test mixed global and project credentials."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "isGlobal": False},
                "anthropic": {"isGlobal": True},  # Global without apiKey
                "custom": {
                    "apiKey": "sk-custom",
                    "isGlobal": False,
                    "baseUrl": "https://custom.api/",
                },
            }
        )
        env = {"PROVIDER_CREDENTIALS": creds_json}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # OpenAI - project credential with API key
            openai_cred = config.get_credential("openai")
            assert openai_cred is not None
            assert openai_cred.is_global is False
            assert openai_cred.is_valid() is True

            # Anthropic - global without API key (valid because global)
            anthropic_cred = config.get_credential("anthropic")
            assert anthropic_cred is not None
            assert anthropic_cred.is_global is True
            assert anthropic_cred.is_valid() is True

            # Custom - project with custom base URL
            custom_cred = config.get_credential("custom")
            assert custom_cred is not None
            assert (
                custom_cred.base_url == "https://custom.api"
            )  # Trailing slash removed
            assert custom_cred.is_valid() is True

    def test_provider_status_complete_report(self):
        """Test complete provider status report."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "defaultModel": "gpt-4o"},
                "anthropic": {"apiKey": "sk-ant"},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()
            summary = config.get_credentials_summary()

            assert status["provider"] == "opencode"
            assert status["is_valid"] is True
            assert len(summary["credentials"]) == 2
            assert "openai" in summary["credentials"]
            assert "anthropic" in summary["credentials"]
