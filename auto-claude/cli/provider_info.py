#!/usr/bin/env python3
"""
Provider Info CLI
==================

Python CLI helper for UI bridge. Provides provider status and validation
functions that can be called via subprocess from Electron IPC handlers.

Usage:
    python cli/provider_info.py get-status --project-dir /path/to/project
    python cli/provider_info.py validate --config '{"agentProvider": "opencode"}'

Functions:
    get_provider_status(project_dir) - Get current provider configuration status
    validate_provider_config(config_data) - Validate a provider configuration
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

# Ensure parent directory is in path for imports
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# Optional dotenv import with fallback
try:
    from dotenv import dotenv_values
except ImportError:
    # Fallback implementation for environments without python-dotenv
    def dotenv_values(filepath: str | Path) -> dict[str, str]:  # type: ignore[misc]
        """Simple .env file parser fallback."""
        result: dict[str, str] = {}
        path = Path(filepath) if isinstance(filepath, str) else filepath
        if not path.exists():
            return result
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Parse KEY=value format
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        # Remove surrounding quotes if present
                        if len(value) >= 2:
                            if (value.startswith('"') and value.endswith('"')) or (
                                value.startswith("'") and value.endswith("'")
                            ):
                                value = value[1:-1]
                        result[key] = value
        except OSError:
            pass
        return result


# ============================================
# Type Definitions (matching TypeScript types)
# ============================================

# Agent provider types
AgentProviderType = Literal["claude_code", "opencode"]

# Configuration source types
ConfigSource = Literal["cli_flag", "project_env", "global_settings", "default"]

# Credential source types
CredentialSource = Literal["global", "project", "missing"]


# ============================================
# Provider Normalization (must match TypeScript)
# ============================================


def normalize_provider_id(name: str) -> str:
    """
    Normalize a provider name to a consistent ID format.

    CRITICAL: This function must match TypeScript normalizeProviderId() exactly.

    Test cases that must match:
    - "OpenAI" -> "openai"
    - "Z.ai GLM 4.7" -> "zai-glm-47"
    - "Custom Provider" -> "custom-provider"
    - "  OpenAI  " -> "openai" (whitespace trimming)
    - "Custom---Provider" -> "custom-provider" (dash deduplication)
    - "Z.ai GLM 4.7!@#" -> "zai-glm-47" (special char removal)

    Args:
        name: The provider name to normalize

    Returns:
        Normalized provider ID
    """
    # Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
    normalized = name.lower().strip().replace(" ", "-")

    # Step 2: Remove all characters except a-z, 0-9, and dash
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)

    # Step 3: Collapse multiple consecutive dashes into a single dash
    normalized = re.sub(r"-+", "-", normalized)

    # Step 4: Remove leading and trailing dashes
    return normalized.strip("-")


# ============================================
# Global Settings Loader
# ============================================


def get_global_settings_path() -> Path:
    """
    Get the path to the global settings file.

    Returns:
        Path to ~/.config/auto-claude-ui/settings.json
    """
    # Use XDG_CONFIG_HOME on Linux, fall back to ~/.config
    if sys.platform == "darwin":
        # macOS: use ~/Library/Application Support for native apps
        # but auto-claude-ui uses ~/.config for consistency
        config_home = Path.home() / ".config"
    elif sys.platform == "win32":
        # Windows: use APPDATA
        config_home = Path(
            os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        )
    else:
        # Linux/Unix: use XDG_CONFIG_HOME or ~/.config
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return config_home / "auto-claude-ui" / "settings.json"


def load_global_settings() -> dict[str, Any]:
    """
    Load global settings from ~/.config/auto-claude-ui/settings.json.

    Returns:
        Settings dictionary, or empty dict if file doesn't exist or is invalid
    """
    settings_path = get_global_settings_path()

    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
            if isinstance(settings, dict):
                return settings
            return {}
    except (json.JSONDecodeError, OSError):
        return {}


def get_global_credential(
    settings: dict[str, Any], provider_id: str
) -> dict[str, Any] | None:
    """
    Get a global credential from settings by provider ID.

    Args:
        settings: Global settings dictionary
        provider_id: Normalized provider ID

    Returns:
        Credential dictionary if found, None otherwise
    """
    provider_credentials = settings.get("providerCredentials", {})
    if not isinstance(provider_credentials, dict):
        return None

    normalized_id = normalize_provider_id(provider_id)
    credential = provider_credentials.get(normalized_id)

    if not isinstance(credential, dict):
        return None

    return credential


# ============================================
# Project Environment Loader
# ============================================


def load_project_env(project_dir: Path) -> dict[str, str]:
    """
    Load project environment variables from .auto-claude/.env

    Args:
        project_dir: Project root directory

    Returns:
        Dictionary of environment variables
    """
    env_path = project_dir / ".auto-claude" / ".env"

    if not env_path.exists():
        return {}

    try:
        return dict(dotenv_values(env_path))
    except Exception:
        return {}


def parse_provider_credentials(json_str: str | None) -> dict[str, Any]:
    """
    Parse PROVIDER_CREDENTIALS JSON from environment.

    Args:
        json_str: JSON string from environment variable

    Returns:
        Parsed dictionary or empty dict on error
    """
    if not json_str or json_str.strip() == "":
        return {}

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except json.JSONDecodeError:
        return {}


# ============================================
# Provider Status Functions
# ============================================


def get_provider_status(project_dir: Path) -> dict[str, Any]:
    """
    Get the current provider configuration status for a project.

    Args:
        project_dir: Project root directory

    Returns:
        ProviderStatusResponse dictionary with:
        - provider: Current provider type
        - source: Configuration source (cli_flag, project_env, global_settings, default)
        - isConfigured: Whether the provider is properly configured
        - errors: List of configuration errors
        - credentialSources: Map of provider IDs to their credential source
    """
    errors: list[str] = []
    credential_sources: dict[str, CredentialSource] = {}

    # Load configurations
    project_env = load_project_env(project_dir)
    global_settings = load_global_settings()

    # Determine provider and source (priority: project_env > global_settings > default)
    agent_provider: AgentProviderType = "claude_code"
    source: ConfigSource = "default"

    # Check project environment
    env_provider = project_env.get("AGENT_PROVIDER", "").strip().lower()
    if env_provider in ("claude_code", "opencode"):
        agent_provider = env_provider  # type: ignore
        source = "project_env"

    # Check global settings (fallback)
    elif global_settings.get("globalDefaultProvider"):
        global_provider = (
            str(global_settings.get("globalDefaultProvider", "")).strip().lower()
        )
        if global_provider in ("claude_code", "opencode"):
            agent_provider = global_provider  # type: ignore
            source = "global_settings"

    # Validate configuration
    is_configured = True

    if agent_provider == "opencode":
        # OpenCode requires provider selection and credentials
        opencode_provider = project_env.get(
            "OPENCODE_PROVIDER", ""
        ) or global_settings.get("globalOpencodeProvider", "")

        if not opencode_provider:
            is_configured = False
            errors.append("OpenCode provider not selected")
        else:
            opencode_provider = normalize_provider_id(opencode_provider)

            # Check credential source
            provider_credentials = parse_provider_credentials(
                project_env.get("PROVIDER_CREDENTIALS")
            )
            cred_ref = provider_credentials.get(opencode_provider, {})

            if cred_ref.get("isGlobal", False):
                # Using global credential
                global_cred = get_global_credential(global_settings, opencode_provider)
                if global_cred and global_cred.get("apiKey"):
                    credential_sources[opencode_provider] = "global"
                else:
                    credential_sources[opencode_provider] = "missing"
                    is_configured = False
                    errors.append(f"Global credential '{opencode_provider}' not found")
            elif cred_ref.get("apiKey"):
                # Project-specific credential
                credential_sources[opencode_provider] = "project"
            else:
                # No credential configured
                credential_sources[opencode_provider] = "missing"
                is_configured = False
                errors.append(
                    f"No credential configured for provider '{opencode_provider}'"
                )

    elif agent_provider == "claude_code":
        # Claude Code requires OAuth token
        oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or project_env.get(
            "CLAUDE_CODE_OAUTH_TOKEN"
        )
        if not oauth_token:
            # Check if using global token
            is_global = project_env.get("CLAUDE_TOKEN_IS_GLOBAL", "").lower() == "true"
            if is_global:
                global_token = global_settings.get("claudeOAuthToken")
                if global_token:
                    credential_sources["claude_code"] = "global"
                else:
                    credential_sources["claude_code"] = "missing"
                    is_configured = False
                    errors.append("Global Claude OAuth token not found")
            else:
                credential_sources["claude_code"] = "missing"
                is_configured = False
                errors.append(
                    "Claude OAuth token not configured. Run 'claude setup-token' to authenticate."
                )
        else:
            credential_sources["claude_code"] = (
                "global" if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") else "project"
            )

    return {
        "provider": agent_provider,
        "source": source,
        "isConfigured": is_configured,
        "errors": errors,
        "credentialSources": credential_sources,
    }


# ============================================
# Provider Validation Functions
# ============================================


def validate_provider_config(config_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a provider configuration.

    Args:
        config_data: AgentProviderConfig dictionary with:
            - agentProvider: Provider type
            - agentProviderIsGlobal: Whether using global credentials
            - providerCredentials: Provider credentials store
            - opencodeProvider: OpenCode provider ID (if applicable)
            - opencodeModel: OpenCode model (if applicable)

    Returns:
        ProviderValidationResult dictionary with:
        - isValid: Whether the configuration is valid
        - errors: List of validation errors
        - warnings: List of validation warnings
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate agent provider type
    agent_provider = config_data.get("agentProvider", "")
    if agent_provider not in ("claude_code", "opencode"):
        errors.append(
            f"Invalid agent provider: '{agent_provider}'. Must be 'claude_code' or 'opencode'"
        )
        return {"isValid": False, "errors": errors, "warnings": warnings}

    if agent_provider == "opencode":
        # Validate OpenCode configuration
        opencode_provider = config_data.get("opencodeProvider", "")
        if not opencode_provider:
            errors.append("OpenCode provider is required when using 'opencode' agent")
        else:
            normalized = normalize_provider_id(opencode_provider)
            if not normalized:
                errors.append(f"Invalid OpenCode provider ID: '{opencode_provider}'")
            else:
                # Check credentials
                provider_credentials = config_data.get("providerCredentials", {})
                cred_ref = provider_credentials.get(normalized, {})

                if config_data.get("agentProviderIsGlobal", False) or cred_ref.get(
                    "isGlobal", False
                ):
                    # Will use global credential - can't fully validate without loading settings
                    global_settings = load_global_settings()
                    global_cred = get_global_credential(global_settings, normalized)
                    if not global_cred or not global_cred.get("apiKey"):
                        errors.append(f"Global credential for '{normalized}' not found")
                else:
                    # Project-specific credential required
                    if not cred_ref.get("apiKey"):
                        errors.append(f"API key required for provider '{normalized}'")
                    else:
                        # Validate API key format for known providers
                        api_key = cred_ref.get("apiKey", "")
                        key_error = validate_api_key_format(normalized, api_key)
                        if key_error:
                            warnings.append(key_error)

        # Validate OpenCode model (optional but warn if unusual)
        opencode_model = config_data.get("opencodeModel", "")
        if opencode_model and not re.match(r"^[a-zA-Z0-9._-]+$", opencode_model):
            warnings.append(f"Unusual model name format: '{opencode_model}'")

    # Check for conflicting configurations
    if agent_provider == "opencode" and config_data.get("providerCredentials"):
        provider_credentials = config_data.get("providerCredentials", {})
        for provider_id, cred_ref in provider_credentials.items():
            if cred_ref.get("isGlobal", False) and cred_ref.get("apiKey"):
                warnings.append(
                    f"Provider '{provider_id}' has both isGlobal=true and an apiKey. "
                    "The apiKey will be ignored in favor of the global credential."
                )

    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_api_key_format(provider_id: str, api_key: str) -> str | None:
    """
    Validate an API key format for known providers.

    Args:
        provider_id: Normalized provider ID
        api_key: API key to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not api_key or api_key.strip() == "":
        return "API key is required"

    # Known API key patterns
    patterns: dict[str, tuple[str, str]] = {
        "openai": (r"^sk-", 'OpenAI API keys should start with "sk-"'),
        "anthropic": (r"^sk-ant-", 'Anthropic API keys should start with "sk-ant-"'),
    }

    # Check patterns for providers that start with known prefixes
    for prefix, (pattern, message) in patterns.items():
        if provider_id.startswith(prefix) or provider_id == prefix:
            if not re.match(pattern, api_key):
                return message

    return None


