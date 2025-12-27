"""
Task API Routes
===============

REST endpoints for task execution, management, and monitoring.
Mirrors Electron IPC task handlers.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from api.utils.ipc_bridge import (
    get_task_status,
    start_spec_creation,
    start_task_execution,
    stop_task_execution,
)
from fastapi import APIRouter, HTTPException
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


# Request/Response Models
class TaskCreateRequest(BaseModel):
    """Request to create a new task."""

    projectId: str
    title: str
    description: str | None = None
    requireReviewBeforeCoding: bool = False


class TaskStartRequest(BaseModel):
    """Request to start a task."""

    taskId: str
    projectId: str
    specId: str | None = None
    options: dict[str, Any] | None = None


class TaskStopRequest(BaseModel):
    """Request to stop a task."""

    taskId: str


class TaskResponse(BaseModel):
    """Generic task response."""

    success: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:50]  # Limit length


def get_next_spec_number(specs_dir: Path) -> str:
    """Get the next available spec number (001, 002, etc.)."""
    existing = []
    if specs_dir.exists():
        for item in specs_dir.iterdir():
            if item.is_dir():
                # Extract number prefix if exists (e.g., "001-feature" -> 1)
                match = re.match(r"^(\d+)-", item.name)
                if match:
                    existing.append(int(match.group(1)))

    next_num = max(existing, default=0) + 1
    return f"{next_num:03d}"


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """
    Create a new task with spec directory structure.

    Creates the spec directory with initial files (implementation_plan.json,
    task_metadata.json, requirements.json).

    Args:
        request: Task creation parameters

    Returns:
        Created task data
    """
    import time

    try:
        # Get project
        project = get_project_by_id(request.projectId)
        if not project:
            return TaskResponse(
                success=False, error=f"Project not found: {request.projectId}"
            )

        project_path = project.get("path")
        if not project_path:
            return TaskResponse(success=False, error="Project path not configured")

        # Create spec directory
        specs_dir = Path(project_path) / ".auto-claude" / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)

        # Generate spec ID: XXX-slugified-title
        spec_number = get_next_spec_number(specs_dir)
        title_slug = slugify(request.title)
        spec_id = f"{spec_number}-{title_slug}" if title_slug else spec_number

        spec_dir = specs_dir / spec_id
        spec_dir.mkdir(parents=True, exist_ok=True)

        # Generate task ID
        task_id = f"task-{int(time.time() * 1000)}"

        # Create implementation_plan.json
        implementation_plan = {
            "specId": spec_id,
            "title": request.title,
            "description": request.description or "",
            "status": "backlog",
            "subtasks": [],
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000),
        }
        with open(spec_dir / "implementation_plan.json", "w") as f:
            json.dump(implementation_plan, f, indent=2)

        # Create task_metadata.json
        task_metadata = {
            "taskId": task_id,
            "specId": spec_id,
            "projectId": request.projectId,
            "title": request.title,
            "description": request.description or "",
            "status": "backlog",
            "requireReviewBeforeCoding": request.requireReviewBeforeCoding,
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000),
        }
        with open(spec_dir / "task_metadata.json", "w") as f:
            json.dump(task_metadata, f, indent=2)

        # Create requirements.json
        requirements = {
            "title": request.title,
            "description": request.description or "",
            "requirements": [],
            "constraints": [],
        }
        with open(spec_dir / "requirements.json", "w") as f:
            json.dump(requirements, f, indent=2)

        print(f"[Task] Created task: id={task_id}, specId={spec_id}, path={spec_dir}")

        return TaskResponse(
            success=True,
            data={
                "id": task_id,
                "specId": spec_id,
                "projectId": request.projectId,
                "title": request.title,
                "description": request.description,
                "status": "backlog",
                "specDir": str(spec_dir),
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/start", response_model=TaskResponse)
async def start_task(request: TaskStartRequest):
    """
    Start task execution.

    If spec.md doesn't exist, first runs spec_runner.py to create the spec.
    Then spawns Python subprocess to run the task using run.py.
    Progress is streamed via WebSocket.

    Args:
        request: Task start parameters

    Returns:
        Success/error response
    """
    print(
        f"[Task] start_task called: taskId={request.taskId}, projectId={request.projectId}, specId={request.specId}"
    )
    try:
        # Get project path from project ID
        project = get_project_by_id(request.projectId)
        if not project:
            return TaskResponse(
                success=False, error=f"Project not found: {request.projectId}"
            )

        project_path = project.get("path")
        if not project_path:
            return TaskResponse(success=False, error="Project path not configured")

        # Get spec ID from request or extract from taskId
        spec_id = request.specId
        if not spec_id:
            # Try to extract spec ID from taskId (e.g., "task-123-spec-001" -> "001")
            # For now, we need specId to be provided
            return TaskResponse(success=False, error="specId is required")

        # Import ws_manager here to avoid circular imports
        from api.server import ws_manager

        # Check if spec.md exists
        spec_dir = Path(project_path) / ".auto-claude" / "specs" / spec_id
        spec_file = spec_dir / "spec.md"

        if not spec_file.exists():
            # Need to run spec creation first
            print(f"[Task] spec.md not found at {spec_file}, starting spec creation")

            # Get task description from metadata or requirements
            task_description = ""
            metadata_file = spec_dir / "task_metadata.json"
            requirements_file = spec_dir / "requirements.json"

            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                        task_description = metadata.get("description") or metadata.get(
                            "title", ""
                        )
                except (OSError, json.JSONDecodeError):
                    pass

            if not task_description and requirements_file.exists():
                try:
                    with open(requirements_file) as f:
                        requirements = json.load(f)
                        task_description = requirements.get(
                            "description"
                        ) or requirements.get("title", "")
                except (OSError, json.JSONDecodeError):
                    pass

            if not task_description:
                task_description = spec_id  # Fallback to spec ID

            # Determine if we should auto-approve based on options or metadata
            auto_approve = True
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                        # If requireReviewBeforeCoding is set, don't auto-approve
                        if metadata.get("requireReviewBeforeCoding"):
                            auto_approve = False
                except (OSError, json.JSONDecodeError):
                    pass

            # Start spec creation
            result = await start_spec_creation(
                task_id=request.taskId,
                project_dir=project_path,
                spec_dir=str(spec_dir),
                task_description=task_description,
                auto_approve=auto_approve,
                ws_manager=ws_manager,
            )

            return TaskResponse(
                success=result.get("success", False),
                data={
                    **result,
                    "phase": "spec_creation",
                    "message": "Spec creation started. Task will run after spec is ready.",
                },
            )

        # spec.md exists, start task execution via IPC bridge
        result = await start_task_execution(
            task_id=request.taskId,
            project_dir=project_path,
            spec_id=spec_id,
            options=request.options or {},
            ws_manager=ws_manager,
        )

        return TaskResponse(success=result.get("success", False), data=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/stop", response_model=TaskResponse)
async def stop_task(request: TaskStopRequest):
    """
    Stop a running task.

    Kills the Python subprocess for the specified task.

    Args:
        request: Task stop parameters

    Returns:
        Success/error response
    """
    try:
        result = await stop_task_execution(request.taskId)
        return TaskResponse(success=result.get("success", False), data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    Get task details and status.

    Reads task state from filesystem (implementation_plan.json, etc.)

    Args:
        task_id: Task identifier

    Returns:
        Task details
    """
    try:
        result = get_task_status(task_id)
        return TaskResponse(success=result.get("success", False), data=result)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.get("/tasks", response_model=TaskResponse)
