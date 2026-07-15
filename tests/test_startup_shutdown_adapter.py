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

"""Tests for concrete startup shutdown process-manager adapter."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import startup_shutdown_adapter
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shutdown_adapter.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_ADAPTER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_process_manager_shutdown_adapter_supplies_cleanup_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown adapter should bind process-manager cleanup to the runtime factory."""

    runtime = object()
    managed_state = {"pid": 123}
    save_calls: list[str] = []
    factory_calls: list[dict[str, Any]] = []

    def fake_kill_process(_state: object | None) -> object:
        """Return one fake cleanup result."""

        return object()

    def fake_create_runtime(**kwargs: Any) -> StartupShutdownRuntime:
        """Record shutdown runtime factory ports."""

        factory_calls.append(kwargs)
        return cast(StartupShutdownRuntime, runtime)

    monkeypatch.setattr(
        startup_shutdown_adapter,
        "create_startup_shutdown_runtime",
        fake_create_runtime,
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_shutdown_adapter."
        "process_manager.kill_comfyui_state",
        fake_kill_process,
    )

    result = startup_shutdown_adapter.create_process_manager_startup_shutdown_runtime(
        comfy_state_getter=lambda: managed_state,
        save_session_before_cleanup=lambda: save_calls.append("save"),
    )

    assert result is runtime
    assert len(factory_calls) == 1
    call = factory_calls[0]
    assert call["comfy_state_getter"]() is managed_state
    assert call["kill_process"] is fake_kill_process
    call["save_session_before_cleanup"]()
    assert save_calls == ["save"]


def test_startup_shutdown_adapter_imports_no_forbidden_boundaries() -> None:
    """Shutdown adapter should avoid direct Qt/UI/process-shell imports."""

    imported_modules = _imported_module_names(ADAPTER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ADAPTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_process_manager_shutdown_adapter() -> None:
    """Startup should not import or re-export process-manager cleanup wiring."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "from substitute.infrastructure.comfy import process_manager" not in source
    assert "process_manager.kill_comfyui_state" not in source
    assert "create_startup_shell_runtime_graph(" in source
    assert "create_process_manager_startup_shutdown_runtime(" not in source
    assert '"process_manager"' not in source


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
