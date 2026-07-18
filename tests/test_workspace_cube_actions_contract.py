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

"""Contract tests for extracted workspace cube actions."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.cubes import (
    CubeStackDraft,
    CubeStackDraftEntry,
    CubeStackService,
    CubeLoadService,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.application.ports import CubeCatalogSnapshot
from substitute.infrastructure.comfy.prompt_gateway import ComfyEndpoint
from substitute.infrastructure.cubes import BackendCubeRepository
from substitute.infrastructure.external import SubstituteBackendCubeLibraryClient
from substitute.domain.links import NodeLinkEndpointIndex, PromptEndpointIndex
from substitute.presentation.errors import ErrorPresenter


def _import_module():
    """Import the workspace cube actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_cube_picker_actions"
    )


def _import_stack_module():
    """Import the focused workspace cube-card actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_cube_stack_actions"
    )


def _stack_actions(module: Any, view: object) -> object:
    """Build focused cube-card actions with unused feature dependencies."""

    return module.WorkspaceCubeStackActions(
        view,
        duplication_service=SimpleNamespace(),
        stack_presenter=SimpleNamespace(),
        surface_projector=SimpleNamespace(),
    )


def _surface_refresher(
    refresh: Callable[..., None],
) -> SimpleNamespace:
    """Build a composed active workflow surface refresher double."""

    return SimpleNamespace(refresh_active_workflow_surface=refresh)


class _CubeStack:
    """Cube-stack double tracking inserted placeholders and selection."""

    def __init__(self) -> None:
        self.items: list[object] = []
        self.current_indices: list[int] = []
        self.bypassed_updates: list[tuple[int, bool]] = []

    def count(self) -> int:
        """Return item count."""

        return len(self.items)

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert one placeholder cube tab."""

        item = SimpleNamespace(
            index=index,
            kwargs=kwargs,
            _route_key=kwargs.get("routeKey", ""),
        )
        item.routeKey = lambda item=item: item._route_key
        item.setRouteKey = lambda key, item=item: setattr(item, "_route_key", key)
        self.items.insert(index, item)
        return item

    def tabItem(self, index: int) -> object:
        """Return one stack item."""

        return self.items[index]

    def removeTab(self, index: int) -> None:
        """Remove one stack item."""

        self.items.pop(index)

    def reorder_by_route_keys(self, route_keys: list[str]) -> None:
        """Project item order by route key."""

        if len(route_keys) != len(self.items):
            return
        by_route = {item.routeKey(): item for item in self.items}
        if any(route_key not in by_route for route_key in route_keys):
            return
        self.items = [by_route[route_key] for route_key in route_keys]

    def setCurrentIndex(self, index: int) -> None:
        """Record current-index changes."""

        self.current_indices.append(index)

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Record bypass presentation updates."""

        self.bypassed_updates.append((index, bypassed))


class _EmptyNodeBehaviorService:
    """Endpoint provider double that exposes no linkable nodes."""

    def build_prompt_endpoint_index(
        self,
        cube_states: object,
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return an empty prompt endpoint index."""

        return PromptEndpointIndex()

    def build_node_link_endpoint_index(
        self,
        cube_states: object,
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return an empty whole-node endpoint index."""

        return NodeLinkEndpointIndex()


class _EditorBusyRecorder:
    """Record editor busy controller calls for cube action tests."""

    def __init__(self, calls: list[tuple[str, object]]) -> None:
        """Store the shared call list."""

        self._calls = calls

    def begin(self, workflow_id: str, *, message: str = "Loading") -> object:
        """Record a begin request and return a stable token."""

        self._calls.append(("begin", (workflow_id, message)))
        return "busy-token"

    def end(self, token: object) -> None:
        """Record an end request."""

        self._calls.append(("end", token))


def _finish_queued_load(
    queued: list[dict[str, object]],
    stack: _CubeStack,
    index: int,
    resolved_alias: str | None,
) -> None:
    """Resolve a queued loader callback the way the real cube loader does."""

    queued_call = queued[index]
    if resolved_alias is not None:
        placeholder_index = queued_call["placeholder_index"]
        assert isinstance(placeholder_index, int)
        stack.tabItem(placeholder_index).setRouteKey(resolved_alias)
    finish = queued_call["on_load_finished"]
    assert callable(finish)
    finish(resolved_alias)


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
    assert queued[0]["presentation_intent"].select_after_load is True
    assert queued[0]["presentation_intent"].scroll_after_load is True
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
    assert [call["presentation_intent"].select_after_load for call in queued] == [
        False,
        False,
        False,
    ]
    assert [call["presentation_intent"].scroll_after_load for call in queued] == [
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


def test_show_cube_picker_activates_batch_alias_after_surface_refresh_completes() -> (
    None
):
    """Batch navigation should wait until the refreshed editor surface is ready."""

    mod = _import_module()
    stack = _CubeStack()
    records = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A"),
        CubeCatalogRecord(cube_id="base_b", version="1.0.0", display_name="B"),
    ]
    queued: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    refresh_callbacks: list[Callable[[], None] | None] = []
    activated: list[tuple[str, str]] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    def refresh_active_workflow_surface(
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Record the deferred editor refresh completion callback."""

        refresh_callbacks.append(on_complete)

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
            refresh_active_workflow_surface
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

    _finish_queued_load(queued, stack, 0, "A")
    _finish_queued_load(queued, stack, 1, "B")

    assert len(refresh_callbacks) == 1
    on_complete = refresh_callbacks[0]
    assert callable(on_complete)
    assert busy_calls == [("begin", ("wf-a", "Loading"))]
    assert activated == []

    on_complete()

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert activated == [("wf-a", "A")]


def test_show_cube_picker_reconciles_batch_after_restoring_final_draft_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch completion should reconcile links after restoring the accepted order."""

    mod = _import_module()
    events: list[tuple[str, object]] = []
    stack = _CubeStack()
    stack.insertTab(0, routeKey="Existing", text="Existing")
    records = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A"),
        CubeCatalogRecord(cube_id="base_b", version="1.0.0", display_name="B"),
    ]
    queued: list[dict[str, object]] = []
    workflow = SimpleNamespace(
        cubes={"Existing": SimpleNamespace(cube_id="base_existing", version="1.0.0")},
        stack_order=["Existing"],
    )

    class _RecordingLinkService:
        """Record the batch-final link reconciliation lifecycle."""

        def __init__(
            self,
            *,
            prompt_endpoint_provider: object,
            node_link_endpoint_provider: object,
        ) -> None:
            """Record construction without inspecting endpoint providers."""

            events.append(("link_service_init", prompt_endpoint_provider))
            events.append(("node_provider", node_link_endpoint_provider))

        def reconcile_transition(
            self,
            *,
            previous_cube_states: object,
            previous_stack_order: list[str] | None,
            current_cube_states: object,
            current_stack_order: list[str] | None,
        ) -> None:
            """Record transition orders used by batch completion."""

            events.append(
                (
                    "reconcile",
                    {
                        "previous_order": list(previous_stack_order or []),
                        "current_order": list(current_stack_order or []),
                    },
                )
            )

        def sanitize_current_state(
            self,
            *,
            cube_states: object,
            stack_order: list[str] | None,
        ) -> None:
            """Record final sanitize order."""

            events.append(("sanitize", list(stack_order or [])))

    monkeypatch.setattr(
        mod,
        "WorkflowLinkReconciliationService",
        _RecordingLinkService,
    )
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
            lambda: events.append(("refresh", list(workflow.stack_order)))
        ),
        editor_busy=SimpleNamespace(
            begin=lambda workflow_id, *, message="Loading": (
                events.append(("begin_busy", (workflow_id, message))),
                "busy-token",
            )[1],
            end=lambda token: events.append(("end_busy", token)),
        ),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: SimpleNamespace(
            activate_loaded_cube=lambda workflow_id, cube_alias: events.append(
                ("activate", (workflow_id, cube_alias, list(workflow.stack_order)))
            )
        ),
    )

    class _Picker:
        @staticmethod
        def stage_cubes(**kwargs: object) -> object:
            initial_draft = cast(CubeStackDraft, kwargs["initial_draft"])
            return cube_stack_draft_result(
                [
                    initial_draft.entries[0],
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

    workflow.cubes["B"] = SimpleNamespace(cube_id="base_b", version="1.0.0")
    workflow.stack_order = ["Existing", "B"]
    _finish_queued_load(queued, stack, 1, "B")
    workflow.cubes["A"] = SimpleNamespace(cube_id="base_a", version="1.0.0")
    workflow.stack_order = ["Existing", "B", "A"]
    _finish_queued_load(queued, stack, 0, "A")

    assert workflow.stack_order == ["Existing", "A", "B"]
    assert (
        "reconcile",
        {
            "previous_order": ["Existing"],
            "current_order": ["Existing", "A", "B"],
        },
    ) in events
    assert ("sanitize", ["Existing", "A", "B"]) in events
    assert events[-3:] == [
        ("refresh", ["Existing", "A", "B"]),
        ("end_busy", "busy-token"),
        ("activate", ("wf-a", "A", ["Existing", "A", "B"])),
    ]


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
            begin=lambda _workflow_id, *, message="Loading": (
                service_calls.append(("busy", message)),
                "busy-token",
            )[1],
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


def test_show_cube_picker_queue_failure_uses_default_error_presenter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue failures should lazily resolve the copyable application error modal."""

    mod = _import_module()
    stack = _CubeStack()
    busy_calls: list[tuple[str, object]] = []
    presented: list[dict[str, Any]] = []
    record = CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A")
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: [record]),
        cube_stack_service=SimpleNamespace(
            resolve_unique_alias=lambda _workflow, seed: seed
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        _pending_cubes={},
        editor_busy=_EditorBusyRecorder(busy_calls),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )
    monkeypatch.setattr(
        mod,
        "ErrorPresenter",
        lambda *, parent: SimpleNamespace(
            parent=parent,
            show_exception_report=lambda **kwargs: presented.append(kwargs),
        ),
    )

    class _Picker:
        @staticmethod
        def stage_cubes(**_kwargs: object) -> object:
            return cube_stack_draft_result(
                [cube_stack_draft_entry_from_record(record, draft_id="copy-a")]
            )

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    def _raise_loader(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("queue failed")

    actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=_IconProvider,
        cube_loader=_raise_loader,
    )

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert presented[0]["title"] == "Staged cube queue failed"
    assert presented[0]["stage"] == "cube_load"
    assert str(presented[0]["error"]) == "queue failed"
    assert presented[0]["context"].operation == "queue_staged_cubes"


