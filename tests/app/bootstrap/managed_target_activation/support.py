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

"""Provide deterministic collaborators for managed-target activation tests."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)


def task_factory(*_args: object, **_kwargs: object) -> object:
    """Provide a sentinel managed task factory for activation tests."""

    return object()


def context(tmp_path: Path, *, launch_owned: bool) -> InstallationContext:
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
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=launch_owned,
        ),
    )


def imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class Splash:
    """Collect splash log lines."""

    def __init__(self) -> None:
        """Initialize collected lines."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self.lines.append(line)


class DisposedSplash:
    """Raise when late output reaches a disposed splash."""

    def append_log(self, _line: str) -> None:
        """Simulate a disposed splash widget."""

        raise RuntimeError("disposed")


class FailingAfterActivationSplash:
    """Accept activation output before rejecting later writes."""

    def __init__(self) -> None:
        """Initialize accepted lines and failed output attempts."""

        self.lines: list[str] = []
        self.failure_count = 0

    def append_log(self, line: str) -> None:
        """Accept setup output and reject every later write as a socket failure."""

        if self.lines:
            self.failure_count += 1
            raise TimeoutError("splash endpoint closed")
        self.lines.append(line)


class DisposedStream:
    """Raise when late output reaches a disposed shell stream."""

    def append_line(self, _line: str) -> None:
        """Simulate a disposed shell output stream."""

        raise RuntimeError("disposed")


class Stream:
    """Collect terminal output stream lines."""

    def __init__(self) -> None:
        """Initialize collected lines."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one terminal output line."""

        self.lines.append(line)


class Diagnostics:
    """Collect classified startup diagnostics lines."""

    def __init__(self) -> None:
        """Initialize collected lines."""

        self.lines: list[str] = []

    def append_output(self, line: str) -> None:
        """Record one diagnostics line."""

        self.lines.append(line)


class FailingDiagnostics:
    """Raise during diagnostics classification."""

    def append_output(self, _line: str) -> None:
        """Simulate diagnostics classification failure."""

        raise RuntimeError("classification failed")
