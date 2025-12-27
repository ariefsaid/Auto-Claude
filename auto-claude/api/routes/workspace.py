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


class MergeRequest(BaseModel):
    """Request to merge a worktree."""

    projectId: str
    specId: str
    commitMessage: str | None = None
    stageOnly: bool = False  # If true, stage changes but don't commit


class DiscardRequest(BaseModel):
    """Request to discard a worktree."""

    projectId: str
    specId: str
    deleteBranch: bool = True  # Also delete the branch


async def run_git_command(
    args: list[str], cwd: str, timeout: int = 60
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


@router.get("/workspace/diff", response_model=WorkspaceResponse)
async def get_worktree_diff(project_id: str, spec_id: str):
    """
    Get detailed diff of changes in a worktree.

    Args:
        project_id: Project identifier
        spec_id: Spec identifier

    Returns:
        Diff information with file-by-file changes
    """
    project = get_project_by_id(project_id)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {project_id}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    worktree_path = Path(project_path) / ".worktrees" / spec_id
    if not worktree_path.exists():
        return WorkspaceResponse(success=False, error=f"Worktree not found: {spec_id}")

    diff_data = {
        "specId": spec_id,
        "files": [],
        "summary": {"additions": 0, "deletions": 0, "changedFiles": 0},
    }

    try:
        # Get list of changed files with stats
        returncode, stdout, stderr = await run_git_command(
            ["diff", "--stat", "HEAD"],
            str(worktree_path),
        )

        if returncode == 0 and stdout:
            lines = stdout.split("\n")
            for line in lines[:-1]:  # Skip summary line
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        filename = parts[0].strip()
                        stats = parts[1].strip()
                        diff_data["files"].append(
                            {"filename": filename, "stats": stats}
                        )

        # Get detailed diff
        returncode, stdout, stderr = await run_git_command(
            ["diff", "HEAD"],
            str(worktree_path),
        )

        if returncode == 0:
            diff_data["diff"] = stdout

        # Get diff stats summary
        returncode, stdout, stderr = await run_git_command(
            ["diff", "--shortstat", "HEAD"],
            str(worktree_path),
        )

        if returncode == 0 and stdout:
            # Parse "X files changed, Y insertions(+), Z deletions(-)"
            import re

            match = re.search(r"(\d+) files? changed", stdout)
            if match:
                diff_data["summary"]["changedFiles"] = int(match.group(1))
            match = re.search(r"(\d+) insertions?\(\+\)", stdout)
            if match:
                diff_data["summary"]["additions"] = int(match.group(1))
            match = re.search(r"(\d+) deletions?\(-\)", stdout)
            if match:
                diff_data["summary"]["deletions"] = int(match.group(1))

        # Also get staged changes
        returncode, stdout, stderr = await run_git_command(
            ["diff", "--cached", "--stat"],
            str(worktree_path),
        )

        if returncode == 0 and stdout:
            diff_data["stagedChanges"] = stdout

        return WorkspaceResponse(success=True, data=diff_data)

    except Exception as e:
        return WorkspaceResponse(success=False, error=str(e))


@router.post("/workspace/merge-preview", response_model=WorkspaceResponse)
async def preview_merge(request: MergeRequest):
    """
    Preview what would happen if we merge the worktree.

    Checks for conflicts, uncommitted changes, etc.

    Args:
        request: Merge preview parameters

    Returns:
        Preview of merge including potential conflicts
    """
    project = get_project_by_id(request.projectId)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {request.projectId}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    worktree_path = Path(project_path) / ".worktrees" / request.specId
    if not worktree_path.exists():
        return WorkspaceResponse(
            success=False, error=f"Worktree not found: {request.specId}"
        )

    preview_data = {
        "specId": request.specId,
        "canMerge": True,
        "warnings": [],
        "conflicts": [],
        "changes": [],
    }

    try:
        # Check for uncommitted changes in worktree
        returncode, stdout, stderr = await run_git_command(
            ["status", "--porcelain"],
            str(worktree_path),
        )

        if returncode == 0 and stdout:
            preview_data["warnings"].append(
                "Worktree has uncommitted changes that will not be included in merge"
            )
            preview_data["uncommittedFiles"] = stdout.split("\n")

        # Get the branch name
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            str(worktree_path),
        )

        branch_name = stdout if returncode == 0 else f"auto-claude/{request.specId}"
        preview_data["branch"] = branch_name

        # Check for uncommitted changes in main project
        returncode, stdout, stderr = await run_git_command(
            ["status", "--porcelain"],
            str(project_path),
        )

        if returncode == 0 and stdout:
            preview_data["warnings"].append(
                "Main project has uncommitted changes - recommend committing or stashing first"
            )
            preview_data["mainProjectChanges"] = stdout.split("\n")

        # Do a dry-run merge to check for conflicts
        returncode, stdout, stderr = await run_git_command(
            ["merge", "--no-commit", "--no-ff", branch_name, "--dry-run"],
            str(project_path),
            timeout=120,
        )

        if returncode != 0:
            if "CONFLICT" in stderr or "conflict" in stderr.lower():
                preview_data["canMerge"] = False
                preview_data["conflicts"].append(stderr)
                preview_data["warnings"].append(
                    "Merge would result in conflicts that need resolution"
                )
            elif "Already up to date" in stdout or "Already up to date" in stderr:
                preview_data["warnings"].append(
                    "Branch is already merged or has no new changes"
                )

        # Get list of commits to be merged
        returncode, stdout, stderr = await run_git_command(
            ["log", "--oneline", f"HEAD..{branch_name}"],
            str(project_path),
        )

        if returncode == 0 and stdout:
            preview_data["commits"] = stdout.split("\n")
            preview_data["commitCount"] = len(preview_data["commits"])
        else:
            preview_data["commits"] = []
            preview_data["commitCount"] = 0

        # Get files that would be changed
        returncode, stdout, stderr = await run_git_command(
            ["diff", "--name-only", f"HEAD...{branch_name}"],
            str(project_path),
        )

        if returncode == 0 and stdout:
            preview_data["changes"] = stdout.split("\n")

        return WorkspaceResponse(success=True, data=preview_data)

    except Exception as e:
        return WorkspaceResponse(success=False, error=str(e))


