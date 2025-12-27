"""
Project API Routes
==================

REST endpoints for project management.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ProjectResponse(BaseModel):
    """Generic project response."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@router.get("/projects", response_model=ProjectResponse)
async def list_projects():
    """
    List all projects.

    Returns:
        List of projects
    """
    # TODO: Implement project listing from filesystem
    return ProjectResponse(
        success=True, data={"projects": [], "message": "Projects retrieved"}
    )


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
