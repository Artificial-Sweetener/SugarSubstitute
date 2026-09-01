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

"""Verify session-gated Output preview admission."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from substitute.application.ports import PreviewImageUpdate
from substitute.application.generation import VisualAuthorizationService
from substitute.application.workflows import (
    OutputPreviewLanePlacement,
    OutputPreviewRegistry,
    OutputPreviewRejectionReason,
)
from substitute.domain.workflow import (
    CanvasGenerationIdentity,
    CanvasSessionBoundary,
)


from tests.application.workflows.output_preview_lifecycle.registry_support import (
    build_preview_event,
    build_registry_session,
    uuid_sequence,
)


def test_registry_accepts_only_strict_preview_event_for_current_session() -> None:
    """Accepted previews should be keyed by backend run identity and session revision."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=("wf:save",))
    event = build_preview_event(source_key="wf:save")

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
    session = build_registry_session(source_keys=("wf:save",))

    inactive = registry.accept_preview(
        build_preview_event(workflow_id="other", source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    unauthorized = registry.accept_preview(
        build_preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: False,
    )
    foreign_source = registry.accept_preview(
        build_preview_event(source_key="wf:other"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
    )
    missing_authorization = registry.accept_preview(
        build_preview_event(source_key="wf:save"),
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
    session = build_registry_session(source_keys=("wf:save",))
    authorization = VisualAuthorizationService()
    authorization.register_run(
        workflow_id="wf",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
    )

    stale_prompt = registry.accept_preview(
        build_preview_event(source_key="wf:save", prompt_id="old-prompt"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=authorization.authorize_preview,
    )
    stale_client = registry.accept_preview(
        build_preview_event(source_key="wf:save", client_id="old-client"),
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


def test_registry_accepts_expected_source_before_first_final_output() -> None:
    """An active run may preview an expected source before session projection exists."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=())
    authorization = VisualAuthorizationService()
    authorization.register_run(
        workflow_id="wf",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        preview_source_keys=frozenset({"wf:save"}),
    )

    result = registry.accept_preview(
        build_preview_event(source_key="wf:save"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=authorization.authorize_preview,
        is_valid_source_placeholder=authorization.authorize_preview_source,
    )

    assert result.accepted is True
    assert result.lanes[0].key.source_key == "wf:save"


def test_registry_rejects_unexpected_source_before_first_final_output() -> None:
    """A backend source absent from run metadata must not create a preview lane."""

    registry = OutputPreviewRegistry()
    session = build_registry_session(source_keys=())
    authorization = VisualAuthorizationService()
    authorization.register_run(
        workflow_id="wf",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        preview_source_keys=frozenset({"wf:save"}),
    )

    result = registry.accept_preview(
        build_preview_event(source_key="wf:other"),
        session=session,
        active_workflow_id="wf",
        authorize_preview=authorization.authorize_preview,
        is_valid_source_placeholder=authorization.authorize_preview_source,
    )

    assert (
        result.rejection_reason is OutputPreviewRejectionReason.SOURCE_OUTSIDE_SESSION
    )
    assert registry.images_by_id() == {}


def test_registry_retires_old_session_previews_without_accepting_route_mutation() -> (
    None
):
    """A new session revision should retire previous lanes and report cache ids only."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    boundary = CanvasSessionBoundary()
    first_session = build_registry_session(source_keys=("wf:save",), boundary=boundary)
    second_session = build_registry_session(source_keys=("wf:save",), boundary=boundary)
    event = build_preview_event(source_key="wf:save")

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


def test_registry_rebind_retires_preview_from_superseded_generation() -> None:
    """Do not carry a previous run's preview into a newer final-output session."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    boundary = CanvasSessionBoundary()
    first_session = build_registry_session(source_keys=(), boundary=boundary)
    acceptance = registry.accept_preview(
        build_preview_event(source_key="cube:Text to Image"),
        session=first_session,
        active_workflow_id="wf",
        authorize_preview=lambda _identity: True,
        is_valid_source_placeholder=lambda _identity: True,
    )
    next_session = build_registry_session(
        source_keys=("cube:Text to Image",),
        boundary=boundary,
    )
    next_session = replace(
        next_session,
        session=replace(
            next_session.session,
            generation_identity=CanvasGenerationIdentity(
                generation_run_id="new-run",
                prompt_id="new-prompt",
                client_id="new-client",
            ),
        ),
    )

    retired_ids = registry.rebind_workflow_session(next_session)

    assert acceptance.accepted
    assert retired_ids == (UUID(int=1),)
    assert registry.images_by_id() == {}


def test_registry_accepts_in_progress_scene_placeholder_for_same_workflow_run() -> None:
    """Scene previews may introduce running scene placeholders for the active run."""

    registry = OutputPreviewRegistry(_uuid_factory=uuid_sequence())
    session = build_registry_session(source_keys=("wf:save",), scene_keys=())
    event = build_preview_event(
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
    session = build_registry_session(source_keys=("wf:save",), scene_keys=())

    result = registry.accept_preview(
        build_preview_event(
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