async def list_tasks(project_id: str):
    """
    List all tasks for a project.

    Reads spec directories from .auto-claude/specs/

    Args:
        project_id: Project identifier

    Returns:
        List of tasks
    """
    try:
        project = get_project_by_id(project_id)
        if not project:
            return TaskResponse(success=True, data=[])

        project_path = project.get("path")
        if not project_path:
            return TaskResponse(success=True, data=[])

        specs_dir = Path(project_path) / ".auto-claude" / "specs"
        if not specs_dir.exists():
            return TaskResponse(success=True, data=[])

        tasks = []
        for spec_dir in specs_dir.iterdir():
            if not spec_dir.is_dir():
                continue

            spec_id = spec_dir.name
            task_data = {
                "id": f"task-{spec_id}",
                "specId": spec_id,
                "projectId": project_id,
                "title": spec_id,
                "status": "backlog",
            }

            # Try to read spec.md for title
            spec_file = spec_dir / "spec.md"
            if spec_file.exists():
                try:
                    content = spec_file.read_text()
                    # Extract title from first heading
                    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    if match:
                        task_data["title"] = match.group(1)
                except OSError:
                    pass

            # Try to read implementation_plan.json for status
            plan_file = spec_dir / "implementation_plan.json"
            if plan_file.exists():
                try:
                    with open(plan_file) as f:
                        plan = json.load(f)
                        if plan.get("status"):
                            task_data["status"] = plan["status"]
                except (OSError, json.JSONDecodeError):
                    pass

            tasks.append(task_data)

        return TaskResponse(success=True, data=tasks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
