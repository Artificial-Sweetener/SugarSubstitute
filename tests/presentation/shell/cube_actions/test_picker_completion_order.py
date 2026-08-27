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

"""Cube-picker out-of-order completion contracts."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.cubes import (
    CubeStackService,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _EditorBusyRecorder,
    _EmptyNodeBehaviorService,
    _finish_queued_load,
    _import_module,
    _surface_refresher,
)


def test_show_cube_picker_activates_first_staged_alias_after_out_of_order_completion() -> (
    None
):
    """Batch completion should activate the first staged success, not last finisher."""

    mod = _import_module()
    stack = _CubeStack()
    records = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A"),
        CubeCatalogRecord(cube_id="base_b", version="1.0.0", display_name="B"),
        CubeCatalogRecord(cube_id="base_c", version="1.0.0", display_name="C"),
    ]
    queued: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    refresh_calls: list[str] = []
    activated: list[tuple[str, str]] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: records),
        cube_stack_service=CubeStackService(),
        node_behavior_service=_EmptyNodeBehaviorService(),
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
        def stage_cubes(**_kwargs: object) -> object:
            return cube_stack_draft_result(
                [
                    cube_stack_draft_entry_from_record(records[0], draft_id="copy-a"),
                    cube_stack_draft_entry_from_record(records[1], draft_id="copy-b"),
                    cube_stack_draft_entry_from_record(records[2], draft_id="copy-c"),
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

    _finish_queued_load(queued, stack, 2, "C")
    _finish_queued_load(queued, stack, 0, "A")
    _finish_queued_load(queued, stack, 1, "B")

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert refresh_calls == ["refresh"]
    assert activated == [("wf-a", "A")]
