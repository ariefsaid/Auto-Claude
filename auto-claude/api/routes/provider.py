"""
Provider API Routes
====================

REST endpoints for multi-provider configuration and testing.
"""

import asyncio
import json
import os
import re
import ssl
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


def get_app_data_path() -> Path:
    """Get the application data path based on platform."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "auto-claude-ui"
    elif os.uname().sysname == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "auto-claude-ui"
    else:  # Linux
        return Path.home() / ".config" / "auto-claude-ui"


def get_settings_path() -> Path:
    """Get the settings file path."""
    return get_app_data_path() / "settings.json"


def get_projects_path() -> Path:
    """Get the projects file path."""
    return get_app_data_path() / "projects.json"


def load_settings() -> dict[str, Any]:
    """Load global settings from disk."""
    settings_path = get_settings_path()
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_settings(settings: dict[str, Any]) -> None:
    """Save global settings to disk."""
    settings_path = get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)


def load_projects() -> list[dict[str, Any]]:
    """Load projects from disk."""
    projects_path = get_projects_path()
    if projects_path.exists():
        try:
            with open(projects_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return []


def get_project_by_id(project_id: str) -> dict[str, Any] | None:
    """Find project by ID."""
    projects = load_projects()
    for p in projects:
        if p.get("id") == project_id:
            return p
    return None


def normalize_provider_id(name: str) -> str:
    """
    Normalize a provider name to a consistent ID format.
    Must match TypeScript normalizeProviderId() exactly.
    """
    # Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
    normalized = name.lower().strip().replace(" ", "-")

    # Step 2: Remove all characters except a-z, 0-9, and dash
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)

    # Step 3: Collapse multiple consecutive dashes into a single dash
    normalized = re.sub(r"-+", "-", normalized)

    # Step 4: Remove leading and trailing dashes
    return normalized.strip("-")


def to_title_case(normalized_id: str) -> str:
    """Convert a normalized provider ID to title case for display."""
    return " ".join(word.capitalize() for word in normalized_id.split("-"))


def parse_env_file(content: str) -> dict[str, str]:
    """Parse .env file content into a dictionary."""
    env = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            # Remove quotes if present
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            env[key.strip()] = value
    return env


# =============================================================================
# Request/Response Models
# =============================================================================


class ProviderResponse(BaseModel):
    """Generic provider response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class ProviderCredential(BaseModel):
    """Provider credential for adding to global settings."""

    provider: str
    displayName: str | None = None
    apiKey: str | None = None
    baseUrl: str | None = None
    defaultModel: str | None = None
    metadata: dict[str, Any] | None = None


class ProviderConfig(BaseModel):
    """Provider configuration for validation."""

    agentProvider: str  # 'claude_code' or 'opencode'
    opencodeProvider: str | None = None
    opencodeModel: str | None = None
    agentProviderIsGlobal: bool = False
    providerCredentials: dict[str, dict[str, Any]] | None = None


