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

"""Cube-picker draft reorder, removal, and alias contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast


from substitute.application.cubes import (
    CubeStackDraft,
    CubeStackDraftEntry,
    CubeStackService,
    cube_stack_draft_result,
)


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _EditorBusyRecorder,
    _import_module,
    _surface_refresher,
)


def test_cube_stack_draft_reorders_and_removes_existing_without_loading() -> None:
    """Applying existing-only draft edits should mutate workflow only on Apply."""

    mod = _import_module()
    stack = _CubeStack()
    stack.insertTab(0, routeKey="Text", text="Text")
    stack.insertTab(1, routeKey="Upscale", text="Upscale")
    workflow = SimpleNamespace(
        stack_order=["Text", "Upscale"],
        cubes={
            "Text": SimpleNamespace(cube_id="base_text", version="1.0.0", ui={}),
            "Upscale": SimpleNamespace(cube_id="base_upscale", version="1.0.0", ui={}),
        },
    )
    service = CubeStackService()
    refresh_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    activated: list[tuple[str, str]] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: []),
        cube_stack_service=service,
        get_active_workflow=lambda: workflow,
        _pending_cubes={},
        active_workflow_surface_refresher=_surface_refresher(
            lambda: refresh_calls.append("refresh")
        ),
        editor_busy=_EditorBusyRecorder(busy_calls),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: SimpleNamespace(
            activate_loaded_cube=lambda workflow_id, cube_alias: activated.append(
                (workflow_id, cube_alias)
            )
        ),
    )

    class _Picker:
        @staticmethod
        def edit_stack(**_kwargs: object) -> object:
            return cube_stack_draft_result(
                [
                    CubeStackDraftEntry(
                        draft_id="existing:Upscale",
                        source="existing",
                        cube_id="base_upscale",
                        display_name="Upscale",
                        secondary_text="v1.0.0",
                        icon=None,
                        existing_alias="Upscale",
                    )
                ]
            )

    actions.show_cube_picker(
        cube_picker=_Picker,
        cube_loader=lambda *_args, **_kwargs: None,
    )

    assert workflow.stack_order == ["Upscale"]
    assert list(workflow.cubes) == ["Upscale"]
    assert [item.routeKey() for item in stack.items] == ["Upscale"]
    assert refresh_calls == ["refresh"]
    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert activated == [("wf-a", "Upscale")]


def test_cube_stack_draft_queues_new_aliases_around_locked_existing_duplicate() -> None:
    """Cart apply should use the same new/existing/new alias plan shown in the cart."""

    mod = _import_module()
    stack = _CubeStack()
    stack.insertTab(
        0,
        routeKey="Diffusion Upscale",
        text="Diffusion Upscale",
    )
    queued: list[dict[str, object]] = []
    service_calls: list[tuple[str, object]] = []

    def begin_busy(_workflow_id: str, *, message: str = "Loading") -> str:
        """Record busy-state acquisition and return its token."""
        service_calls.append(("busy", message))
        return "busy-token"

    workflow = SimpleNamespace(
        stack_order=["Diffusion Upscale"],
        cubes={
            "Diffusion Upscale": SimpleNamespace(
                cube_id="base_upscale",
                version="1.0.0",
                ui={},
            )
        },
    )

    class _StackService(CubeStackService):
        def resolve_unique_alias(
            self,
            workflow: object,
            requested_alias: str,
            *,
            exclude_alias: str | None = None,
        ) -> str:
            """Fail if cart commit tries to re-resolve planned aliases."""

            _ = workflow, requested_alias, exclude_alias
            raise AssertionError("cart commit should use the alias plan")

    service = _StackService()
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: []),
        cube_stack_service=service,
        get_active_workflow=lambda: workflow,
        _pending_cubes={},
        editor_busy=SimpleNamespace(
            begin=begin_busy,
            end=lambda token: service_calls.append(("end", token)),
        ),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: SimpleNamespace(),
    )

    class _Picker:
        @staticmethod
        def edit_stack(**kwargs: object) -> object:
            initial_draft = cast(CubeStackDraft, kwargs["initial_draft"])
            existing = initial_draft.entries[0]
            return cube_stack_draft_result(
                [
                    CubeStackDraftEntry(
                        draft_id="copy-a",
                        source="new",
                        cube_id="base_upscale",
                        display_name="Diffusion Upscale",
                        secondary_text="v1.0.0",
                        icon=None,
                    ),
                    existing,
                    CubeStackDraftEntry(
                        draft_id="copy-b",
                        source="new",
                        cube_id="base_upscale",
                        display_name="Diffusion Upscale",
                        secondary_text="v1.0.0",
                        icon=None,
                    ),
                ]
            )

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=_IconProvider,
        cube_loader=lambda callbacks, cube_id, alias_name, placeholder_index, **kwargs: (
            queued.append(
                {
                    "callbacks": callbacks,
                    "cube_id": cube_id,
                    "alias_name": alias_name,
                    "placeholder_index": placeholder_index,
                    **kwargs,
                }
            )
        ),
    )

    assert [item.routeKey() for item in stack.items] == [
        "loading:Diffusion Upscale 2",
        "Diffusion Upscale",
        "loading:Diffusion Upscale 3",
    ]
    assert workflow.stack_order == ["Diffusion Upscale"]
    assert list(workflow.cubes) == ["Diffusion Upscale"]
    assert [call["alias_name"] for call in queued] == [
        "Diffusion Upscale 2",
        "Diffusion Upscale 3",
    ]
    assert [call["placeholder_index"] for call in queued] == [0, 2]
    assert view._pending_cubes == {
        "Diffusion Upscale 2": 0,
        "Diffusion Upscale 3": 2,
    }
