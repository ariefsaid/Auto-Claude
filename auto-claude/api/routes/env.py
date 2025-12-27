"""
Project Environment API Routes
==============================

REST endpoints for project .env configuration.
Mirrors Electron IPC env-handlers.
"""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


def get_projects_path() -> Path:
    """Get the projects file path based on platform."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        app_dir = base / "auto-claude-ui"
    elif os.uname().sysname == "Darwin":  # macOS
        app_dir = Path.home() / "Library" / "Application Support" / "auto-claude-ui"
    else:  # Linux
        app_dir = Path.home() / ".config" / "auto-claude-ui"

    return app_dir / "projects.json"


def get_settings_path() -> Path:
    """Get the settings file path based on platform."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        app_dir = base / "auto-claude-ui"
    elif os.uname().sysname == "Darwin":  # macOS
        app_dir = Path.home() / "Library" / "Application Support" / "auto-claude-ui"
    else:  # Linux
        app_dir = Path.home() / ".config" / "auto-claude-ui"

    return app_dir / "settings.json"


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


def parse_env_file(content: str) -> dict[str, str]:
    """Parse .env file content into a dictionary."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Parse KEY=VALUE
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            result[key] = value
    return result


class EnvResponse(BaseModel):
    """Environment config response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class UpdateEnvRequest(BaseModel):
    """Request body for updating environment config."""

    config: dict[str, Any]


def get_project_by_id(project_id: str) -> dict[str, Any] | None:
    """Find project by ID."""
    projects = load_projects()
    for p in projects:
        if p.get("id") == project_id:
            return p
    return None


def build_env_config(
    env_vars: dict[str, str], global_settings: dict[str, Any]
) -> dict[str, Any]:
    """Build ProjectEnvConfig from .env vars and global settings."""
    config: dict[str, Any] = {
        "claudeAuthStatus": "not_configured",
        "linearEnabled": False,
        "githubEnabled": False,
        "graphitiEnabled": False,
        "enableFancyUi": True,
        "claudeTokenIsGlobal": False,
        "openaiKeyIsGlobal": False,
    }

    # Claude OAuth Token: project-specific takes precedence, then global
    if env_vars.get("CLAUDE_CODE_OAUTH_TOKEN"):
        config["claudeOAuthToken"] = env_vars["CLAUDE_CODE_OAUTH_TOKEN"]
        config["claudeAuthStatus"] = "token_set"
        config["claudeTokenIsGlobal"] = False
    elif global_settings.get("globalClaudeOAuthToken"):
        config["claudeOAuthToken"] = global_settings["globalClaudeOAuthToken"]
        config["claudeAuthStatus"] = "token_set"
        config["claudeTokenIsGlobal"] = True

    if env_vars.get("AUTO_BUILD_MODEL"):
        config["autoBuildModel"] = env_vars["AUTO_BUILD_MODEL"]

    # Linear config
    if env_vars.get("LINEAR_API_KEY"):
        config["linearEnabled"] = True
        config["linearApiKey"] = env_vars["LINEAR_API_KEY"]
    if env_vars.get("LINEAR_TEAM_ID"):
        config["linearTeamId"] = env_vars["LINEAR_TEAM_ID"]
    if env_vars.get("LINEAR_PROJECT_ID"):
        config["linearProjectId"] = env_vars["LINEAR_PROJECT_ID"]
    if env_vars.get("LINEAR_REALTIME_SYNC", "").lower() == "true":
        config["linearRealtimeSync"] = True

    # GitHub config
    if env_vars.get("GITHUB_TOKEN"):
        config["githubEnabled"] = True
        config["githubToken"] = env_vars["GITHUB_TOKEN"]
    if env_vars.get("GITHUB_REPO"):
        config["githubRepo"] = env_vars["GITHUB_REPO"]
    if env_vars.get("GITHUB_AUTO_SYNC", "").lower() == "true":
        config["githubAutoSync"] = True

    # Git/Worktree config
    if env_vars.get("DEFAULT_BRANCH"):
        config["defaultBranch"] = env_vars["DEFAULT_BRANCH"]

    # Graphiti/Memory config
    if env_vars.get("GRAPHITI_ENABLED", "").lower() == "true":
        config["graphitiEnabled"] = True

    # OpenAI API Key: project-specific takes precedence, then global
    if env_vars.get("OPENAI_API_KEY"):
        config["openaiApiKey"] = env_vars["OPENAI_API_KEY"]
        config["openaiKeyIsGlobal"] = False
    elif global_settings.get("globalOpenAIApiKey"):
        config["openaiApiKey"] = global_settings["globalOpenAIApiKey"]
        config["openaiKeyIsGlobal"] = True

    if env_vars.get("GRAPHITI_DATABASE"):
        config["graphitiDatabase"] = env_vars["GRAPHITI_DATABASE"]
    if env_vars.get("GRAPHITI_DB_PATH"):
        config["graphitiDbPath"] = env_vars["GRAPHITI_DB_PATH"]

    if env_vars.get("ENABLE_FANCY_UI", "").lower() == "false":
        config["enableFancyUi"] = False

    # Agent Provider Configuration (Multi-provider support)
    agent_provider = env_vars.get("AGENT_PROVIDER", "").lower()
    if agent_provider in ("claude_code", "opencode"):
        config["agentProvider"] = agent_provider
    elif global_settings.get("selectedAgentProvider"):
        config["agentProvider"] = global_settings["selectedAgentProvider"]

    # Parse AGENT_PROVIDER_IS_GLOBAL
    if env_vars.get("AGENT_PROVIDER_IS_GLOBAL") is not None:
        config["agentProviderIsGlobal"] = (
            env_vars.get("AGENT_PROVIDER_IS_GLOBAL", "").lower() == "true"
        )

    # Parse OpenCode provider and model
    if env_vars.get("OPENCODE_PROVIDER"):
        config["opencodeProvider"] = env_vars["OPENCODE_PROVIDER"]
    elif global_settings.get("globalOpencodeProvider"):
        config["opencodeProvider"] = global_settings["globalOpencodeProvider"]

    if env_vars.get("OPENCODE_MODEL"):
        config["opencodeModel"] = env_vars["OPENCODE_MODEL"]
    elif global_settings.get("globalOpencodeModel"):
        config["opencodeModel"] = global_settings["globalOpencodeModel"]

    # Parse PROVIDER_CREDENTIALS JSON
    if env_vars.get("PROVIDER_CREDENTIALS"):
        try:
            parsed = json.loads(env_vars["PROVIDER_CREDENTIALS"])
            if isinstance(parsed, dict):
                config["providerCredentials"] = parsed
        except json.JSONDecodeError:
            pass

    # Merge with global provider credentials if not in project
    if not config.get("providerCredentials") and global_settings.get(
        "providerCredentials"
    ):
        config["providerCredentials"] = global_settings["providerCredentials"]

    return config


