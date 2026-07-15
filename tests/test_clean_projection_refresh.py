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

"""Verify clean projection refresh behavior and ownership boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel.clean_projection_refresh import (
    EditorCleanProjectionRefreshController,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEAN_REFRESH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "clean_projection_refresh.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


class _Panel:
    """Record clean projection refresh calls and state mutation."""

    def __init__(self) -> None:
        """Create empty panel state and call records."""

        self._cube_states: dict[str, object] | None = None
        self._stack_order: list[str] | None = None
        self.calls: list[tuple[str, dict[str, object]]] = []

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Record prompt editor value synchronization."""

        self.calls.append(("prompt_values", {}))

    def _refresh_link_widgets(self) -> None:
        """Record link-widget refresh."""

        self.calls.append(("links", {}))

    def refresh_node_behavior_state(self, **kwargs: object) -> None:
        """Record node-behavior refresh arguments."""

        self.calls.append(("behavior", kwargs))


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_clean_projection_refresh_updates_state_and_cached_behavior() -> None:
    """Clean refresh should update panel state and use cached behavior snapshots."""

    panel = _Panel()
    cube = object()

    EditorCleanProjectionRefreshController(panel).refresh_clean_projection(
        cube_states={"Cube": cube},
        stack_order=("Cube",),
    )

    assert panel._cube_states == {"Cube": cube}
    assert panel._stack_order == ["Cube"]
    assert panel.calls == [
        ("prompt_values", {}),
        ("links", {}),
        ("behavior", {"use_cached_snapshot": True}),
    ]


def test_clean_projection_refresh_accepts_empty_projection_state() -> None:
    """Clean refresh should preserve the existing None-state semantics."""

    panel = _Panel()

    EditorCleanProjectionRefreshController(panel).refresh_clean_projection(
        cube_states=None,
        stack_order=None,
    )

    assert panel._cube_states is None
    assert panel._stack_order is None
    assert panel.calls[-1] == ("behavior", {"use_cached_snapshot": True})


def test_clean_projection_refresh_does_not_import_qt_or_coordinator() -> None:
    """Clean projection refresh should stay Qt-free and coordinator-free."""

    imports = _imported_module_names(CLEAN_REFRESH_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_delegates_clean_projection_refresh() -> None:
    """The coordinator should keep only a public facade for clean refresh."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    coordinator_class = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name == "EditorPanelProjectionCoordinator"
    )
    method = next(
        node
        for node in coordinator_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "refresh_clean_projection"
    )

    assert any(
        isinstance(node, ast.Attribute) and node.attr == "clean_projection_refresh"
        for node in ast.walk(method)
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "refresh_node_behavior_state"
        for node in ast.walk(method)
    )