def test_show_cube_picker_list_failure_reports_through_error_presenter() -> None:
    """Cube catalog failures should use the unified error modal presenter."""

    mod = _import_module()
    stack = _CubeStack()
    presented: list[dict[str, Any]] = []
    failure = RuntimeError("catalog unavailable")
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: (_ for _ in ()).throw(failure)
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    actions.show_cube_picker()

    assert presented[0]["title"] == "Cube picker failed"
    assert presented[0]["stage"] == "cube_picker"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "list_cubes_for_picker"
    assert context.workflow_id == "wf-a"
    assert context.trace_id


def test_show_cube_picker_missing_catalog_refresh_error_does_not_open_empty_picker() -> (
    None
):
    """Unavailable catalog snapshots should fail loudly instead of showing no cubes."""

    mod = _import_module()
    stack = _CubeStack()
    presented: list[dict[str, Any]] = []
    picker_calls: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[],
                state="missing",
            ),
            refresh_picker_catalog=lambda: CubeCatalogSnapshot(
                entries=[],
                state="error",
                error="backend refused connection",
            ),
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    class _Picker:
        @staticmethod
        def select_cube(**_kwargs: object) -> CubeCatalogRecord | None:
            picker_calls.append("opened")
            return None

    actions.show_cube_picker(
        cube_picker=_Picker,
    )

    assert picker_calls == []
    assert presented[0]["title"] == "Cube picker failed"
    assert presented[0]["stage"] == "cube_picker"
    assert str(presented[0]["error"]) == "backend refused connection"
    context = presented[0]["context"]
    assert context.operation == "list_cubes_for_picker"
    assert context.workflow_id == "wf-a"
    assert context.values["catalog_state"] == "error"


