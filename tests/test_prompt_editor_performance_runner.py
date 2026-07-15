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

"""Tests for prompt editor performance scenario runner."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

from substitute.devtools.prompt_editor_performance import runner
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    ScenarioResult,
)
from substitute.devtools.prompt_editor_performance.scenarios import (
    ALL_PROMPT_EDITOR_FEATURES,
    Scenario,
)
from substitute.presentation.editor.prompt_editor import PromptEditor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_MODULE = (
    PROJECT_ROOT / "substitute" / "devtools" / "prompt_editor_performance" / "runner.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "tests",
    "tools",
)


class _CursorDouble:
    """Record selection positions set by the runner."""

    def __init__(self) -> None:
        """Initialize recorded cursor movement calls."""

        self.positions: list[tuple[int, QTextCursor.MoveMode]] = []

    def setPosition(
        self,
        position: int,
        mode: QTextCursor.MoveMode,
    ) -> None:
        """Record one cursor positioning call."""

        self.positions.append((position, mode))


class _EditorDouble:
    """Expose the minimal selection API used by the runner."""

    def __init__(self) -> None:
        """Initialize cursor and set-cursor recording state."""

        self.cursor = _CursorDouble()
        self.set_cursor_calls: list[_CursorDouble] = []

    def textCursor(self) -> _CursorDouble:
        """Return the reusable cursor double."""

        return self.cursor

    def setTextCursor(self, cursor: _CursorDouble) -> None:
        """Record the selected cursor object."""

        self.set_cursor_calls.append(cursor)


def test_prompt_editor_performance_runner_imports_no_tools() -> None:
    """Runner may use Qt and presentation, but not tests or tools."""

    imported_modules = _imported_module_names(
        ast.parse(RUNNER_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_run_scenarios_delegates_in_order(monkeypatch: MonkeyPatch) -> None:
    """Scenario collection runner should preserve scenario order."""

    scenarios = (
        Scenario("first", "alpha"),
        Scenario("second", "beta"),
    )
    calls: list[str] = []

    def fake_run_scenario(
        app: QApplication,
        scenario: Scenario,
    ) -> ScenarioResult:
        """Record delegated scenario names and return a minimal result."""

        _ = app
        calls.append(scenario.name)
        return ScenarioResult(
            name=scenario.name,
            characters=len(scenario.initial_text),
            operations=0,
            average_ms=0.0,
            p95_ms=0.0,
            max_ms=0.0,
            instrumentation=Instrumentation.create(),
        )

    monkeypatch.setattr(runner, "run_scenario", fake_run_scenario)

    results = runner.run_scenarios(cast(QApplication, object()), scenarios)

    assert calls == ["first", "second"]
    assert [result.name for result in results] == ["first", "second"]


def test_feature_profile_for_scenario_only_enables_explicit_feature_scenarios() -> None:
    """Feature profile selection should avoid unnecessary explicit feature setup."""

    assert runner.feature_profile_for_scenario(Scenario("plain", "")) is None

    profile = runner.feature_profile_for_scenario(
        Scenario("wildcard", "{missing}", wildcard_gateway="static")
    )

    assert profile is not None
    assert tuple(decision.feature for decision in profile.decisions) == (
        ALL_PROMPT_EDITOR_FEATURES
    )
    assert all(decision.enabled for decision in profile.decisions)


def test_set_selection_range_uses_move_then_keep_anchor() -> None:
    """Selection setup should select the exact source range for menu scenarios."""

    editor = _EditorDouble()

    runner.set_selection_range(cast(PromptEditor, editor), 2, 7)

    assert editor.cursor.positions == [
        (2, QTextCursor.MoveMode.MoveAnchor),
        (7, QTextCursor.MoveMode.KeepAnchor),
    ]
    assert editor.set_cursor_calls == [editor.cursor]


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