class TestConnectionRequest(BaseModel):
    """Request to test a provider connection."""

    provider: str
    apiKey: str
    baseUrl: str | None = None
    model: str | None = None


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/provider/status", response_model=ProviderResponse)
async def get_provider_status(project_id: str):
    """
    Get provider status for a project.

    Returns the current provider configuration status including:
    - provider: Current provider type (claude_code or opencode)
    - source: Where the configuration came from
    - isConfigured: Whether the provider is properly configured
    - errors: List of configuration errors
    - credentialSources: Map of provider IDs to their credential source
    """
    project = get_project_by_id(project_id)
    if not project:
        return ProviderResponse(success=False, error=f"Project not found: {project_id}")

    global_settings = load_settings()
    errors: list[str] = []
    credential_sources: dict[str, str] = {}

    # Load project environment
    project_env: dict[str, str] = {}
    project_path = project.get("path")
    auto_build_path = project.get("autoBuildPath")

    if project_path and auto_build_path:
        env_path = Path(project_path) / auto_build_path / ".env"
        if env_path.exists():
            try:
                project_env = parse_env_file(env_path.read_text())
            except OSError:
                pass

    # Determine provider and source (priority: project_env > global_settings > default)
    agent_provider = "claude_code"
    source = "default"

    env_provider = project_env.get("AGENT_PROVIDER", "").strip().lower()
    if env_provider in ("claude_code", "opencode"):
        agent_provider = env_provider
        source = "project_env"
    elif global_settings.get("globalDefaultProvider"):
        global_provider = global_settings["globalDefaultProvider"]
        if global_provider in ("claude_code", "opencode"):
            agent_provider = global_provider
            source = "global_settings"

    # Validate configuration
    is_configured = True

    if agent_provider == "opencode":
        # OpenCode requires provider selection and credentials
        opencode_provider = project_env.get("OPENCODE_PROVIDER") or global_settings.get(
            "globalOpencodeProvider", ""
        )

        if not opencode_provider:
            is_configured = False
            errors.append("OpenCode provider not selected")
        else:
            normalized_provider = normalize_provider_id(opencode_provider)

            # Parse provider credentials from project env
            provider_credentials: dict[str, dict[str, Any]] = {}
            try:
                cred_json = project_env.get("PROVIDER_CREDENTIALS", "")
                if cred_json:
                    provider_credentials = json.loads(cred_json)
            except json.JSONDecodeError:
                pass

            cred_ref = provider_credentials.get(normalized_provider, {})

            if cred_ref.get("isGlobal"):
                # Using global credential
                global_cred = global_settings.get("providerCredentials", {}).get(
                    normalized_provider
                )
                if global_cred and global_cred.get("apiKey"):
                    credential_sources[normalized_provider] = "global"
                else:
                    credential_sources[normalized_provider] = "missing"
                    is_configured = False
                    errors.append(
                        f"Global credential '{normalized_provider}' not found"
                    )
            elif cred_ref.get("apiKey"):
                # Project-specific credential
                credential_sources[normalized_provider] = "project"
            else:
                # Check global credentials as fallback
                global_cred = global_settings.get("providerCredentials", {}).get(
                    normalized_provider
                )
                if global_cred and global_cred.get("apiKey"):
                    credential_sources[normalized_provider] = "global"
                else:
                    credential_sources[normalized_provider] = "missing"
                    is_configured = False
                    errors.append(
                        f"No credential configured for provider '{normalized_provider}'"
                    )

    elif agent_provider == "claude_code":
        # Claude Code requires OAuth token
        oauth_token = project_env.get("CLAUDE_CODE_OAUTH_TOKEN")
        is_global = project_env.get("CLAUDE_TOKEN_IS_GLOBAL", "").lower() == "true"

        if not oauth_token:
            if is_global and global_settings.get("globalClaudeOAuthToken"):
                credential_sources["claude_code"] = "global"
            elif is_global:
                credential_sources["claude_code"] = "missing"
                is_configured = False
                errors.append("Global Claude OAuth token not found")
            elif global_settings.get("globalClaudeOAuthToken"):
                # Fallback to global token
                credential_sources["claude_code"] = "global"
            else:
                credential_sources["claude_code"] = "missing"
                is_configured = False
                errors.append(
                    "Claude OAuth token not configured. Run 'claude setup-token' to authenticate."
                )
        else:
            credential_sources["claude_code"] = "global" if is_global else "project"

    return ProviderResponse(
        success=True,
        data={
            "provider": agent_provider,
            "source": source,
            "isConfigured": is_configured,
            "errors": errors,
            "credentialSources": credential_sources,
        },
    )


