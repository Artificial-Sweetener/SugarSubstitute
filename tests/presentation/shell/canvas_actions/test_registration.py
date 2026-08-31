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

"""Test workspace output registration actions."""

from __future__ import annotations

import uuid
from types import SimpleNamespace


from substitute.application.workflows.output_preview_results import (
    OutputPreviewAcceptance,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
    OutputPreviewCloseIdentity,
    OutputProjectionSchedulingIntent,
)


from tests.presentation.shell.canvas_actions.support import (
    _import_module,
    _record_and_return,
    _registration_result,
)


def test_handle_add_output_image_registers_without_direct_output_route_mutation() -> (
    None
):
    """Final outputs should register state without directly mutating Output routes."""

    mod = _import_module()
    added: list[tuple[object, ...]] = []
    closed_preview_lanes: list[OutputPreviewCloseIdentity] = []
    preview_acceptances: list[OutputPreviewAcceptance] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    unread_tabs: list[tuple[str, bool]] = []
    recorded_activity: list[tuple[str, str]] = []
    first_image_id = uuid.uuid4()
    second_image_id = uuid.uuid4()
    preview_identity = OutputPreviewCloseIdentity(
        workflow_id="wf-a",
        image_id=first_image_id,
        source_key="wf-a:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        node_id="save",
        list_index=0,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )

    def register_output(
        _workflows: object,
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        image_id = first_image_id if workflow_id == "wf-a" else second_image_id
        added.append(("register", workflow_id, active_workflow_id, image, image_meta))
        return _registration_result(
            workflow_id=workflow_id,
            image_id=image_id,
            should_schedule=workflow_id == active_workflow_id,
            preview_close_identity=preview_identity
            if workflow_id == active_workflow_id
            else None,
        )

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=register_output,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda identity: _record_and_return(
                closed_preview_lanes,
                identity,
                SimpleNamespace(closed=True, closed_preview_ids=(uuid.uuid4(),)),
            )
        ),
        canvas_host=SimpleNamespace(
            canvas_for={
                "Output": SimpleNamespace(
                    apply_preview_acceptance=preview_acceptances.append
                )
            }.get,
            focus_attached_canvas=lambda _label: (_ for _ in ()).throw(
                AssertionError("registration must not focus Output")
            ),
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda workflow_id, active_workflow_id: _record_and_return(
                recorded_activity,
                (workflow_id, active_workflow_id),
                workflow_id != active_workflow_id,
            )
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda workflow_id, unread: unread_tabs.append(
                (workflow_id, unread)
            )
        ),
    )

    actions = mod.WorkspaceCanvasActions(view)
    actions.handle_add_output_image("wf-a", "image-a", "meta-a")
    actions.handle_add_output_image("wf-b", "image-b", "meta-b")

    assert [entry[0] for entry in added] == ["register", "register"]
    assert closed_preview_lanes == [preview_identity]
    assert len(preview_acceptances) == 1
    assert preview_acceptances[0].retired_preview_ids
    assert len(scheduled_projection) == 1
    assert scheduled_projection[0].workflow_id == "wf-a"
    assert scheduled_projection[0].registered_image_id == first_image_id
    assert recorded_activity == [("wf-a", "wf-a"), ("wf-b", "wf-a")]
    assert unread_tabs == [("wf-b", True)]


def test_handle_loaded_output_image_schedules_without_generated_output_side_effects() -> (
    None
):
    """Loaded recipe outputs should not trigger generated-output maintenance."""

    mod = _import_module()
    added: list[tuple[object, ...]] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    image_id = uuid.uuid4()

    def register_output(
        _workflows: object,
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        added.append(("register", workflow_id, active_workflow_id, image, image_meta))
        return _registration_result(
            workflow_id=workflow_id,
            image_id=image_id,
            should_schedule=workflow_id == active_workflow_id,
        )

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=register_output,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda _identity: (_ for _ in ()).throw(
                AssertionError("loaded output must not close preview lanes")
            )
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: (_ for _ in ()).throw(
                AssertionError("loaded output must not record generated activity")
            )
        ),
        workflow_surface_invalidation_service=SimpleNamespace(
            mark_dirty=lambda *_args: (_ for _ in ()).throw(
                AssertionError("loaded output must not dirty generation surfaces")
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).handle_loaded_output_image(
        "wf-a",
        "image-a",
        "meta-a",
    )

    assert added == [("register", "wf-a", "wf-a", "image-a", "meta-a")]
    assert len(scheduled_projection) == 1
    assert scheduled_projection[0].workflow_id == "wf-a"
    assert scheduled_projection[0].registered_image_id == image_id


def test_handle_add_output_image_leaves_inactive_preview_lane_visible() -> None:
    """Inactive final output registration should not close visible preview lanes."""

    mod = _import_module()
    image_id = uuid.uuid4()
    close_identity = OutputPreviewCloseIdentity(
        workflow_id="wf-b",
        image_id=image_id,
        source_key="wf-b:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        node_id="save",
        list_index=0,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )
    closed_preview_lanes: list[OutputPreviewCloseIdentity] = []
    preview_acceptances: list[OutputPreviewAcceptance] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object(), "wf-b": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *_args: _registration_result(
                workflow_id="wf-b",
                image_id=image_id,
                should_schedule=False,
                preview_close_identity=close_identity,
            )
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda identity: _record_and_return(
                closed_preview_lanes,
                identity,
                SimpleNamespace(closed=True, closed_preview_ids=(uuid.uuid4(),)),
            )
        ),
        canvas_host=SimpleNamespace(
            canvas_for={
                "Output": SimpleNamespace(
                    apply_preview_acceptance=preview_acceptances.append
                )
            }.get
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: False,
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
    )

    mod.WorkspaceCanvasActions(view).handle_add_output_image("wf-b", "image", "meta")

    assert closed_preview_lanes == [close_identity]
    assert preview_acceptances == []
    assert scheduled_projection == []
