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

"""Cube-picker missing-alias, empty, and initial-draft contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast


from substitute.application.cubes import (
    CubeStackDraft,
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


def test_show_cube_picker_continues_staged_batch_after_missing_resolved_alias() -> None:
    """A failed staged callback should advance the queue and let later loads finish."""

    mod = _import_module()
    stack = _CubeStack()
    records = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A"),
        CubeCatalogRecord(cube_id="base_b", version="1.0.0", display_name="B"),
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

    assert [call["cube_id"] for call in queued] == ["base_a", "base_b"]
    _finish_queued_load(queued, stack, 0, None)
    assert busy_calls == [("begin", ("wf-a", "Loading"))]

    _finish_queued_load(queued, stack, 1, "B")

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert refresh_calls == ["refresh"]
    assert activated == [("wf-a", "B")]


def test_show_cube_picker_empty_staging_result_returns_without_loading() -> None:
    """Empty applies should leave the real workflow stack untouched."""

    mod = _import_module()
    stack = _CubeStack()
    queued: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: [
                CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A")
            ]
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        @staticmethod
        def stage_cubes(**_kwargs: object) -> object:
            return cube_stack_draft_result([])

    actions.show_cube_picker(
        cube_picker=_Picker,
        cube_loader=lambda *_args, **_kwargs: queued.append("queued"),
    )

    assert stack.items == []
    assert queued == []


def test_show_cube_picker_passes_active_workflow_stack_as_initial_draft() -> None:
    """The picker drawer should open with the real active workflow stack."""

    mod = _import_module()
    stack = _CubeStack()
    workflow = SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                cube_id="base_text",
                version="1.0.0",
                display_name="Text to Image",
                ui={"cube_icon": "icon-token"},
            )
        },
    )
    captured: list[dict[str, object]] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: []),
        get_active_workflow=lambda: workflow,
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        @staticmethod
        def edit_stack(**kwargs: object) -> object:
            captured.append(kwargs)
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    initial_draft = cast(CubeStackDraft, captured[0]["initial_draft"])
    assert [entry.display_name for entry in initial_draft.entries] == ["Text"]
    assert initial_draft.entries[0].existing_alias == "Text"
    assert initial_draft.entries[0].icon == "icon-token"
    assert captured[0]["stack_anchor"] is stack
