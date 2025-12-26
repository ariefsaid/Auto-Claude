"""
OpenCode Subprocess Manager
============================

Subprocess lifecycle management for OpenCode CLI.
Handles spawning, communication, and cleanup of OpenCode CLI processes.

This module provides:
- OpenCodeSubprocess: Manages OpenCode CLI subprocess lifecycle
- Process spawning with proper arguments
- Streaming stdout/stderr handling
- Timeout management
- Graceful shutdown with signal handling
- Error handling for crashes, timeouts, and missing CLI

The subprocess manager:
- Spawns `opencode build --non-interactive` subprocess
- Passes provider, model, and API key arguments
- Handles stdin for sending queries
- Streams stdout for receiving responses
- Captures stderr for error reporting
- Manages process lifecycle (start, stop, cleanup)

Usage:
    from auto_claude.core.providers.adapters.opencode_subprocess import (
        OpenCodeSubprocess,
        OpenCodeSubprocessError,
    )

    # Create subprocess manager
    subprocess_mgr = OpenCodeSubprocess(
        provider="openai",
        model="gpt-4o",
        api_key="sk-...",
    )

    # Use as async context manager
    async with subprocess_mgr as proc:
        # Send a query
        await proc.send_query("What files are in this directory?")

        # Stream responses
        async for line in proc.read_output_stream():
            process(line)

    # Or manually manage lifecycle
    await subprocess_mgr.start()
    try:
        await subprocess_mgr.send_query("...")
        output = await subprocess_mgr.read_output()
    finally:
        await subprocess_mgr.stop()
"""

import asyncio
import os
import shutil
import signal
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class OpenCodeSubprocessError(Exception):
    """
    Exception raised when OpenCode subprocess operations fail.

    Attributes:
        message: Error description
        exit_code: Process exit code (if available)
        stderr: Captured stderr output (if available)
    """

    def __init__(
        self,
        message: str,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.exit_code is not None:
            parts.append(f"Exit code: {self.exit_code}")
        if self.stderr:
            parts.append(f"Stderr: {self.stderr[:500]}")
        return " | ".join(parts)


class OpenCodeNotInstalledError(OpenCodeSubprocessError):
    """
    Exception raised when OpenCode CLI is not installed.

    Provides installation instructions for the user.
    """

    INSTALLATION_INSTRUCTIONS = """
OpenCode CLI is not installed or not found in PATH.

To install OpenCode, run:
    curl -fsSL https://opencode.ai/install | bash

Or visit: https://opencode.ai/docs/installation

After installation, ensure 'opencode' is in your PATH.
"""

    def __init__(self) -> None:
        super().__init__(
            "OpenCode CLI not installed",
            exit_code=None,
            stderr=self.INSTALLATION_INSTRUCTIONS,
        )


class OpenCodeTimeoutError(OpenCodeSubprocessError):
    """
    Exception raised when OpenCode subprocess times out.

    Attributes:
        timeout_seconds: The timeout that was exceeded
        operation: The operation that timed out
    """

    def __init__(self, timeout_seconds: float, operation: str = "operation") -> None:
        super().__init__(
            f"OpenCode {operation} timed out after {timeout_seconds} seconds",
            exit_code=None,
            stderr=None,
        )
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class OpenCodeCrashError(OpenCodeSubprocessError):
    """
    Exception raised when OpenCode subprocess crashes unexpectedly.
    """

    def __init__(self, exit_code: int, stderr: str | None = None) -> None:
        message = f"OpenCode CLI crashed with exit code {exit_code}"
        super().__init__(message, exit_code=exit_code, stderr=stderr)


@dataclass
class SubprocessConfig:
    """
    Configuration for OpenCode subprocess.

    Attributes:
        provider: AI provider to use (openai, anthropic, google, etc.)
        model: Model name to use (gpt-4o, claude-3-5-sonnet, etc.)
        api_key: API key for the provider (optional, can use env var)
        working_dir: Working directory for the subprocess
        timeout: Default timeout for operations in seconds
        env: Additional environment variables
        _current_query: Internal field to store the current query (for command building)
    """

    provider: str
    model: str | None = None
    api_key: str | None = None
    working_dir: Path | None = None
    timeout: float = 300.0  # 5 minutes default
    env: dict[str, str] = field(default_factory=dict)
    _current_query: str | None = field(default=None, init=False, repr=False)

    def get_command_args(self) -> list[str]:
        """
        Get command-line arguments for OpenCode CLI.

        OpenCode CLI format: opencode run [message] --model provider/model --format json

        Returns:
            List of command-line arguments
        """
        args = ["run"]  # Use 'run' command, not 'build'

        # Add query message as positional argument (if provided)
        if self._current_query:
            args.append(self._current_query)

        # Model format: provider/model (e.g., "zai-coding-plan/glm-4.7")
        if self.provider and self.model:
            model_spec = f"{self.provider}/{self.model}"
            args.extend(["--model", model_spec])
        elif self.model:
            # If model already includes provider (e.g., "zai-coding-plan/glm-4.7")
            args.extend(["--model", self.model])

        # Request JSON output for parsing
        args.extend(["--format", "json"])

        # Note: API key is passed via environment variable for security

        return args

    def get_env(self) -> dict[str, str]:
        """
        Get environment variables for subprocess.

        Returns:
            Dictionary of environment variables
        """
        env = os.environ.copy()

        # Add custom environment variables
        env.update(self.env)

        # Set API key if provided
        if self.api_key:
            # Provider-specific API key environment variables
            provider_env_vars = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
                "aws-bedrock": "AWS_ACCESS_KEY_ID",
                "groq": "GROQ_API_KEY",
                "azure": "AZURE_API_KEY",
                "zai": "ZAI_API_KEY",
                "zai-coding-plan": "ZAI_API_KEY",  # Z.ai coding plan uses same env var
                "openrouter": "OPENROUTER_API_KEY",
                "opencode": "OPENAI_API_KEY",  # OpenCode default uses OpenAI
            }
            env_var = provider_env_vars.get(
                self.provider, f"{self.provider.upper().replace('-', '_')}_API_KEY"
            )
            env[env_var] = self.api_key

        return env


