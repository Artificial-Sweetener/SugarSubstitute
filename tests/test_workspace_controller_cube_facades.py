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

"""Tests for WorkspaceController cube action facade behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.ports import CubeCatalogRecord
from tests.workspace_controller_test_support import import_workspace_controller_module


def test_show_cube_picker_uses_display_name_for_alias_seed_and_cube_id_for_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller cube actions should seed aliases from display names."""

    mod = import_workspace_controller_module(monkeypatch)

    picker_records: list[list[CubeCatalogRecord]] = []
    alias_inputs: list[str] = []
    load_calls: list[tuple[object, str, str, int, dict[str, object]]] = []
    busy_calls: list[tuple[str, str]] = []

    class _Picker:
        """Select the first available cube."""

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            """Record picker records and return the first cube."""

            records = cast(list[CubeCatalogRecord], kwargs["records"])
            picker_records.append(list(records))
            return records[0]

    class _Stack:
        """Record tab insertion and selection."""

        def __init__(self) -> None:
            """Initialize tab and current-index records."""

            self.items: list[object] = []
            self.current_indices: list[int] = []

        def __bool__(self) -> bool:
            """Report that the stack is usable."""

            return True

        def count(self) -> int:
            """Return the current tab count."""

            return len(self.items)

        def insertTab(self, index: int, **_kwargs: object) -> object:
            """Insert a placeholder tab."""

            item = object()
            self.items.insert(index, item)
            return item

        def setCurrentIndex(self, index: int) -> None:
            """Record the selected tab index."""

            self.current_indices.append(index)

    active_stack = _Stack()

    def _resolve_unique_alias(_workflow: object, seed: str) -> str:
        """Record the alias seed and return the resolved alias."""

        alias_inputs.append(seed)
        return "text to image"

    def _begin_busy(workflow_id: str, *, message: str = "Loading") -> str:
        """Record editor busy state and return a token."""

        busy_calls.append((workflow_id, message))
        return "busy-token"

    view = SimpleNamespace(
        active_cube_stack=active_stack,
        cube_icon_factory=SimpleNamespace(icon_for_cube=lambda **_kwargs: object()),
        node_behavior_service=SimpleNamespace(),
        active_workflow_surface_refresher=SimpleNamespace(
            refresh_active_workflow_surface=lambda **_kwargs: None
        ),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: [
                CubeCatalogRecord(
                    cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
                    version="1.0.0",
                    display_name="text to image",
                )
            ]
        ),
        cube_stack_service=SimpleNamespace(resolve_unique_alias=_resolve_unique_alias),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={}
        ),
        cube_stacks={"wf-a": active_stack},
        editor_panels={"wf-a": SimpleNamespace()},
        refresh_active_workflow_surface=lambda: None,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        editor_busy=SimpleNamespace(
            begin=_begin_busy,
            end=lambda _token: None,
        ),
        _pending_cubes={},
    )
    controller = mod.WorkspaceController(view)

    controller.cube_picker_actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=SimpleNamespace(CLOSE=SimpleNamespace(icon=lambda: object())),
        cube_loader=lambda callbacks, cube_id, alias_name, placeholder_index, **kwargs: (
            load_calls.append(
                (callbacks, cube_id, alias_name, placeholder_index, kwargs)
            )
        ),
    )

    assert [
        [record.display_name for record in records] for records in picker_records
    ] == [["text to image"]]
    assert alias_inputs == []
    assert len(load_calls) == 1
    callbacks, cube_id, alias_name, placeholder_index, kwargs = load_calls[0]
    assert isinstance(callbacks, mod.CubeLoadUiCallbacks)
    assert callbacks.workflow_session_service is view.workflow_session_service
    assert callbacks.cube_stacks is view.cube_stacks
    assert callbacks.editor_panels is view.editor_panels
    assert callbacks.cube_load_service is view.cube_load_service
    assert callbacks.cube_stack_service is view.cube_stack_service
    assert callable(callbacks.refresh_loaded_cube_surface)
    assert callable(callbacks.activate_loaded_cube)
    assert cube_id == "Artificial-Sweetener/Base-Cubes/Text to Image.cube"
    assert alias_name == "text to image"
    assert placeholder_index == 0
    assert callable(kwargs["on_load_finished"])
    assert busy_calls == [("wf-a", "Loading")]
    assert view._pending_cubes == {"text to image": 0}
    assert active_stack.current_indices == [0]


