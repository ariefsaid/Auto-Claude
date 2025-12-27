"""
Workspace API Routes
====================

REST endpoints for git worktree operations.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


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
        Worktree status
    """
    # TODO: Implement worktree status check
    return WorkspaceResponse(
        success=True,
        data={
            "projectId": project_id,
            "specId": spec_id,
            "message": "Status retrieved",
        },
    )