@dataclass
class OpenCodeSubprocess:
    """
    Manages OpenCode CLI subprocess lifecycle.

    Handles spawning, communication, and cleanup of OpenCode CLI processes.
    Supports streaming output, timeout management, and graceful shutdown.

    Attributes:
        config: Subprocess configuration
        _process: The asyncio subprocess (when running)
        _started: Whether the subprocess has been started
        _stopped: Whether the subprocess has been stopped

    Example:
        config = SubprocessConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-...",
        )
        subprocess_mgr = OpenCodeSubprocess(config)

        async with subprocess_mgr:
            await subprocess_mgr.send_query("List files")
            async for line in subprocess_mgr.read_output_stream():
                print(line)
    """

    config: SubprocessConfig
    _process: asyncio.subprocess.Process | None = field(default=None, init=False)
    _started: bool = field(default=False, init=False)
    _stopped: bool = field(default=False, init=False)
    _stderr_buffer: str = field(default="", init=False)

    @classmethod
    def from_config(
        cls,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        working_dir: Path | None = None,
        timeout: float = 300.0,
    ) -> "OpenCodeSubprocess":
        """
        Create subprocess manager from configuration parameters.

        Args:
            provider: AI provider to use
            model: Model name to use
            api_key: API key for the provider
            working_dir: Working directory for the subprocess
            timeout: Default timeout in seconds

        Returns:
            Configured OpenCodeSubprocess instance
        """
        config = SubprocessConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            working_dir=working_dir,
            timeout=timeout,
        )
        return cls(config=config)

    @staticmethod
    def find_opencode_executable() -> str | None:
        """
        Find the OpenCode CLI executable.

        Searches for 'opencode' in PATH and common installation locations.

        Returns:
            Path to opencode executable or None if not found
        """
        # Check PATH first
        opencode_path = shutil.which("opencode")
        if opencode_path:
            return opencode_path

        # Check common installation locations
        common_paths = [
            Path.home() / ".local" / "bin" / "opencode",
            Path.home() / "bin" / "opencode",
            Path("/usr/local/bin/opencode"),
            Path("/usr/bin/opencode"),
        ]

        for path in common_paths:
            if path.exists() and path.is_file():
                return str(path)

        return None

    @staticmethod
    def is_installed() -> bool:
        """
        Check if OpenCode CLI is installed.

        Returns:
            True if OpenCode is installed and accessible
        """
        return OpenCodeSubprocess.find_opencode_executable() is not None

    @property
    def is_running(self) -> bool:
        """
        Check if the subprocess is currently running.

        Returns:
            True if process is started and not stopped
        """
        return (
            self._started
            and not self._stopped
            and self._process is not None
            and self._process.returncode is None
        )

    async def start(self) -> None:
        """
        Start the OpenCode subprocess.

        Spawns the OpenCode CLI process with the configured parameters.

        Raises:
            OpenCodeNotInstalledError: If OpenCode CLI is not installed
            OpenCodeSubprocessError: If process fails to start
        """
        if self._started:
            if self.is_running:
                return  # Already running
            # Process was started but stopped, need to restart
            self._stopped = False

        # Find executable
        executable = self.find_opencode_executable()
        if not executable:
            raise OpenCodeNotInstalledError()

        # Build command
        cmd = [executable] + self.config.get_command_args()

        # Get environment
        env = self.config.get_env()

        # Get working directory
        cwd = self.config.working_dir or Path.cwd()

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
            )
            self._started = True
            self._stopped = False
            self._stderr_buffer = ""

        except FileNotFoundError as e:
            raise OpenCodeNotInstalledError() from e
        except PermissionError as e:
            raise OpenCodeSubprocessError(
                f"Permission denied executing OpenCode CLI: {e}"
            ) from e
        except OSError as e:
            raise OpenCodeSubprocessError(
                f"Failed to start OpenCode subprocess: {e}"
            ) from e

    async def stop(self, timeout: float | None = None) -> None:
        """
        Stop the OpenCode subprocess gracefully.

        Attempts graceful shutdown first, then forceful termination.

        Args:
            timeout: Timeout for graceful shutdown (default: 5 seconds)
        """
        if not self._process or self._stopped:
            return

        timeout = timeout or 5.0

        try:
            # Try graceful shutdown first
            if self._process.stdin:
                self._process.stdin.close()
                await self._process.stdin.wait_closed()

            try:
                # Wait for process to exit gracefully
                await asyncio.wait_for(
                    self._process.wait(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Graceful shutdown failed, send SIGTERM
                self._send_signal(signal.SIGTERM)

                try:
                    await asyncio.wait_for(
                        self._process.wait(),
                        timeout=2.0,
                    )
                except asyncio.TimeoutError:
                    # SIGTERM failed, force kill
                    self._send_signal(signal.SIGKILL)
                    await self._process.wait()

        except ProcessLookupError:
            # Process already dead
            pass
        finally:
            self._stopped = True

    def _send_signal(self, sig: signal.Signals) -> None:
        """
        Send a signal to the subprocess.

        Args:
            sig: Signal to send
        """
        if self._process and self._process.returncode is None:
            try:
                self._process.send_signal(sig)
            except ProcessLookupError:
                pass  # Process already dead

    async def send_query(self, query: str) -> None:
        """
        Send a query to the OpenCode subprocess.

        For OpenCode CLI, the message must be passed as a positional argument
        when starting the process, not via stdin. This method restarts the
        process with the query included in the command.

        Args:
            query: The query text to send

        Raises:
            OpenCodeSubprocessError: If subprocess fails to start
        """
        # Stop existing process if running
        if self.is_running:
            await self.stop()

        # Store query in config for get_command_args to use
        self.config._current_query = query  # type: ignore

        # Start subprocess with query in command args
        await self.start()

    async def read_output(self, timeout: float | None = None) -> str:
        """
        Read all output from the subprocess.

        Args:
            timeout: Timeout in seconds (default: use config timeout)

        Returns:
            Complete stdout output as string

        Raises:
            OpenCodeTimeoutError: If read times out
            OpenCodeCrashError: If subprocess crashes
        """
        if not self._process or not self._process.stdout:
            raise OpenCodeSubprocessError("Cannot read output: subprocess not running")

        timeout = timeout or self.config.timeout

        try:
            stdout, stderr = await asyncio.wait_for(
                self._process.communicate(),
                timeout=timeout,
            )

            if stderr:
                self._stderr_buffer = stderr.decode(errors="replace")

            # Check exit code
            if self._process.returncode != 0:
                raise OpenCodeCrashError(
                    self._process.returncode or -1,
                    stderr=self._stderr_buffer,
                )

            return stdout.decode(errors="replace")

        except asyncio.TimeoutError as e:
            await self.stop()
            raise OpenCodeTimeoutError(timeout, "read_output") from e

    async def read_output_stream(
        self,
        timeout: float | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream output lines from the subprocess.

        Yields lines as they become available from stdout.

        Args:
            timeout: Timeout for each read operation

        Yields:
            Lines of output as they become available

        Raises:
            OpenCodeTimeoutError: If read times out
            OpenCodeCrashError: If subprocess crashes
        """
        if not self._process or not self._process.stdout:
            raise OpenCodeSubprocessError("Cannot read output: subprocess not running")

        timeout = timeout or self.config.timeout

        try:
            while True:
                try:
                    line = await asyncio.wait_for(
                        self._process.stdout.readline(),
                        timeout=timeout,
                    )

                    if not line:
                        # EOF reached
                        break

                    yield line.decode(errors="replace").rstrip("\n\r")

                except asyncio.TimeoutError as e:
                    await self.stop()
                    raise OpenCodeTimeoutError(timeout, "read_stream") from e

            # Check for errors after stream ends
            await self._check_exit_status()

        except OpenCodeSubprocessError:
            raise
        except Exception as e:
            await self._capture_stderr()
            raise OpenCodeSubprocessError(
                f"Stream read error: {e}",
                stderr=self._stderr_buffer,
            ) from e

    async def _capture_stderr(self) -> None:
        """Capture any remaining stderr output."""
        if self._process and self._process.stderr:
            try:
                stderr = await asyncio.wait_for(
                    self._process.stderr.read(),
                    timeout=1.0,
                )
                if stderr:
                    self._stderr_buffer = stderr.decode(errors="replace")
            except asyncio.TimeoutError:
                pass

    async def _check_exit_status(self) -> None:
        """
        Check subprocess exit status and raise appropriate errors.

        Raises:
            OpenCodeCrashError: If process exited with non-zero code
        """
        if self._process and self._process.returncode is not None:
            if self._process.returncode != 0:
                await self._capture_stderr()
                raise OpenCodeCrashError(
                    self._process.returncode,
                    stderr=self._stderr_buffer,
                )

    async def get_version(self) -> str | None:
        """
        Get the OpenCode CLI version.

        Returns:
            Version string or None if cannot be determined
        """
        executable = self.find_opencode_executable()
        if not executable:
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=5.0,
            )
            return stdout.decode().strip()
        except (asyncio.TimeoutError, OSError):
            return None

    async def __aenter__(self) -> "OpenCodeSubprocess":
        """
        Enter async context manager.

        Starts the subprocess.

        Returns:
            The subprocess manager instance
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        """
        Exit async context manager.

        Stops the subprocess and cleans up resources.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate exceptions
        """
        await self.stop()
        return False


# Re-export for convenience
__all__ = [
    "OpenCodeSubprocess",
    "SubprocessConfig",
    "OpenCodeSubprocessError",
    "OpenCodeNotInstalledError",
    "OpenCodeTimeoutError",
    "OpenCodeCrashError",
]
