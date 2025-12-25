"""Tests for TaskLogger functionality."""
import json
import os
import tempfile
from pathlib import Path
import pytest

from task_logger.logger import TaskLogger
from task_logger.models import LogPhase
from task_logger.utils import get_task_logger


def test_logger_initialization():
    """Test TaskLogger initialization in temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        logger = TaskLogger(spec_dir)
        assert logger.spec_dir == spec_dir
        assert logger.log_file == spec_dir / "task_logs.json"


def test_logger_saves_logs():
    """Test that logs are persisted to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        logger = TaskLogger(spec_dir)
        logger.start_phase(LogPhase.PLANNING, "Starting planning")
        logger.log("Planning message")
        logger.end_phase(LogPhase.PLANNING, success=True)

        # Verify file was written
        assert logger.log_file.exists()

        # Verify content
        with open(logger.log_file) as f:
            data = json.load(f)

        assert data["spec_id"] is not None
        assert data["phases"]["planning"]["status"] == "completed"
        assert len(data["phases"]["planning"]["entries"]) > 0


def test_logger_handles_missing_directory():
    """Test that logger raises error for missing directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "nonexistent"

        with pytest.raises(ValueError, match="does not exist"):
            get_task_logger(spec_dir)


def test_logger_handles_readonly_directory():
    """Test that logger raises error for readonly directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        # Make directory readonly
        os.chmod(spec_dir, 0o444)

        try:
            with pytest.raises(ValueError, match="not writable"):
                get_task_logger(spec_dir)
        finally:
            # Restore permissions for cleanup
            os.chmod(spec_dir, 0o755)


def test_logger_multiple_phases():
    """Test logging through multiple phases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        logger = TaskLogger(spec_dir)

        # Planning phase
        logger.start_phase(LogPhase.PLANNING, "Starting planning")
        logger.log("Planning entry 1")
        logger.log("Planning entry 2")
        logger.end_phase(LogPhase.PLANNING, success=True)

        # Coding phase
        logger.start_phase(LogPhase.CODING, "Starting coding")
        logger.log("Coding entry 1")
        logger.log("Coding entry 2")
        logger.end_phase(LogPhase.CODING, success=True)

        # Validation phase
        logger.start_phase(LogPhase.VALIDATION, "Starting validation")
        logger.log("Validation entry 1")
        logger.end_phase(LogPhase.VALIDATION, success=True)

        # Verify file was written
        assert logger.log_file.exists()

        # Verify all phases are logged
        with open(logger.log_file) as f:
            data = json.load(f)

        assert data["phases"]["planning"]["status"] == "completed"
        assert len(data["phases"]["planning"]["entries"]) >= 2

        assert data["phases"]["coding"]["status"] == "completed"
        assert len(data["phases"]["coding"]["entries"]) >= 2

        assert data["phases"]["validation"]["status"] == "completed"
        assert len(data["phases"]["validation"]["entries"]) >= 1


def test_logger_tool_logging():
    """Test tool start/end logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        logger = TaskLogger(spec_dir)
        logger.start_phase(LogPhase.CODING, "Starting coding")

        # Log tool execution
        logger.tool_start("Read", "/path/to/file.py")
        logger.log("Reading file contents")
        logger.tool_end("Read", success=True, result="File read successfully")

        logger.end_phase(LogPhase.CODING, success=True)

        # Verify logs contain tool entries
        with open(logger.log_file) as f:
            data = json.load(f)

        coding_entries = data["phases"]["coding"]["entries"]
        tool_starts = [e for e in coding_entries if e["type"] == "tool_start"]
        tool_ends = [e for e in coding_entries if e["type"] == "tool_end"]

        assert len(tool_starts) >= 1
        assert len(tool_ends) >= 1
        assert tool_starts[0]["tool_name"] == "Read"


def test_logger_reuse():
    """Test that get_task_logger reuses existing logger for same spec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "spec"
        spec_dir.mkdir()

        # Get logger first time
        logger1 = get_task_logger(spec_dir)
        logger1.start_phase(LogPhase.PLANNING, "Starting")
        logger1.log("Entry 1")

        # Get logger second time - should be same instance
        logger2 = get_task_logger(spec_dir)
        assert logger2 is logger1

        # Log should be cumulative
        logger2.log("Entry 2")
        logger2.end_phase(LogPhase.PLANNING, success=True)

        # Verify both entries are in the log
        with open(logger1.log_file) as f:
            data = json.load(f)

        assert len(data["phases"]["planning"]["entries"]) >= 2
