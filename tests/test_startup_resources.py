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

"""Tests for startup resource registration and shutdown ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.startup_resources import (
    StartupResourceRegistry,
    create_startup_resource_registry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_RESOURCES_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_resources.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_STARTUP_RESOURCE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_resource_registry_registers_and_exposes_restore_preload() -> None:
    """Registry should retain startup resources and expose the first preload."""

    registry = StartupResourceRegistry()
    refresh = _Refresh("metadata")
    preload = _ShutdownResource("preload")
    metadata_bridge = object()

    assert registry.register_model_metadata_refresh(refresh) is refresh
    assert registry.register_workspace_restore_asset_preload(preload) is preload
    assert registry.register_metadata_update_bridge(metadata_bridge) is metadata_bridge

    assert registry.metadata_refreshes() == [refresh]
    assert registry.first_workspace_restore_asset_preload() is preload
    assert registry.metadata_update_bridges == [metadata_bridge]


def test_create_startup_resource_registry_returns_empty_registry() -> None:
    """Resource registry factory should own startup registry construction."""

    registry = create_startup_resource_registry()

    assert isinstance(registry, StartupResourceRegistry)
    assert registry.model_metadata_refreshes == []
    assert registry.cube_icon_warmups == []
    assert registry.qpane_sam_warmups == []
    assert registry.editor_startup_warmups == []
    assert registry.workspace_restore_asset_preloads == []
    assert registry.startup_diagnostics_tasks == []
    assert registry.startup_diagnostics_bridges == []
    assert registry.readiness_probes == []
    assert registry.runtime_compatibility_probes == []
    assert registry.metadata_update_bridges == []


def test_startup_resource_registry_shuts_down_registered_resources() -> None:
    """Registry should shut down resources in the existing startup cleanup order."""

    calls: list[str] = []
    registry = StartupResourceRegistry()
    registry.register_model_metadata_refresh(_Refresh("metadata", calls))
    registry.register_cube_icon_warmup(_ShutdownResource("cube", calls))
    registry.register_qpane_sam_warmup(_ShutdownResource("sam", calls))
    registry.register_editor_startup_warmup(_ShutdownResource("editor", calls))
    registry.register_startup_diagnostics_task(
        _ShutdownResource("diagnostics_task", calls)
    )
    registry.register_readiness_probe(_ShutdownResource("readiness", calls))
    registry.register_runtime_compatibility_probe(_RuntimeProbe("compatibility", calls))
    registry.register_workspace_restore_asset_preload(
        _ShutdownResource("preload", calls)
    )

    registry.shutdown_all()

    assert calls == [
        "metadata.cancel",
        "metadata.shutdown",
        "cube.shutdown",
        "sam.shutdown",
        "editor.shutdown",
        "diagnostics_task.shutdown",
        "readiness.shutdown",
        "compatibility.shutdown",
        "preload.shutdown",
    ]


def test_startup_resources_imports_no_forbidden_boundaries() -> None:
    """Startup resource registry should stay free of concrete UI and IO adapters."""

    imported_modules = _imported_module_names(STARTUP_RESOURCES_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_RESOURCE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_resource_lists_and_shutdown() -> None:
    """Startup should delegate startup-lifetime resource ownership."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_resource_registry()" in source
    assert "StartupResourceRegistry()" not in source
    assert "model_metadata_refreshes: list" not in source
    assert "workspace_restore_asset_preloads: list" not in source
    assert "for refresh in model_metadata_refreshes" not in source
    assert "run_startup_shell_flow(" in source
    assert "run_startup_event_loop_and_shutdown(" not in source
    assert "startup_resources.shutdown_all()" not in source


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


class _Refresh:
    """Record metadata refresh cancellation and shutdown."""

    def __init__(self, name: str, calls: list[str] | None = None) -> None:
        """Create refresh records."""

        self._name = name
        self._calls = calls

    def cancel(self) -> None:
        """Record cancellation."""

        if self._calls is not None:
            self._calls.append(f"{self._name}.cancel")

    def start(self) -> None:
        """Accept startup requests."""

    def shutdown(self) -> None:
        """Record shutdown."""

        if self._calls is not None:
            self._calls.append(f"{self._name}.shutdown")


class _ShutdownResource:
    """Record generic resource shutdown."""

    def __init__(self, name: str, calls: list[str] | None = None) -> None:
        """Create shutdown records."""

        self._name = name
        self._calls = calls

    def shutdown(self) -> None:
        """Record shutdown."""

        if self._calls is not None:
            self._calls.append(f"{self._name}.shutdown")


class _RuntimeProbe(_ShutdownResource):
    """Record runtime probe cancellation and shutdown."""

    def cancel_current(self) -> None:
        """Accept in-flight cancellation requests."""