def test_show_cube_picker_missing_catalog_refresh_success_opens_with_records() -> None:
    """Cold cache opens should recover when the synchronous refresh gets records."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    refreshed: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[],
                state="missing",
            ),
            refresh_picker_catalog=lambda: (
                refreshed.append("refresh"),
                CubeCatalogSnapshot(entries=catalog, state="fresh"),
            )[1],
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert refreshed == ["refresh"]
    assert _Picker.records == catalog


def test_show_cube_picker_live_backend_catalog_opens_with_records() -> None:
    """Live backend smoke: Add Cubes receives records from a ready catalog."""

    mod = _import_module()
    stack = _CubeStack()
    endpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    client = SubstituteBackendCubeLibraryClient(endpoint, timeout_seconds=10.0)
    catalog = client.get_catalog()
    if catalog is None or not catalog.cubes:
        pytest.skip("Substitute BackEnd has not published a cube catalog on port 8188.")
    cube_load_service = CubeLoadService(BackendCubeRepository(client=client))
    presented: list[dict[str, Any]] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-live"),
        cube_icon_factory=object(),
        cube_load_service=cube_load_service,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    class _Picker:
        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert presented == []
    assert _Picker.records
    assert any(record.cube_id for record in _Picker.records)


def test_show_cube_picker_queue_failure_reports_through_error_presenter() -> None:
    """Staged queue failures should produce a complete copyable error report."""

    mod = _import_module()
    stack = _CubeStack()
    busy_calls: list[tuple[str, object]] = []
    presented: list[tuple[Any, str]] = []
    record = CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A")
    failure = RuntimeError("queue failed")

    def _dialog_factory(
        _parent: object | None,
        report: Any,
        report_text: str,
        _open_console: Callable[[], None] | None,
    ) -> object:
        """Capture the report payload used by the standard copy-report dialog."""

        presented.append((report, report_text))
        return SimpleNamespace(exec=lambda: None)

    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: [record]),
        cube_stack_service=SimpleNamespace(
            resolve_unique_alias=lambda _workflow, seed: seed
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        _pending_cubes={},
        editor_busy=_EditorBusyRecorder(busy_calls),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=ErrorPresenter(
            parent=None,
            dialog_factory=_dialog_factory,
        ),
    )

    class _Picker:
        @staticmethod
        def stage_cubes(**_kwargs: object) -> object:
            return cube_stack_draft_result(
                [cube_stack_draft_entry_from_record(record, draft_id="copy-a")]
            )

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    def _raise_loader(*_args: object, **_kwargs: object) -> None:
        raise failure

    actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=_IconProvider,
        cube_loader=_raise_loader,
    )

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    report, report_text = presented[0]
    assert report.title == "Staged cube queue failed"
    assert report.stage == "cube_load"
    context = report.operation_context
    assert context is not None
    assert context.operation == "queue_staged_cubes"
    assert context.workflow_id == "wf-a"
    assert context.values["failed_queue_count"] == 1
    assert context.values["staged_count"] == 1
    assert "Operation: queue_staged_cubes" in report_text
    assert "Workflow ID: wf-a" in report_text
    assert "Failed Queue Count: 1" in report_text
    assert "RuntimeError: queue failed" in report_text


def test_show_cube_picker_uses_warm_snapshot_without_blocking_list() -> None:
    """Warm picker opens should use cached snapshot data immediately."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    list_calls: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=catalog,
                state="fresh",
            ),
            list_available_cubes=lambda: list_calls.append("list"),
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert _Picker.records == catalog
    assert list_calls == []


