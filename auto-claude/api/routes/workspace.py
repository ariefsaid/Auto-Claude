"""
Workspace API Routes
====================

REST endpoints for git worktree operations.
"""

import asyncio
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


class WorkspaceResponse(BaseModel):
    """Generic workspace response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@router.get("/workspace/status", response_model=WorkspaceResponse)
async def get_workspace_status(project_id: str, spec_id: str):
    """
    Get worktree status.

    Args:
        project_id: Project identifier
        spec_id: Spec identifier

    Returns:
        Worktree status including branch, modified files, etc.
    """
    project = get_project_by_id(project_id)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {project_id}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    # Check if worktree exists
    worktree_path = Path(project_path) / ".worktrees" / spec_id
    worktree_exists = worktree_path.exists() and worktree_path.is_dir()

    status_data = {
        "projectId": project_id,
        "specId": spec_id,
        "worktreePath": str(worktree_path) if worktree_exists else None,
        "exists": worktree_exists,
        "branch": None,
        "modifiedFiles": [],
        "hasUncommittedChanges": False,
    }

    if worktree_exists:
        try:
            # Get current branch
            branch_result = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await branch_result.communicate()
            if branch_result.returncode == 0:
                status_data["branch"] = stdout.decode().strip()

            # Get modified files
            status_result = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await status_result.communicate()
            if status_result.returncode == 0:
                output = stdout.decode().strip()
                if output:
                    status_data["modifiedFiles"] = output.split("\n")
                    status_data["hasUncommittedChanges"] = True

        except Exception:
            # Git commands failed, worktree may be corrupted
            pass

    return WorkspaceResponse(success=True, data=status_data)


@router.get("/workspace/list", response_model=WorkspaceResponse)
async def list_worktrees(project_id: str):
    """
    List all worktrees for a project.

    Args:
        project_id: Project identifier

    Returns:
        List of worktrees
    """
    project = get_project_by_id(project_id)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {project_id}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    worktrees_dir = Path(project_path) / ".worktrees"
    if not worktrees_dir.exists():
        return WorkspaceResponse(success=True, data={"worktrees": []})

    worktrees = []
    for item in worktrees_dir.iterdir():
        if item.is_dir():
            worktrees.append(
                {
                    "specId": item.name,
                    "path": str(item),
                }
            )

    return WorkspaceResponse(success=True, data={"worktrees": worktrees})