def generate_env_content(
    config: dict[str, Any], existing_content: str | None = None
) -> str:
    """Generate .env file content from config."""
    # Parse existing content to preserve values
    existing_vars = parse_env_file(existing_content) if existing_content else {}

    # Update with new values
    if config.get("claudeOAuthToken") is not None:
        existing_vars["CLAUDE_CODE_OAUTH_TOKEN"] = config["claudeOAuthToken"]
    if config.get("autoBuildModel") is not None:
        existing_vars["AUTO_BUILD_MODEL"] = config["autoBuildModel"]
    if config.get("linearApiKey") is not None:
        existing_vars["LINEAR_API_KEY"] = config["linearApiKey"]
    if config.get("linearTeamId") is not None:
        existing_vars["LINEAR_TEAM_ID"] = config["linearTeamId"]
    if config.get("linearProjectId") is not None:
        existing_vars["LINEAR_PROJECT_ID"] = config["linearProjectId"]
    if config.get("linearRealtimeSync") is not None:
        existing_vars["LINEAR_REALTIME_SYNC"] = (
            "true" if config["linearRealtimeSync"] else "false"
        )
    if config.get("githubToken") is not None:
        existing_vars["GITHUB_TOKEN"] = config["githubToken"]
    if config.get("githubRepo") is not None:
        existing_vars["GITHUB_REPO"] = config["githubRepo"]
    if config.get("githubAutoSync") is not None:
        existing_vars["GITHUB_AUTO_SYNC"] = (
            "true" if config["githubAutoSync"] else "false"
        )
    if config.get("defaultBranch") is not None:
        existing_vars["DEFAULT_BRANCH"] = config["defaultBranch"]
    if config.get("graphitiEnabled") is not None:
        existing_vars["GRAPHITI_ENABLED"] = (
            "true" if config["graphitiEnabled"] else "false"
        )
    if config.get("openaiApiKey") is not None:
        existing_vars["OPENAI_API_KEY"] = config["openaiApiKey"]
    if config.get("graphitiDatabase") is not None:
        existing_vars["GRAPHITI_DATABASE"] = config["graphitiDatabase"]
    if config.get("graphitiDbPath") is not None:
        existing_vars["GRAPHITI_DB_PATH"] = config["graphitiDbPath"]
    if config.get("enableFancyUi") is not None:
        existing_vars["ENABLE_FANCY_UI"] = (
            "true" if config["enableFancyUi"] else "false"
        )
    if config.get("agentProvider") is not None:
        existing_vars["AGENT_PROVIDER"] = config["agentProvider"]
    if config.get("agentProviderIsGlobal") is not None:
        existing_vars["AGENT_PROVIDER_IS_GLOBAL"] = (
            "true" if config["agentProviderIsGlobal"] else "false"
        )
    if config.get("opencodeProvider") is not None:
        existing_vars["OPENCODE_PROVIDER"] = config["opencodeProvider"]
    if config.get("opencodeModel") is not None:
        existing_vars["OPENCODE_MODEL"] = config["opencodeModel"]
    if config.get("providerCredentials") is not None:
        existing_vars["PROVIDER_CREDENTIALS"] = json.dumps(
            config["providerCredentials"]
        )

    # Generate .env content
    lines = [
        "# Auto Claude Framework Environment Variables",
        "# Managed by Auto Claude UI",
        "",
    ]

    # Add all variables
    for key, value in existing_vars.items():
        if value:
            lines.append(f"{key}={value}")

    return "\n".join(lines) + "\n"


