"""
Git API Routes
==============

REST endpoints for git operations.
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


async def run_git_command(
    args: list[str], cwd: str, timeout: int = 30
) -> tuple[int, str, str]:
    """Run a git command and return result."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return (
            process.returncode or 0,
            stdout.decode().strip(),
            stderr.decode().strip(),
        )
    except asyncio.TimeoutError:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


class GitResponse(BaseModel):
    """Generic git response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@router.get("/git/status", response_model=GitResponse)
async def get_git_status(project_id: str):
    """
    Get git status for a project.

    Args:
        project_id: Project identifier

    Returns:
        Git status information
    """
    project = get_project_by_id(project_id)
    if not project:
        return GitResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return GitResponse(success=False, error="Project path not configured")

    # Check if it's a git repository
    git_dir = Path(project_path) / ".git"
    if not git_dir.exists():
        return GitResponse(
            success=True,
            data={
                "isGitRepo": False,
                "projectId": project_id,
            },
        )

    status_data: dict[str, Any] = {
        "isGitRepo": True,
        "projectId": project_id,
        "branch": None,
        "isClean": True,
        "staged": [],
        "modified": [],
        "untracked": [],
        "ahead": 0,
        "behind": 0,
    }

    try:
        # Get current branch
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            project_path,
        )
        if returncode == 0:
            status_data["branch"] = stdout

        # Get status
        returncode, stdout, stderr = await run_git_command(
            ["status", "--porcelain"],
            project_path,
        )

        if returncode == 0 and stdout:
            status_data["isClean"] = False
            for line in stdout.split("\n"):
                if not line:
                    continue
                status_code = line[:2]
                file_path = line[3:]

                if status_code[0] in "MADRC":
                    status_data["staged"].append(file_path)
                if status_code[1] == "M":
                    status_data["modified"].append(file_path)
                if status_code == "??":
                    status_data["untracked"].append(file_path)

        # Get ahead/behind count
        returncode, stdout, stderr = await run_git_command(
            ["rev-list", "--count", "--left-right", "@{upstream}...HEAD"],
            project_path,
        )
        if returncode == 0 and stdout:
            parts = stdout.split("\t")
            if len(parts) == 2:
                status_data["behind"] = int(parts[0])
                status_data["ahead"] = int(parts[1])

        return GitResponse(success=True, data=status_data)

    except Exception as e:
        return GitResponse(success=False, error=str(e))


@router.get("/git/branches", response_model=GitResponse)
async def get_git_branches(project_id: str):
    """
    Get list of git branches for a project.

    Args:
        project_id: Project identifier

    Returns:
        List of branches
    """
    project = get_project_by_id(project_id)
    if not project:
        return GitResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return GitResponse(success=False, error="Project path not configured")

    try:
        # Get all branches
        returncode, stdout, stderr = await run_git_command(
            [
                "branch",
                "-a",
                "--format=%(refname:short)|%(objectname:short)|%(upstream:short)",
            ],
            project_path,
        )

        if returncode != 0:
            return GitResponse(success=False, error=stderr or "Failed to get branches")

        branches = []
        current_branch = None

        # Get current branch
        rc, current, _ = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            project_path,
        )
        if rc == 0:
            current_branch = current

        for line in stdout.split("\n"):
            if not line:
                continue
            parts = line.split("|")
            branch_name = parts[0]
            commit = parts[1] if len(parts) > 1 else ""
            upstream = parts[2] if len(parts) > 2 else ""

            branches.append(
                {
                    "name": branch_name,
                    "commit": commit,
                    "upstream": upstream,
                    "isCurrent": branch_name == current_branch,
                    "isRemote": branch_name.startswith("origin/"),
                }
            )

        return GitResponse(
            success=True,
            data={
                "projectId": project_id,
                "currentBranch": current_branch,
                "branches": branches,
            },
        )

    except Exception as e:
        return GitResponse(success=False, error=str(e))


@router.get("/git/current-branch", response_model=GitResponse)
async def get_current_branch(project_id: str):
    """
    Get current git branch for a project.

    Args:
        project_id: Project identifier

    Returns:
        Current branch name
    """
    project = get_project_by_id(project_id)
    if not project:
        return GitResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return GitResponse(success=False, error="Project path not configured")

    try:
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            project_path,
        )

        if returncode != 0:
            return GitResponse(success=False, error=stderr or "Failed to get branch")

        return GitResponse(
            success=True,
            data={
                "projectId": project_id,
                "branch": stdout,
            },
        )

    except Exception as e:
        return GitResponse(success=False, error=str(e))


@router.get("/git/main-branch", response_model=GitResponse)
async def detect_main_branch(project_id: str):
    """
    Detect the main branch (main or master) for a project.

    Args:
        project_id: Project identifier

    Returns:
        Main branch name
    """
    project = get_project_by_id(project_id)
    if not project:
        return GitResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return GitResponse(success=False, error="Project path not configured")

    try:
        # Try 'main' first
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--verify", "main"],
            project_path,
        )
        if returncode == 0:
            return GitResponse(
                success=True,
                data={"projectId": project_id, "mainBranch": "main"},
            )

        # Try 'master'
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--verify", "master"],
            project_path,
        )
        if returncode == 0:
            return GitResponse(
                success=True,
                data={"projectId": project_id, "mainBranch": "master"},
            )

        # Check remote
        returncode, stdout, stderr = await run_git_command(
            ["remote", "show", "origin"],
            project_path,
        )
        if returncode == 0 and "HEAD branch:" in stdout:
            for line in stdout.split("\n"):
                if "HEAD branch:" in line:
                    main_branch = line.split(":")[-1].strip()
                    return GitResponse(
                        success=True,
                        data={"projectId": project_id, "mainBranch": main_branch},
                    )

        return GitResponse(
            success=True,
            data={"projectId": project_id, "mainBranch": "main"},  # Default
        )

    except Exception as e:
        return GitResponse(success=False, error=str(e))


@router.post("/git/init", response_model=GitResponse)
async def init_git_repo(project_id: str):
    """
    Initialize a git repository in a project.

    Args:
        project_id: Project identifier

    Returns:
        Initialization result
    """
    project = get_project_by_id(project_id)
    if not project:
        return GitResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return GitResponse(success=False, error="Project path not configured")

    # Check if already a git repo
    git_dir = Path(project_path) / ".git"
    if git_dir.exists():
        return GitResponse(
            success=True,
            data={
                "projectId": project_id,
                "initialized": False,
                "message": "Already a git repository",
            },
        )

    try:
        returncode, stdout, stderr = await run_git_command(
            ["init"],
            project_path,
        )

        if returncode != 0:
            return GitResponse(success=False, error=stderr or "Failed to init git")

        print(f"[Git] Initialized repository in: {project_path}")
        return GitResponse(
            success=True,
            data={
                "projectId": project_id,
                "initialized": True,
                "message": stdout,
            },
        )

    except Exception as e:
        return GitResponse(success=False, error=str(e))
