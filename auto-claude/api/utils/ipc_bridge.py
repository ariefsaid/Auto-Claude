"""
IPC Bridge
==========

Bridges HTTP/WebSocket API to existing Python CLI logic (run.py, spec_runner.py).
Manages subprocess execution and streams output to WebSocket clients.

This module replicates the functionality of Electron's agent-process.ts
but for HTTP/WebSocket instead of IPC.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskProcess:
    """Manages a Python subprocess for task execution."""

    def __init__(self, task_id: str, ws_manager):
        """
        Initialize task process manager.

        Args:
            task_id: Unique task identifier
            ws_manager: WebSocket manager for streaming output
        """
        self.task_id = task_id
        self.ws_manager = ws_manager
        self.process: asyncio.subprocess.Process | None = None
        self.is_running = False

    async def start(
        self,
        project_dir: str,
        spec_id: str,
        options: dict[str, Any | None] = None,
    ):
        """
        Start task execution subprocess.

        Args:
            project_dir: Project directory path
            spec_id: Spec identifier
            options: Optional execution options

        Returns:
            True if started successfully
        """
        try:
            # Get Python executable from virtual environment
            venv_python = self._get_venv_python(project_dir)

            # Build command args
            auto_claude_dir = Path(project_dir) / "auto-claude"
            run_script = auto_claude_dir / "run.py"

            args = [
                str(venv_python),
                str(run_script),
                "--spec",
                spec_id,
                "--project-dir",
                project_dir,
                "--auto-continue",  # Non-interactive mode
                "--force",  # Skip approval check
            ]

            # Add optional flags
            if options:
                if options.get("model"):
                    args.extend(["--model", options["model"]])
                if options.get("baseBranch"):
                    args.extend(["--base-branch", options["baseBranch"]])
                if options.get("qaOnly"):
                    args.append("--qa")

            logger.info(f"Starting task {self.task_id}: {' '.join(args)}")

            # Spawn subprocess
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(auto_claude_dir),
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
            )

            self.is_running = True

            # Start output streaming tasks
            asyncio.create_task(self._stream_stdout())
            asyncio.create_task(self._stream_stderr())
            asyncio.create_task(self._wait_for_exit())

            return True

        except Exception as e:
            logger.error(f"Error starting task {self.task_id}: {e}")
            await self.ws_manager.send_error(self.task_id, str(e))
            return False

    async def stop(self):
        """Stop the running subprocess."""
        if self.process and self.is_running:
            logger.info(f"Stopping task {self.task_id}")
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Task {self.task_id} did not terminate, killing...")
                self.process.kill()
                await self.process.wait()
            finally:
                self.is_running = False

    async def _stream_stdout(self):
        """Stream stdout to WebSocket clients."""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                log = line.decode("utf-8", errors="replace")
                await self.ws_manager.send_log(self.task_id, log)

                # Parse for special markers (phase transitions, etc.)
                await self._parse_log_markers(log)

        except Exception as e:
            logger.error(f"Error streaming stdout for {self.task_id}: {e}")

    async def _stream_stderr(self):
        """Stream stderr to WebSocket clients."""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break

                log = line.decode("utf-8", errors="replace")
                await self.ws_manager.send_log(self.task_id, log)

        except Exception as e:
            logger.error(f"Error streaming stderr for {self.task_id}: {e}")

    async def _wait_for_exit(self):
        """Wait for process to exit and send completion event."""
        if not self.process:
            return

        try:
            exit_code = await self.process.wait()
            self.is_running = False

            logger.info(f"Task {self.task_id} exited with code {exit_code}")

            # Determine status based on exit code
            if exit_code == 0:
                status = "completed"
            else:
                status = "failed"

            await self.ws_manager.send_status_change(self.task_id, status)

        except Exception as e:
            logger.error(f"Error waiting for task {self.task_id}: {e}")
            self.is_running = False

    async def _parse_log_markers(self, log: str):
        """
        Parse log output for special markers.

        Look for JSON markers like __TASK_LOG_PHASE_START__, etc.
        These are emitted by the Python CLI to indicate phase transitions.

        Args:
            log: Log line to parse
        """
        try:
            # Phase start marker
            if "__TASK_LOG_PHASE_START__:" in log:
                json_str = log.split("__TASK_LOG_PHASE_START__:")[1].strip()
                data = json.loads(json_str)
                await self.ws_manager.send_execution_progress(
                    self.task_id,
                    {"phase": data.get("phase"), "status": "started"},
                )

            # Phase end marker
            elif "__TASK_LOG_PHASE_END__:" in log:
                json_str = log.split("__TASK_LOG_PHASE_END__:")[1].strip()
                data = json.loads(json_str)
                await self.ws_manager.send_execution_progress(
                    self.task_id,
                    {"phase": data.get("phase"), "status": "completed"},
                )

        except Exception:
            # Ignore parsing errors - not all logs have markers
            pass

    def _get_venv_python(self, project_dir: str) -> Path:
        """
        Get Python executable from virtual environment.

        Args:
            project_dir: Project directory

        Returns:
            Path to Python executable
        """
        auto_claude_dir = Path(project_dir) / "auto-claude"
        venv_dir = auto_claude_dir / ".venv"

        # Check for venv
        if venv_dir.exists():
            if sys.platform == "win32":
                python_exe = venv_dir / "Scripts" / "python.exe"
            else:
                python_exe = venv_dir / "bin" / "python"

            if python_exe.exists():
                return python_exe

        # Fallback to system Python
        return Path(sys.executable)


# Global process registry
_task_processes: dict[str, TaskProcess] = {}


async def start_task_execution(
    task_id: str,
    project_dir: str,
    spec_id: str,
    options: dict[str, Any | None],
    ws_manager,
) -> dict[str, Any]:
    """
    Start task execution.

    Args:
        task_id: Task identifier
        project_dir: Project directory
        spec_id: Spec identifier
        options: Execution options
        ws_manager: WebSocket manager

    Returns:
        Result dictionary
    """
    # Stop existing process if running
    if task_id in _task_processes:
        await _task_processes[task_id].stop()

    # Create and start new process
    process = TaskProcess(task_id, ws_manager)
    _task_processes[task_id] = process

    success = await process.start(project_dir, spec_id, options)

    return {
        "success": success,
        "taskId": task_id,
        "status": "started" if success else "failed",
    }


async def stop_task_execution(task_id: str) -> dict[str, Any]:
    """
    Stop task execution.

    Args:
        task_id: Task identifier

    Returns:
        Result dictionary
    """
    if task_id in _task_processes:
        await _task_processes[task_id].stop()
        del _task_processes[task_id]
        return {"success": True, "taskId": task_id, "status": "stopped"}
    else:
        return {"success": False, "taskId": task_id, "error": "Task not found"}


def get_task_status(task_id: str) -> dict[str, Any]:
    """
    Get task status.

    Args:
        task_id: Task identifier

    Returns:
        Status dictionary
    """
    if task_id in _task_processes:
        process = _task_processes[task_id]
        return {
            "success": True,
            "taskId": task_id,
            "status": "running" if process.is_running else "stopped",
        }
    else:
        return {"success": False, "taskId": task_id, "error": "Task not found"}
