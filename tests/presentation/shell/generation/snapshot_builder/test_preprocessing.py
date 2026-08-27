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

"""Tests for shell generation snapshot-building helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    preprocess_generation_workflow,
)


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


def test_preprocess_generation_workflow_uses_optional_service() -> None:
    """Prompt wildcard preprocessing should be delegated when supported."""

    original_workflow = object()
    processed_workflow = object()
    wildcard_context = object()
    endpoint_index = PromptEndpointIndex()
    calls: list[dict[str, object]] = []

    class _PreprocessingService:
        """Record preprocessing arguments and return a processed workflow."""

        def preprocess_workflow(
            self,
            *,
            workflow: object,
            workflow_id: str,
            wildcard_context: object | None,
            prompt_endpoint_index: object | None,
        ) -> object:
            """Record the preprocessing call."""

            calls.append(
                {
                    "workflow": workflow,
                    "workflow_id": workflow_id,
                    "wildcard_context": wildcard_context,
                    "prompt_endpoint_index": prompt_endpoint_index,
                }
            )
            return processed_workflow

    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=_PreprocessingService(),
            workflow=original_workflow,
            workflow_id="workflow-a",
            wildcard_context=wildcard_context,
            prompt_endpoint_index=endpoint_index,
        )
        is processed_workflow
    )
    assert calls == [
        {
            "workflow": original_workflow,
            "workflow_id": "workflow-a",
            "wildcard_context": wildcard_context,
            "prompt_endpoint_index": endpoint_index,
        }
    ]


def test_preprocess_generation_workflow_returns_original_without_service() -> None:
    """Missing prompt wildcard preprocessing support should preserve workflow."""

    workflow = object()

    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=None,
            workflow=workflow,
            workflow_id="workflow-a",
        )
        is workflow
    )
    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=SimpleNamespace(),
            workflow=workflow,
            workflow_id="workflow-a",
        )
        is workflow
    )
