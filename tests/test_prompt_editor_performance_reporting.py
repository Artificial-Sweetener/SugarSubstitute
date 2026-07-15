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

"""Tests for prompt editor performance benchmark reporting."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    ScenarioResult,
)
from substitute.devtools.prompt_editor_performance.reporting import (
    format_table_row,
    print_results,
    result_table_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTING_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "reporting.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_reporting_imports_no_qt_or_tools() -> None:
    """Reporting helpers must remain pure and independent from the CLI script."""

    imported_modules = _imported_module_names(
        ast.parse(REPORTING_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_format_table_row_preserves_existing_alignment() -> None:
    """Table rows should left-align the first cell and right-align metric cells."""

    assert format_table_row(("scenario", "ops", "avg"), (10, 4, 5)) == (
        "scenario    ops   avg"
    )
    assert format_table_row(("plain", "2", "1.25"), (10, 4, 5)) == (
        "plain         2  1.25"
    )


def test_result_table_rows_include_metric_summaries_without_prompt_text() -> None:
    """Reporting should include numeric summaries and omit typed prompt content."""

    instrumentation = Instrumentation.create()
    instrumentation.projection_rebuild.record(1.5)
    instrumentation.layout_snapshot.record(2.0)
    instrumentation.context_menu_snapshot.record(0.25)
    instrumentation.context_menu_open.record(0.75)
    instrumentation.diagnostics_activation.record(0.5)
    result = ScenarioResult(
        name="plain-prompt-type",
        characters=99,
        operations=3,
        average_ms=1.234,
        p95_ms=2.345,
        max_ms=3.456,
        instrumentation=instrumentation,
        extra_counts={"max_drag_move_ms": 4.567},
    )

    rows = result_table_rows((result,))

    assert rows[0].startswith("scenario")
    assert "max_drag" in rows[0]
    assert "plain-prompt-type" in rows[1]
    assert "99" in rows[1]
    assert "1.23" in rows[1]
    assert "2.35" in rows[1]
    assert "3.46" in rows[1]
    assert "4.57" in rows[1]
    assert "typed secret" not in "\n".join(rows)


def test_print_results_writes_generated_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI-facing printer should emit the same rows returned by the formatter."""

    result = ScenarioResult(
        name="empty",
        characters=0,
        operations=0,
        average_ms=0.0,
        p95_ms=0.0,
        max_ms=0.0,
        instrumentation=Instrumentation.create(),
    )

    print_results((result,))
    captured = capsys.readouterr()

    assert captured.out.splitlines() == list(result_table_rows((result,)))


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
