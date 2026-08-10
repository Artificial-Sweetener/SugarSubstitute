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

"""Tests for startup shutdown coordinator construction."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import startup_shutdown_coordinator
from substitute.app.bootstrap.lifecycle import ManagedComfyCleanupResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_shutdown_coordinator.py"
)
FORBIDDEN_COORDINATOR_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.infrastructure",
    "subprocess",
)


def test_create_startup_shutdown_coordinator_forwards_runtime_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown coordinator factory should wire runtime cleanup ports."""

    app = _App()
    runtime = _ShutdownRuntime()
    cleanup_submitter = object()
    calls: list[dict[str, object]] = []
    coordinator = object()

    def fake_shutdown_coordinator(**kwargs: object) -> object:
        """Record coordinator construction kwargs."""

        calls.append(kwargs)
        return coordinator

    monkeypatch.setattr(
        startup_shutdown_coordinator,
        "ShutdownCoordinator",
        fake_shutdown_coordinator,
    )

    result = startup_shutdown_coordinator.create_startup_shutdown_coordinator(
        app=app,
        cleanup=runtime.cleanup,
        before_cleanup=runtime.before_cleanup,
        cleanup_bypass=cast(Any, runtime.cleanup_bypass),
        cleanup_submitter=cast(Any, cleanup_submitter),
    )

    assert result is coordinator
    assert calls == [
        {
            "app": app,
            "cleanup": runtime.cleanup,
            "cleanup_submitter": cleanup_submitter,
            "cleanup_lane": "disk_io_low_priority",
            "before_cleanup": runtime.before_cleanup,
            "skip_cleanup_on_force_close": runtime.cleanup_bypass,
        }
    ]


def test_shell_shutdown_request_adapts_parent_window() -> None:
    """Shell shutdown port should forward optional parent windows."""

    coordinator = _ShutdownCoordinator()
    parent = object()

    request_shutdown = startup_shutdown_coordinator.shell_shutdown_request(
        cast(Any, coordinator)
    )

    request_shutdown(parent)
    request_shutdown(None)

    assert coordinator.parents == [parent, None]


def test_create_startup_shutdown_request_ports_groups_request_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown request port factory should own coordinator/request pairing."""

    app = _App()
    runtime = _ShutdownRuntime()
    cleanup_submitter = object()
    coordinator = _ShutdownCoordinator()
    created_ports: list[dict[str, object]] = []

    def fake_create_startup_shutdown_coordinator(**kwargs: object) -> object:
        """Record coordinator factory kwargs."""

        created_ports.append(kwargs)
        return coordinator

    monkeypatch.setattr(
        startup_shutdown_coordinator,
        "create_startup_shutdown_coordinator",
        fake_create_startup_shutdown_coordinator,
    )

    ports = startup_shutdown_coordinator.create_startup_shutdown_request_ports(
        app=app,
        cleanup=runtime.cleanup,
        before_cleanup=runtime.before_cleanup,
        cleanup_bypass=cast(Any, runtime.cleanup_bypass),
        cleanup_submitter=cast(Any, cleanup_submitter),
    )
    parent = object()

    ports.request_shell_shutdown(parent)

    assert created_ports == [
        {
            "app": app,
            "cleanup": runtime.cleanup,
            "before_cleanup": runtime.before_cleanup,
            "cleanup_bypass": runtime.cleanup_bypass,
            "cleanup_submitter": cleanup_submitter,
        }
    ]
    assert coordinator.parents == [parent]


def test_startup_shutdown_coordinator_imports_no_forbidden_boundaries() -> None:
    """Shutdown coordinator adapter should avoid infrastructure and subprocess."""

    imported_modules = _imported_module_names(COORDINATOR_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_COORDINATOR_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shutdown_coordinator_construction() -> None:
    """Startup should not assemble shutdown coordinator kwargs directly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_shell_runtime_graph(" in source
    assert "create_startup_shutdown_request_ports(" not in source
    assert "create_startup_shutdown_coordinator(" not in source
    assert "ShutdownCoordinator(" not in source
    assert "coordinator_kwargs" not in source
    assert "skip_cleanup_on_force_close" not in source
    assert "shell_shutdown_request(" not in source
    assert "shutdown_request=cast(" not in source
    assert "shutdown_coordinator.request_shutdown" not in source


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


class _App:
    """Application shutdown test double."""

    def quit(self) -> None:
        """Accept quit requests."""


class _ShutdownRuntime:
    """Expose shutdown runtime ports for adapter tests."""

    cleanup_bypass = object()

    def cleanup(self) -> ManagedComfyCleanupResult:
        """Return one fake cleanup result."""

        return cast(ManagedComfyCleanupResult, object())

    def before_cleanup(self, _source_shell: object | None) -> None:
        """Accept pre-cleanup preparation requests."""


class _ShutdownCoordinator:
    """Record shell shutdown requests."""

    def __init__(self) -> None:
        """Initialize recorded parent windows."""

        self.parents: list[object | None] = []

    def request_shutdown(self, parent_window: object | None = None) -> None:
        """Record one shutdown parent."""

        self.parents.append(parent_window)