@router.post("/provider/validate", response_model=ProviderResponse)
async def validate_provider(config: ProviderConfig):
    """
    Validate a provider configuration before saving.

    Checks that the configuration is complete and valid:
    - Agent provider type is valid
    - OpenCode provider is specified when using opencode
    - Credentials are available (global or project-specific)
    """
    errors: list[str] = []
    warnings: list[str] = []
    global_settings = load_settings()

    # Validate agent provider type
    agent_provider = config.agentProvider
    if agent_provider not in ("claude_code", "opencode"):
        errors.append(
            f"Invalid agent provider: '{agent_provider}'. Must be 'claude_code' or 'opencode'"
        )
        return ProviderResponse(
            success=True,
            data={"isValid": False, "errors": errors, "warnings": warnings},
        )

    if agent_provider == "opencode":
        # Validate OpenCode configuration
        opencode_provider = config.opencodeProvider
        if not opencode_provider:
            errors.append("OpenCode provider is required when using 'opencode' agent")
        else:
            normalized = normalize_provider_id(opencode_provider)
            if not normalized:
                errors.append(f"Invalid OpenCode provider ID: '{opencode_provider}'")
            else:
                # Check credentials
                cred_ref = (config.providerCredentials or {}).get(normalized, {})

                if config.agentProviderIsGlobal or cred_ref.get("isGlobal"):
                    # Will use global credential
                    global_cred = global_settings.get("providerCredentials", {}).get(
                        normalized
                    )
                    if not global_cred or not global_cred.get("apiKey"):
                        errors.append(f"Global credential for '{normalized}' not found")
                else:
                    # Project-specific credential required
                    if not cred_ref.get("apiKey"):
                        errors.append(f"API key required for provider '{normalized}'")
                    else:
                        # Validate API key format for known providers
                        key_error = validate_api_key_format(
                            normalized, cred_ref["apiKey"]
                        )
                        if key_error:
                            warnings.append(key_error)

        # Validate OpenCode model (optional but warn if unusual)
        opencode_model = config.opencodeModel
        if opencode_model and not re.match(r"^[a-zA-Z0-9._/-]+$", opencode_model):
            warnings.append(f"Unusual model name format: '{opencode_model}'")

    # Check for conflicting configurations
    if agent_provider == "opencode" and config.providerCredentials:
        for provider_id, cred_ref in config.providerCredentials.items():
            if cred_ref.get("isGlobal") and cred_ref.get("apiKey"):
                warnings.append(
                    f"Provider '{provider_id}' has both isGlobal=true and an apiKey. "
                    "The apiKey will be ignored in favor of the global credential."
                )

    return ProviderResponse(
        success=True,
        data={"isValid": len(errors) == 0, "errors": errors, "warnings": warnings},
    )


@router.post("/provider/test", response_model=ProviderResponse)
async def test_provider_connection(request: TestConnectionRequest):
    """
    Test a provider connection by making a real API call.

    Validates that the API key is valid and the provider is reachable.
    """
    provider = normalize_provider_id(request.provider)
    api_key = request.apiKey.strip() if request.apiKey else ""

    if not api_key and provider != "ollama":
        return ProviderResponse(success=False, error="API key is required")

    # Test the connection based on provider type
    try:
        result = await test_provider_api(
            provider, api_key, request.baseUrl, request.model
        )
        return ProviderResponse(success=True, data=result)
    except Exception as e:
        return ProviderResponse(success=False, error=str(e))


@router.get("/provider/configured", response_model=ProviderResponse)
async def get_configured_providers():
    """
    Get list of configured providers from global settings.
    """
    settings = load_settings()
    provider_credentials = settings.get("providerCredentials", {})

    providers = []
    for provider_id, cred in provider_credentials.items():
        if cred and cred.get("apiKey"):
            providers.append(
                {
                    "provider": provider_id,
                    "displayName": cred.get("displayName")
                    or to_title_case(provider_id),
                    "hasApiKey": True,
                    "isGlobal": True,
                    "baseUrl": cred.get("baseUrl"),
                    "defaultModel": cred.get("defaultModel"),
                }
            )

    return ProviderResponse(success=True, data={"providers": providers})


@router.post("/provider/add", response_model=ProviderResponse)
async def add_provider_credential(credential: ProviderCredential):
    """
    Add a provider credential to global settings.
    """
    if not credential.provider:
        return ProviderResponse(success=False, error="Provider ID is required")

    normalized_id = normalize_provider_id(credential.provider)
    if not normalized_id:
        return ProviderResponse(success=False, error="Invalid provider ID")

    if not credential.apiKey and normalized_id != "ollama":
        return ProviderResponse(success=False, error="API key is required")

    # Load current settings
    settings = load_settings()

    # Initialize providerCredentials if it doesn't exist
    if "providerCredentials" not in settings:
        settings["providerCredentials"] = {}

    # Add or update the credential
    settings["providerCredentials"][normalized_id] = {
        "provider": normalized_id,
        "displayName": credential.displayName or to_title_case(normalized_id),
        "apiKey": credential.apiKey,
        "isGlobal": True,
    }

    # Add optional fields
    if credential.baseUrl:
        settings["providerCredentials"][normalized_id]["baseUrl"] = credential.baseUrl
    if credential.defaultModel:
        settings["providerCredentials"][normalized_id]["defaultModel"] = (
            credential.defaultModel
        )
    if credential.metadata:
        settings["providerCredentials"][normalized_id]["metadata"] = credential.metadata

    # Save settings
    save_settings(settings)

    return ProviderResponse(success=True, data={"providerId": normalized_id})