def test_show_cube_picker_schedules_background_refresh_for_stale_snapshot(
    monkeypatch,
) -> None:
    """Stale warm catalog data should show immediately and refresh in background."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    scheduled: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=catalog,
                state="stale",
            ),
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )
    monkeypatch.setattr(
        actions,
        "_schedule_catalog_refresh",
        lambda trace_id: scheduled.append(trace_id),
    )

    class _Picker:
        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert _Picker.records == catalog
    assert len(scheduled) == 1


def test_prepare_node_behavior_runtime_delegates_to_service() -> None:
    """Runtime preparation should use the node-behavior service directly."""

    mod = _import_module()
    runtime_state = object()
    service_calls: list[str] = []
    loaded_cube = SimpleNamespace(
        cube_id="CubeA", version="1.0.0", display_name="Cube A", ui_payload={}
    )
    view = SimpleNamespace(
        node_behavior_service=SimpleNamespace(
            prepare_runtime_state=lambda _loaded_cube, alias_name: (
                service_calls.append(alias_name),
                runtime_state,
            )[1],
        )
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    result = actions.prepare_node_behavior_runtime(loaded_cube, "AliasA")

    assert result is runtime_state
    assert service_calls == ["AliasA"]


def test_cube_rename_edit_request_expands_compact_stack_before_editing() -> None:
    """Compact rename editing should wait for temporary expansion completion."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []
    completion_callbacks: list[Callable[[], None]] = []

    class _Stack:
        def __init__(self) -> None:
            self.edit_requests: list[str] = []

        def begin_alias_editing(self, route_key: str) -> bool:
            self.edit_requests.append(route_key)
            events.append(("begin_edit", route_key))
            return True

        def isCompact(self) -> bool:
            return True

    stack = _Stack()

    lease = SimpleNamespace(release=lambda: events.append(("release", "Old")))

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        events.append(("acquire", "Old"))
        if on_expanded is not None:
            completion_callbacks.append(on_expanded)
        return lease

    view = SimpleNamespace(
        active_cube_stack=stack,
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("Old")

    assert events == [("acquire", "Old")]
    assert stack.edit_requests == []

    completion_callbacks[0]()

    assert stack.edit_requests == ["Old"]
    assert events == [
        ("acquire", "Old"),
        ("begin_edit", "Old"),
    ]


def test_cube_rename_edit_finish_releases_temporary_expansion_lease() -> None:
    """Alias editing should release its presentation lease on every finish path."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []

    class _Stack:
        def begin_alias_editing(self, route_key: str) -> bool:
            events.append(("begin_edit", route_key))
            return True

        def isCompact(self) -> bool:
            return False

    lease_counter = {"value": 0}

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        lease_counter["value"] += 1
        lease_id = lease_counter["value"]
        events.append(("acquire", lease_id))
        if on_expanded is not None:
            on_expanded()
        return SimpleNamespace(
            release=lambda: events.append(("release", lease_id)),
        )

    view = SimpleNamespace(
        active_cube_stack=_Stack(),
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("CompactAlias")
    actions.on_cube_rename_edit_finished("CompactAlias")

    actions.on_cube_rename_edit_requested("ExpandedAlias")
    actions.on_cube_rename_edit_finished("ExpandedAlias")

    assert events == [
        ("acquire", 1),
        ("begin_edit", "CompactAlias"),
        ("release", 1),
        ("acquire", 2),
        ("begin_edit", "ExpandedAlias"),
        ("release", 2),
    ]


def test_cube_rename_edit_abort_restores_compact_when_item_disappears() -> None:
    """Failed post-expansion editor start should undo temporary expansion."""

    mod = _import_stack_module()
    events: list[tuple[str, object]] = []

    class _Stack:
        def begin_alias_editing(self, route_key: str) -> bool:
            events.append(("begin_edit", route_key))
            return False

        def isCompact(self) -> bool:
            return True

    def acquire_expansion(
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> object:
        events.append(("acquire", "Gone"))
        if on_expanded is not None:
            on_expanded()
        return SimpleNamespace(
            release=lambda: events.append(("release", "Gone")),
        )

    view = SimpleNamespace(
        active_cube_stack=_Stack(),
        active_editor_panel=object(),
        cube_stack_presentation_controller=SimpleNamespace(
            acquire_expansion=acquire_expansion,
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_edit_requested("Gone")

    assert events == [
        ("acquire", "Gone"),
        ("begin_edit", "Gone"),
        ("release", "Gone"),
    ]


def test_cube_rename_request_uses_service_resolution_to_update_ui_and_editor() -> None:
    """Rename requests should apply the service-resolved alias back into the shell state."""

    mod = _import_stack_module()
    service_calls: list[tuple[str, object]] = []
    workflow = SimpleNamespace(cubes={"Old": object()}, stack_order=["Old"])
    tab_item = SimpleNamespace(
        _route_key="Old",
        text="Old",
        tooltip="Old",
        secondary_text="v1.0.0 · base-cubes",
        routeKey=lambda: tab_item._route_key,
        setRouteKey=lambda key: setattr(tab_item, "_route_key", key),
        setText=lambda text: setattr(tab_item, "text", text),
        setToolTip=lambda text: setattr(tab_item, "tooltip", text),
    )
    active_panel = SimpleNamespace(
        rename_cube=lambda old_key, new_key: service_calls.append(
            (
                "panel_rename",
                (old_key, new_key),
            )
        ),
        scroll_to_cube=lambda alias, animated=False: service_calls.append(
            (
                "panel_scroll",
                (alias, animated),
            )
        ),
    )
    active_stack = SimpleNamespace(
        itemMap={"Old": tab_item},
        count=lambda: 1,
        tabItem=lambda _index: tab_item,
        removeTab=lambda index: service_calls.append(("remove_tab", index)),
    )
    view = SimpleNamespace(
        active_editor_panel=active_panel,
        active_cube_stack=active_stack,
        cube_stack_service=SimpleNamespace(
            apply_cube_rename=lambda workflow_state, old_alias, new_alias: (
                service_calls.append(
                    ("rename", (old_alias, new_alias, workflow_state))
                ),
                SimpleNamespace(resolved_alias="New 2"),
            )[1],
            apply_reordered_aliases=lambda workflow_state, new_order: (
                service_calls.append(("reorder", (new_order, workflow_state)))
            ),
            apply_cube_removal=lambda workflow_state, alias_name: service_calls.append(
                (
                    "remove",
                    (alias_name, workflow_state),
                )
            ),
        ),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: service_calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_rename_requested(
        "Old", "New", timer=SimpleNamespace(singleShot=lambda _ms, fn: fn())
    )

    assert ("rename", ("Old", "New", workflow)) in service_calls
    assert ("panel_rename", ("Old", "New 2")) in service_calls
    assert ("panel_scroll", ("New 2", True)) in service_calls
    assert active_stack.itemMap == {"New 2": tab_item}
    assert tab_item.routeKey() == "New 2"
    assert tab_item.text == "New 2"
    assert tab_item.tooltip == "New 2"
    assert tab_item.secondary_text == "v1.0.0 · base-cubes"


def test_cube_stack_reorder_and_remove_delegate_to_service_apply_methods() -> None:
    """Reorder and remove flows should call the synchronized stack service helpers once."""

    mod = _import_stack_module()
    service_calls: list[tuple[str, object]] = []
    workflow = SimpleNamespace(cubes={"New": object()}, stack_order=["New"])
    active_stack = SimpleNamespace(
        count=lambda: 1,
        tabItem=lambda _index: SimpleNamespace(routeKey=lambda: "New"),
        removeTab=lambda index: service_calls.append(("remove_tab", index)),
    )
    view = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            remove_cube=lambda alias: service_calls.append(("panel_remove", alias))
        ),
        active_cube_stack=active_stack,
        cube_stack_service=SimpleNamespace(
            apply_reordered_aliases=lambda workflow_state, new_order: (
                service_calls.append(("reorder", (new_order, workflow_state)))
            ),
            apply_cube_removal=lambda workflow_state, alias_name: service_calls.append(
                (
                    "remove",
                    (alias_name, workflow_state),
                )
            ),
        ),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: service_calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_move_finished()
    actions.on_cube_close_requested(0)

    assert ("reorder", (["New"], workflow)) in service_calls
    assert ("remove", ("New", workflow)) in service_calls
    assert ("panel_remove", "New") in service_calls


def test_cube_bypass_toggle_updates_state_and_refreshes_active_surfaces() -> None:
    """Bypass toggle should go through service and refresh stack/editor presentation."""

    mod = _import_stack_module()
    stack = _CubeStack()
    stack.insertTab(0, routeKey="Active")
    stack.insertTab(1, routeKey="Muted")
    workflow = SimpleNamespace(
        cubes={
            "Active": SimpleNamespace(bypassed=False),
            "Muted": SimpleNamespace(bypassed=False),
        },
        stack_order=["Active", "Muted"],
    )
    calls: list[tuple[str, object]] = []

    class _InvalidationService:
        """Record workflow surface invalidation calls."""

        def mark_dirty(
            self,
            workflow_id: str,
            surfaces: object,
            reason: object,
        ) -> None:
            """Record one dirty request."""

            calls.append(("dirty", (workflow_id, surfaces, reason)))

    view = SimpleNamespace(
        active_cube_stack=stack,
        active_editor_panel=SimpleNamespace(
            refresh_cube_header=lambda alias: calls.append(("header", alias))
        ),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workflow_surface_invalidation_service=_InvalidationService(),
        cube_stack_service=CubeStackService(),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_bypass_toggle_requested("Muted")

    assert workflow.cubes["Muted"].bypassed is True
    assert stack.bypassed_updates == [(1, True)]
    assert ("header", "Muted") in calls
    assert ("refresh", None) in calls
    dirty_reasons = [
        payload[2]
        for name, payload in calls
        if name == "dirty" and isinstance(payload, tuple)
    ]
    assert mod.WorkflowInvalidationReason.CUBE_BYPASS_CHANGED in dirty_reasons
