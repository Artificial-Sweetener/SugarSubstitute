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

"""Tests for prompt editor performance observability fields."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    ScenarioResult,
)
from substitute.devtools.prompt_editor_performance.observability import (
    PROMPT_PERFORMANCE_METRIC_NAME,
    feature_profile_name_for_scenario,
    scenario_log_fields,
)
from substitute.devtools.prompt_editor_performance.scenarios import Scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OBSERVABILITY_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "observability.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_observability_imports_no_qt_or_tools() -> None:
    """Observability field extraction must stay pure and reusable."""

    imported_modules = _imported_module_names(
        ast.parse(OBSERVABILITY_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_scenario_log_fields_include_required_context_and_counters() -> None:
    """Scenario logs should include required safe context and counter fields."""

    instrumentation = Instrumentation.create()
    instrumentation.projection_rebuild.record(2.5)
    result = ScenarioResult(
        name="observability",
        characters=42,
        operations=3,
        average_ms=1.25,
        p95_ms=1.75,
        max_ms=2.25,
        instrumentation=instrumentation,
        extra_counts={"preview_scheduler_request_count": 4},
    )

    fields = scenario_log_fields(
        Scenario(
            "observability",
            "secret prompt text",
            typed_text="secret typed text",
            clipboard_text="secret clipboard text",
            operation="paste",
        ),
        result,
    )

    assert fields["metric_name"] == PROMPT_PERFORMANCE_METRIC_NAME
    assert fields["scenario_name"] == "observability"
    assert fields["scenario_operation"] == "paste"
    assert fields["scenario_operation_count"] == 3
    assert fields["scenario_character_count"] == 42
    assert fields["feature_profile_name"] == "default"
    assert fields["average_ms"] == 1.25
    assert fields["p95_ms"] == 1.75
    assert fields["max_ms"] == 2.25
    assert fields["instrumentation_projection_rebuild_count"] == 1
    assert fields["instrumentation_projection_rebuild_elapsed_ms"] == 2.5
    assert fields["extra_preview_scheduler_request_count"] == 4


def test_scenario_log_fields_do_not_include_prompt_text_values() -> None:
    """Prompt, typed, clipboard, and selection text must stay out of log fields."""

    secret_values = {
        "SECRET_INITIAL_PROMPT",
        "SECRET_TYPED_PROMPT",
        "SECRET_CLIPBOARD_PROMPT",
    }
    result = ScenarioResult(
        name="secret-free",
        characters=21,
        operations=1,
        average_ms=0.5,
        p95_ms=0.5,
        max_ms=0.5,
        instrumentation=Instrumentation.create(),
    )

    fields = scenario_log_fields(
        Scenario(
            "secret-free",
            "SECRET_INITIAL_PROMPT",
            typed_text="SECRET_TYPED_PROMPT",
            clipboard_text="SECRET_CLIPBOARD_PROMPT",
            selection_range=(0, 6),
        ),
        result,
    )
    rendered_fields = repr(fields)

    assert all(secret_value not in rendered_fields for secret_value in secret_values)


def test_feature_profile_name_identifies_explicit_feature_scenarios() -> None:
    """Feature profile names should distinguish default from all-feature runs."""

    assert feature_profile_name_for_scenario(Scenario("default", "")) == "default"
    assert (
        feature_profile_name_for_scenario(
            Scenario("wildcard", "{missing}", wildcard_gateway="static")
        )
        == "all_features"
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
