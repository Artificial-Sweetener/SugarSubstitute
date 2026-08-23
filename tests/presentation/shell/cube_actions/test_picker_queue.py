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

"""Cube-picker staged queueing contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast


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


def test_show_cube_picker_inserts_loading_tab_and_tracks_pending_cube() -> None:
    """Cube selection should insert a loading tab, select it, and queue the load."""

    mod = _import_module()
    stack = _CubeStack()
    queued: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: [
                CubeCatalogRecord(
                    cube_id="base_a", version="1.0.0", display_name="Loader"
                )
            ]
        ),
        cube_stack_service=SimpleNamespace(
            resolve_unique_alias=lambda _workflow, seed: f"{seed} 2"
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        _pending_cubes={},
        editor_busy=_EditorBusyRecorder(busy_calls),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        selected_records: list[CubeCatalogRecord] = []

        @staticmethod
        def stage_cubes(**kwargs: object) -> object:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.selected_records = records
            return cube_stack_draft_result(
                [cube_stack_draft_entry_from_record(records[0], draft_id="copy-a")]
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

    assert stack.items[0].kwargs["routeKey"] == "loading:Loader"
    assert _Picker.selected_records[0].cube_id == "base_a"
    assert stack.items[0].kwargs["text"] == "Loading..."
    assert stack.current_indices == [0]
    assert view._pending_cubes == {"Loader": 0}
    assert len(queued) == 1
    assert queued[0]["callbacks"] == "callbacks"
    assert queued[0]["cube_id"] == "base_a"
    assert queued[0]["alias_name"] == "Loader"
    assert queued[0]["placeholder_index"] == 0
    assert queued[0]["reveal_after_load"] is True
    presentation_intent = cast(Any, queued[0]["presentation_intent"])
    assert presentation_intent.select_after_load is True
    assert presentation_intent.scroll_after_load is True
    assert busy_calls == [("begin", ("wf-a", "Loading"))]
    queued_finish = queued[0]["on_load_finished"]
    assert callable(queued_finish)
    queued_finish("Loader")
    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]


def test_show_cube_picker_queues_multiple_staged_cube_loads_immediately() -> None:
    """Applying staged cubes should queue all loads before any completion callback."""

    mod = _import_module()
    stack = _CubeStack()
    records = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Shared"),
        CubeCatalogRecord(cube_id="base_b", version="1.0.0", display_name="Shared"),
        CubeCatalogRecord(cube_id="base_c", version="1.0.0", display_name="Shared"),
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
        def stage_cubes(**kwargs: object) -> object:
            picker_records = kwargs["records"]
            assert picker_records == records
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

    assert [item.kwargs["routeKey"] for item in stack.items] == [
        "loading:Shared",
        "loading:Shared 2",
        "loading:Shared 3",
    ]
    assert [call["cube_id"] for call in queued] == ["base_a", "base_b", "base_c"]
    assert [call["alias_name"] for call in queued] == [
        "Shared",
        "Shared 2",
        "Shared 3",
    ]
    assert [call["placeholder_index"] for call in queued] == [0, 1, 2]
    assert [call["reveal_after_load"] for call in queued] == [False, False, False]
    assert [
        cast(Any, call["presentation_intent"]).select_after_load for call in queued
    ] == [
        False,
        False,
        False,
    ]
    assert [
        cast(Any, call["presentation_intent"]).scroll_after_load for call in queued
    ] == [
        False,
        False,
        False,
    ]
    assert view._pending_cubes == {"Shared": 0, "Shared 2": 1, "Shared 3": 2}
    assert busy_calls == [("begin", ("wf-a", "Loading"))]

    _finish_queued_load(queued, stack, 0, "Shared")
    assert busy_calls == [("begin", ("wf-a", "Loading"))]

    _finish_queued_load(queued, stack, 1, "Shared 2")
    assert busy_calls == [("begin", ("wf-a", "Loading"))]

    _finish_queued_load(queued, stack, 2, "Shared 3")
    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert refresh_calls == ["refresh"]
    assert activated == [("wf-a", "Shared")]
