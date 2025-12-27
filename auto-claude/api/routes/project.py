"""
Project API Routes
==================

REST endpoints for project management.
"""

import json
import os
import uuid
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

    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "projects.json"


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


def save_projects(projects: list[dict[str, Any]]) -> None:
    """Save projects to disk."""
    projects_path = get_projects_path()
    with open(projects_path, "w") as f:
        json.dump(projects, f, indent=2)


class ProjectResponse(BaseModel):
    """Generic project response."""

    success: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None


class AddProjectRequest(BaseModel):
    """Request body for adding a project."""

    projectPath: str


@router.get("/projects", response_model=ProjectResponse)
async def list_projects():
    """
    List all projects.

    Returns:
        List of projects
    """
    projects = load_projects()
    return ProjectResponse(success=True, data=projects)


@router.post("/projects", response_model=ProjectResponse)
async def add_project(request: AddProjectRequest):
    """
    Add a new project.

    Args:
        request: Project path to add

    Returns:
        Created project
    """
    project_path = request.projectPath

    # Validate path exists
    if not os.path.isdir(project_path):
        return ProjectResponse(
            success=False, error=f"Directory not found: {project_path}"
        )

    # Load existing projects
    projects = load_projects()

    # Check if project already exists
    for p in projects:
        if p.get("path") == project_path:
            return ProjectResponse(success=True, data=p)

    # Create new project
    project_name = os.path.basename(project_path)
    project = {
        "id": str(uuid.uuid4()),
        "name": project_name,
        "path": project_path,
        "autoBuildPath": None,
        "createdAt": None,
        "updatedAt": None,
    }

    projects.append(project)
    save_projects(projects)

    print(f"[Projects] Added project: {project_name} at {project_path}")
    return ProjectResponse(success=True, data=project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """
    Get project details.

    Args:
        project_id: Project identifier

    Returns:
        Project details
    """
    # TODO: Implement project details retrieval
    return ProjectResponse(
        success=True, data={"projectId": project_id, "message": "Project retrieved"}
    )
