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


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class TaskStatusRequest(BaseModel):
    """Request to update task status."""

    status: str
    autoStart: bool = False


class TaskReviewRequest(BaseModel):
    """Request to review (approve/reject) a task."""

    action: str  # "approve" or "reject"
    feedback: str | None = None
    projectId: str


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


@router.get("/tasks/running", response_model=TaskResponse)
async def get_running_tasks():
    """
    Get count and list of currently running tasks.

    Returns:
        Running task count and IDs
    """
    from api.utils.ipc_bridge import get_running_tasks

    try:
        running = get_running_tasks()
        return TaskResponse(
            success=True,
            data={
                "count": len(running),
                "tasks": running,
            },
        )
    except Exception as e:
        return TaskResponse(success=False, error=str(e))


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


def find_spec_dir(project_id: str, spec_id: str) -> tuple[Path | None, str | None]:
    """
    Find spec directory for a task.

    Args:
        project_id: Project identifier
        spec_id: Spec identifier (can be spec_id or task-{spec_id})

    Returns:
        Tuple of (spec_dir Path, error message)
    """
    project = get_project_by_id(project_id)
    if not project:
        return None, f"Project not found: {project_id}"

    project_path = project.get("path")
    if not project_path:
        return None, "Project path not configured"

    # Handle both spec_id and task-{spec_id} formats
    if spec_id.startswith("task-"):
        # Try to extract spec_id from task_id by looking for spec dirs
        specs_dir = Path(project_path) / ".auto-claude" / "specs"
        if specs_dir.exists():
            # Check task_metadata.json files for matching taskId
            for spec_dir in specs_dir.iterdir():
                if spec_dir.is_dir():
                    metadata_file = spec_dir / "task_metadata.json"
                    if metadata_file.exists():
                        try:
                            with open(metadata_file) as f:
                                metadata = json.load(f)
                                if metadata.get("taskId") == spec_id:
                                    return spec_dir, None
                        except (OSError, json.JSONDecodeError):
                            pass
        return None, f"Spec not found for task: {spec_id}"

    spec_dir = Path(project_path) / ".auto-claude" / "specs" / spec_id
    if not spec_dir.exists():
        return None, f"Spec directory not found: {spec_id}"

    return spec_dir, None


@router.put("/tasks/{spec_id}", response_model=TaskResponse)
async def update_task(spec_id: str, request: TaskUpdateRequest, project_id: str):
    """
    Update a task's metadata.

    Args:
        spec_id: Spec identifier
        request: Update parameters
        project_id: Project identifier (query param)

    Returns:
        Updated task data
    """
    import time

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Update task_metadata.json
        metadata_file = spec_dir / "task_metadata.json"
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        # Apply updates
        if request.title is not None:
            metadata["title"] = request.title
        if request.description is not None:
            metadata["description"] = request.description
        if request.status is not None:
            metadata["status"] = request.status
        if request.metadata is not None:
            metadata.update(request.metadata)

        metadata["updatedAt"] = int(time.time() * 1000)

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        # Also update implementation_plan.json if status changed
        if request.status is not None:
            plan_file = spec_dir / "implementation_plan.json"
            if plan_file.exists():
                try:
                    with open(plan_file) as f:
                        plan = json.load(f)
                    plan["status"] = request.status
                    plan["updatedAt"] = int(time.time() * 1000)
                    with open(plan_file, "w") as f:
                        json.dump(plan, f, indent=2)
                except (OSError, json.JSONDecodeError):
                    pass

        print(f"[Task] Updated task: specId={spec_id}")
        return TaskResponse(success=True, data=metadata)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{spec_id}", response_model=TaskResponse)
async def delete_task(spec_id: str, project_id: str):
    """
    Delete a task and its spec directory.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier (query param)

    Returns:
        Success/error response
    """
    import shutil

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Remove the spec directory
        shutil.rmtree(spec_dir)

        print(f"[Task] Deleted task: specId={spec_id}")
        return TaskResponse(success=True, data={"deleted": spec_id})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{spec_id}/status", response_model=TaskResponse)
