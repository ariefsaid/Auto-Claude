"""
Utility functions for task logging.
"""

import os
import sys
from pathlib import Path

from .logger import TaskLogger

# Global logger instance for easy access
_current_logger: TaskLogger | None = None


def get_task_logger(
    spec_dir: Path | None = None, emit_markers: bool = True
) -> TaskLogger | None:
    """
    Get or create a task logger for the given spec directory.

    Args:
        spec_dir: Path to the spec directory (creates new logger if different from current)
        emit_markers: Whether to emit streaming markers

    Returns:
        TaskLogger instance or None if no spec_dir

    Raises:
        ValueError: If spec_dir does not exist or is not writable
    """
    global _current_logger

    if spec_dir is None:
        return _current_logger

    spec_dir = Path(spec_dir)

    # Validate spec directory exists
    if not spec_dir.exists():
        raise ValueError(
            f"Spec directory does not exist: {spec_dir}\n" f"CWD: {os.getcwd()}"
        )

    # Validate spec directory is writable
    if not os.access(spec_dir, os.W_OK):
        raise ValueError(
            f"Spec directory is not writable: {spec_dir}\n"
            f"Permissions: {oct(spec_dir.stat().st_mode) if spec_dir.exists() else 'N/A'}"
        )

    # Create or reuse logger
    if _current_logger is None or _current_logger.spec_dir != spec_dir:
        print(f"[TaskLogger] Creating new logger for {spec_dir}", file=sys.stderr)
        _current_logger = TaskLogger(spec_dir, emit_markers)
    else:
        print(f"[TaskLogger] Reusing existing logger for {spec_dir}", file=sys.stderr)

    return _current_logger


def clear_task_logger() -> None:
    """Clear the global task logger."""
    global _current_logger
    _current_logger = None


def update_task_logger_path(new_spec_dir: Path) -> None:
    """
    Update the global task logger's spec directory after a rename.

    This should be called after renaming a spec directory to ensure
    the logger continues writing to the correct location.

    Args:
        new_spec_dir: The new path to the spec directory
    """
    global _current_logger

    if _current_logger is None:
        return

    # Update the logger's internal paths
    _current_logger.spec_dir = Path(new_spec_dir)
    _current_logger.log_file = _current_logger.spec_dir / TaskLogger.LOG_FILE

    # Update spec_id in the storage
    _current_logger.storage.update_spec_id(new_spec_dir.name)

    # Save to the new location
    _current_logger.storage.save()
