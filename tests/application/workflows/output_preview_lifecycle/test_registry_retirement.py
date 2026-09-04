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

"""Verify Output preview lane retirement and nondurable ownership."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.domain.workflow import (
    CanvasSessionRevision,
    WorkflowState,
)


from tests.application.workflows.output_preview_lifecycle.registry_support import (
    build_close_identity,
    build_preview_event,
    build_registry_session,
    uuid_sequence,
)


def test_registry_closes_only_matching_final_output_preview_lanes() -> None:
    """Final output identity should close only lanes with the same run/source/scene."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=("wf:save", "wf:other"))
    save = build_preview_event(source_key="wf:save")
    other = build_preview_event(source_key="wf:other")
    for event in (save, other):
        registry.accept_preview(
            event,
            session=session,
            active_workflow_id="wf",
            authorize_preview=lambda _identity: True,
        )

    close = registry.close_final_output_lane(
        build_close_identity(source_key="wf:save", image_id=UUID(int=99))
    )

    assert close.closed_preview_ids == (UUID(int=1),)
    assert tuple(registry.images_by_id()) == (UUID(int=2),)


def test_registry_keeps_preview_until_first_tensor_batch_member_finishes() -> None:
    """A later batch member must not retire the preview occupying batch slot zero."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=("wf:save",))
    registry.accept_preview(
        build_preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )

    later_member = registry.close_final_output_lane(
        build_close_identity(
            source_key="wf:save",
            image_id=UUID(int=98),
            batch_index=1,
        )
    )

    assert later_member.closed_preview_ids == ()
    assert tuple(registry.images_by_id()) == (UUID(int=1),)

    first_member = registry.close_final_output_lane(
        build_close_identity(
            source_key="wf:save",
            image_id=UUID(int=99),
            batch_index=0,
        )
    )

    assert first_member.closed_preview_ids == (UUID(int=1),)
    assert registry.images_by_id() == {}


def test_registry_retires_every_lane_for_preview_id() -> None:
    """Preview-id retirement should remove all lanes represented by that image."""

    registry = OutputPreviewRegistry()
    shared_preview_id = UUID(int=42)
    scene_lane = OutputPreviewLane(
        key=OutputPreviewLaneKey.scene(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            source_key="wf:save",
            scene_run_id="scene-run",
            scene_key="portrait",
        ),
        preview_id=shared_preview_id,
        image=object(),
        source_label="Save",
        client_id="client",
        session_revision=CanvasSessionRevision(1),
        accepted_for_overview=True,
    )
    source_lane = OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            source_key="wf:save",
            scene_run_id="scene-run",
            scene_key="portrait",
        ),
        preview_id=shared_preview_id,
        image=object(),
        source_label="Save",
        client_id="client",
        session_revision=CanvasSessionRevision(1),
    )
    remaining_lane = OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            source_key="wf:other",
        ),
        preview_id=UUID(int=99),
        image=object(),
        source_label="Other",
        client_id="client",
        session_revision=CanvasSessionRevision(1),
    )
    registry.store_accepted_lane(scene_lane)
    registry.store_accepted_lane(source_lane)
    registry.store_accepted_lane(remaining_lane)

    assert registry.retire_preview_id(shared_preview_id) is True

    assert registry.lane_for_id(shared_preview_id) is None
    assert registry.images_by_id() == {UUID(int=99): remaining_lane.image}
    assert registry.retire_preview_id(shared_preview_id) is False


def test_registry_final_close_requires_exact_source_key_with_duplicate_labels() -> None:
    """Final output closure must not use display labels as source authority."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=("wf:save-a", "wf:save-b"))
    for source_key in ("wf:save-a", "wf:save-b"):
        registry.accept_preview(
            build_preview_event(source_key=source_key, source_label="Duplicate"),
            session=session,
            active_workflow_id="wf",
            authorize_preview=lambda _identity: True,
        )

    close = registry.close_final_output_lane(
        build_close_identity(
            source_key="wf:save-b",
            image_id=UUID(int=99),
            source_label="Duplicate",
        )
    )

    assert close.closed_preview_ids == (UUID(int=2),)
    assert tuple(registry.images_by_id()) == (UUID(int=1),)


def test_registry_preview_state_does_not_create_durable_output_membership() -> None:
    """Preview lanes should not mutate workflow final-output UUID membership."""

    registry = OutputPreviewRegistry()
    workflow = WorkflowState()
    session = build_registry_session(source_keys=("wf:save",))

    registry.accept_preview(
        build_preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )

    assert workflow.output_image_uuids == []
