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

"""Workflow duplication shell-projection contracts."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.domain.workflow import CubeState, WorkflowState
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


def test_duplicate_workflow_projects_cloned_cube_metadata_tooltip() -> None:
    """Duplicated workflow cube stacks should keep rich metadata tooltips."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    class _PresentingCubeStack(_CubeStack):
        def setTabPresentation(
            self,
            index: int,
            *,
            primary_text: str,
            secondary_text: str,
            tooltip_text: str,
        ) -> None:
            """Record complete cube tab presentation metadata."""

            self.tabs[index]["text"] = primary_text
            self.tabs[index]["secondary_text"] = secondary_text
            self.tabs[index]["tooltip_text"] = tooltip_text

    cloned_workflow = WorkflowState(
        cubes={
            "Workflow Alias": CubeState(
                cube_id="ArtificialSweetener/Base-Cubes/Upscale.cube",
                version="2.0.0",
                alias="Workflow Alias",
                original_cube={},
                buffer={},
                display_name="Diffusion Upscale",
                ui={
                    "canonical_cube": {
                        "cube_id": "ArtificialSweetener/Base-Cubes/Upscale.cube",
                        "version": "2.0.0",
                        "description": "Upscales images with stable defaults.",
                        "metadata": {
                            "default_alias": "Diffusion Upscale",
                            "supported_models": ["SDXL 1.0"],
                            "tags": ["upscale"],
                        },
                    },
                    "source": {"repo_ref": "ArtificialSweetener/Base-Cubes"},
                },
            )
        },
        stack_order=["Workflow Alias"],
    )

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create duplicate UI with presentation-recording cube stack."""

        del set_as_current
        cube_stack = _PresentingCubeStack(f"{workflow_id}:cube", view.calls)
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
    assert isinstance(duplicate_stack, _PresentingCubeStack)
    tooltip = str(duplicate_stack.tabs[0]["tooltip_text"])
    assert "<b>Diffusion Upscale</b>, v2.0.0" in tooltip
    assert "Base-Cubes by ArtificialSweetener" in tooltip
    assert "<b>Supported models:</b> SDXL 1.0" in tooltip
    assert "<b>Description:</b> Upscales images" in tooltip
    assert "<b>Tags:</b> upscale" in tooltip


def test_duplicate_workflow_projects_cloned_cubes_into_active_editor() -> None:
    """Duplicating should refresh the new editor with cloned cube state."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    cloned_workflow = WorkflowState(
        cubes={
            "CubeA": CubeState(
                cube_id="Owner/Repo/CubeA.cube",
                version="1.0.0",
                alias="CubeA",
                original_cube={},
                buffer={},
            ),
            "CubeB": CubeState(
                cube_id="Owner/Repo/CubeB.cube",
                version="1.0.0",
                alias="CubeB",
                original_cube={},
                buffer={},
            ),
        },
        stack_order=["CubeA", "CubeB"],
    )
    loaded: list[dict[str, object]] = []

    def _create_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create duplicated workflow UI doubles with editor-load capture."""

        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor_panel = SimpleNamespace(
            load_all_cubes=lambda **kwargs: loaded.append(kwargs)
        )
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor_panel
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return WorkflowUiSurfaces(cube_stack, editor_panel, True)

    def _refresh_active_workflow_surface(**_kwargs: object) -> None:
        """Refresh active editor double from the active workflow session."""

        workflow_id = view.workflow_session_service.active_workflow_id
        workflow = view.workflow_session_service.workflows[workflow_id]
        editor_panel = view.editor_panels[workflow_id]
        editor_panel.load_all_cubes(
            cube_entries=[
                (alias, workflow.cubes[alias]) for alias in workflow.stack_order
            ],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
        )
        view.calls.append(f"refresh:{workflow_id}")

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=_create_workflow_ui)
    view.refresh_active_workflow_surface = _refresh_active_workflow_surface

    duplicated_id = mod.WorkflowWorkspaceCoordinator(view).duplicate_workflow(
        "wf-a",
        cloned_workflow,
        base_label="Recipe",
    )

    assert duplicated_id is not None
    assert len(loaded) == 1
    assert loaded[0]["cube_entries"] == [
        ("CubeA", cloned_workflow.cubes["CubeA"]),
        ("CubeB", cloned_workflow.cubes["CubeB"]),
    ]
    assert loaded[0]["cube_states"] is cloned_workflow.cubes
    assert loaded[0]["stack_order"] == cloned_workflow.stack_order
    assert view.calls.index(f"create:{duplicated_id}:True") < view.calls.index(
        f"canvas:project:{duplicated_id}"
    )
