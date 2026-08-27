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

"""Support shell generation snapshot-building helpers."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.node_behavior import NodeDisplayDecision


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


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


def _behavior_snapshot(
    prompt_endpoint_index: PromptEndpointIndex | None = None,
) -> EditorBehaviorSnapshot:
    """Return a behavior snapshot with one activation delta."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "enabled_from_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "disabled_from_default": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=prompt_endpoint_index or PromptEndpointIndex(),
    )


def _workflow() -> SimpleNamespace:
    """Return a workflow-like object with activation defaults."""

    return SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "enabled_from_bypass": {"mode": 4},
                        "disabled_from_default": {},
                    }
                }
            )
        },
    )


def _prompt_workflow(prompt_text: str) -> SimpleNamespace:
    """Return a workflow-like object with one positive prompt endpoint."""

    return SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {"inputs": {"prompt_template": prompt_text}},
                    }
                }
            )
        },
    )
