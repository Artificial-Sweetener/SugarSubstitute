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

"""Contract tests for session-gated Output preview registry ownership."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from substitute.application.ports import PreviewImageUpdate
from substitute.application.generation import VisualAuthorizationService
from substitute.application.workflows import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSession,
    OutputCanvasSourceGroup,
    OutputPreviewCloseIdentity,
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewLanePlacement,
    OutputPreviewRegistry,
    OutputPreviewRejectionReason,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    CanvasSessionRevision,
    WorkflowState,
)


def test_registry_accepts_only_strict_preview_event_for_current_session() -> None:
    """Accepted previews should be keyed by backend run identity and session revision."""

    registry = OutputPreviewRegistry(_uuid_factory=_uuid_sequence())
    session = _session(source_keys=("wf:save",))
    event = _preview_event(source_key="wf:save")

    result = registry.accept_preview(
        event,
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )

    assert result.accepted is True
    assert len(result.lanes) == 1
    lane = result.lanes[0]
    assert lane.preview_id == UUID(int=1)
    assert lane.session_revision == session.revision
    assert lane.key.workflow_id == "wf"
    assert lane.key.generation_run_id == "run"
    assert lane.key.prompt_id == "prompt"
    assert lane.key.source_key == "wf:save"
    assert lane.key.scene_run_id is None
    assert lane.key.scene_key is None
    assert lane.key.placement is OutputPreviewLanePlacement.SOURCE

    loose_update = registry.accept_preview(
        PreviewImageUpdate(
            workflow_id="wf",
            image=object(),
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            node_id="preview-node",
            source_key="wf:save",
            source_label="wf:save",
        ),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    assert (
        loose_update.rejection_reason
        is OutputPreviewRejectionReason.STRICT_EVENT_REQUIRED
    )


def test_registry_rejects_inactive_unauthorized_and_foreign_source_previews() -> None:
    """Preview display should fail closed before QPane sees inactive or stale lanes."""

    registry = OutputPreviewRegistry()
    session = _session(source_keys=("wf:save",))

    inactive = registry.accept_preview(
        _preview_event(workflow_id="other", source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    unauthorized = registry.accept_preview(
        _preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: False,
    )
    foreign_source = registry.accept_preview(
        _preview_event(source_key="wf:other"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    missing_authorization = registry.accept_preview(
        _preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=None,
    )

    assert inactive.rejection_reason is OutputPreviewRejectionReason.INACTIVE_WORKFLOW
    assert (
        unauthorized.rejection_reason is OutputPreviewRejectionReason.UNAUTHORIZED_RUN
    )
    assert (
        foreign_source.rejection_reason
        is OutputPreviewRejectionReason.SOURCE_OUTSIDE_SESSION
    )
    assert (
        missing_authorization.rejection_reason
        is OutputPreviewRejectionReason.AUTHORIZATION_REQUIRED
    )
    assert registry.images_by_id() == {}


def test_registry_rejects_stale_prompt_or_client_identity() -> None:
    """Preview authorization should reject stale prompt/client identities."""

    registry = OutputPreviewRegistry()
    session = _session(source_keys=("wf:save",))
    authorization = VisualAuthorizationService()
    authorization.register_run(
        workflow_id="wf",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
    )

    stale_prompt = registry.accept_preview(
        _preview_event(source_key="wf:save", prompt_id="old-prompt"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=authorization.authorize_preview,
    )
    stale_client = registry.accept_preview(
        _preview_event(source_key="wf:save", client_id="old-client"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=authorization.authorize_preview,
    )

    assert (
        stale_prompt.rejection_reason is OutputPreviewRejectionReason.UNAUTHORIZED_RUN
    )
    assert (
        stale_client.rejection_reason is OutputPreviewRejectionReason.UNAUTHORIZED_RUN
    )
    assert registry.images_by_id() == {}


def test_registry_retires_old_session_previews_without_accepting_route_mutation() -> (
    None
):
    """A new session revision should retire previous lanes and report cache ids only."""

    registry = OutputPreviewRegistry(_uuid_factory=_uuid_sequence())
    boundary = CanvasSessionBoundary()
    first_session = _session(source_keys=("wf:save",), boundary=boundary)
    second_session = _session(source_keys=("wf:save",), boundary=boundary)
    event = _preview_event(source_key="wf:save")

    first = registry.accept_preview(
        event,
        session=first_session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    second = registry.accept_preview(
        event,
        session=second_session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )

    assert first.accepted is True
    assert second.accepted is True
    assert second.retired_preview_ids == (UUID(int=1),)
    assert second.lanes[0].preview_id == UUID(int=2)
    assert tuple(registry.images_by_id()) == (UUID(int=2),)


def test_registry_accepts_in_progress_scene_placeholder_for_same_workflow_run() -> None:
    """Scene previews may introduce running scene placeholders for the active run."""

    registry = OutputPreviewRegistry(_uuid_factory=_uuid_sequence())
    session = _session(source_keys=("wf:save",), scene_keys=())
    event = _preview_event(
        source_key="wf:save",
        scene_run_id="scene-run",
        scene_key="scene-a",
        scene_title="Scene A",
        scene_order=0,
        scene_count=2,
    )

    result = registry.accept_preview(
        event,
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
        is_valid_scene_placeholder=lambda scene, identity: (
            scene.run_id == "scene-run"
            and scene.key == "scene-a"
            and identity.generation_run_id == "run"
        ),
    )

    assert result.accepted is True
    assert result.lanes[0].key.placement is OutputPreviewLanePlacement.SCENE
    assert result.lanes[0].key.scene_key == "scene-a"
    assert registry.preview_scene_groups(session)["scene-a"].status == "running"


def test_registry_rejects_invalid_in_progress_scene_placeholder() -> None:
    """Unknown scene placeholders should fail closed outside session scene keys."""

    registry = OutputPreviewRegistry()
    session = _session(source_keys=("wf:save",), scene_keys=())

    result = registry.accept_preview(
        _preview_event(
            source_key="wf:save",
            scene_run_id="scene-run",
            scene_key="unexpected-scene",
            scene_title="Unexpected",
            scene_order=1,
            scene_count=2,
        ),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
        is_valid_scene_placeholder=lambda _scene, _identity: False,
    )

    assert result.rejection_reason is OutputPreviewRejectionReason.SCENE_OUTSIDE_SESSION
    assert registry.images_by_id() == {}


def test_registry_closes_only_matching_final_output_preview_lanes() -> None:
    """Final output identity should close only lanes with the same run/source/scene."""

    registry = OutputPreviewRegistry(_uuid_factory=_uuid_sequence())
    session = _session(source_keys=("wf:save", "wf:other"))
    save = _preview_event(source_key="wf:save")
    other = _preview_event(source_key="wf:other")
    for event in (save, other):
        registry.accept_preview(
            event,
            session=session,
            active_workflow_id="wf",
            authorize_preview=lambda _identity: True,
        )

    close = registry.close_final_output_lane(
        _close_identity(source_key="wf:save", image_id=UUID(int=99))
    )

    assert close.closed_preview_ids == (UUID(int=1),)
    assert tuple(registry.images_by_id()) == (UUID(int=2),)


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

    registry = OutputPreviewRegistry(_uuid_factory=_uuid_sequence())
    session = _session(source_keys=("wf:save-a", "wf:save-b"))
    for source_key in ("wf:save-a", "wf:save-b"):
        registry.accept_preview(
            _preview_event(source_key=source_key, source_label="Duplicate"),
            session=session,
            active_workflow_id="wf",
            authorize_preview=lambda _identity: True,
        )

    close = registry.close_final_output_lane(
        _close_identity(
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
    session = _session(source_keys=("wf:save",))

    registry.accept_preview(
        _preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )

    assert workflow.output_image_uuids == []


def _session(
    *,
    source_keys: tuple[str, ...],
    scene_keys: tuple[str, ...] = (),
    boundary: CanvasSessionBoundary | None = None,
) -> OutputCanvasSession:
    """Build an Output canvas session with the requested source/scene authority."""

    projection = OutputCanvasProjection(
        sources=tuple(
            OutputCanvasSourceGroup(
                source_key=source_key,
                label=source_key,
                images_by_set={},
            )
            for source_key in source_keys
        ),
        active_source_key=source_keys[0] if source_keys else None,
        active_set_index=0 if source_keys else 1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(
            OutputCanvasSceneGroup(
                scene_run_id="scene-run",
                scene_key=scene_key,
                title=scene_key,
                order=0,
                sources=(),
            )
            for scene_key in scene_keys
        ),
        active_scene_key=scene_keys[0] if scene_keys else None,
        active_scene_overview=False,
        scene_count=len(scene_keys),
    )
    return bind_output_canvas_session(
        boundary or CanvasSessionBoundary(),
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={},
    )


def _preview_event(
    *,
    workflow_id: str = "wf",
    source_key: str,
    source_label: str | None = None,
    generation_run_id: str = "run",
    prompt_id: str = "prompt",
    client_id: str = "client",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> LivePreviewEvent:
    """Build a strict preview event for registry tests."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id=workflow_id,
            image=object(),
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
            node_id="preview-node",
            source_key=source_key,
            source_label=source_label or source_key,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
        )
    )
    assert event is not None
    return event


def _close_identity(
    *,
    source_key: str,
    image_id: UUID,
    source_label: str | None = None,
) -> OutputPreviewCloseIdentity:
    """Build final-output preview close identity for registry tests."""

    return OutputPreviewCloseIdentity(
        workflow_id="wf",
        image_id=image_id,
        source_key=source_key,
        source_label=source_label or source_key,
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        node_id="save",
        list_index=0,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )


def _uuid_sequence() -> Callable[[], UUID]:
    """Return a UUID factory that starts at one and increments."""

    next_value = 0

    def factory() -> UUID:
        nonlocal next_value
        next_value += 1
        return UUID(int=next_value)

    return factory
