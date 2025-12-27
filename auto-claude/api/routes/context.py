"""
Context API Routes
==================

REST endpoints for project context and indexing.
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


class ContextResponse(BaseModel):
    """Generic context response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@router.get("/context", response_model=ContextResponse)
async def get_project_context(project_id: str):
    """
    Get project context/index.

    Returns cached project index if available.

    Args:
        project_id: Project identifier

    Returns:
        Project context data
    """
    project = get_project_by_id(project_id)
    if not project:
        return ContextResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return ContextResponse(success=False, error="Project path not configured")

    context_data: dict[str, Any] = {
        "projectId": project_id,
        "projectPath": project_path,
        "hasIndex": False,
        "index": None,
        "stats": None,
    }

    # Check for project_index.json in .auto-claude directory
    auto_claude_dir = Path(project_path) / ".auto-claude"
    index_file = auto_claude_dir / "project_index.json"

    if index_file.exists():
        try:
            with open(index_file) as f:
                index_data = json.load(f)
            context_data["hasIndex"] = True
            context_data["index"] = index_data
            context_data["stats"] = {
                "fileCount": len(index_data.get("files", [])),
                "lastIndexed": index_data.get("indexed_at"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    # Also check specs directory for context files
    specs_dir = auto_claude_dir / "specs"
    if specs_dir.exists():
        spec_contexts = []
        for spec_dir in specs_dir.iterdir():
            if spec_dir.is_dir():
                spec_context_file = spec_dir / "context.json"
                if spec_context_file.exists():
                    try:
                        with open(spec_context_file) as f:
                            spec_context = json.load(f)
                        spec_contexts.append(
                            {
                                "specId": spec_dir.name,
                                "context": spec_context,
                            }
                        )
                    except (OSError, json.JSONDecodeError):
                        pass
        if spec_contexts:
            context_data["specContexts"] = spec_contexts

    return ContextResponse(success=True, data=context_data)


@router.post("/context/refresh", response_model=ContextResponse)
async def refresh_project_index(project_id: str):
    """
    Refresh/rebuild the project index.

    Scans the project directory and creates a new index.

    Args:
        project_id: Project identifier

    Returns:
        Refresh result
    """
    import time

    project = get_project_by_id(project_id)
    if not project:
        return ContextResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return ContextResponse(success=False, error="Project path not configured")

    try:
        # Create .auto-claude directory if needed
        auto_claude_dir = Path(project_path) / ".auto-claude"
        auto_claude_dir.mkdir(parents=True, exist_ok=True)

        # Build simple file index
        files = []
        ignore_patterns = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".auto-claude",
            ".worktrees",
            "dist",
            "build",
            ".next",
            "coverage",
        }

        ignore_extensions = {
            ".pyc",
            ".pyo",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".class",
            ".jar",
            ".lock",
        }

        def should_ignore(path: Path) -> bool:
            for part in path.parts:
                if part in ignore_patterns:
                    return True
            if path.suffix in ignore_extensions:
                return True
            return False

        project_root = Path(project_path)
        for file_path in project_root.rglob("*"):
            if file_path.is_file() and not should_ignore(file_path):
                rel_path = file_path.relative_to(project_root)
                try:
                    stat = file_path.stat()
                    files.append(
                        {
                            "path": str(rel_path),
                            "size": stat.st_size,
                            "modified": int(stat.st_mtime * 1000),
                            "extension": file_path.suffix,
                        }
                    )
                except OSError:
                    pass

        # Sort by path
        files.sort(key=lambda x: x["path"])

        # Create index
        index_data = {
            "projectId": project_id,
            "projectPath": project_path,
            "indexed_at": int(time.time() * 1000),
            "file_count": len(files),
            "files": files,
        }

        # Save index
        index_file = auto_claude_dir / "project_index.json"
        with open(index_file, "w") as f:
            json.dump(index_data, f, indent=2)

        print(
            f"[Context] Refreshed index for project: {project_id}, {len(files)} files"
        )

        return ContextResponse(
            success=True,
            data={
                "projectId": project_id,
                "fileCount": len(files),
                "indexPath": str(index_file),
                "refreshedAt": index_data["indexed_at"],
            },
        )

    except Exception as e:
        return ContextResponse(success=False, error=str(e))


@router.get("/context/search", response_model=ContextResponse)
async def search_context(project_id: str, query: str, limit: int = 20):
    """
    Search project context/files.

    Args:
        project_id: Project identifier
        query: Search query
        limit: Maximum results to return

    Returns:
        Search results
    """
    project = get_project_by_id(project_id)
    if not project:
        return ContextResponse(success=False, error=f"Project not found: {project_id}")

    project_path = project.get("path")
    if not project_path:
        return ContextResponse(success=False, error="Project path not configured")

    # Load index
    index_file = Path(project_path) / ".auto-claude" / "project_index.json"
    if not index_file.exists():
        return ContextResponse(
            success=False,
            error="Project index not found. Run refresh first.",
        )

    try:
        with open(index_file) as f:
            index_data = json.load(f)

        files = index_data.get("files", [])
        query_lower = query.lower()

        # Simple filename search
        results = []
        for file_info in files:
            file_path = file_info.get("path", "")
            if query_lower in file_path.lower():
                results.append(file_info)
                if len(results) >= limit:
                    break

        return ContextResponse(
            success=True,
            data={
                "projectId": project_id,
                "query": query,
                "results": results,
                "totalMatches": len(results),
            },
        )

    except Exception as e:
        return ContextResponse(success=False, error=str(e))
