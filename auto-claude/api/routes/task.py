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


@router.post("/tasks/start", response_model=TaskResponse)
async def start_task(request: TaskStartRequest):
    """
    Start task execution.

    Spawns Python subprocess to run the task using run.py.
    Progress is streamed via WebSocket.

    Args:
        request: Task start parameters

    Returns:
        Success/error response
    """
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

        # Start task execution via IPC bridge
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