@router.delete("/provider/{provider_id}", response_model=ProviderResponse)
async def remove_provider_credential(provider_id: str):
    """
    Remove a provider from global settings.
    """
    normalized_id = normalize_provider_id(provider_id)
    if not normalized_id:
        return ProviderResponse(success=False, error="Invalid provider ID")

    # Load current settings
    settings = load_settings()

    if not settings.get("providerCredentials", {}).get(normalized_id):
        return ProviderResponse(
            success=False,
            error=f"Provider '{normalized_id}' not found in global settings",
        )

    # Remove the credential
    del settings["providerCredentials"][normalized_id]

    # Save settings
    save_settings(settings)

    return ProviderResponse(success=True, data={"removedProviderId": normalized_id})


@router.get("/provider/models", response_model=ProviderResponse)
async def get_provider_models(provider: str):
    """
    Get available models for a provider.

    Returns a list of known models for the given provider.
    """
    normalized = normalize_provider_id(provider)

    # Known models for common providers
    known_models: dict[str, list[dict[str, str]]] = {
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
            {"id": "gpt-4", "name": "GPT-4"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
            {"id": "o1", "name": "O1"},
            {"id": "o1-mini", "name": "O1 Mini"},
            {"id": "o1-preview", "name": "O1 Preview"},
        ],
        "anthropic": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-opus-4-20250514", "name": "Claude Opus 4"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
        ],
        "google": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
        ],
        "zai-glm": [
            {"id": "glm-4.7", "name": "GLM 4.7"},
            {"id": "glm-4", "name": "GLM 4"},
            {"id": "glm-4-flash", "name": "GLM 4 Flash"},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
        ],
        "ollama": [
            {"id": "llama3.2", "name": "Llama 3.2"},
            {"id": "llama3.1", "name": "Llama 3.1"},
            {"id": "codellama", "name": "Code Llama"},
            {"id": "mistral", "name": "Mistral"},
            {"id": "mixtral", "name": "Mixtral"},
            {"id": "qwen2.5-coder", "name": "Qwen 2.5 Coder"},
        ],
    }

    models = known_models.get(normalized, [])

    return ProviderResponse(
        success=True,
        data={
            "provider": normalized,
            "models": models,
            "isComplete": normalized in known_models,
        },
    )


# =============================================================================
# Helper Functions
# =============================================================================


def validate_api_key_format(provider_id: str, api_key: str) -> str | None:
    """
    Validate an API key format for known providers.
    Returns None if valid, or an error message if invalid.
    """
    if not api_key or not api_key.strip():
        return "API key is required"

    # Known API key patterns
    patterns: dict[str, tuple[str, str]] = {
        "openai": (r"^sk-", 'OpenAI API keys should start with "sk-"'),
        "anthropic": (r"^sk-ant-", 'Anthropic API keys should start with "sk-ant-"'),
        "zai-glm": (r"^zai-", 'Z.ai API keys should start with "zai-"'),
        "google": (r"^AIza", 'Google AI API keys should start with "AIza"'),
    }

    # Check if we have a pattern for this provider
    for prefix, (pattern, message) in patterns.items():
        if provider_id.startswith(prefix) or provider_id == prefix:
            if not re.match(pattern, api_key):
                return message

    # No specific pattern known - accept any non-empty string
    return None


