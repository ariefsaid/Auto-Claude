"""
Provider Integration Tests - CLI -> Config -> Client Flow
============================================================

This test suite verifies the complete integration flow for provider
configuration loading, validation, and client creation:

1. CLI provider loading with priority: CLI flag > Project .env > Global settings > Default
2. Provider configuration validation
3. Global credential inheritance
4. Provider switching between Claude Code and OpenCode

Test coverage:
- get_provider_config() logic (reimplemented from cli/main.py)
- load_project_env() and load_global_settings() from cli/provider_info.py
- validate_provider_config() from cli/provider_info.py
- Provider status retrieval with get_provider_status()
"""

import json
import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

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

# Import functions from provider_info
normalize_provider_id = _provider_info.normalize_provider_id
load_project_env = _provider_info.load_project_env
load_global_settings = _provider_info.load_global_settings
get_global_settings_path = _provider_info.get_global_settings_path
get_global_credential = _provider_info.get_global_credential
get_provider_status = _provider_info.get_provider_status
validate_provider_config = _provider_info.validate_provider_config
parse_provider_credentials = _provider_info.parse_provider_credentials
validate_api_key_format = _provider_info.validate_api_key_format

# Type aliases matching cli/main.py
AgentProviderType = Literal["claude_code", "opencode"]
ConfigSource = Literal["cli_flag", "project_env", "global_settings", "default"]
ProviderConfig = dict[str, str | bool | dict | None]


