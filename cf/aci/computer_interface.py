"""Main Computer Interface for CodeFusion Agent Computer Interface."""

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import CfConfig
from .environment_manager import EnvironmentManager
from .repo import CodeRepo
from .system_access import SystemAccess


@dataclass
class SystemInfo:
    """Information about the computer system."""

    platform: str
    architecture: str
    python_version: str
    working_directory: str
    user: str
    environment_variables: Dict[str, str]


@dataclass
class CommandResult:
    """Result of executing a system command."""

    command: str
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    success: bool


class ComputerInterface:
    """Main interface between agents and the computer system.

    This class provides a unified interface for agents to interact with:
    - File system and repositories
    - Environment variables and configuration
    - System commands and processes
    - Network and external resources
    """

    def __init__(
        self, repo: Optional[CodeRepo] = None, config: Optional[CfConfig] = None
    ):
        self.config = config or CfConfig()
        self.repo = repo

        # Initialize sub-components
        self.system_access = SystemAccess()
        self.environment_manager = EnvironmentManager(repo, config) if repo else None

        # System information
        self._system_info = None

        # Command execution settings
        self.command_timeout = 30  # seconds
        self.allowed_commands = {
            "ls",
            "dir",
            "cat",
            "head",
            "tail",
            "grep",
            "find",
            "python",
            "pip",
            "npm",
            "node",
            "git",
            "docker",
            "pytest",
            "unittest",
            "coverage",
            "flake8",
            "black",
            "mypy",
            "pylint",
            "bandit",
            "safety",
        }

    def get_system_info(self) -> SystemInfo:
        """Get comprehensive system information."""
        if self._system_info is None:
            import sys

            self._system_info = SystemInfo(
                platform=platform.system(),
                architecture=platform.machine(),
                python_version=sys.version,
                working_directory=os.getcwd(),
                user=os.getenv("USER", os.getenv("USERNAME", "unknown")),
                environment_variables=dict(os.environ),
            )

        return self._system_info

    def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        safe_mode: bool = True,
    ) -> CommandResult:
        """Execute a system command safely.

        Args:
            command: Command to execute
            cwd: Working directory for command execution
            timeout: Timeout in seconds
            safe_mode: If True, only allow predefined safe commands

        Returns:
            CommandResult with execution details
        """
        import shlex
        import time

        start_time = time.time()
        timeout = timeout or self.command_timeout

        # Parse command for safety check
        if safe_mode:
            try:
                cmd_parts = shlex.split(command)
                base_command = cmd_parts[0] if cmd_parts else ""

                if base_command not in self.allowed_commands:
                    return CommandResult(
                        command=command,
                        return_code=-1,
                        stdout="",
                        stderr=f'Command "{base_command}" not allowed in safe mode',
                        execution_time=0.0,
                        success=False,
                    )
            except ValueError as e:
                return CommandResult(
                    command=command,
                    return_code=-1,
                    stdout="",
                    stderr=f"Invalid command syntax: {e}",
                    execution_time=0.0,
                    success=False,
                )

        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                timeout=timeout,
                capture_output=True,
                text=True,
                check=False,
            )

            execution_time = time.time() - start_time

            return CommandResult(
                command=command,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                success=result.returncode == 0,
            )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return CommandResult(
                command=command,
                return_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                execution_time=execution_time,
                success=False,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return CommandResult(
                command=command,
                return_code=-1,
                stdout="",
                stderr=f"Command execution failed: {e}",
                execution_time=execution_time,
                success=False,
            )

    def check_tool_availability(self, tool: str) -> bool:
        """Check if a tool/command is available on the system."""
        try:
            result = subprocess.run(
                f"which {tool}" if platform.system() != "Windows" else f"where {tool}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_environment_variable(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        """Get environment variable through system access."""
        return self.system_access.get(key, default)

    def set_environment_variable(self, key: str, value: str) -> None:
        """Set environment variable."""
        os.environ[key] = value

    def get_available_tools(self) -> Dict[str, bool]:
        """Get availability status of common development tools."""
        tools = [
            "python",
            "pip",
            "git",
            "npm",
            "node",
            "docker",
            "pytest",
            "coverage",
            "flake8",
            "black",
            "mypy",
            "java",
            "mvn",
            "gradle",
            "go",
            "cargo",
            "rustc",
        ]

        return {tool: self.check_tool_availability(tool) for tool in tools}

    def get_python_packages(self) -> List[str]:
        """Get list of installed Python packages."""
        try:
            result = self.execute_command("pip list --format=freeze", safe_mode=True)
            if result.success:
                return [
                    line.split("==")[0]
                    for line in result.stdout.split("\n")
                    if "==" in line
                ]
        except Exception:
            pass
        return []

    def get_git_info(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Get Git repository information."""
        cwd = repo_path or (self.repo.repo_path if self.repo else None)

        git_info = {
            "is_git_repo": False,
            "branch": None,
            "remote_url": None,
            "status": None,
            "last_commit": None,
        }

        if cwd and Path(cwd).exists():
            # Check if it's a git repo
            result = self.execute_command(
                "git rev-parse --is-inside-work-tree", cwd=cwd
            )
            if result.success and "true" in result.stdout:
                git_info["is_git_repo"] = True

                # Get branch
                result = self.execute_command("git branch --show-current", cwd=cwd)
                if result.success:
                    git_info["branch"] = result.stdout.strip()

                # Get remote URL
                result = self.execute_command("git remote get-url origin", cwd=cwd)
                if result.success:
                    git_info["remote_url"] = result.stdout.strip()

                # Get status
                result = self.execute_command("git status --porcelain", cwd=cwd)
                if result.success:
                    git_info["status"] = (
                        "clean" if not result.stdout.strip() else "dirty"
                    )

                # Get last commit
                result = self.execute_command('git log -1 --format="%h %s"', cwd=cwd)
                if result.success:
                    git_info["last_commit"] = result.stdout.strip()

        return git_info

    def get_network_info(self) -> Dict[str, Any]:
        """Get basic network connectivity information."""
        network_info = {
            "internet_available": False,
            "dns_working": False,
            "proxy_detected": False,
        }

        # Check internet connectivity
        try:
            import urllib.request

            urllib.request.urlopen("http://www.google.com", timeout=5)
            network_info["internet_available"] = True
            network_info["dns_working"] = True
        except Exception:
            pass

        # Check for proxy environment variables
        proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        network_info["proxy_detected"] = any(os.getenv(var) for var in proxy_vars)

        return network_info

    def get_resource_usage(self) -> Dict[str, Any]:
        """Get system resource usage information."""
        try:
            import psutil

            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "available_memory_gb": psutil.virtual_memory().available / (1024**3),
                "total_memory_gb": psutil.virtual_memory().total / (1024**3),
            }
        except ImportError:
            # Fallback without psutil
            return {
                "cpu_percent": "unknown",
                "memory_percent": "unknown",
                "disk_percent": "unknown",
                "available_memory_gb": "unknown",
                "total_memory_gb": "unknown",
                "note": "Install psutil for detailed resource monitoring",
            }

    def create_workspace(self, name: str, base_path: Optional[str] = None) -> str:
        """Create a temporary workspace directory for agent operations."""
        import tempfile

        base_path = base_path or tempfile.gettempdir()
        workspace_path = Path(base_path) / f"codefusion_workspace_{name}"
        workspace_path.mkdir(parents=True, exist_ok=True)

        return str(workspace_path)

    def cleanup_workspace(self, workspace_path: str) -> bool:
        """Clean up a temporary workspace directory."""
        try:
            import shutil

            if Path(workspace_path).exists():
                shutil.rmtree(workspace_path)
            return True
        except Exception:
            return False

    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status for agent decision making."""
        return {
            "system_info": self.get_system_info(),
            "available_tools": self.get_available_tools(),
            "python_packages": self.get_python_packages()[:20],  # Limit to first 20
            "git_info": self.get_git_info(),
            "network_info": self.get_network_info(),
            "resource_usage": self.get_resource_usage(),
            "llm_config_available": self.system_access.has_llm_config(),
        }
