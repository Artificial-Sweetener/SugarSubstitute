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

"""Verify projected widget lifecycle preparation behavior."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel.projected_widget_lifecycle import (
    call_widget_bool_method,
    prepare_projected_widget_for_hidden_build,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projected_widget_lifecycle.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


class _HideWidget:
    """Record hidden-build preparation calls for widgets with ``hide``."""

    def __init__(self) -> None:
        """Create empty call records."""

        self.updates_enabled: list[bool] = []
        self.hidden = 0
        self.visible_changes: list[bool] = []

    def setUpdatesEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record update-suppression changes."""

        self.updates_enabled.append(enabled)

    def hide(self) -> None:
        """Record hide fallback use."""

        self.hidden += 1

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record unexpected visibility fallback calls."""

        self.visible_changes.append(visible)


class _VisibleOnlyWidget:
    """Record hidden-build preparation calls for widgets without ``hide``."""

    def __init__(self) -> None:
        """Create empty call records."""

        self.calls: list[tuple[str, bool]] = []

    def setUpdatesEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record update-suppression changes."""

        self.calls.append(("updates", enabled))

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record visibility fallback changes."""

        self.calls.append(("visible", visible))


class _MethodWidget:
    """Expose one bool-taking method for helper tests."""

    def __init__(self) -> None:
        """Create empty value records."""

        self.values: list[bool] = []

    def setFlag(self, value: bool) -> None:  # noqa: N802
        """Record helper-dispatched values."""

        self.values.append(value)


def _imported_module_names(path: Path) -> set[str]:
    """Return all top-level imported module names in a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_prepare_projected_widget_for_hidden_build_prefers_hide() -> None:
    """Hidden build preparation should suppress updates and prefer ``hide``."""

    widget = _HideWidget()

    prepare_projected_widget_for_hidden_build(widget)

    assert widget.updates_enabled == [False]
    assert widget.hidden == 1
    assert widget.visible_changes == []


def test_prepare_projected_widget_for_hidden_build_uses_visible_fallback() -> None:
    """Widgets without ``hide`` should fall back to ``setVisible(False)``."""

    widget = _VisibleOnlyWidget()

    prepare_projected_widget_for_hidden_build(widget)

    assert widget.calls == [("updates", False), ("visible", False)]


def test_call_widget_bool_method_is_optional() -> None:
    """Boolean method dispatch should call supported methods and ignore gaps."""

    widget = _MethodWidget()

    call_widget_bool_method(widget, "setFlag", True)
    call_widget_bool_method(widget, "missingMethod", False)
    call_widget_bool_method(object(), "setFlag", False)

    assert widget.values == [True]


def test_projected_widget_lifecycle_does_not_import_coordinator_or_fluent() -> None:
    """Lifecycle helpers should remain a small presentation adapter boundary."""

    imports = _imported_module_names(LIFECYCLE_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_no_longer_defines_projected_widget_helpers() -> None:
    """Moved lifecycle helpers should not return to the coordinator monolith."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    defined_functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_prepare_projected_widget_for_hidden_build" not in defined_functions
    assert "_call_widget_bool_method" not in defined_functions
    assert "ProjectedWidgetBuilder" in {
        alias.name
        for node in ast.walk(ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