def get_provider_config(
    project_dir: Path,
    cli_provider: str | None = None,
) -> ProviderConfig:
    """
    Get provider configuration with priority: CLI flag > Project .env > Global settings > Default.

    This is a reimplementation of the logic from cli/main.py for testing purposes,
    avoiding relative import issues. The actual implementation in cli/main.py uses
    the same logic with the same helper functions from provider_info.

    Args:
        project_dir: Project root directory
        cli_provider: Provider specified via --provider CLI flag (optional)

    Returns:
        ProviderConfig dictionary with:
        - provider: Agent provider type ('claude_code' or 'opencode')
        - source: Configuration source ('cli_flag', 'project_env', 'global_settings', 'default')
        - opencode_provider: OpenCode LLM provider ID (if using opencode)
        - opencode_model: OpenCode model override (if using opencode)
        - is_global: Whether using global credentials
        - credentials: Credential reference information
    """
    provider: AgentProviderType = "claude_code"
    source: ConfigSource = "default"
    opencode_provider: str | None = None
    opencode_model: str | None = None
    is_global: bool = False
    credentials: dict = {}

    # Priority 1: CLI flag (highest)
    if cli_provider and cli_provider in ("claude_code", "opencode"):
        provider = cli_provider  # type: ignore
        source = "cli_flag"

    # Priority 2: Project .env
    if source == "default":
        project_env = load_project_env(project_dir)
        env_provider = project_env.get("AGENT_PROVIDER", "").strip().lower()
        if env_provider in ("claude_code", "opencode"):
            provider = env_provider  # type: ignore
            source = "project_env"

    # Priority 3: Global settings
    if source == "default":
        global_settings = load_global_settings()
        global_provider = (
            str(global_settings.get("globalDefaultProvider", "")).strip().lower()
        )
        if global_provider in ("claude_code", "opencode"):
            provider = global_provider  # type: ignore
            source = "global_settings"

    # Load additional configuration based on provider type
    if provider == "opencode":
        # Load OpenCode-specific configuration
        oc_project_env = load_project_env(project_dir)
        oc_global_settings = load_global_settings()

        # Get OpenCode provider and model
        opencode_provider = oc_project_env.get("OPENCODE_PROVIDER", "").strip() or None
        if not opencode_provider:
            opencode_provider = oc_global_settings.get("globalOpencodeProvider") or None
        if opencode_provider:
            opencode_provider = normalize_provider_id(opencode_provider)

        opencode_model = oc_project_env.get("OPENCODE_MODEL", "").strip() or None
        if not opencode_model:
            opencode_model = oc_global_settings.get("globalOpencodeModel") or None

        # Check if using global credentials
        is_global_str = oc_project_env.get("AGENT_PROVIDER_IS_GLOBAL", "").lower()
        is_global = is_global_str == "true"

        # Parse provider credentials
        provider_credentials = parse_provider_credentials(
            oc_project_env.get("PROVIDER_CREDENTIALS")
        )
        if opencode_provider and opencode_provider in provider_credentials:
            credentials = provider_credentials[opencode_provider]
            # Check credential reference's isGlobal flag
            if credentials.get("isGlobal", False):
                is_global = True

    return {
        "provider": provider,
        "source": source,
        "opencode_provider": opencode_provider,
        "opencode_model": opencode_model,
        "is_global": is_global,
        "credentials": credentials,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory with .auto-claude folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir(parents=True, exist_ok=True)
        yield project_dir


@pytest.fixture
def temp_global_settings() -> Generator[Path, None, None]:
    """Create a temporary global settings file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_dir = Path(tmpdir) / "auto-claude-ui"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.json"
        yield settings_path


def write_env_file(project_dir: Path, content: str) -> Path:
    """Write a .env file to the project's .auto-claude directory."""
    env_path = project_dir / ".auto-claude" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(content)
    return env_path


def write_global_settings(settings_path: Path, settings: dict[str, Any]) -> None:
    """Write global settings to the settings file."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2))


# =============================================================================
# Test: Configuration Priority (CLI flag > Project .env > Global settings > Default)
# =============================================================================


class TestConfigurationPriority:
    """Test provider configuration loading priority order."""

    def test_default_provider_is_claude_code(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Default provider should be claude_code when no config exists."""
        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "claude_code"
        assert config["source"] == "default"

    def test_global_settings_overrides_default(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Global settings should override default."""
        write_global_settings(
            temp_global_settings, {"globalDefaultProvider": "opencode"}
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "opencode"
        assert config["source"] == "global_settings"

    def test_project_env_overrides_global(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Project .env should override global settings."""
        # Set global to opencode
        write_global_settings(
            temp_global_settings, {"globalDefaultProvider": "opencode"}
        )

        # Set project to claude_code
        write_env_file(temp_project_dir, "AGENT_PROVIDER=claude_code")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "claude_code"
        assert config["source"] == "project_env"

    def test_cli_flag_overrides_project_env(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """CLI flag should override project .env."""
        # Set project to claude_code
        write_env_file(temp_project_dir, "AGENT_PROVIDER=claude_code")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider="opencode")

        assert config["provider"] == "opencode"
        assert config["source"] == "cli_flag"

    def test_invalid_provider_type_ignored(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Invalid provider types should be ignored."""
        write_env_file(temp_project_dir, "AGENT_PROVIDER=invalid_provider")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        # Should fall back to default
        assert config["provider"] == "claude_code"
        assert config["source"] == "default"


# =============================================================================
# Test: OpenCode Configuration Loading
# =============================================================================


class TestOpenCodeConfiguration:
    """Test OpenCode-specific configuration loading."""

    def test_opencode_provider_from_project_env(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """OpenCode provider should be loaded from project .env."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "opencode"
        assert config["opencode_provider"] == "openai"
        assert config["opencode_model"] == "gpt-4o"

    def test_opencode_provider_from_global_settings(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """OpenCode provider should fall back to global settings."""
        write_env_file(temp_project_dir, "AGENT_PROVIDER=opencode")

        write_global_settings(
            temp_global_settings,
            {
                "globalOpencodeProvider": "google-gemini",
                "globalOpencodeModel": "gemini-pro",
            },
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "opencode"
        assert config["opencode_provider"] == "google-gemini"
        assert config["opencode_model"] == "gemini-pro"

    def test_opencode_provider_normalization(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """OpenCode provider ID should be normalized."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=OpenAI
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["opencode_provider"] == "openai"


# =============================================================================
# Test: Global Credential Inheritance
# =============================================================================


class TestGlobalCredentialInheritance:
    """Test global credential inheritance and lookup."""

    def test_is_global_flag_from_env(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """is_global flag should be read from project .env."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
AGENT_PROVIDER_IS_GLOBAL=true
OPENCODE_PROVIDER=openai
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["is_global"] is True

    def test_is_global_from_credential_reference(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """is_global should be set when credential reference has isGlobal=true."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":true}}
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["is_global"] is True

    def test_global_credential_lookup(self, temp_global_settings: Path) -> None:
        """get_global_credential should find credentials by normalized ID."""
        settings = {
            "providerCredentials": {
                "openai": {
                    "displayName": "OpenAI",
                    "apiKey": "sk-test123",
                    "defaultModel": "gpt-4o",
                }
            }
        }
        write_global_settings(temp_global_settings, settings)

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded_settings = load_global_settings()
            credential = get_global_credential(loaded_settings, "openai")

        assert credential is not None
        assert credential["apiKey"] == "sk-test123"
        assert credential["displayName"] == "OpenAI"

    def test_global_credential_lookup_with_normalization(
        self, temp_global_settings: Path
    ) -> None:
        """get_global_credential should normalize the provider ID before lookup."""
        settings = {
            "providerCredentials": {
                "google-gemini": {
                    "displayName": "Google Gemini",
                    "apiKey": "test-key-123",
                }
            }
        }
        write_global_settings(temp_global_settings, settings)

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded_settings = load_global_settings()
            # Pass unnormalized ID
            credential = get_global_credential(loaded_settings, "Google Gemini")

        assert credential is not None
        assert credential["apiKey"] == "test-key-123"

    def test_missing_global_credential_returns_none(
        self, temp_global_settings: Path
    ) -> None:
        """get_global_credential should return None for missing credentials."""
        write_global_settings(temp_global_settings, {"providerCredentials": {}})

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded_settings = load_global_settings()
            credential = get_global_credential(loaded_settings, "nonexistent")

        assert credential is None


# =============================================================================
# Test: Provider Status
# =============================================================================


class TestProviderStatus:
    """Test get_provider_status() function."""

    def test_status_with_default_config(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should reflect default configuration."""
        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["provider"] == "claude_code"
        assert status["source"] == "default"
        assert status["isConfigured"] is False  # No OAuth token

    def test_status_with_claude_code_token_in_env(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should show configured when OAuth token is present."""
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"}):
            with patch.object(
                _provider_info,
                "get_global_settings_path",
                return_value=temp_global_settings,
            ):
                status = get_provider_status(temp_project_dir)

        assert status["provider"] == "claude_code"
        assert status["isConfigured"] is True
        assert status["credentialSources"]["claude_code"] == "global"

    def test_status_with_opencode_missing_provider(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should show error when OpenCode provider not selected."""
        write_env_file(temp_project_dir, "AGENT_PROVIDER=opencode")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["provider"] == "opencode"
        assert status["isConfigured"] is False
        assert "OpenCode provider not selected" in status["errors"]

    def test_status_with_opencode_missing_credentials(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should show error when OpenCode credentials are missing."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["provider"] == "opencode"
        assert status["isConfigured"] is False
        assert status["credentialSources"]["openai"] == "missing"

    def test_status_with_opencode_global_credential(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should show configured when using global credentials."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":true}}
""",
        )

        write_global_settings(
            temp_global_settings,
            {"providerCredentials": {"openai": {"apiKey": "sk-test123"}}},
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["provider"] == "opencode"
        assert status["isConfigured"] is True
        assert status["credentialSources"]["openai"] == "global"

    def test_status_with_opencode_project_credential(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Status should show configured when using project credentials."""
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":false,"apiKey":"sk-project-key"}}
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["provider"] == "opencode"
        assert status["isConfigured"] is True
        assert status["credentialSources"]["openai"] == "project"


# =============================================================================
# Test: Provider Configuration Validation
# =============================================================================


class TestProviderConfigValidation:
    """Test validate_provider_config() function."""

    def test_validate_valid_claude_code_config(self) -> None:
        """Valid Claude Code config should pass validation."""
        config = {"agentProvider": "claude_code"}
        result = validate_provider_config(config)

        assert result["isValid"] is True
        assert len(result["errors"]) == 0

    def test_validate_invalid_provider_type(self) -> None:
        """Invalid provider type should fail validation."""
        config = {"agentProvider": "invalid_provider"}
        result = validate_provider_config(config)

        assert result["isValid"] is False
        assert any("Invalid agent provider" in e for e in result["errors"])

    def test_validate_opencode_without_provider(self) -> None:
        """OpenCode without provider selection should fail validation."""
        config = {"agentProvider": "opencode"}
        result = validate_provider_config(config)

        assert result["isValid"] is False
        assert any("OpenCode provider is required" in e for e in result["errors"])

    def test_validate_opencode_with_valid_provider(
        self, temp_global_settings: Path
    ) -> None:
        """OpenCode with valid provider and credentials should pass."""
        write_global_settings(
            temp_global_settings,
            {"providerCredentials": {"openai": {"apiKey": "sk-test123"}}},
        )

        config = {
            "agentProvider": "opencode",
            "opencodeProvider": "openai",
            "agentProviderIsGlobal": True,
        }

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            result = validate_provider_config(config)

        assert result["isValid"] is True

    def test_validate_opencode_with_missing_global_credential(
        self, temp_global_settings: Path
    ) -> None:
        """OpenCode with missing global credential should fail."""
        write_global_settings(temp_global_settings, {"providerCredentials": {}})

        config = {
            "agentProvider": "opencode",
            "opencodeProvider": "openai",
            "agentProviderIsGlobal": True,
        }

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            result = validate_provider_config(config)

        assert result["isValid"] is False
        assert any("not found" in e for e in result["errors"])

    def test_validate_opencode_with_project_credential(self) -> None:
        """OpenCode with project credential should pass."""
        config = {
            "agentProvider": "opencode",
            "opencodeProvider": "openai",
            "providerCredentials": {"openai": {"isGlobal": False, "apiKey": "sk-test"}},
        }

        result = validate_provider_config(config)

        assert result["isValid"] is True

    def test_validate_opencode_missing_project_credential(self) -> None:
        """OpenCode without project credential should fail."""
        config = {
            "agentProvider": "opencode",
            "opencodeProvider": "openai",
            "providerCredentials": {"openai": {"isGlobal": False}},  # No apiKey
        }

        result = validate_provider_config(config)

        assert result["isValid"] is False
        assert any("API key required" in e for e in result["errors"])

    def test_validate_warns_conflicting_credential(self) -> None:
        """Should warn when credential has both isGlobal and apiKey."""
        config = {
            "agentProvider": "opencode",
            "opencodeProvider": "openai",
            "providerCredentials": {
                "openai": {"isGlobal": True, "apiKey": "sk-test"}  # Conflicting
            },
        }

        result = validate_provider_config(config)

        assert any("will be ignored" in w for w in result["warnings"])


# =============================================================================
# Test: API Key Format Validation
# =============================================================================


class TestApiKeyFormatValidation:
    """Test validate_api_key_format() function."""

    def test_valid_openai_key(self) -> None:
        """Valid OpenAI key should pass."""
        result = validate_api_key_format("openai", "sk-test123")
        assert result is None

    def test_invalid_openai_key(self) -> None:
        """Invalid OpenAI key should return error."""
        result = validate_api_key_format("openai", "invalid-key")
        assert result is not None
        assert "sk-" in result

    def test_valid_anthropic_key(self) -> None:
        """Valid Anthropic key should pass."""
        result = validate_api_key_format("anthropic", "sk-ant-test123")
        assert result is None

    def test_invalid_anthropic_key(self) -> None:
        """Invalid Anthropic key should return error."""
        result = validate_api_key_format("anthropic", "sk-test123")
        assert result is not None
        assert "sk-ant-" in result

    def test_unknown_provider_accepts_any_key(self) -> None:
        """Unknown provider should accept any key format."""
        result = validate_api_key_format("custom-provider", "any-format-key")
        assert result is None

    def test_empty_key_returns_error(self) -> None:
        """Empty key should return error."""
        result = validate_api_key_format("openai", "")
        assert result is not None


# =============================================================================
# Test: Provider Credentials Parsing
# =============================================================================


class TestProviderCredentialsParsing:
    """Test parse_provider_credentials() function."""

    def test_parse_valid_json(self) -> None:
        """Valid JSON should be parsed correctly."""
        json_str = '{"openai":{"isGlobal":true}}'
        result = parse_provider_credentials(json_str)

        assert result == {"openai": {"isGlobal": True}}

    def test_parse_complex_credentials(self) -> None:
        """Complex credentials should be parsed correctly."""
        json_str = '{"openai":{"isGlobal":false,"apiKey":"sk-test","model":"gpt-4o"}}'
        result = parse_provider_credentials(json_str)

        assert result["openai"]["isGlobal"] is False
        assert result["openai"]["apiKey"] == "sk-test"
        assert result["openai"]["model"] == "gpt-4o"

    def test_parse_empty_string(self) -> None:
        """Empty string should return empty dict."""
        result = parse_provider_credentials("")
        assert result == {}

    def test_parse_none(self) -> None:
        """None should return empty dict."""
        result = parse_provider_credentials(None)
        assert result == {}

    def test_parse_invalid_json(self) -> None:
        """Invalid JSON should return empty dict."""
        result = parse_provider_credentials("{invalid json}")
        assert result == {}

    def test_parse_non_dict_json(self) -> None:
        """Non-dict JSON should return empty dict."""
        result = parse_provider_credentials('["array", "not", "dict"]')
        assert result == {}


# =============================================================================
# Test: Project Environment Loading
# =============================================================================


class TestProjectEnvironmentLoading:
    """Test load_project_env() function."""

    def test_load_existing_env_file(self, temp_project_dir: Path) -> None:
        """Should load existing .env file correctly."""
        write_env_file(
            temp_project_dir,
            """
# Comment line
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o
""",
        )

        env = load_project_env(temp_project_dir)

        assert env["AGENT_PROVIDER"] == "opencode"
        assert env["OPENCODE_PROVIDER"] == "openai"
        assert env["OPENCODE_MODEL"] == "gpt-4o"

    def test_load_nonexistent_env_file(self, temp_project_dir: Path) -> None:
        """Should return empty dict for nonexistent .env file."""
        env = load_project_env(temp_project_dir)
        assert env == {}

    def test_load_env_with_quoted_values(self, temp_project_dir: Path) -> None:
        """Should handle quoted values correctly."""
        write_env_file(
            temp_project_dir,
            """
PROVIDER_CREDENTIALS='{"openai":{"isGlobal":true}}'
MODEL="gpt-4o"
""",
        )

        env = load_project_env(temp_project_dir)

        assert env["PROVIDER_CREDENTIALS"] == '{"openai":{"isGlobal":true}}'
        assert env["MODEL"] == "gpt-4o"


# =============================================================================
# Test: Global Settings Loading
# =============================================================================


class TestGlobalSettingsLoading:
    """Test load_global_settings() function."""

    def test_load_existing_settings(self, temp_global_settings: Path) -> None:
        """Should load existing settings file correctly."""
        settings = {
            "globalDefaultProvider": "opencode",
            "providerCredentials": {"openai": {"apiKey": "sk-test"}},
        }
        write_global_settings(temp_global_settings, settings)

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded = load_global_settings()

        assert loaded["globalDefaultProvider"] == "opencode"
        assert loaded["providerCredentials"]["openai"]["apiKey"] == "sk-test"

    def test_load_nonexistent_settings(self, temp_global_settings: Path) -> None:
        """Should return empty dict for nonexistent settings file."""
        # Don't create the file
        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded = load_global_settings()

        assert loaded == {}

    def test_load_invalid_json_settings(self, temp_global_settings: Path) -> None:
        """Should return empty dict for invalid JSON."""
        temp_global_settings.parent.mkdir(parents=True, exist_ok=True)
        temp_global_settings.write_text("{invalid json}")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            loaded = load_global_settings()

        assert loaded == {}


# =============================================================================
# Test: Provider Switching
# =============================================================================


class TestProviderSwitching:
    """Test switching between providers."""

    def test_switch_from_claude_code_to_opencode(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Should correctly switch from Claude Code to OpenCode."""
        # Start with Claude Code
        write_env_file(temp_project_dir, "AGENT_PROVIDER=claude_code")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config1 = get_provider_config(temp_project_dir, cli_provider=None)

        assert config1["provider"] == "claude_code"

        # Switch to OpenCode
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config2 = get_provider_config(temp_project_dir, cli_provider=None)

        assert config2["provider"] == "opencode"
        assert config2["opencode_provider"] == "openai"

    def test_cli_flag_enables_quick_switching(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """CLI flag should enable quick switching without file changes."""
        # Project configured for Claude Code
        write_env_file(temp_project_dir, "AGENT_PROVIDER=claude_code")

        # Quick switch to OpenCode via CLI
        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider="opencode")

        assert config["provider"] == "opencode"
        assert config["source"] == "cli_flag"


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_env_file(self, temp_project_dir: Path) -> None:
        """Empty .env file should be handled gracefully."""
        write_env_file(temp_project_dir, "")
        env = load_project_env(temp_project_dir)
        assert env == {}

    def test_env_file_with_only_comments(self, temp_project_dir: Path) -> None:
        """Env file with only comments should return empty dict."""
        write_env_file(
            temp_project_dir,
            """
# This is a comment
# Another comment
""",
        )
        env = load_project_env(temp_project_dir)
        assert env == {}

    def test_provider_config_with_whitespace(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Provider config with extra whitespace should be handled."""
        write_env_file(temp_project_dir, "AGENT_PROVIDER=  opencode  ")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        # Should be trimmed and recognized
        assert config["provider"] == "opencode"

    def test_case_insensitive_provider_type(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Provider type should be case-insensitive."""
        write_env_file(temp_project_dir, "AGENT_PROVIDER=OPENCODE")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)

        assert config["provider"] == "opencode"

    def test_nonexistent_project_dir(self, temp_global_settings: Path) -> None:
        """Nonexistent project directory should be handled gracefully."""
        nonexistent = Path("/nonexistent/project/dir")

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(nonexistent)

        # Should still return a status with default provider
        assert status["provider"] == "claude_code"
        assert (
            "does not exist" in str(status.get("error", "")) or status["errors"] == []
        )


# =============================================================================
# Test: Integration Scenarios
# =============================================================================


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_typical_opencode_setup(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Test typical OpenCode setup with global credentials."""
        # User has configured OpenAI globally
        write_global_settings(
            temp_global_settings,
            {
                "globalDefaultProvider": "opencode",
                "globalOpencodeProvider": "openai",
                "providerCredentials": {
                    "openai": {
                        "displayName": "OpenAI",
                        "apiKey": "sk-production-key",
                        "defaultModel": "gpt-4o",
                    }
                },
            },
        )

        # Project uses global settings
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":true}}
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            config = get_provider_config(temp_project_dir, cli_provider=None)
            status = get_provider_status(temp_project_dir)

        assert config["provider"] == "opencode"
        assert config["opencode_provider"] == "openai"
        assert config["is_global"] is True
        assert status["isConfigured"] is True
        assert status["credentialSources"]["openai"] == "global"

    def test_project_override_scenario(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Test project overriding global credentials."""
        # Global has OpenAI configured
        write_global_settings(
            temp_global_settings,
            {
                "globalDefaultProvider": "opencode",
                "globalOpencodeProvider": "openai",
                "providerCredentials": {
                    "openai": {"apiKey": "sk-global-key"},
                },
            },
        )

        # Project overrides with project-specific key
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":false,"apiKey":"sk-project-specific-key"}}
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["isConfigured"] is True
        assert status["credentialSources"]["openai"] == "project"

    def test_missing_global_credential_error(
        self, temp_project_dir: Path, temp_global_settings: Path
    ) -> None:
        """Test error when referencing missing global credential."""
        # No global credentials configured
        write_global_settings(temp_global_settings, {"providerCredentials": {}})

        # Project references global that doesn't exist
        write_env_file(
            temp_project_dir,
            """
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
PROVIDER_CREDENTIALS={"openai":{"isGlobal":true}}
""",
        )

        with patch.object(
            _provider_info,
            "get_global_settings_path",
            return_value=temp_global_settings,
        ):
            status = get_provider_status(temp_project_dir)

        assert status["isConfigured"] is False
        assert "Global credential 'openai' not found" in status["errors"]
        assert status["credentialSources"]["openai"] == "missing"
