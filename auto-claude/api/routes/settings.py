"""
Settings API Routes
===================

REST endpoints for application and project settings.
Mirrors Electron's settings persistence behavior.
"""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# Settings file location - mirrors Electron's userData path
# macOS: ~/Library/Application Support/auto-claude-ui/
# Linux: ~/.config/auto-claude-ui/
def get_settings_path() -> Path:
    """Get the settings file path based on platform."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        app_dir = base / "auto-claude-ui"
    elif os.uname().sysname == "Darwin":  # macOS
        app_dir = Path.home() / "Library" / "Application Support" / "auto-claude-ui"
    else:  # Linux
        app_dir = Path.home() / ".config" / "auto-claude-ui"

    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "settings.json"


# Default settings - mirrors auto-claude-ui/src/shared/constants/settings.ts
DEFAULT_APP_SETTINGS = {
    "autoBuildPath": None,
    "pythonPath": None,
    "selectedAgentProfile": "auto",
    "selectedAgentProvider": "claude_code",
    "providerCredentials": {},
}


class SettingsResponse(BaseModel):
    """Generic settings response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class SaveSettingsRequest(BaseModel):
    """Request body for saving settings."""

    settings: dict[str, Any]


def load_settings() -> dict[str, Any]:
    """Load settings from disk, merging with defaults."""
    settings_path = get_settings_path()
    settings = DEFAULT_APP_SETTINGS.copy()

    if settings_path.exists():
        try:
            with open(settings_path) as f:
                saved_settings = json.load(f)
                settings.update(saved_settings)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[Settings] Error loading settings: {e}")

    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Save settings to disk."""
    settings_path = get_settings_path()

    # Merge with existing settings
    current = load_settings()
    current.update(settings)

    with open(settings_path, "w") as f:
        json.dump(current, f, indent=2)

    print(f"[Settings] Saved settings to {settings_path}")


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """
    Get application settings.

    Returns:
        Application settings
    """
    try:
        settings = load_settings()
        return SettingsResponse(success=True, data=settings)
    except Exception as e:
        return SettingsResponse(success=False, error=str(e))


@router.post("/settings", response_model=SettingsResponse)
async def post_save_settings(request: SaveSettingsRequest):
    """
    Save application settings.

    Args:
        request: Settings to save (partial update supported)

    Returns:
        Success status
    """
    try:
        save_settings(request.settings)
        return SettingsResponse(success=True, data=load_settings())
    except Exception as e:
        return SettingsResponse(success=False, error=str(e))
