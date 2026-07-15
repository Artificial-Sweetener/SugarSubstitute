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

"""Verify runtime issue projection decisions for projected widget builds."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel.runtime_issue_projection_adapter import (
    RuntimeIssueProjectionAdapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "runtime_issue_projection_adapter.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


class _Widget:
    """Expose optional runtime issue severity for adapter tests."""

    def __init__(self, severity: str | None = None) -> None:
        """Store the severity returned by the widget hook."""

        self._severity = severity

    def issueSeverity(self) -> str | None:  # noqa: N802
        """Return the configured issue severity."""

        return self._severity


class _Panel:
    """Record error-widget construction through the panel boundary."""

    def __init__(self) -> None:
        """Create empty error-widget build records."""

        self.built_errors: list[tuple[str, object]] = []
        self.error_widget = object()

    def _build_error_cube_widget(self, cube_alias: str, cube_state: object) -> object:
        """Record error-widget construction."""

        self.built_errors.append((cube_alias, cube_state))
        return self.error_widget


class _RuntimeIssues:
    """Return configured runtime issue aliases."""

    def __init__(self, errored_aliases: set[str]) -> None:
        """Store aliases that should render as errored."""

        self._errored_aliases = errored_aliases

    def is_errored_cube(self, cube_alias: str) -> bool:
        """Return whether the alias has active error-severity runtime issues."""

        return cube_alias in self._errored_aliases


def _imported_module_names(path: Path) -> set[str]:
    """Return imported module names from one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_runtime_issue_adapter_replaces_non_error_widget_for_errored_cube() -> None:
    """Errored aliases should replace visible widgets not already rendering errors."""

    adapter = RuntimeIssueProjectionAdapter(
        panel=_Panel(),
        runtime_issues=_RuntimeIssues({"Cube"}),
    )

    assert adapter.should_replace_visible_widget_for_runtime_issue(
        "Cube",
        _Widget("warning"),
    )
    assert not adapter.should_replace_visible_widget_for_runtime_issue(
        "Cube",
        _Widget("error"),
    )
    assert not adapter.should_replace_visible_widget_for_runtime_issue(
        "Other",
        _Widget("warning"),
    )


def test_runtime_issue_adapter_builds_error_widget_only_for_errored_cube() -> None:
    """Error-widget construction should be gated by runtime issue state."""

    panel = _Panel()
    cube_state = object()
    adapter = RuntimeIssueProjectionAdapter(
        panel=panel,
        runtime_issues=_RuntimeIssues({"Cube"}),
    )

    assert adapter.build_error_widget_if_required("Other", cube_state) is None
    assert (
        adapter.build_error_widget_if_required("Cube", cube_state) is panel.error_widget
    )
    assert panel.built_errors == [("Cube", cube_state)]


def test_runtime_issue_projection_adapter_does_not_import_qt_or_coordinator() -> None:
    """Runtime issue build decisions should stay portable and coordinator-free."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(ADAPTER_SOURCE)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()
