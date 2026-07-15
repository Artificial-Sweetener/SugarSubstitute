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

"""Verify pure cube-section build planning policy."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.cube_section_build_plan import (
    empty_card_outcome_kind,
    is_connection_value,
    is_first_usable_card,
    leading_first_usable_node_count,
    node_card_build_outcome,
    node_order_for_cube,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "cube_section_build_plan.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_PLAN_IMPORT_PREFIXES = (
    "PySide6",
    "qpane",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.widgets",
    "substitute.presentation.editor.panel.node_card",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_node_order_prefers_field_spec_order_before_comfy_order() -> None:
    """Prepared field specs should define the cube-section card order."""

    nodes: dict[str, object] = {
        "ksampler": {"class_type": "KSampler", "inputs": {}},
        "positive": {"class_type": "CLIPTextEncode", "inputs": {}},
    }
    field_spec = cast(ResolvedFieldSpec, object())

    assert node_order_for_cube(
        nodes,
        {
            "ksampler": {"seed": field_spec},
            "positive": {"text": field_spec},
        },
    ) == ["ksampler", "positive"]


def test_node_order_falls_back_to_comfy_card_order() -> None:
    """Missing field specs should use the shared Comfy node-card order."""

    nodes: dict[str, object] = {
        "ksampler": {"class_type": "KSampler", "inputs": {"positive": ["positive", 0]}},
        "positive": {"class_type": "CLIPTextEncode", "inputs": {}},
    }

    assert node_order_for_cube(nodes, {}) == ["positive", "ksampler"]


def test_first_usable_detection_uses_behavior_and_legacy_prompt_terms() -> None:
    """First-usable cards should include behavior prompt mode and legacy prompt names."""

    cube = {
        "nodes": {
            "behavior_prompt": {"class_type": "CustomNode", "inputs": {}},
            "positive": {"class_type": "CLIPTextEncode", "inputs": {}},
            "sampler": {"class_type": "KSampler", "inputs": {}},
        }
    }
    behavior_snapshot = SimpleNamespace(
        resolved_nodes_by_alias={
            "Cube": {
                "behavior_prompt": SimpleNamespace(
                    card=SimpleNamespace(card_mode=SimpleNamespace(value="prompt"))
                )
            }
        }
    )

    assert is_first_usable_card(
        "behavior_prompt",
        cube=cube,
        behavior_snapshot=behavior_snapshot,
        cube_alias="Cube",
    )
    assert is_first_usable_card(
        "positive",
        cube=cube,
        behavior_snapshot=SimpleNamespace(),
        cube_alias="Cube",
    )
    assert (
        leading_first_usable_node_count(
            node_order=["behavior_prompt", "positive", "sampler"],
            cube=cube,
            behavior_snapshot=behavior_snapshot,
            cube_alias="Cube",
        )
        == 2
    )


def test_empty_card_outcome_classifies_missing_and_connection_only_cases() -> None:
    """Empty-card classification should explain why no widget was produced."""

    field_spec = cast(ResolvedFieldSpec, object())

    assert (
        empty_card_outcome_kind(
            inputs={"value": "text"},
            field_specs={"value": field_spec},
            display_decision=SimpleNamespace(visible=False),
        )
        == "hidden_by_policy"
    )
    assert (
        empty_card_outcome_kind(
            inputs={"value": "text"},
            field_specs={},
            display_decision=None,
        )
        == "missing_field_specs"
    )
    assert (
        empty_card_outcome_kind(
            inputs={"value": ["upstream", 0]},
            field_specs={"value": field_spec},
            display_decision=None,
        )
        == "connection_only"
    )
    assert (
        empty_card_outcome_kind(
            inputs={"value": "text"},
            field_specs={"value": field_spec},
            display_decision=None,
        )
        == "factory_returned_none"
    )


def test_connection_values_require_list_with_source_node_name() -> None:
    """Connection detection should only accept Comfy-style list references."""

    assert is_connection_value(["upstream", 0])
    assert not is_connection_value([])
    assert not is_connection_value([0, "upstream"])
    assert not is_connection_value("upstream")


def test_node_card_build_outcome_records_prompt_safe_context() -> None:
    """Outcome records should capture structural context without field values."""

    outcome = node_card_build_outcome(
        node_name="ksampler",
        node_class_type="KSampler",
        kind="build_error",
        field_spec_count=3,
        message="failed",
    )

    assert outcome.node_name == "ksampler"
    assert outcome.node_class_type == "KSampler"
    assert outcome.kind == "build_error"
    assert outcome.field_spec_count == 3
    assert outcome.message == "failed"


def test_cube_section_build_plan_does_not_import_qt_or_widget_modules() -> None:
    """Build planning policy should remain pure and widget-free."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(PLAN_SOURCE)
            if imported_module.startswith(FORBIDDEN_PLAN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_projection_coordinator_does_not_own_build_plan_policy() -> None:
    """Projection coordinator should call the build-plan owner for pure policy."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "class NodeCardBuildOutcome" not in source
    assert "NodeCardBuildOutcomeKind = Literal" not in source
    assert "def _leading_first_usable_node_count" not in source
    assert "def _is_first_usable_card" not in source
    assert "def _empty_card_outcome_kind" not in source
    assert "def _is_connection_value" not in source
