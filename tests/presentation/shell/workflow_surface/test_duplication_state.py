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

"""Workflow duplication state and asset contracts."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from substitute.application.workflows import (
    WorkflowDuplicateService,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _CubeStack,
    _Manager,
    _deletable,
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def test_duplicate_workflow_registers_cloned_state_and_projects_unique_tab(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating should register cloned workflow state and project the new tab."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view.workflow_tabbar.itemMap["wf-a"].setText("Recipe")
    cloned_workflow = WorkflowState(metadata={"title": "Cloned"})

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create workflow-scoped doubles for the duplicated workflow."""

        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = _deletable(f"{workflow_id}:editor", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return WorkflowUiSurfaces(cube_stack, editor_panel, True)

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_workspace_coordinator",
    )

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    assert duplicated_id not in {"wf-a", "wf-b"}
    assert view.workflow_session_service.workflows[duplicated_id] is cloned_workflow
    assert view.workflow_session_service.active_workflow_id == duplicated_id
    assert view.workflow_tabbar.itemMap[duplicated_id].text() == "Recipe (2)"
    assert view.workflow_tabbar.selected[-1] == (duplicated_id, False)
    assert f"create:{duplicated_id}:True" in view.calls
    assert f"canvas:project:{duplicated_id}" in view.calls
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs == []
    assert view.workflow_session_service.workflows["wf-a"] is not cloned_workflow
    assert "Workflow duplicate coordinator started" in caplog.text
    assert "Workflow duplicate tab planned" in caplog.text
    assert "Workflow duplicate existing workflow registered" in caplog.text
    assert "Workflow duplicate UI created" in caplog.text
    assert "Workflow duplicate cube-stack materialization started" in caplog.text
    assert "Workflow duplicate projection started" in caplog.text
    assert "Workflow duplicate projection completed" in caplog.text
    assert "Workflow duplicate coordinator completed" in caplog.text


def test_duplicate_workflow_missing_source_is_noop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating should not create UI state when the source workflow is missing."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_workspace_coordinator",
    )

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "missing",
        WorkflowState(),
        base_label="Recipe",
    )

    assert duplicated_id is None
    assert set(view.workflow_session_service.workflows) == {"wf-a", "wf-b"}
    assert view.workflow_tabbar.workflow_ids_in_order() == ["wf-a", "wf-b"]
    assert (
        "Skipped workflow duplication because source workflow was missing"
        in caplog.text
    )
    assert "source_workflow_id=missing" in caplog.text


def test_duplicate_workflow_preserves_asset_metadata_and_resets_live_canvas() -> None:
    """Duplication should preserve durable state without copying live canvas UUIDs."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    source_workflow = view.workflow_session_service.workflows["wf-a"]
    source_workflow.cubes["CubeA"] = CubeState(
        cube_id="Owner/Repo/CubeA.cube",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {"Load": {"inputs": {"image": "old.png"}}}},
        buffer={
            "nodes": {
                "Load": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "assets/input.png"},
                },
            }
        },
    )
    source_workflow.stack_order.append("CubeA")
    source_workflow.metadata["asset_refs"] = {
        "input_images": {
            "CubeA:Load": {
                "kind": "project_asset",
                "relative_path": "assets/input.png",
            },
        },
        "input_masks": {
            "CubeA:Mask": {
                "kind": "project_mask",
                "relative_path": "mask.png",
            },
        },
    }
    image_id = uuid4()
    source_workflow.canvas.bind_image("CubeA:Load", image_id)
    source_workflow.canvas.input_image_uuid = image_id

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create workflow-scoped doubles for the duplicated workflow."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = _deletable(f"{workflow_id}:editor", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return WorkflowUiSurfaces(cube_stack, editor_panel, True)

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    cloned_workflow = WorkflowDuplicateService().duplicate_workflow(source_workflow)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate = view.workflow_session_service.workflows[duplicated_id]
    assert duplicate.metadata == source_workflow.metadata
    assert duplicate.cubes["CubeA"].buffer == source_workflow.cubes["CubeA"].buffer
    assert duplicate.cubes["CubeA"].buffer is not source_workflow.cubes["CubeA"].buffer
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs[0]["routeKey"] == "CubeA"
    assert duplicate_stack.tabs[0]["text"] == "CubeA"
    duplicate_icon = cast(AppIcon, duplicate_stack.tabs[0]["icon"])
    assert duplicate_icon.value == AppIcon.CUBE_20_FILLED.value
    assert duplicate_stack.current_index == 0
    duplicate_buffer = cast(dict[str, Any], duplicate.cubes["CubeA"].buffer)
    duplicate_nodes = cast(dict[str, Any], duplicate_buffer["nodes"])
    duplicate_load = cast(dict[str, Any], duplicate_nodes["Load"])
    duplicate_inputs = cast(dict[str, Any], duplicate_load["inputs"])
    duplicate_inputs["image"] = "assets/changed.png"
    source_buffer = cast(dict[str, Any], source_workflow.cubes["CubeA"].buffer)
    source_nodes = cast(dict[str, Any], source_buffer["nodes"])
    source_load = cast(dict[str, Any], source_nodes["Load"])
    source_inputs = cast(dict[str, Any], source_load["inputs"])
    assert source_inputs["image"] == "assets/input.png"
    assert duplicate.canvas.image_entries == {}
    assert duplicate.canvas.input_image_uuid is None