def test_show_cube_picker_disambiguates_duplicate_display_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller cube actions should keep duplicate display-name loads canonical."""

    mod = import_workspace_controller_module(monkeypatch)

    picker_records: list[list[CubeCatalogRecord]] = []
    alias_inputs: list[str] = []
    load_calls: list[tuple[object, str, str, int, dict[str, object]]] = []
    busy_calls: list[tuple[str, str]] = []

    class _Picker:
        """Select the second available cube."""

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            """Record picker records and return the second cube."""

            records = cast(list[CubeCatalogRecord], kwargs["records"])
            picker_records.append(list(records))
            return records[1]

    class _Stack:
        """Record tab insertion."""

        def __init__(self) -> None:
            """Initialize tab records."""

            self.items: list[object] = []

        def __bool__(self) -> bool:
            """Report that the stack is usable."""

            return True

        def count(self) -> int:
            """Return the current tab count."""

            return len(self.items)

        def insertTab(self, index: int, **_kwargs: object) -> object:
            """Insert a placeholder tab."""

            item = object()
            self.items.insert(index, item)
            return item

        def setCurrentIndex(self, _index: int) -> None:
            """Accept selection requests."""

            return None

    def _resolve_unique_alias(_workflow: object, seed: str) -> str:
        """Record the alias seed and return the resolved alias."""

        alias_inputs.append(seed)
        return "Shared 2"

    def _begin_busy(workflow_id: str, *, message: str = "Loading") -> str:
        """Record editor busy state and return a token."""

        busy_calls.append((workflow_id, message))
        return "busy-token"

    view = SimpleNamespace(
        active_cube_stack=_Stack(),
        cube_icon_factory=SimpleNamespace(icon_for_cube=lambda **_kwargs: object()),
        node_behavior_service=SimpleNamespace(),
        active_workflow_surface_refresher=SimpleNamespace(
            refresh_active_workflow_surface=lambda **_kwargs: None
        ),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: [
                CubeCatalogRecord(
                    cube_id="Artificial-Sweetener/Base-Cubes/Cube A.cube",
                    version="1.0.0",
                    display_name="Shared",
                ),
                CubeCatalogRecord(
                    cube_id="Artificial-Sweetener/Base-Cubes/Cube B.cube",
                    version="1.0.0",
                    display_name="Shared",
                ),
            ]
        ),
        cube_stack_service=SimpleNamespace(resolve_unique_alias=_resolve_unique_alias),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={}
        ),
        cube_stacks={"wf-a": _Stack()},
        editor_panels={"wf-a": SimpleNamespace()},
        refresh_active_workflow_surface=lambda: None,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        editor_busy=SimpleNamespace(
            begin=_begin_busy,
            end=lambda _token: None,
        ),
        _pending_cubes={},
    )
    view.cube_stacks["wf-a"] = view.active_cube_stack
    controller = mod.WorkspaceController(view)

    controller.cube_picker_actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=SimpleNamespace(CLOSE=SimpleNamespace(icon=lambda: object())),
        cube_loader=lambda callbacks, cube_id, alias_name, placeholder_index, **kwargs: (
            load_calls.append(
                (callbacks, cube_id, alias_name, placeholder_index, kwargs)
            )
        ),
    )

    assert [[record.cube_id for record in records] for records in picker_records] == [
        [
            "Artificial-Sweetener/Base-Cubes/Cube A.cube",
            "Artificial-Sweetener/Base-Cubes/Cube B.cube",
        ]
    ]
    assert alias_inputs == []
    assert len(load_calls) == 1
    callbacks, cube_id, alias_name, placeholder_index, kwargs = load_calls[0]
    assert isinstance(callbacks, mod.CubeLoadUiCallbacks)
    assert callbacks.workflow_session_service is view.workflow_session_service
    assert cube_id == "Artificial-Sweetener/Base-Cubes/Cube B.cube"
    assert alias_name == "Shared"
    assert placeholder_index == 0
    assert callable(kwargs["on_load_finished"])
    assert busy_calls == [("wf-a", "Loading")]
