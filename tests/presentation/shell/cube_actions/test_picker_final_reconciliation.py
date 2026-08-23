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

"""Cube-picker final draft-order reconciliation contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.cubes import (
    CubeStackDraft,
    CubeStackService,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _EmptyNodeBehaviorService,
    _finish_queued_load,
    _import_module,
    _surface_refresher,
)


def test_show_cube_picker_reconciles_batch_after_restoring_final_draft_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch completion should reconcile links after restoring the accepted order."""

    mod = _import_module()
    events: list[tuple[str, object]] = []

    def begin_busy(workflow_id: str, *, message: str = "Loading") -> str:
        """Record busy-state acquisition and return its token."""
        events.append(("begin_busy", (workflow_id, message)))
        return "busy-token"

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
            begin=begin_busy,
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