async def update_task_status(spec_id: str, request: TaskStatusRequest, project_id: str):
    """
    Update task status with optional auto-start.

    Args:
        spec_id: Spec identifier
        request: Status update parameters
        project_id: Project identifier (query param)

    Returns:
        Updated task data
    """
    import time

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        valid_statuses = [
            "backlog",
            "ready",
            "in_progress",
            "review",
            "done",
            "failed",
            "blocked",
        ]
        if request.status not in valid_statuses:
            return TaskResponse(
                success=False,
                error=f"Invalid status: {request.status}. Valid: {valid_statuses}",
            )

        # Update implementation_plan.json
        plan_file = spec_dir / "implementation_plan.json"
        plan = {}
        if plan_file.exists():
            try:
                with open(plan_file) as f:
                    plan = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        plan["status"] = request.status
        plan["updatedAt"] = int(time.time() * 1000)

        with open(plan_file, "w") as f:
            json.dump(plan, f, indent=2)

        # Also update task_metadata.json
        metadata_file = spec_dir / "task_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                metadata["status"] = request.status
                metadata["updatedAt"] = int(time.time() * 1000)
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)
            except (OSError, json.JSONDecodeError):
                pass

        print(f"[Task] Updated status: specId={spec_id}, status={request.status}")

        # Auto-start if requested and status is ready/in_progress
        if request.autoStart and request.status in ["ready", "in_progress"]:
            # Get task ID from metadata
            task_id = None
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                        task_id = metadata.get("taskId", f"task-{spec_id}")
                except (OSError, json.JSONDecodeError):
                    task_id = f"task-{spec_id}"

            if task_id:
                from api.server import ws_manager

                project = get_project_by_id(project_id)
                project_path = project.get("path") if project else None

                if project_path:
                    spec_file = spec_dir / "spec.md"
                    if spec_file.exists():
                        result = await start_task_execution(
                            task_id=task_id,
                            project_dir=project_path,
                            spec_id=spec_id,
                            options={},
                            ws_manager=ws_manager,
                        )
                        return TaskResponse(
                            success=True,
                            data={"status": request.status, "started": True, **result},
                        )

        return TaskResponse(success=True, data={"status": request.status})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{spec_id}/recover", response_model=TaskResponse)
