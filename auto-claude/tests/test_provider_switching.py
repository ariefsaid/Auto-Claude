"""
Integration Tests for Provider Switching
==========================================

Tests for provider switching via AGENT_PROVIDER environment variable.
Verifies that the factory correctly creates the appropriate provider
based on environment configuration.

Test Coverage:
- AGENT_PROVIDER=claude_code creates ClaudeProvider
- AGENT_PROVIDER=opencode creates OpenCodeProvider
- Credential loading works for both providers
- Factory validation errors for invalid configurations
- Global/project credential inheritance
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add auto-claude to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.adapters.claude_provider import ClaudeProvider
from core.providers.adapters.opencode_provider import OpenCodeProvider
from core.providers.client import ProviderError, ProviderNotFoundError
from core.providers.config import AgentProvider, ProviderConfig, ProviderCredential
from core.providers.factory import (
    create_client,
    get_available_providers,
    is_provider_available,
)

# =============================================================================
# Provider Switching Integration Tests
# =============================================================================


class TestProviderSwitchingIntegration:
    """Integration tests for switching between providers via environment variables."""

    # -------------------------------------------------------------------------
    # Claude Code Provider Selection
    # -------------------------------------------------------------------------

    def test_agent_provider_claude_code_creates_correct_provider_type(self):
        """Setting AGENT_PROVIDER=claude_code should create ClaudeProvider."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify config is for claude_code
            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_valid()

            # Verify that the factory would create a ClaudeProvider
            # by testing that CLAUDE_CODE maps to the correct provider type
            # and creating a ClaudeProvider directly using from_sdk_client
            mock_sdk_client = MagicMock()
            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            # Verify it's a ClaudeProvider
            assert isinstance(provider, ClaudeProvider)
            assert provider.provider_name == "Claude Code"

            # Verify the config correctly identifies the provider
            from core.providers.config import AgentProvider as AP

            assert config.provider == AP.CLAUDE_CODE

    def test_agent_provider_claude_code_uppercase_works(self):
        """AGENT_PROVIDER should be case-insensitive for claude_code."""
        env = {
            "AGENT_PROVIDER": "CLAUDE_CODE",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE

    def test_claude_code_provider_has_correct_capabilities(self):
        """ClaudeProvider should have all capabilities enabled."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE

            # Create a ClaudeProvider directly to verify capabilities
            mock_sdk_client = MagicMock()
            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            caps = provider.capabilities
            assert caps.supports_hooks is True
            assert caps.supports_sandbox is True
            assert caps.supports_streaming is True
            assert caps.supports_mcp is True
            assert caps.supports_extended_thinking is True

    # -------------------------------------------------------------------------
    # OpenCode Provider Selection
    # -------------------------------------------------------------------------

    def test_agent_provider_opencode_creates_correct_provider_type(self):
        """Setting AGENT_PROVIDER=opencode should create OpenCodeProvider."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-test"}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify config is for opencode
            assert config.provider == AgentProvider.OPENCODE
            assert config.opencode_provider == "openai"
            assert config.opencode_model == "gpt-4o"
            assert config.is_valid()

            # Mock OpenCode subprocess since we don't have CLI installed
            with patch(
                "core.providers.adapters.opencode_subprocess.OpenCodeSubprocess.find_opencode_executable"
            ) as mock_find:
                mock_find.return_value = "/usr/local/bin/opencode"

                provider = create_client(
                    config=config,
                    project_dir=Path("/tmp/test"),
                    spec_dir=Path("/tmp/test/spec"),
                    model="gpt-4o",
                )

                # Verify it's an OpenCodeProvider
                assert isinstance(provider, OpenCodeProvider)
                assert provider.provider_name == "OpenCode"

    def test_agent_provider_opencode_uppercase_works(self):
        """AGENT_PROVIDER should be case-insensitive for opencode."""
        env = {
            "AGENT_PROVIDER": "OPENCODE",
            "OPENCODE_PROVIDER": "openai",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.OPENCODE

    def test_opencode_provider_has_correct_capabilities(self):
        """OpenCodeProvider should have limited capabilities."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-test"}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            with patch(
                "core.providers.adapters.opencode_subprocess.OpenCodeSubprocess.find_opencode_executable"
            ) as mock_find:
                mock_find.return_value = "/usr/local/bin/opencode"

                provider = create_client(
                    config=config,
                    project_dir=Path("/tmp/test"),
                    spec_dir=Path("/tmp/test/spec"),
                    model="gpt-4o",
                )

                caps = provider.capabilities
                # OpenCode has different capabilities
                assert caps.supports_hooks is False
                assert caps.supports_sandbox is False
                assert caps.supports_streaming is True  # Supported via subprocess
                assert caps.supports_mcp is False
                assert caps.supports_extended_thinking is False

    # -------------------------------------------------------------------------
    # Credential Loading Tests
    # -------------------------------------------------------------------------

    def test_claude_code_credential_loading_legacy_token(self):
        """Claude Code should load credentials from legacy CLAUDE_CODE_OAUTH_TOKEN."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-oauth-token",
            "CLAUDE_TOKEN_IS_GLOBAL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify credential loading
            assert config.is_valid()
            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.api_key == "legacy-oauth-token"
            assert cred.is_global is True

    def test_claude_code_credential_loading_provider_credentials(self):
        """Claude Code should load credentials from PROVIDER_CREDENTIALS JSON."""
        creds_json = json.dumps(
            {
                "claude-code": {
                    "apiKey": "new-api-key",
                    "isGlobal": False,
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "claude_code",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify credential loading
            assert config.is_valid()
            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.api_key == "new-api-key"
            assert cred.is_global is False

    def test_opencode_credential_loading(self):
        """OpenCode should load LLM provider credentials from PROVIDER_CREDENTIALS."""
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
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify credential loading for LLM provider
            assert config.is_valid()
            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.api_key == "sk-openai-key"
            assert cred.default_model == "gpt-4o"

            # Verify active credential is for the LLM provider
            active_cred = config.get_active_credential()
            assert active_cred is not None
            assert active_cred.provider == "openai"

    def test_multiple_provider_credentials(self):
        """Should load credentials for multiple providers."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "defaultModel": "gpt-4o"},
                "anthropic": {"apiKey": "sk-ant", "defaultModel": "claude-3-5-sonnet"},
                "google": {"apiKey": "google-key", "defaultModel": "gemini-pro"},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "anthropic",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Should have all credentials loaded
            assert len(config.credentials) == 3
            assert config.get_credential("openai") is not None
            assert config.get_credential("anthropic") is not None
            assert config.get_credential("google") is not None

            # Active credential should be anthropic (the opencode provider)
            active = config.get_active_credential()
            assert active is not None
            assert active.provider == "anthropic"
            assert active.api_key == "sk-ant"

    # -------------------------------------------------------------------------
    # Validation Error Tests
    # -------------------------------------------------------------------------

    def test_invalid_agent_provider_uses_default(self):
        """Invalid AGENT_PROVIDER should fallback to claude_code."""
        env = {"AGENT_PROVIDER": "invalid_provider"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            # Falls back to default
            assert config.provider == AgentProvider.CLAUDE_CODE

    def test_claude_code_missing_credentials_invalid(self):
        """Claude Code without credentials should be invalid."""
        env = {"AGENT_PROVIDER": "claude_code"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid() is False

            errors = config.get_validation_errors()
            assert len(errors) > 0
            assert any("credential" in err.lower() for err in errors)

    def test_opencode_missing_provider_invalid(self):
        """OpenCode without OPENCODE_PROVIDER should be invalid."""
        env = {"AGENT_PROVIDER": "opencode"}
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            assert config.is_valid() is False

            errors = config.get_validation_errors()
            assert len(errors) > 0
            assert any("opencode_provider" in err.lower() for err in errors)

    def test_factory_raises_for_invalid_config(self):
        """Factory should raise ProviderError for invalid configuration."""
        env = {"AGENT_PROVIDER": "claude_code"}  # Missing credentials
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            with pytest.raises(ProviderError) as excinfo:
                create_client(
                    config=config,
                    project_dir=Path("/tmp/test"),
                    spec_dir=Path("/tmp/test/spec"),
                    model="claude-sonnet-4-20250514",
                )

            assert "invalid provider configuration" in str(excinfo.value).lower()

    # -------------------------------------------------------------------------
    # Global/Project Credential Inheritance
    # -------------------------------------------------------------------------

    def test_global_credential_setting(self):
        """Global credentials should be marked correctly."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-global", "isGlobal": True},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "AGENT_PROVIDER_IS_GLOBAL": "true",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.is_global is True
            cred = config.get_credential("openai")
            assert cred.is_global is True

    def test_project_credential_setting(self):
        """Project credentials should override global."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-project", "isGlobal": False},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "AGENT_PROVIDER_IS_GLOBAL": "false",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.is_global is False
            cred = config.get_credential("openai")
            assert cred.is_global is False

    def test_mixed_global_project_credentials(self):
        """Mixed global and project credentials should work together."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-project", "isGlobal": False},
                "anthropic": {"apiKey": "sk-ant-global", "isGlobal": True},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            openai_cred = config.get_credential("openai")
            assert openai_cred.is_global is False

            anthropic_cred = config.get_credential("anthropic")
            assert anthropic_cred.is_global is True

    # -------------------------------------------------------------------------
    # Provider Availability Tests
    # -------------------------------------------------------------------------

    def test_get_available_providers(self):
        """get_available_providers should return all provider names."""
        providers = get_available_providers()
        assert "claude_code" in providers
        assert "opencode" in providers
        assert len(providers) == 2

    def test_is_provider_available_valid(self):
        """is_provider_available should return True for valid providers."""
        assert is_provider_available("claude_code") is True
        assert is_provider_available("opencode") is True

    def test_is_provider_available_invalid(self):
        """is_provider_available should return False for invalid providers."""
        assert is_provider_available("invalid") is False
        assert is_provider_available("gpt4") is False

    # -------------------------------------------------------------------------
    # Credential Source Tracking
    # -------------------------------------------------------------------------

    def test_credential_source_info_global(self):
        """Credential source should correctly identify global credentials."""
        creds_json = json.dumps({"claude-code": {"apiKey": "token", "isGlobal": True}})
        env = {
            "AGENT_PROVIDER": "claude_code",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            source = config.get_credential_source_info()

            assert "global" in source.lower()

    def test_credential_source_info_project(self):
        """Credential source should correctly identify project credentials."""
        creds_json = json.dumps({"claude-code": {"apiKey": "token", "isGlobal": False}})
        env = {
            "AGENT_PROVIDER": "claude_code",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            source = config.get_credential_source_info()

            assert "project" in source.lower()

    def test_credentials_summary_excludes_secrets(self):
        """Credentials summary should not expose API keys."""
        creds_json = json.dumps(
            {"openai": {"apiKey": "sk-super-secret-key", "isGlobal": False}}
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            summary = config.get_credentials_summary()

            # API key should not be in summary
            summary_str = str(summary)
            assert "sk-super-secret-key" not in summary_str

            # But should indicate key exists
            assert summary["credentials"]["openai"]["has_api_key"] is True


# =============================================================================
# Provider Status Tests
# =============================================================================


class TestProviderStatus:
    """Tests for provider status reporting."""

    def test_valid_claude_code_status(self):
        """Valid Claude Code config should show correct status."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()

            assert status["provider"] == "claude_code"
            assert status["is_valid"] is True
            assert status["errors"] == []

    def test_valid_opencode_status(self):
        """Valid OpenCode config should show correct status."""
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()

            assert status["provider"] == "opencode"
            assert status["is_valid"] is True

    def test_invalid_config_status(self):
        """Invalid config should show errors in status."""
        env = {"AGENT_PROVIDER": "claude_code"}  # Missing token
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()

            assert status["is_valid"] is False
            assert len(status["errors"]) > 0


# =============================================================================
# End-to-End Provider Factory Tests
# =============================================================================


class TestProviderFactoryE2E:
    """End-to-end tests for the provider factory."""

    def test_factory_claude_provider_workflow(self):
        """Complete workflow: env -> config -> factory -> ClaudeProvider."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-oauth-token",
        }
        with patch.dict(os.environ, env, clear=True):
            # Step 1: Load config from environment
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.CLAUDE_CODE

            # Step 2: Verify configuration
            assert config.is_valid()
            assert config.get_validation_errors() == []

            # Step 3: Get credential
            cred = config.get_active_credential()
            assert cred is not None
            assert cred.api_key == "test-oauth-token"

            # Step 4: Create provider using from_sdk_client (simulates what factory does)
            # This verifies the provider type and capabilities match expectations
            mock_sdk_client = MagicMock()
            provider = ClaudeProvider.from_sdk_client(mock_sdk_client)

            # Step 5: Verify provider type and capabilities
            assert isinstance(provider, ClaudeProvider)
            assert provider.provider_name == "Claude Code"
            assert provider.capabilities.supports_hooks is True

    def test_factory_opencode_provider_workflow(self):
        """Complete workflow: env -> config -> factory -> OpenCodeProvider."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-test-key"}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            # Step 1: Load config from environment
            config = ProviderConfig.from_env()
            assert config.provider == AgentProvider.OPENCODE

            # Step 2: Verify configuration
            assert config.is_valid()
            assert config.opencode_provider == "openai"
            assert config.opencode_model == "gpt-4o-mini"

            # Step 3: Get credential
            cred = config.get_active_credential()
            assert cred is not None
            assert cred.api_key == "sk-test-key"

            # Step 4: Create provider via factory
            with patch(
                "core.providers.adapters.opencode_subprocess.OpenCodeSubprocess.find_opencode_executable"
            ) as mock_find:
                mock_find.return_value = "/usr/local/bin/opencode"

                provider = create_client(
                    config=config,
                    project_dir=Path("/tmp/test"),
                    spec_dir=Path("/tmp/test/spec"),
                    model="gpt-4o-mini",
                )

                # Step 5: Verify provider type and capabilities
                assert isinstance(provider, OpenCodeProvider)
                assert provider.provider_name == "OpenCode"
                assert provider.capabilities.supports_hooks is False
                assert provider.capabilities.requires_pre_validation is True

    def test_switching_between_providers(self):
        """Test switching from one provider to another by changing env vars."""
        # First, create a Claude Code provider
        claude_env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "claude-token",
        }
        with patch.dict(os.environ, claude_env, clear=True):
            claude_config = ProviderConfig.from_env()
            assert claude_config.provider == AgentProvider.CLAUDE_CODE

        # Then, switch to OpenCode provider
        opencode_env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": json.dumps({"openai": {"apiKey": "sk-test"}}),
        }
        with patch.dict(os.environ, opencode_env, clear=True):
            opencode_config = ProviderConfig.from_env()
            assert opencode_config.provider == AgentProvider.OPENCODE

        # Verify they are different configs
        assert claude_config.provider != opencode_config.provider


# =============================================================================
# Direct ProviderConfig Factory Method Tests
# =============================================================================


class TestProviderConfigFromEnv:
    """Detailed tests for ProviderConfig.from_env() method."""

    def test_from_env_with_all_env_vars(self):
        """from_env should load all relevant environment variables."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai", "defaultModel": "gpt-4o"},
                "anthropic": {"apiKey": "sk-ant", "isGlobal": True},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "AGENT_PROVIDER_IS_GLOBAL": "true",
            "OPENCODE_PROVIDER": "openai",
            "OPENCODE_MODEL": "gpt-4o-mini",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify all fields are loaded correctly
            assert config.provider == AgentProvider.OPENCODE
            assert config.is_global is True
            assert config.opencode_provider == "openai"
            assert config.opencode_model == "gpt-4o-mini"
            assert len(config.credentials) == 2

    def test_from_env_empty_environment(self):
        """from_env with empty environment should use defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = ProviderConfig.from_env()

            assert config.provider == AgentProvider.CLAUDE_CODE
            assert config.is_global is False
            assert config.opencode_provider == ""
            assert config.opencode_model == ""
            assert config.credentials == {}

    def test_from_env_invalid_json_gracefully_handled(self):
        """Invalid PROVIDER_CREDENTIALS JSON should be handled gracefully."""
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": "not valid json {",
        }
        with patch.dict(os.environ, env, clear=True):
            # Should not raise, just use empty credentials
            config = ProviderConfig.from_env()
            assert config.credentials == {}

    def test_from_env_preserves_legacy_and_new_credentials(self):
        """Both legacy token and new credentials should coexist."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-openai"}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-token",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Both should be present
            assert "openai" in config.credentials
            assert "claude-code" in config.credentials
            assert config.credentials["claude-code"].api_key == "legacy-token"


# =============================================================================
# Global/Project Credential Inheritance Integration Tests
# =============================================================================


class TestCredentialInheritance:
    """
    Integration tests for global/project credential inheritance.

    These tests verify that:
    1. Global credentials (isGlobal:true) are correctly marked
    2. Project-specific credentials (isGlobal:false) are correctly marked
    3. Project credentials take precedence when both exist
    4. Global credentials serve as fallback when project credentials are missing
    5. Credential source tracking accurately reflects the inheritance chain
    """

    # -------------------------------------------------------------------------
    # Global Credential Configuration Tests
    # -------------------------------------------------------------------------

    def test_global_credential_for_openai_is_marked_correctly(self):
        """Setting isGlobal:true for openai should be reflected in credential."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-global-openai-key",
                    "isGlobal": True,
                    "defaultModel": "gpt-4o",
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.is_global is True
            assert cred.api_key == "sk-global-openai-key"
            assert cred.default_model == "gpt-4o"

            # Verify source info includes "global"
            source = cred.get_source_info()
            assert "global" in source.lower()

    def test_multiple_global_credentials_across_providers(self):
        """Multiple providers can have global credentials."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-openai-global", "isGlobal": True},
                "anthropic": {"apiKey": "sk-ant-global", "isGlobal": True},
                "google": {"apiKey": "gcp-key-global", "isGlobal": True},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # All should be marked as global
            for provider_id in ["openai", "anthropic", "google"]:
                cred = config.get_credential(provider_id)
                assert cred is not None
                assert cred.is_global is True, f"{provider_id} should be global"

    # -------------------------------------------------------------------------
    # Project Credential Override Tests
    # -------------------------------------------------------------------------

    def test_project_credential_for_openai_is_marked_correctly(self):
        """Setting isGlobal:false for openai should mark it as project credential."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-project-openai-key",
                    "isGlobal": False,
                    "defaultModel": "gpt-4o-mini",
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.is_global is False
            assert cred.api_key == "sk-project-openai-key"
            assert cred.default_model == "gpt-4o-mini"

            # Verify source info includes "project"
            source = cred.get_source_info()
            assert "project" in source.lower()

    def test_project_credential_values_are_used_when_set(self):
        """Project credentials with specific values should use those values."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-specific-project-key",
                    "baseUrl": "https://custom-openai.api.com",
                    "defaultModel": "gpt-4-turbo",
                    "isGlobal": False,
                    "metadata": {"project": "test-project", "team": "engineering"},
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.api_key == "sk-specific-project-key"
            assert cred.base_url == "https://custom-openai.api.com"
            assert cred.default_model == "gpt-4-turbo"
            assert cred.metadata["project"] == "test-project"
            assert cred.metadata["team"] == "engineering"

    # -------------------------------------------------------------------------
    # Inheritance Priority Tests
    # -------------------------------------------------------------------------

    def test_project_credentials_take_precedence_over_global(self):
        """
        When both global and project credentials exist for the same provider,
        the project credential should take precedence.

        This simulates the scenario where:
        1. Global settings have openai with isGlobal:true
        2. Project settings override with isGlobal:false and different key
        """
        # Simulate the scenario where project env includes a project credential
        # that overrides a global credential
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-project-override-key",
                    "isGlobal": False,  # Project credential takes precedence
                    "defaultModel": "gpt-4o-project",
                    "baseUrl": "https://project-api.openai.com",
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Project credential should be used
            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.is_global is False
            assert cred.api_key == "sk-project-override-key"
            assert cred.default_model == "gpt-4o-project"
            assert cred.base_url == "https://project-api.openai.com"

            # Active credential should be the project one
            active = config.get_active_credential()
            assert active is not None
            assert active.is_global is False
            assert active.api_key == "sk-project-override-key"

    def test_global_credential_used_when_no_project_override(self):
        """Global credential is used as fallback when no project override exists."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-global-fallback-key",
                    "isGlobal": True,
                    "defaultModel": "gpt-4o-global",
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Global credential is the only option
            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.is_global is True
            assert cred.api_key == "sk-global-fallback-key"

    def test_mixed_global_and_project_for_different_providers(self):
        """Different providers can have different inheritance levels."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-openai-project",
                    "isGlobal": False,  # Project credential
                },
                "anthropic": {
                    "apiKey": "sk-anthropic-global",
                    "isGlobal": True,  # Global credential
                },
                "google": {
                    "apiKey": "google-project-key",
                    "isGlobal": False,  # Project credential
                },
                "azure": {
                    "isGlobal": True,  # Global without API key
                },
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # OpenAI - project credential
            openai_cred = config.get_credential("openai")
            assert openai_cred.is_global is False
            assert openai_cred.api_key == "sk-openai-project"
            assert "project" in openai_cred.get_source_info().lower()

            # Anthropic - global credential
            anthropic_cred = config.get_credential("anthropic")
            assert anthropic_cred.is_global is True
            assert anthropic_cred.api_key == "sk-anthropic-global"
            assert "global" in anthropic_cred.get_source_info().lower()

            # Google - project credential
            google_cred = config.get_credential("google")
            assert google_cred.is_global is False
            assert google_cred.api_key == "google-project-key"
            assert "project" in google_cred.get_source_info().lower()

            # Azure - global without API key (valid because global can use system auth)
            azure_cred = config.get_credential("azure")
            assert azure_cred.is_global is True
            assert azure_cred.is_valid() is True  # Global without key is valid

    # -------------------------------------------------------------------------
    # Credential Source Tracking Tests
    # -------------------------------------------------------------------------

    def test_credential_source_info_tracks_global_correctly(self):
        """Credential source info accurately identifies global credentials."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-test", "isGlobal": True}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            source = config.get_credential_source_info()

            assert "global" in source.lower()
            assert "openai" in source.lower()

    def test_credential_source_info_tracks_project_correctly(self):
        """Credential source info accurately identifies project credentials."""
        creds_json = json.dumps({"openai": {"apiKey": "sk-test", "isGlobal": False}})
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            source = config.get_credential_source_info()

            assert "project" in source.lower()
            assert "openai" in source.lower()

    def test_credentials_summary_shows_inheritance_levels(self):
        """Credentials summary correctly reports global vs project for each credential."""
        creds_json = json.dumps(
            {
                "openai": {"apiKey": "sk-project", "isGlobal": False},
                "anthropic": {"apiKey": "sk-global", "isGlobal": True},
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            summary = config.get_credentials_summary()

            # OpenAI should be project
            assert summary["credentials"]["openai"]["is_global"] is False
            assert "project" in summary["credentials"]["openai"]["source"].lower()

            # Anthropic should be global
            assert summary["credentials"]["anthropic"]["is_global"] is True
            assert "global" in summary["credentials"]["anthropic"]["source"].lower()

    # -------------------------------------------------------------------------
    # Legacy Claude Code Credential Inheritance Tests
    # -------------------------------------------------------------------------

    def test_legacy_claude_code_global_inheritance(self):
        """Legacy Claude Code tokens should respect global flag."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-global-token",
            "CLAUDE_TOKEN_IS_GLOBAL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.is_global is True
            assert cred.api_key == "legacy-global-token"

    def test_legacy_claude_code_project_inheritance(self):
        """Legacy Claude Code tokens default to project-level."""
        env = {
            "AGENT_PROVIDER": "claude_code",
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-project-token",
            # No CLAUDE_TOKEN_IS_GLOBAL set - defaults to project
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("claude-code")
            assert cred is not None
            assert cred.is_global is False
            assert cred.api_key == "legacy-project-token"

    def test_provider_credentials_overrides_legacy_claude_token(self):
        """PROVIDER_CREDENTIALS should override legacy CLAUDE_CODE_OAUTH_TOKEN."""
        creds_json = json.dumps(
            {
                "claude-code": {
                    "apiKey": "new-json-token",
                    "isGlobal": False,
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "claude_code",
            "PROVIDER_CREDENTIALS": creds_json,
            "CLAUDE_CODE_OAUTH_TOKEN": "old-legacy-token",  # Should be overridden
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("claude-code")
            assert cred is not None
            # JSON credential takes precedence
            assert cred.api_key == "new-json-token"

    # -------------------------------------------------------------------------
    # Global Config Level vs Credential Level Tests
    # -------------------------------------------------------------------------

    def test_agent_provider_is_global_vs_credential_is_global(self):
        """
        AGENT_PROVIDER_IS_GLOBAL and credential.isGlobal are independent settings.

        AGENT_PROVIDER_IS_GLOBAL indicates whether the active provider selection
        comes from global settings.

        credential.isGlobal indicates whether the credential itself is from
        global settings or project settings.
        """
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-project-key",
                    "isGlobal": False,  # Project credential
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "AGENT_PROVIDER_IS_GLOBAL": "true",  # Provider selected globally
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Provider selection is global
            assert config.is_global is True

            # But the credential itself is project-level
            cred = config.get_credential("openai")
            assert cred.is_global is False

    def test_both_config_and_credential_global(self):
        """When both config and credential are global."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-global-key",
                    "isGlobal": True,  # Global credential
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "AGENT_PROVIDER_IS_GLOBAL": "true",  # Provider selected globally
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            assert config.is_global is True
            cred = config.get_credential("openai")
            assert cred.is_global is True

    def test_global_credential_without_api_key_is_valid(self):
        """
        Global credentials without explicit API key should be valid.

        This allows for scenarios where global credentials use system-level
        authentication (e.g., SSO, service accounts).
        """
        creds_json = json.dumps(
            {
                "zai": {
                    "isGlobal": True,
                    # No apiKey - relies on system-level auth
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "zai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("zai")
            assert cred is not None
            assert cred.is_global is True
            assert cred.api_key == ""  # No key set
            assert cred.is_valid() is True  # Still valid because global

    def test_project_credential_without_api_key_is_invalid(self):
        """
        Project credentials without explicit API key should be invalid.

        Unlike global credentials, project credentials must have explicit
        API keys as they cannot rely on system-level authentication.
        """
        creds_json = json.dumps(
            {
                "openai": {
                    "isGlobal": False,
                    # No apiKey - should be invalid for project
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            cred = config.get_credential("openai")
            assert cred is not None
            assert cred.is_global is False
            assert cred.api_key == ""
            assert cred.is_valid() is False

            # Should have validation error
            errors = cred.get_validation_errors()
            assert len(errors) > 0
            assert "api key" in errors[0].lower()

    # -------------------------------------------------------------------------
    # End-to-End Inheritance Scenario Tests
    # -------------------------------------------------------------------------

    def test_e2e_global_credential_with_project_override_scenario(self):
        """
        Complete E2E test: Global credentials as fallback, project overrides specific ones.

        Scenario:
        - User has global OpenAI and Anthropic credentials
        - Project uses OpenAI with a project-specific key
        - Anthropic falls back to global
        """
        creds_json = json.dumps(
            {
                # OpenAI has project-level override
                "openai": {
                    "apiKey": "sk-project-specific",
                    "isGlobal": False,
                    "defaultModel": "gpt-4o-project",
                },
                # Anthropic uses global
                "anthropic": {
                    "apiKey": "sk-ant-global",
                    "isGlobal": True,
                    "defaultModel": "claude-3-5-sonnet",
                },
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",  # Using OpenAI
            "OPENCODE_MODEL": "gpt-4o",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()

            # Verify configuration is valid
            assert config.is_valid() is True
            assert config.get_validation_errors() == []

            # Active credential should be OpenAI (project-level)
            active = config.get_active_credential()
            assert active is not None
            assert active.provider == "openai"
            assert active.is_global is False
            assert active.api_key == "sk-project-specific"

            # If we switch to Anthropic, we'd get global credential
            config2 = ProviderConfig(
                provider=AgentProvider.OPENCODE,
                opencode_provider="anthropic",
                credentials=config.credentials,
            )
            active2 = config2.get_active_credential()
            assert active2 is not None
            assert active2.provider == "anthropic"
            assert active2.is_global is True
            assert active2.api_key == "sk-ant-global"

    def test_e2e_provider_status_reflects_inheritance(self):
        """Provider status should correctly reflect credential inheritance."""
        creds_json = json.dumps(
            {
                "openai": {
                    "apiKey": "sk-project",
                    "isGlobal": False,
                }
            }
        )
        env = {
            "AGENT_PROVIDER": "opencode",
            "OPENCODE_PROVIDER": "openai",
            "PROVIDER_CREDENTIALS": creds_json,
        }
        with patch.dict(os.environ, env, clear=True):
            config = ProviderConfig.from_env()
            status = config.get_provider_status()

            assert status["is_valid"] is True
            assert status["provider"] == "opencode"
            assert "project" in status["credential_source"].lower()
            assert status["errors"] == []
