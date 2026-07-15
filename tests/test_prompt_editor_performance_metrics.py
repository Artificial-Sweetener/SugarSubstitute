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

"""Tests for prompt editor performance metric helpers."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
    REORDER_GEOMETRY_COUNT_COLUMNS,
    REORDER_INTERACTION_COUNT_COLUMNS,
    ScenarioResult,
    average,
    format_extra_value,
    percentile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "metrics.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_metrics_imports_no_qt_or_tools() -> None:
    """Metric helpers must stay pure and reusable outside the benchmark CLI."""

    imported_modules = _imported_module_names(
        ast.parse(METRICS_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_operation_counter_records_and_resets_elapsed_time() -> None:
    """Operation counters should preserve counts and total elapsed milliseconds."""

    counter = OperationCounter()

    counter.record(1.25)
    counter.record(2.75)

    assert counter.count == 2
    assert counter.elapsed_ms == 4.0

    counter.reset()

    assert counter.count == 0
    assert counter.elapsed_ms == 0.0


def test_instrumentation_create_and_reset_covers_all_counters() -> None:
    """Instrumentation factory and reset should cover every declared counter."""

    instrumentation = Instrumentation.create()

    instrumentation.projection_rebuild.record(3.0)
    instrumentation.context_menu_open.record(4.0)
    instrumentation.focus_in.record(5.0)

    instrumentation.reset()

    assert all(
        isinstance(value, OperationCounter)
        and value.count == 0
        and value.elapsed_ms == 0.0
        for value in (
            getattr(instrumentation, instrumentation_field.name)
            for instrumentation_field in fields(instrumentation)
        )
    )


def test_average_and_percentile_match_existing_table_semantics() -> None:
    """Metric helpers should preserve the benchmark's existing summary math."""

    assert average([]) == 0.0
    assert average([1.0, 2.0, 6.0]) == 3.0
    assert percentile([], 95) == 0.0
    assert percentile([10.0, 1.0, 5.0, 7.0], 50) == 7.0
    assert percentile([10.0, 1.0, 5.0, 7.0], 95) == 10.0


def test_scenario_result_and_extra_formatting_are_prompt_safe() -> None:
    """Results should store numeric summaries without prompt text fields."""

    result = ScenarioResult(
        name="plain-prompt-type",
        characters=120,
        operations=25,
        average_ms=1.25,
        p95_ms=2.5,
        max_ms=4.0,
        instrumentation=Instrumentation.create(),
        extra_counts={"max_drag_move_ms": 1.234},
    )

    assert result.name == "plain-prompt-type"
    assert result.characters == 120
    assert "prompt" not in result.__dataclass_fields__
    assert format_extra_value(3) == "3"
    assert format_extra_value(1.234) == "1.23"


def test_reorder_metric_columns_preserve_existing_labels() -> None:
    """Reorder table columns should keep stable labels used by benchmark output."""

    assert REORDER_GEOMETRY_COUNT_COLUMNS[0] == (
        "base_hit",
        "base_chip_geometry_cache_hit_count",
    )
    assert REORDER_INTERACTION_COUNT_COLUMNS[-1] == (
        "max_plan",
        "max_render_plan_ms",
    )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
