#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Provide deterministic managed-recovery adapter test collaborators."""

from __future__ import annotations
import ast
from pathlib import Path
from typing import Any
from sugarsubstitute_shared.launch_splash import SplashActivity
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ADAPTER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "managed_recovery_adapters.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
FORBIDDEN_ADAPTER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


class _DisposedSplash:
    """Raise when late recovery output reaches a disposed splash."""

    def append_log(self, _line: str) -> None:
        """Simulate a disposed splash client."""

        raise RuntimeError("disposed")

    def start_activity(self, _activity: SplashActivity) -> None:
        """Simulate a disposed splash client."""

        raise RuntimeError("disposed")

    def clear_activity(self) -> None:
        """Simulate a disposed splash client."""

        raise RuntimeError("disposed")

    def close(self) -> None:
        """Satisfy the launch splash protocol."""


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _ManagedState:
    """Expose managed-state cleanup synchronization for adapter tests."""

    def with_spawn_lock(self, action: Any) -> object:
        """Run the supplied cleanup action immediately."""

        return action()


class _OutputStream:
    """Collect recovery output stream lines."""

    def __init__(self) -> None:
        """Initialize empty output capture."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one output line."""

        self.lines.append(line)


def _task_factory(*_args: object, **_kwargs: object) -> object:
    """Provide a sentinel managed process task factory."""

    return object()


class _Splash:
    """Collect splash log lines."""

    def __init__(self) -> None:
        """Initialize empty splash log capture."""

        self.lines: list[str] = []
        self.activities: list[SplashActivity] = []
        self.clear_activity_calls = 0

    def append_log(self, line: str) -> None:
        """Record one splash line."""

        self.lines.append(line)

    def start_activity(self, activity: SplashActivity) -> None:
        """Record one splash activity."""

        self.activities.append(activity)

    def clear_activity(self) -> None:
        """Record one splash activity clear request."""

        self.clear_activity_calls += 1

    def close(self) -> None:
        """Satisfy the launch splash protocol."""


class _ExecutionRuntime:
    """Record managed recovery submitter construction."""

    def __init__(self, submitter: _Submitter) -> None:
        """Store the submitter returned by runtime calls."""

        self._submitter = submitter
        self.submitter_calls: list[dict[str, object]] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _Submitter:
        """Record one runtime submitter request."""

        self.submitter_calls.append(
            {
                "name": name,
                "owner_id": owner_id,
            }
        )
        assert dispatcher is not None
        return self._submitter


def _context(tmp_path: Path) -> InstallationContext:
    """Build one managed-local installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=_target(tmp_path, ComfyTargetMode.MANAGED_LOCAL),
    )


def _target(tmp_path: Path, mode: ComfyTargetMode) -> ComfyTargetConfiguration:
    """Build one target configuration with normal ownership for its mode."""

    workspace = tmp_path / "ComfyUI"
    binding = (
        ComfyPythonBinding(
            executable=workspace / ".venv" / "Scripts" / "python.exe",
            version="3.13",
            architecture="AMD64",
            prefix=workspace / ".venv",
            base_prefix=workspace / ".venv",
            source=ComfyPythonSelectionSource.DISCOVERED,
        )
        if mode is ComfyTargetMode.ATTACHED_LOCAL
        else None
    )
    return ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None if mode is ComfyTargetMode.REMOTE else workspace,
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=mode is not ComfyTargetMode.REMOTE,
        python_binding=binding,
    )


class _Submitter:
    """Record runtime submitter close calls."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.close_calls += 1


def _compatibility(
    status: RuntimeCompatibilityStatus,
) -> BackendCompatibilityResult:
    """Build one incompatible runtime compatibility result."""

    return BackendCompatibilityResult(
        status=status,
        summary="SugarCubes version is incompatible.",
        installed_backend_version="1.6.2",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="0.8.0",
        required_sugarcubes_version="0.11.0",
        repairable=True,
    )