@router.post("/workspace/merge", response_model=WorkspaceResponse)
async def merge_worktree(request: MergeRequest):
    """
    Merge worktree changes into main project.

    Args:
        request: Merge parameters

    Returns:
        Merge result
    """

    project = get_project_by_id(request.projectId)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {request.projectId}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    worktree_path = Path(project_path) / ".worktrees" / request.specId
    if not worktree_path.exists():
        return WorkspaceResponse(
            success=False, error=f"Worktree not found: {request.specId}"
        )

    merge_result = {
        "specId": request.specId,
        "merged": False,
        "commitHash": None,
    }

    try:
        # Get the branch name
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            str(worktree_path),
        )

        branch_name = stdout if returncode == 0 else f"auto-claude/{request.specId}"
        merge_result["branch"] = branch_name

        # Check for uncommitted changes in worktree and commit them first
        returncode, stdout, stderr = await run_git_command(
            ["status", "--porcelain"],
            str(worktree_path),
        )

        if returncode == 0 and stdout:
            # Stage and commit uncommitted changes
            await run_git_command(["add", "-A"], str(worktree_path))
            commit_msg = (
                request.commitMessage or f"Auto-commit before merge: {request.specId}"
            )
            await run_git_command(
                ["commit", "-m", commit_msg],
                str(worktree_path),
            )
            merge_result["autoCommitted"] = True

        # Perform the merge in main project
        if request.stageOnly:
            # Merge but don't commit (stage only)
            returncode, stdout, stderr = await run_git_command(
                ["merge", "--no-commit", "--no-ff", branch_name],
                str(project_path),
                timeout=300,
            )
        else:
            # Full merge with commit
            commit_msg = (
                request.commitMessage or f"Merge {branch_name}: {request.specId}"
            )
            returncode, stdout, stderr = await run_git_command(
                ["merge", "--no-ff", "-m", commit_msg, branch_name],
                str(project_path),
                timeout=300,
            )

        if returncode != 0:
            if "CONFLICT" in stderr or "conflict" in stderr.lower():
                merge_result["error"] = "Merge conflicts detected"
                merge_result["conflicts"] = stderr
                return WorkspaceResponse(
                    success=False, data=merge_result, error="Merge conflicts"
                )

            merge_result["error"] = stderr
            return WorkspaceResponse(success=False, data=merge_result, error=stderr)

        merge_result["merged"] = True
        merge_result["output"] = stdout

        # Get the new commit hash
        if not request.stageOnly:
            returncode, stdout, stderr = await run_git_command(
                ["rev-parse", "HEAD"],
                str(project_path),
            )
            if returncode == 0:
                merge_result["commitHash"] = stdout

        print(
            f"[Workspace] Merged worktree: specId={request.specId}, branch={branch_name}"
        )
        return WorkspaceResponse(success=True, data=merge_result)

    except Exception as e:
        return WorkspaceResponse(success=False, error=str(e))


@router.post("/workspace/discard", response_model=WorkspaceResponse)
async def discard_worktree(request: DiscardRequest):
    """
    Discard a worktree and optionally delete its branch.

    Args:
        request: Discard parameters

    Returns:
        Discard result
    """
    import shutil

    project = get_project_by_id(request.projectId)
    if not project:
        return WorkspaceResponse(
            success=False, error=f"Project not found: {request.projectId}"
        )

    project_path = project.get("path")
    if not project_path:
        return WorkspaceResponse(success=False, error="Project path not configured")

    worktree_path = Path(project_path) / ".worktrees" / request.specId
    if not worktree_path.exists():
        return WorkspaceResponse(
            success=False, error=f"Worktree not found: {request.specId}"
        )

    discard_result = {
        "specId": request.specId,
        "discarded": False,
        "branchDeleted": False,
    }

    try:
        # Get the branch name before removing worktree
        returncode, stdout, stderr = await run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            str(worktree_path),
        )

        branch_name = stdout if returncode == 0 else f"auto-claude/{request.specId}"
        discard_result["branch"] = branch_name

        # Remove the worktree using git
        returncode, stdout, stderr = await run_git_command(
            ["worktree", "remove", "--force", str(worktree_path)],
            str(project_path),
        )

        if returncode != 0:
            # Fallback: manually remove the directory
            shutil.rmtree(worktree_path, ignore_errors=True)

            # Also prune worktree references
            await run_git_command(
                ["worktree", "prune"],
                str(project_path),
            )

        discard_result["discarded"] = True

        # Optionally delete the branch
        if request.deleteBranch and branch_name != "main" and branch_name != "master":
            returncode, stdout, stderr = await run_git_command(
                ["branch", "-D", branch_name],
                str(project_path),
            )
            discard_result["branchDeleted"] = returncode == 0

        print(
            f"[Workspace] Discarded worktree: specId={request.specId}, "
            f"branchDeleted={discard_result['branchDeleted']}"
        )
        return WorkspaceResponse(success=True, data=discard_result)

    except Exception as e:
        return WorkspaceResponse(success=False, error=str(e))