# ============================================
# CLI Entry Point
# ============================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Provider Info CLI - Helper for UI bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get provider status for a project
  python cli/provider_info.py get-status --project-dir /path/to/project

  # Validate a provider configuration
  python cli/provider_info.py validate --config '{"agentProvider": "opencode", "opencodeProvider": "openai"}'
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # get-status command
    status_parser = subparsers.add_parser(
        "get-status",
        help="Get provider configuration status for a project",
    )
    status_parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory (default: current working directory)",
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a provider configuration",
    )
    validate_parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Provider configuration as JSON string",
    )

    # normalize command (utility for testing)
    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize a provider name to ID format",
    )
    normalize_parser.add_argument(
        "name",
        type=str,
        help="Provider name to normalize",
    )

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    if not args.command:
        print(json.dumps({"error": "No command specified. Use --help for usage."}))
        sys.exit(1)

    result: dict[str, Any] = {}

    if args.command == "get-status":
        project_dir = args.project_dir or Path.cwd()
        if not project_dir.exists():
            result = {
                "error": f"Project directory does not exist: {project_dir}",
                "provider": "claude_code",
                "source": "default",
                "isConfigured": False,
                "errors": [f"Project directory does not exist: {project_dir}"],
                "credentialSources": {},
            }
        else:
            result = get_provider_status(project_dir)

    elif args.command == "validate":
        try:
            config_data = json.loads(args.config)
            if not isinstance(config_data, dict):
                result = {
                    "isValid": False,
                    "errors": ["Configuration must be a JSON object"],
                    "warnings": [],
                }
            else:
                result = validate_provider_config(config_data)
        except json.JSONDecodeError as e:
            result = {
                "isValid": False,
                "errors": [f"Invalid JSON: {e}"],
                "warnings": [],
            }

    elif args.command == "normalize":
        normalized = normalize_provider_id(args.name)
        result = {
            "input": args.name,
            "output": normalized,
        }

    # Output as JSON for UI integration
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