async def recover_task(spec_id: str, project_id: str):
    """
    Recover a stuck task by analyzing its state and resetting if needed.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier (query param)

    Returns:
        Recovery result
    """
    import time

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Read implementation plan to analyze state
        plan_file = spec_dir / "implementation_plan.json"
        plan = {}
        if plan_file.exists():
            try:
                with open(plan_file) as f:
                    plan = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        # Analyze subtasks to determine actual status
        subtasks = plan.get("subtasks", [])
        completed_count = sum(1 for s in subtasks if s.get("status") == "done")
        failed_count = sum(1 for s in subtasks if s.get("status") == "failed")
        in_progress_count = sum(1 for s in subtasks if s.get("status") == "in_progress")

        # Determine new status based on subtask states
        new_status = "backlog"
        if len(subtasks) == 0:
            new_status = "backlog"
        elif completed_count == len(subtasks):
            new_status = "review"
        elif failed_count > 0:
            new_status = "failed"
        elif in_progress_count > 0 or completed_count > 0:
            new_status = "in_progress"
        else:
            new_status = "ready"

        # Reset any in_progress subtasks to pending
        for subtask in subtasks:
            if subtask.get("status") == "in_progress":
                subtask["status"] = "pending"

        plan["status"] = new_status
        plan["subtasks"] = subtasks
        plan["updatedAt"] = int(time.time() * 1000)
        plan["recoveredAt"] = int(time.time() * 1000)

        with open(plan_file, "w") as f:
            json.dump(plan, f, indent=2)

        print(
            f"[Task] Recovered task: specId={spec_id}, newStatus={new_status}, "
            f"completed={completed_count}/{len(subtasks)}"
        )

        return TaskResponse(
            success=True,
            data={
                "specId": spec_id,
                "previousStatus": plan.get("status"),
                "newStatus": new_status,
                "subtaskStats": {
                    "total": len(subtasks),
                    "completed": completed_count,
                    "failed": failed_count,
                    "inProgress": in_progress_count,
                },
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{spec_id}/review", response_model=TaskResponse)
async def review_task(spec_id: str, request: TaskReviewRequest):
    """
    Approve or reject a completed task.

    Approve: Marks as done, generates QA report
    Reject: Writes QA_FIX_REQUEST.md, can restart QA agent

    Args:
        spec_id: Spec identifier
        request: Review parameters

    Returns:
        Review result
    """
    import time

    try:
        spec_dir, error = find_spec_dir(request.projectId, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        if request.action not in ["approve", "reject"]:
            return TaskResponse(
                success=False, error="Invalid action. Must be 'approve' or 'reject'"
            )

        # Read current plan
        plan_file = spec_dir / "implementation_plan.json"
        plan = {}
        if plan_file.exists():
            try:
                with open(plan_file) as f:
                    plan = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        if request.action == "approve":
            # Mark as done
            plan["status"] = "done"
            plan["reviewedAt"] = int(time.time() * 1000)
            plan["reviewResult"] = "approved"

            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)

            # Write QA report
            qa_report = spec_dir / "qa_report.md"
            report_content = f"""# QA Report

## Status: APPROVED

**Reviewed at:** {time.strftime("%Y-%m-%d %H:%M:%S")}

## Summary
Task has been reviewed and approved.

{f"## Feedback{chr(10)}{request.feedback}" if request.feedback else ""}
"""
            qa_report.write_text(report_content)

            print(f"[Task] Approved task: specId={spec_id}")
            return TaskResponse(
                success=True,
                data={"specId": spec_id, "status": "done", "action": "approved"},
            )

        else:  # reject
            # Mark for QA fix
            plan["status"] = "in_progress"
            plan["reviewedAt"] = int(time.time() * 1000)
            plan["reviewResult"] = "rejected"
            plan["qaFixNeeded"] = True

            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)

            # Write QA fix request
            fix_request = spec_dir / "QA_FIX_REQUEST.md"
            fix_content = f"""# QA Fix Request

## Status: NEEDS FIXES

**Requested at:** {time.strftime("%Y-%m-%d %H:%M:%S")}

## Issues to Address

{request.feedback or "Please review and fix the identified issues."}

## Instructions
1. Review the feedback above
2. Make necessary changes
3. Run tests to verify fixes
4. Mark as ready for re-review
"""
            fix_request.write_text(fix_content)

            print(f"[Task] Rejected task: specId={spec_id}")
            return TaskResponse(
                success=True,
                data={
                    "specId": spec_id,
                    "status": "in_progress",
                    "action": "rejected",
                    "fixRequestPath": str(fix_request),
                },
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{spec_id}/archive", response_model=TaskResponse)
async def archive_task(spec_id: str, project_id: str):
    """
    Archive a completed task.

    Moves the task to archived status in metadata.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier (query param)

    Returns:
        Archive result
    """
    import time

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Update task_metadata.json
        metadata_file = spec_dir / "task_metadata.json"
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        metadata["archived"] = True
        metadata["archivedAt"] = int(time.time() * 1000)
        metadata["updatedAt"] = int(time.time() * 1000)

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"[Task] Archived task: specId={spec_id}")
        return TaskResponse(
            success=True,
            data={"specId": spec_id, "archived": True},
        )

    except Exception as e:
        return TaskResponse(success=False, error=str(e))


@router.post("/tasks/{spec_id}/unarchive", response_model=TaskResponse)
async def unarchive_task(spec_id: str, project_id: str):
    """
    Unarchive a task.

    Restores the task from archived status.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier (query param)

    Returns:
        Unarchive result
    """
    import time

    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Update task_metadata.json
        metadata_file = spec_dir / "task_metadata.json"
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        metadata["archived"] = False
        metadata.pop("archivedAt", None)
        metadata["updatedAt"] = int(time.time() * 1000)

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"[Task] Unarchived task: specId={spec_id}")
        return TaskResponse(
            success=True,
            data={"specId": spec_id, "archived": False},
        )

    except Exception as e:
        return TaskResponse(success=False, error=str(e))


@router.get("/tasks/{spec_id}/logs", response_model=TaskResponse)
async def get_task_logs(spec_id: str, project_id: str, limit: int = 100):
    """
    Get task execution logs.

    Args:
        spec_id: Spec identifier
        project_id: Project identifier (query param)
        limit: Maximum number of log entries to return

    Returns:
        Task logs
    """
    try:
        spec_dir, error = find_spec_dir(project_id, spec_id)
        if error:
            return TaskResponse(success=False, error=error)

        # Read task_logs.json
        logs_file = spec_dir / "task_logs.json"
        logs = []
        if logs_file.exists():
            try:
                with open(logs_file) as f:
                    logs_data = json.load(f)
                    if isinstance(logs_data, list):
                        logs = logs_data[-limit:]
                    elif isinstance(logs_data, dict):
                        # Handle structured log format
                        logs = logs_data.get("entries", [])[-limit:]
            except (OSError, json.JSONDecodeError):
                pass

        # Also check for console output logs
        console_log = spec_dir / "console.log"
        console_output = ""
        if console_log.exists():
            try:
                console_output = console_log.read_text()
                # Take last N lines
                lines = console_output.split("\n")
                console_output = "\n".join(lines[-limit:])
            except OSError:
                pass

        return TaskResponse(
            success=True,
            data={
                "specId": spec_id,
                "logs": logs,
                "consoleOutput": console_output,
                "logsPath": str(logs_file),
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