async def test_provider_api(
    provider: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Test a provider API connection.
    """
    import time

    start_time = time.time()

    # Provider-specific test endpoints
    if provider == "openai":
        return await test_openai_api(api_key, start_time)
    elif provider == "anthropic":
        return await test_anthropic_api(api_key, start_time)
    elif provider.startswith("zai") or provider == "zai-glm":
        return await test_zai_api(api_key, base_url, start_time)
    elif provider == "google":
        return await test_google_api(api_key, start_time)
    elif provider == "ollama":
        return await test_ollama_api(base_url, start_time)
    elif provider == "deepseek":
        return await test_deepseek_api(api_key, start_time)
    else:
        # Generic test - just validate format
        format_error = validate_api_key_format(provider, api_key)
        if format_error:
            return {
                "success": False,
                "message": format_error,
                "provider": provider,
            }
        return {
            "success": True,
            "message": f"API key format valid for {provider} (connection not tested)",
            "provider": provider,
        }


async def test_openai_api(api_key: str, start_time: float) -> dict[str, Any]:
    """Test OpenAI API connection."""
    try:
        # Create SSL context
        ssl_context = ssl.create_default_context()

        request = Request(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: urlopen(request, timeout=15, context=ssl_context)
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status == 200:
            return {
                "success": True,
                "message": "OpenAI API key is valid",
                "provider": "openai",
                "latencyMs": latency_ms,
            }
        else:
            return {
                "success": False,
                "message": f"API error: {response.status}",
                "provider": "openai",
            }

    except HTTPError as e:
        if e.code == 401:
            return {
                "success": False,
                "message": "Invalid API key. Please check your OpenAI API key.",
                "provider": "openai",
            }
        elif e.code == 429:
            # Rate limited but key is valid
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "message": "OpenAI API key is valid (rate limited)",
                "provider": "openai",
                "latencyMs": latency_ms,
            }
        else:
            return {
                "success": False,
                "message": f"API error: {e.code}",
                "provider": "openai",
            }
    except URLError as e:
        return {
            "success": False,
            "message": f"Connection error: {e.reason}",
            "provider": "openai",
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "provider": "openai",
        }


async def test_anthropic_api(api_key: str, start_time: float) -> dict[str, Any]:
    """Test Anthropic API connection."""
    # For Anthropic, just validate the format (no simple list endpoint)
    if not api_key.startswith("sk-ant-"):
        return {
            "success": False,
            "message": 'Invalid API key format. Anthropic API keys should start with "sk-ant-"',
            "provider": "anthropic",
        }

    return {
        "success": True,
        "message": "Anthropic API key format is valid",
        "provider": "anthropic",
    }


async def test_zai_api(
    api_key: str, base_url: str | None, start_time: float
) -> dict[str, Any]:
    """Test Z.ai GLM API connection."""
    # Z.ai doesn't have a simple models endpoint, validate format
    if not api_key.startswith("zai-"):
        return {
            "success": False,
            "message": 'Z.ai API keys should start with "zai-"',
            "provider": "zai-glm",
        }

    return {
        "success": True,
        "message": "Z.ai API key format is valid",
        "provider": "zai-glm",
    }


async def test_google_api(api_key: str, start_time: float) -> dict[str, Any]:
    """Test Google AI API connection."""
    if not api_key.startswith("AIza"):
        return {
            "success": False,
            "message": 'Invalid API key format. Google AI API keys should start with "AIza"',
            "provider": "google",
        }

    return {
        "success": True,
        "message": "Google AI API key format is valid",
        "provider": "google",
    }


async def test_deepseek_api(api_key: str, start_time: float) -> dict[str, Any]:
    """Test DeepSeek API connection."""
    try:
        ssl_context = ssl.create_default_context()

        request = Request(
            "https://api.deepseek.com/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: urlopen(request, timeout=15, context=ssl_context)
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status == 200:
            return {
                "success": True,
                "message": "DeepSeek API key is valid",
                "provider": "deepseek",
                "latencyMs": latency_ms,
            }
        else:
            return {
                "success": False,
                "message": f"API error: {response.status}",
                "provider": "deepseek",
            }

    except HTTPError as e:
        if e.code == 401:
            return {
                "success": False,
                "message": "Invalid API key. Please check your DeepSeek API key.",
                "provider": "deepseek",
            }
        else:
            return {
                "success": False,
                "message": f"API error: {e.code}",
                "provider": "deepseek",
            }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "provider": "deepseek",
        }


async def test_ollama_api(base_url: str | None, start_time: float) -> dict[str, Any]:
    """Test Ollama API connection (local)."""
    import time

    url = base_url or "http://localhost:11434"

    try:
        request = Request(f"{url}/api/tags")

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: urlopen(request, timeout=5))

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status == 200:
            return {
                "success": True,
                "message": "Ollama is running and accessible",
                "provider": "ollama",
                "latencyMs": latency_ms,
            }
        else:
            return {
                "success": False,
                "message": f"Ollama returned status: {response.status}",
                "provider": "ollama",
            }

    except URLError:
        return {
            "success": False,
            "message": f"Cannot connect to Ollama at {url}. Is Ollama running?",
            "provider": "ollama",
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "provider": "ollama",
        }


# Import time at module level for use in async functions
import time
