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

"""Workflow duplication cube-icon contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast


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


def test_duplicate_workflow_materializes_cube_stack_icons() -> None:
    """Duplicated cube-stack tabs should receive resolved cube icons."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    icon_calls: list[dict[str, object]] = []

    def icon_for_cube(**kwargs: object) -> str:
        """Record icon resolution context and return a fake icon."""

        icon_calls.append(kwargs)
        return "cube-icon"

    view.cube_icon_factory = SimpleNamespace(icon_for_cube=icon_for_cube)
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
                display_name="Cube A",
                ui={"cube_icon": "icon-descriptor"},
            )
        },
        stack_order=["CubeA"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create duplicate UI with cube stack that records icons."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = _deletable(
            f"{workflow_id}:editor", view.calls
        )
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return WorkflowUiSurfaces(
            cube_stack,
            view.editor_panels[workflow_id],
            True,
        )

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs == [
        {"routeKey": "CubeA", "text": "CubeA", "icon": "cube-icon"}
    ]
    assert icon_calls == [
        {
            "cube_id": "Owner/Repo/CubeA.cube",
            "display_name": "Cube A",
            "icon": "icon-descriptor",
            "catalog_revision": "",
            "cube_content_hash": "",
        }
    ]


def test_duplicate_workflow_applies_fallback_icon_when_resolution_fails() -> None:
    """Duplicated cube-stack tabs should never finish without an icon."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    def _raise_icon_error(**_kwargs: object) -> object:
        """Raise an expected icon resolution failure."""

        raise ValueError("bad descriptor")

    view.cube_icon_factory = SimpleNamespace(icon_for_cube=_raise_icon_error)
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
                display_name="Cube A",
                ui={"cube_icon": "icon-descriptor"},
            )
        },
        stack_order=["CubeA"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create duplicate UI with cube stack that records icons."""

        del set_as_current
        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = _deletable(
            f"{workflow_id}:editor", view.calls
        )
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        return WorkflowUiSurfaces(
            cube_stack,
            view.editor_panels[workflow_id],
            True,
        )

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    duplicate_stack = view.cube_stacks[duplicated_id]
    assert isinstance(duplicate_stack, _CubeStack)
    assert duplicate_stack.tabs[0]["routeKey"] == "CubeA"
    assert duplicate_stack.tabs[0]["text"] == "CubeA"
    duplicate_icon = cast(AppIcon, duplicate_stack.tabs[0]["icon"])
    assert duplicate_icon.value == AppIcon.CUBE_20_FILLED.value
