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

"""Tests for startup cancellation state ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap import (
    startup as startup_module,
    startup_cancellation as startup_cancellation_module,
    startup_support_graph as startup_support_graph_module,
)
from substitute.app.bootstrap.startup_cancellation import (
    StartupCancellationState,
    create_startup_cancellation_state,
)


FORBIDDEN_STARTUP_CANCELLATION_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_cancellation_state_records_cancel_request() -> None:
    """Start open and keep cancellation idempotent."""

    state = StartupCancellationState()

    assert state.cancelled is False

    state.cancel()
    state.cancel()

    assert state.cancelled is True


def test_create_startup_cancellation_state_returns_open_state() -> None:
    """Construct fresh open state through the bootstrap factory."""

    state = create_startup_cancellation_state()

    assert isinstance(state, StartupCancellationState)
    assert state.cancelled is False


def test_startup_cancellation_imports_no_forbidden_boundaries() -> None:
    """Keep cancellation state free of UI, infrastructure, and subprocess imports."""

    source_path = Path(startup_cancellation_module.__file__).resolve()
    imported_modules = _imported_module_names(source_path)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_CANCELLATION_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_startup_cancellation_state() -> None:
    """Keep startup cancellation ownership in the support graph, not its facade."""

    startup_source = Path(startup_module.__file__).read_text(encoding="utf-8")
    support_graph_source = Path(startup_support_graph_module.__file__).read_text(
        encoding="utf-8"
    )

    assert (
        "create_startup_support_graph(initial_splash=initial_splash)" in startup_source
    )
    assert "create_startup_cancellation_state()" not in startup_source
    assert "create_startup_cancellation_state()" in support_graph_source
    assert "StartupCancellationState()" not in startup_source
    assert "def mark_startup_cancelled" not in startup_source
    assert "nonlocal startup_cancelled" not in startup_source


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
