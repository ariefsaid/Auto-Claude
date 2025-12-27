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


def get_app_data_dir() -> Path:
    """Get the application data directory based on platform."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "auto-claude-ui"
    elif sys.platform == "darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "auto-claude-ui"
    else:  # Linux
        return Path.home() / ".config" / "auto-claude-ui"


def parse_env_file(content: str) -> dict[str, str]:
    """Parse .env file content into a dictionary."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            result[key] = value
    return result


def load_global_settings() -> dict[str, Any]:
    """Load global settings from disk."""
    settings_path = get_app_data_dir() / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def load_projects() -> list[dict[str, Any]]:
    """Load projects from disk."""
    projects_path = get_app_data_dir() / "projects.json"
    if projects_path.exists():
        try:
            with open(projects_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return []


def get_project_by_path(project_path: str) -> dict[str, Any] | None:
    """Find project by path."""
    projects = load_projects()
    for p in projects:
        if p.get("path") == project_path:
            return p
    return None


def get_combined_env(project_dir: str) -> dict[str, str]:
    """
    Get combined environment variables for subprocess.

    Merges:
    1. Current process environment (os.environ)
    2. Global settings (settings.json)
    3. Project-specific .env file

    Project-specific values take precedence over global settings.

    Args:
        project_dir: Project directory path

    Returns:
        Combined environment dictionary
    """
    env = dict(os.environ)

    # Load global settings
    global_settings = load_global_settings()

    # Apply global settings first
    if global_settings.get("globalClaudeOAuthToken"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = global_settings["globalClaudeOAuthToken"]

    if global_settings.get("globalOpenAIApiKey"):
        env["OPENAI_API_KEY"] = global_settings["globalOpenAIApiKey"]

    if global_settings.get("selectedAgentProvider"):
        env["AGENT_PROVIDER"] = global_settings["selectedAgentProvider"]

    if global_settings.get("globalOpencodeProvider"):
        env["OPENCODE_PROVIDER"] = global_settings["globalOpencodeProvider"]

    if global_settings.get("globalOpencodeModel"):
        env["OPENCODE_MODEL"] = global_settings["globalOpencodeModel"]

    # Extract provider/model from providerCredentials if not set directly
    provider_credentials = global_settings.get("providerCredentials", {})
    if provider_credentials:
        env["PROVIDER_CREDENTIALS"] = json.dumps(provider_credentials)

        # If OPENCODE_PROVIDER not set, try to get from first credential
        if not env.get("OPENCODE_PROVIDER"):
            for cred_key, cred_data in provider_credentials.items():
                if isinstance(cred_data, dict):
                    provider = cred_data.get("provider", cred_key)
                    env["OPENCODE_PROVIDER"] = provider

                    # Also get the model if available
                    if not env.get("OPENCODE_MODEL") and cred_data.get("defaultModel"):
                        env["OPENCODE_MODEL"] = cred_data["defaultModel"]

                    # Get API key for this provider
                    if cred_data.get("apiKey"):
                        # Set provider-specific API key env var
                        # e.g., ZHIPU_API_KEY for zai-glm
                        provider_upper = provider.upper().replace("-", "_")
                        env[f"{provider_upper}_API_KEY"] = cred_data["apiKey"]
                        # Also set generic OPENCODE_API_KEY
                        env["OPENCODE_API_KEY"] = cred_data["apiKey"]

                    break  # Use first configured provider

    # Find project and load its .env file (overrides global settings)
    project = get_project_by_path(project_dir)
    if project:
        auto_build_path = project.get("autoBuildPath")
        if auto_build_path:
            env_path = Path(project_dir) / auto_build_path / ".env"
            if env_path.exists():
                try:
                    content = env_path.read_text()
                    project_env = parse_env_file(content)
                    # Project .env overrides global settings
                    env.update(project_env)
                    logger.info(f"Loaded project .env from {env_path}")
                except OSError as e:
                    logger.warning(f"Failed to read project .env: {e}")

    # Always set Python encoding vars
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    return env


def get_model_from_settings(project_dir: str) -> str | None:
    """
    Get the configured model from settings.

    Checks project .env first, then global settings.

    Args:
        project_dir: Project directory path

    Returns:
        Model identifier or None
    """
    # Check project .env first
    project = get_project_by_path(project_dir)
    if project:
        auto_build_path = project.get("autoBuildPath")
        if auto_build_path:
            env_path = Path(project_dir) / auto_build_path / ".env"
            if env_path.exists():
                try:
                    content = env_path.read_text()
                    project_env = parse_env_file(content)
                    if project_env.get("OPENCODE_MODEL"):
                        return project_env["OPENCODE_MODEL"]
                    if project_env.get("AUTO_BUILD_MODEL"):
                        return project_env["AUTO_BUILD_MODEL"]
                except OSError:
                    pass

    # Check global settings
    global_settings = load_global_settings()
    if global_settings.get("globalOpencodeModel"):
        return global_settings["globalOpencodeModel"]

    # Check providerCredentials for defaultModel
    provider_credentials = global_settings.get("providerCredentials", {})
    for cred_data in provider_credentials.values():
        if isinstance(cred_data, dict) and cred_data.get("defaultModel"):
            return cred_data["defaultModel"]

    return None


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
            # Auto-claude directory is where this script is located (up two levels from api/utils/)
            auto_claude_dir = Path(__file__).parent.parent.parent
            run_script = auto_claude_dir / "run.py"

            # Get Python executable from virtual environment
            venv_python = self._get_venv_python(auto_claude_dir)

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

            # If no model specified in options, get from settings
            if not options or not options.get("model"):
                model = get_model_from_settings(project_dir)
                if model:
                    args.extend(["--model", model])

            # Get combined environment (global settings + project .env)
            combined_env = get_combined_env(project_dir)

            print(f"[IPC] Starting task {self.task_id}: {' '.join(args)}")
            print(
                f"[IPC] Environment: AGENT_PROVIDER={combined_env.get('AGENT_PROVIDER', 'not set')}, OPENCODE_PROVIDER={combined_env.get('OPENCODE_PROVIDER', 'not set')}, OPENCODE_MODEL={combined_env.get('OPENCODE_MODEL', 'not set')}"
            )
            logger.info(f"Starting task {self.task_id}: {' '.join(args)}")

            # Spawn subprocess with combined environment
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(auto_claude_dir),
                env=combined_env,
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

    def _get_venv_python(self, auto_claude_dir: Path) -> Path:
        """
        Get Python executable from virtual environment.

        Args:
            auto_claude_dir: Auto-claude directory

        Returns:
            Path to Python executable
        """
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


class SpecCreationProcess:
    """Manages a Python subprocess for spec creation via spec_runner.py."""

    def __init__(self, task_id: str, ws_manager):
        """
        Initialize spec creation process manager.

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
        spec_dir: str,
        task_description: str,
        auto_approve: bool = True,
    ):
        """
        Start spec creation subprocess.

        Args:
            project_dir: Project directory path
            spec_dir: Spec directory path
            task_description: Task description for spec creation
            auto_approve: Whether to auto-approve spec without review

        Returns:
            True if started successfully
        """
        try:
            # Auto-claude directory is where this script is located
            auto_claude_dir = Path(__file__).parent.parent.parent
            spec_runner_script = auto_claude_dir / "runners" / "spec_runner.py"

            # Get Python executable from virtual environment
            venv_python = self._get_venv_python(auto_claude_dir)

            args = [
                str(venv_python),
                str(spec_runner_script),
                "--task",
                task_description,
                "--project-dir",
                project_dir,
                "--spec-dir",
                spec_dir,
            ]

            if auto_approve:
                args.append("--auto-approve")

            # Get model from settings and pass to spec_runner
            model = get_model_from_settings(project_dir)
            if model:
                args.extend(["--model", model])

            # Get combined environment (global settings + project .env)
            combined_env = get_combined_env(project_dir)

            print(f"[IPC] Starting spec creation {self.task_id}: {' '.join(args)}")
            print(
                f"[IPC] Environment: AGENT_PROVIDER={combined_env.get('AGENT_PROVIDER', 'not set')}, OPENCODE_PROVIDER={combined_env.get('OPENCODE_PROVIDER', 'not set')}, OPENCODE_MODEL={combined_env.get('OPENCODE_MODEL', 'not set')}"
            )
            logger.info(f"Starting spec creation {self.task_id}: {' '.join(args)}")

            # Spawn subprocess with combined environment
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(auto_claude_dir),
                env=combined_env,
            )

            self.is_running = True

            # Start output streaming tasks
            asyncio.create_task(self._stream_stdout())
            asyncio.create_task(self._stream_stderr())
            asyncio.create_task(self._wait_for_exit())

            return True

        except Exception as e:
            logger.error(f"Error starting spec creation {self.task_id}: {e}")
            print(f"Error starting spec creation {self.task_id}: {e}")
            await self.ws_manager.send_error(self.task_id, str(e))
            return False

    async def stop(self):
        """Stop the running subprocess."""
        if self.process and self.is_running:
            logger.info(f"Stopping spec creation {self.task_id}")
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Spec creation {self.task_id} did not terminate, killing..."
                )
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

        except Exception as e:
            logger.error(
                f"Error streaming stdout for spec creation {self.task_id}: {e}"
            )

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
            logger.error(
                f"Error streaming stderr for spec creation {self.task_id}: {e}"
            )

    async def _wait_for_exit(self):
        """Wait for process to exit and send completion event."""
        if not self.process:
            return

        try:
            exit_code = await self.process.wait()
            self.is_running = False

            logger.info(f"Spec creation {self.task_id} exited with code {exit_code}")

            # Determine status based on exit code
            if exit_code == 0:
                status = "spec_ready"
            else:
                status = "spec_failed"

            await self.ws_manager.send_status_change(self.task_id, status)

        except Exception as e:
            logger.error(f"Error waiting for spec creation {self.task_id}: {e}")
            self.is_running = False

    def _get_venv_python(self, auto_claude_dir: Path) -> Path:
        """Get Python executable from virtual environment."""
        venv_dir = auto_claude_dir / ".venv"

        if venv_dir.exists():
            if sys.platform == "win32":
                python_exe = venv_dir / "Scripts" / "python.exe"
            else:
                python_exe = venv_dir / "bin" / "python"

            if python_exe.exists():
                return python_exe

        return Path(sys.executable)


# Global spec creation process registry
_spec_processes: dict[str, SpecCreationProcess] = {}


async def start_spec_creation(
    task_id: str,
    project_dir: str,
    spec_dir: str,
    task_description: str,
    auto_approve: bool,
    ws_manager,
) -> dict[str, Any]:
    """
    Start spec creation via spec_runner.py.

    Args:
        task_id: Task identifier
        project_dir: Project directory
        spec_dir: Spec directory path
        task_description: Task description
        auto_approve: Whether to auto-approve spec
        ws_manager: WebSocket manager

    Returns:
        Result dictionary
    """
    # Stop existing process if running
    if task_id in _spec_processes:
        await _spec_processes[task_id].stop()

    # Create and start new process
    process = SpecCreationProcess(task_id, ws_manager)
    _spec_processes[task_id] = process

    success = await process.start(project_dir, spec_dir, task_description, auto_approve)

    return {
        "success": success,
        "taskId": task_id,
        "status": "spec_creating" if success else "failed",
    }
