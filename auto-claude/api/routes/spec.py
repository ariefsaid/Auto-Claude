"""
Spec API Routes
================

REST endpoints for spec content, implementation plans, and task logs.
"""

import json
import os
from pathlib import Path
from typing import Any

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


def get_projects_path() -> Path:
    """Get the projects file path."""
    return get_app_data_path() / "projects.json"


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


def find_spec_dir(project: dict[str, Any], spec_id: str) -> Path | None:
    """Find the spec directory for a given spec ID."""
    project_path = project.get("path")
    auto_build_path = project.get("autoBuildPath", "auto-claude")

    if not project_path:
        return None

    # Check in project's .auto-claude/specs directory
    specs_dir = Path(project_path) / ".auto-claude" / "specs"
    if specs_dir.exists():
        for item in specs_dir.iterdir():
            if item.is_dir() and item.name.startswith(spec_id):
                return item

    # Check in auto-claude/specs directory (legacy)
    legacy_specs_dir = Path(project_path) / auto_build_path / "specs"
    if legacy_specs_dir.exists():
        for item in legacy_specs_dir.iterdir():
            if item.is_dir() and item.name.startswith(spec_id):
                return item

    return None


# =============================================================================
# Request/Response Models
# =============================================================================


class SpecResponse(BaseModel):
    """Generic spec response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


# =============================================================================
# Spec Content Endpoints
# =============================================================================


@router.get("/spec/{spec_id}", response_model=SpecResponse)
async def get_spec_content(spec_id: str, project_id: str):
    """
    Get the spec.md content for a spec.

    Args:
        spec_id: Spec identifier (e.g., "001")
        project_id: Project identifier

    Returns:
        Spec content and metadata
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    spec_file = spec_dir / "spec.md"
    if not spec_file.exists():
        return SpecResponse(
            success=False, error=f"spec.md not found in {spec_dir.name}"
        )

    try:
        content = spec_file.read_text()

        # Also get requirements.json if it exists
        requirements = None
        requirements_file = spec_dir / "requirements.json"
        if requirements_file.exists():
            try:
                requirements = json.loads(requirements_file.read_text())
            except json.JSONDecodeError:
                pass

        # Get context.json if it exists
        context = None
        context_file = spec_dir / "context.json"
        if context_file.exists():
            try:
                context = json.loads(context_file.read_text())
            except json.JSONDecodeError:
                pass

        return SpecResponse(
            success=True,
            data={
                "specId": spec_id,
                "specDir": str(spec_dir),
                "content": content,
                "requirements": requirements,
                "context": context,
            },
        )

    except OSError as e:
        return SpecResponse(success=False, error=f"Failed to read spec: {e}")


@router.get("/spec/{spec_id}/plan", response_model=SpecResponse)
async def get_implementation_plan(spec_id: str, project_id: str):
    """
    Get the implementation plan for a spec.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier

    Returns:
        Implementation plan with subtasks and status
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    plan_file = spec_dir / "implementation_plan.json"
    if not plan_file.exists():
        return SpecResponse(
            success=True,
            data={
                "specId": spec_id,
                "hasPlan": False,
                "plan": None,
            },
        )

    try:
        plan = json.loads(plan_file.read_text())

        # Calculate progress
        subtasks = plan.get("subtasks", [])
        total = len(subtasks)
        completed = sum(1 for s in subtasks if s.get("status") == "completed")
        in_progress = sum(1 for s in subtasks if s.get("status") == "in_progress")
        failed = sum(1 for s in subtasks if s.get("status") == "failed")

        return SpecResponse(
            success=True,
            data={
                "specId": spec_id,
                "hasPlan": True,
                "plan": plan,
                "progress": {
                    "total": total,
                    "completed": completed,
                    "inProgress": in_progress,
                    "failed": failed,
                    "pending": total - completed - in_progress - failed,
                    "percentComplete": round((completed / total) * 100)
                    if total > 0
                    else 0,
                },
            },
        )

    except json.JSONDecodeError as e:
        return SpecResponse(success=False, error=f"Invalid plan JSON: {e}")
    except OSError as e:
        return SpecResponse(success=False, error=f"Failed to read plan: {e}")


@router.get("/spec/{spec_id}/qa", response_model=SpecResponse)
async def get_qa_report(spec_id: str, project_id: str):
    """
    Get the QA report for a spec.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier

    Returns:
        QA report content and fix requests
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    qa_data: dict[str, Any] = {
        "specId": spec_id,
        "hasReport": False,
        "report": None,
        "fixRequest": None,
    }

    # Get QA report
    qa_report_file = spec_dir / "qa_report.md"
    if qa_report_file.exists():
        try:
            qa_data["hasReport"] = True
            qa_data["report"] = qa_report_file.read_text()
        except OSError:
            pass

    # Get fix request if exists
    fix_request_file = spec_dir / "QA_FIX_REQUEST.md"
    if fix_request_file.exists():
        try:
            qa_data["fixRequest"] = fix_request_file.read_text()
        except OSError:
            pass

    return SpecResponse(success=True, data=qa_data)


# =============================================================================
# Task Logging Endpoints
# =============================================================================