@router.get("/projects/{project_id}/env", response_model=EnvResponse)
async def get_project_env(project_id: str):
    """
    Get project environment configuration.

    Reads .env file from project's autoBuildPath and merges with global settings.

    Args:
        project_id: Project identifier

    Returns:
        ProjectEnvConfig
    """
    project = get_project_by_id(project_id)
    if not project:
        return EnvResponse(success=False, error="Project not found")

    auto_build_path = project.get("autoBuildPath")
    if not auto_build_path:
        return EnvResponse(success=False, error="Project not initialized")

    project_path = project.get("path", "")
    env_path = Path(project_path) / auto_build_path / ".env"

    # Load global settings for fallbacks
    global_settings = load_settings()

    # Parse project-specific .env if it exists
    env_vars: dict[str, str] = {}
    if env_path.exists():
        try:
            content = env_path.read_text()
            env_vars = parse_env_file(content)
        except OSError:
            pass

    # Build the config
    config = build_env_config(env_vars, global_settings)

    return EnvResponse(success=True, data=config)


@router.put("/projects/{project_id}/env", response_model=EnvResponse)
async def update_project_env(project_id: str, request: UpdateEnvRequest):
    """
    Update project environment configuration.

    Writes to .env file in project's autoBuildPath.

    Args:
        project_id: Project identifier
        request: Configuration updates

    Returns:
        Success status
    """
    project = get_project_by_id(project_id)
    if not project:
        return EnvResponse(success=False, error="Project not found")

    auto_build_path = project.get("autoBuildPath")
    if not auto_build_path:
        return EnvResponse(success=False, error="Project not initialized")

    project_path = project.get("path", "")
    env_path = Path(project_path) / auto_build_path / ".env"

    try:
        # Read existing content if file exists
        existing_content = None
        if env_path.exists():
            existing_content = env_path.read_text()

        # Generate new content
        new_content = generate_env_content(request.config, existing_content)

        # Ensure directory exists
        env_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        env_path.write_text(new_content)

        print(f"[Env] Updated .env for project {project_id}")
        return EnvResponse(success=True)
    except Exception as e:
        return EnvResponse(success=False, error=str(e))


@router.get("/env/check-auth", response_model=EnvResponse)
async def check_claude_auth():
    """
    Check if Claude OAuth token is configured and valid.

    Checks both global settings and environment variables.

    Returns:
        Authentication status
    """
    import subprocess

    auth_status = {
        "isConfigured": False,
        "source": None,
        "tokenType": None,
        "isValid": False,
        "error": None,
    }

    # Check global settings first
    global_settings = load_settings()
    global_token = global_settings.get("globalClaudeOAuthToken")

    if global_token:
        auth_status["isConfigured"] = True
        auth_status["source"] = "global_settings"
        auth_status["tokenType"] = "oauth"

    # Check environment variable
    env_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if env_token:
        auth_status["isConfigured"] = True
        auth_status["source"] = "environment"
        auth_status["tokenType"] = "oauth"

    # Try to validate by running claude --version (quick check)
    if auth_status["isConfigured"]:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                auth_status["isValid"] = True
                auth_status["claudeVersion"] = result.stdout.strip()
        except FileNotFoundError:
            auth_status["error"] = "Claude CLI not found"
        except subprocess.TimeoutExpired:
            auth_status["error"] = "Claude CLI timeout"
        except Exception as e:
            auth_status["error"] = str(e)

    return EnvResponse(success=True, data=auth_status)
