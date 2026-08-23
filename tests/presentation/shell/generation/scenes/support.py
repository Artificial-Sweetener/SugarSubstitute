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

"""Provide scene generation controller test support."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast


from substitute.application.generation import (
    GenerationFailure,
    GenerationRequest,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.recipes.recipe_io_service import WorkflowLike
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.presentation.shell.workspace_scene_generation_controller import (
    SceneGenerationBindings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_scene_generation_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


class _ScenePreflightError(RuntimeError):
    """Test preflight error carrying workflow context."""

    def __init__(self, *, workflow_id: str, message: str) -> None:
        """Store workflow failure context."""

        super().__init__(message)
        self.workflow_id = workflow_id
        self.message = message


def _preflight_error(*, workflow_id: str, message: str) -> _ScenePreflightError:
    """Return a test scene preflight exception."""

    return _ScenePreflightError(workflow_id=workflow_id, message=message)


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


def _workflow(prompt_text: str) -> SimpleNamespace:
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


def _behavior_snapshot() -> EditorBehaviorSnapshot:
    """Return a behavior snapshot with one positive prompt endpoint."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(
            (
                PromptEndpoint(
                    cube_alias="Text",
                    role=PromptRole.POSITIVE,
                    node_name="positive_prompt",
                    field_key="prompt_template",
                ),
            )
        ),
    )


def _request(workflow: object) -> GenerationRequest:
    """Return a generation request for scene helper tests."""

    return GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(WorkflowLike, workflow),
    )


def _scene_bindings(failures: list[GenerationFailure]) -> SceneGenerationBindings:
    """Return generation bindings for prompt-scene enqueue tests."""

    return cast(
        SceneGenerationBindings,
        SimpleNamespace(
            randomize_seeds=lambda: None,
            on_run_started=lambda _event: None,
            on_progress=lambda _progress: None,
            on_model_load_progress=lambda _progress: None,
            on_preview=lambda _preview: None,
            on_output_image=lambda _output: None,
            on_failure=failures.append,
            on_timing=lambda _timing: None,
            on_completed=lambda _event: None,
        ),
    )


def _generation_failure_from_preflight(
    error_value: object,
    *,
    operation: str,
    values: dict[str, object] | None = None,
) -> GenerationFailure:
    """Return a generation failure from a test preflight exception."""

    _ = operation, values
    error = cast(_ScenePreflightError, error_value)
    return GenerationFailure(
        stage="preflight",
        workflow_id=error.workflow_id,
        message=error.message,
    )