@router.get("/spec/{spec_id}/logs", response_model=SpecResponse)
async def get_task_logs(spec_id: str, project_id: str, tail: int = 0):
    """
    Get task logs for a spec.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier
        tail: If > 0, return only the last N lines

    Returns:
        Task logs including task_logs.json and console.log
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    logs_data: dict[str, Any] = {
        "specId": spec_id,
        "taskLogs": None,
        "consoleLogs": None,
        "agentLogs": [],
    }

    # Get task_logs.json (structured logs)
    task_logs_file = spec_dir / "task_logs.json"
    if task_logs_file.exists():
        try:
            logs_data["taskLogs"] = json.loads(task_logs_file.read_text())
        except (OSError, json.JSONDecodeError):
            pass

    # Get console.log (raw output)
    console_log_file = spec_dir / "console.log"
    if console_log_file.exists():
        try:
            content = console_log_file.read_text()
            if tail > 0:
                lines = content.splitlines()
                content = "\n".join(lines[-tail:])
            logs_data["consoleLogs"] = content
        except OSError:
            pass

    # Get agent-specific logs
    logs_dir = spec_dir / "logs"
    if logs_dir.exists() and logs_dir.is_dir():
        agent_logs = []
        for log_file in sorted(logs_dir.glob("*.log")):
            try:
                content = log_file.read_text()
                if tail > 0:
                    lines = content.splitlines()
                    content = "\n".join(lines[-tail:])
                agent_logs.append(
                    {
                        "name": log_file.stem,
                        "filename": log_file.name,
                        "content": content,
                        "size": log_file.stat().st_size,
                    }
                )
            except OSError:
                pass
        logs_data["agentLogs"] = agent_logs

    # Get memory logs if they exist
    memory_dir = spec_dir / "memory"
    if memory_dir.exists() and memory_dir.is_dir():
        memory_logs = []
        for log_file in sorted(memory_dir.glob("*.json")):
            try:
                content = json.loads(log_file.read_text())
                memory_logs.append(
                    {
                        "name": log_file.stem,
                        "filename": log_file.name,
                        "content": content,
                    }
                )
            except (OSError, json.JSONDecodeError):
                pass
        if memory_logs:
            logs_data["memoryLogs"] = memory_logs

    return SpecResponse(success=True, data=logs_data)


@router.post("/spec/{spec_id}/logs/clear", response_model=SpecResponse)
async def clear_task_logs(spec_id: str, project_id: str):
    """
    Clear task logs for a spec.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier

    Returns:
        Result of log clearing operation
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    cleared: list[str] = []
    errors: list[str] = []

    # Clear console.log
    console_log = spec_dir / "console.log"
    if console_log.exists():
        try:
            console_log.write_text("")
            cleared.append("console.log")
        except OSError as e:
            errors.append(f"console.log: {e}")

    # Clear task_logs.json
    task_logs = spec_dir / "task_logs.json"
    if task_logs.exists():
        try:
            task_logs.write_text("[]")
            cleared.append("task_logs.json")
        except OSError as e:
            errors.append(f"task_logs.json: {e}")

    # Clear logs directory
    logs_dir = spec_dir / "logs"
    if logs_dir.exists() and logs_dir.is_dir():
        for log_file in logs_dir.glob("*.log"):
            try:
                log_file.write_text("")
                cleared.append(f"logs/{log_file.name}")
            except OSError as e:
                errors.append(f"logs/{log_file.name}: {e}")

    return SpecResponse(
        success=len(errors) == 0,
        data={
            "specId": spec_id,
            "cleared": cleared,
            "errors": errors,
        },
        error="; ".join(errors) if errors else None,
    )


@router.get("/spec/{spec_id}/files", response_model=SpecResponse)
async def list_spec_files(spec_id: str, project_id: str):
    """
    List all files in a spec directory.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier

    Returns:
        List of files with metadata
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    files: list[dict[str, Any]] = []

    def scan_dir(directory: Path, prefix: str = "") -> None:
        try:
            for item in sorted(directory.iterdir()):
                rel_path = f"{prefix}{item.name}" if prefix else item.name
                if item.is_file():
                    files.append(
                        {
                            "name": item.name,
                            "path": rel_path,
                            "size": item.stat().st_size,
                            "isDirectory": False,
                        }
                    )
                elif item.is_dir():
                    files.append(
                        {
                            "name": item.name,
                            "path": rel_path,
                            "isDirectory": True,
                        }
                    )
                    scan_dir(item, f"{rel_path}/")
        except OSError:
            pass

    scan_dir(spec_dir)

    return SpecResponse(
        success=True,
        data={
            "specId": spec_id,
            "specDir": str(spec_dir),
            "files": files,
        },
    )


@router.get("/spec/{spec_id}/file/{file_path:path}", response_model=SpecResponse)
async def get_spec_file(spec_id: str, project_id: str, file_path: str):
    """
    Get content of a specific file in a spec directory.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier
        file_path: Relative path to file within spec directory

    Returns:
        File content
    """
    project = get_project_by_id(project_id)
    if not project:
        return SpecResponse(success=False, error=f"Project not found: {project_id}")

    spec_dir = find_spec_dir(project, spec_id)
    if not spec_dir:
        return SpecResponse(success=False, error=f"Spec not found: {spec_id}")

    target_file = spec_dir / file_path

    # Security: ensure file is within spec directory
    try:
        target_file.resolve().relative_to(spec_dir.resolve())
    except ValueError:
        return SpecResponse(
            success=False, error="Access denied: path outside spec directory"
        )

    if not target_file.exists():
        return SpecResponse(success=False, error=f"File not found: {file_path}")

    if not target_file.is_file():
        return SpecResponse(success=False, error=f"Not a file: {file_path}")

    try:
        # Try to read as text
        content = target_file.read_text()
        is_json = file_path.endswith(".json")

        if is_json:
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass

        return SpecResponse(
            success=True,
            data={
                "specId": spec_id,
                "filePath": file_path,
                "content": content,
                "isJson": is_json and isinstance(content, (dict, list)),
                "size": target_file.stat().st_size,
            },
        )

    except UnicodeDecodeError:
        return SpecResponse(
            success=False,
            error=f"Cannot read binary file: {file_path}",
        )
    except OSError as e:
        return SpecResponse(success=False, error=f"Failed to read file: {e}")
