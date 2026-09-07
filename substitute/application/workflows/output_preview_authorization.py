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

"""Validate live Output previews before they can mutate run-owned state."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from substitute.application.ports import GenerationVisualIdentity
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_visual_events import (
    LivePreviewEvent,
    OutputSceneIdentity,
)


class OutputPreviewRejectionReason(StrEnum):
    """Describe why a live preview cannot update visible Output preview state."""

    STRICT_EVENT_REQUIRED = "strict_event_required"
    EMPTY_IMAGE = "empty_image"
    AUTHORIZATION_REQUIRED = "authorization_required"
    INACTIVE_WORKFLOW = "inactive_workflow"
    UNAUTHORIZED_RUN = "unauthorized_run"
    STALE_PROMPT_CLIENT = "stale_prompt_client"
    SOURCE_OUTSIDE_SESSION = "source_outside_session"
    SCENE_OUTSIDE_SESSION = "scene_outside_session"
    STALE_SESSION_REVISION = "stale_session_revision"
    COMPLETED_LANE = "completed_lane"


def preview_rejection_reason(
    event: object,
    *,
    session: OutputCanvasSession,
    active_workflow_id: str,
    authorize_preview: Callable[[GenerationVisualIdentity], bool] | None,
    is_valid_source_placeholder: Callable[[GenerationVisualIdentity], bool]
    | None = None,
    is_valid_scene_placeholder: Callable[
        [OutputSceneIdentity, GenerationVisualIdentity], bool
    ]
    | None = None,
) -> OutputPreviewRejectionReason | None:
    """Return why a preview cannot enter a canvas session, without mutation."""

    if not isinstance(event, LivePreviewEvent):
        return OutputPreviewRejectionReason.STRICT_EVENT_REQUIRED
    identity = event.identity
    if _is_null_image(event.image):
        return OutputPreviewRejectionReason.EMPTY_IMAGE
    if (
        identity.workflow_id != active_workflow_id
        or identity.workflow_id != session.workflow_id.value
    ):
        return OutputPreviewRejectionReason.INACTIVE_WORKFLOW
    visual_identity = _generation_visual_identity(event)
    if not callable(authorize_preview):
        return OutputPreviewRejectionReason.AUTHORIZATION_REQUIRED
    if not authorize_preview(visual_identity):
        return OutputPreviewRejectionReason.UNAUTHORIZED_RUN
    if identity.source_key not in session.allowed_source_keys and not (
        callable(is_valid_source_placeholder)
        and is_valid_source_placeholder(visual_identity)
    ):
        return OutputPreviewRejectionReason.SOURCE_OUTSIDE_SESSION
    scene = identity.scene
    if isinstance(scene, OutputSceneIdentity) and not _scene_is_allowed(
        scene,
        session,
        event=event,
        visual_identity=visual_identity,
        is_valid_scene_placeholder=is_valid_scene_placeholder,
    ):
        return OutputPreviewRejectionReason.SCENE_OUTSIDE_SESSION
    return None


def preview_can_follow_session(
    *,
    generation_run_id: str,
    prompt_id: str,
    client_id: str,
    output_session_id: str,
    session: OutputCanvasSession,
) -> bool:
    """Return whether a preview remains valid after an Output reprojection."""

    output_session_ids = {
        item.image_meta.output_session_id
        for source in session.projection.sources
        for item in source.images_by_set.values()
        if item.image_meta.output_session_id
    }
    output_session_ids.update(
        item.image_meta.output_session_id
        for scene in session.projection.scene_groups
        for source in scene.sources
        for item in source.images_by_set.values()
        if item.image_meta.output_session_id
    )
    if output_session_id and output_session_ids:
        return output_session_id in output_session_ids
    generation = session.generation_identity
    if generation is None:
        return True
    return (
        generation_run_id == generation.generation_run_id
        and prompt_id == generation.prompt_id
        and client_id == generation.client_id
    )


def _generation_visual_identity(event: LivePreviewEvent) -> GenerationVisualIdentity:
    """Return generation authorization identity for one strict preview."""

    identity = event.identity
    scene = identity.scene
    if isinstance(scene, OutputSceneIdentity):
        return GenerationVisualIdentity(
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
            client_id=identity.client_id,
            source_key=identity.source_key,
            source_label=identity.source_label,
            output_session_id=identity.output_session_id,
            scene_run_id=scene.run_id,
            scene_key=scene.key,
            scene_title=scene.title,
            scene_order=scene.order,
            scene_count=scene.count,
            node_id=event.node_identity.resolved_node_id,
            display_node_id=event.node_identity.display_node_id,
        )
    return GenerationVisualIdentity(
        workflow_id=identity.workflow_id,
        generation_run_id=identity.generation_run_id,
        prompt_id=identity.prompt_id,
        client_id=identity.client_id,
        source_key=identity.source_key,
        source_label=identity.source_label,
        output_session_id=identity.output_session_id,
        node_id=event.node_identity.resolved_node_id,
        display_node_id=event.node_identity.display_node_id,
    )


def _scene_is_allowed(
    scene: OutputSceneIdentity,
    session: OutputCanvasSession,
    *,
    event: LivePreviewEvent,
    visual_identity: GenerationVisualIdentity,
    is_valid_scene_placeholder: Callable[
        [OutputSceneIdentity, GenerationVisualIdentity], bool
    ]
    | None,
) -> bool:
    """Return whether a scene preview belongs to the active session."""

    if scene.key in session.allowed_scene_keys:
        return True
    if (
        scene.count <= 1
        or not scene.run_id
        or not scene.key
        or event.identity.workflow_id != session.workflow_id.value
        or is_valid_scene_placeholder is None
    ):
        return False
    return is_valid_scene_placeholder(scene, visual_identity)


def _is_null_image(image: object) -> bool:
    """Return whether a preview image is absent or explicitly null."""

    is_null = getattr(image, "isNull", None)
    return image is None or (callable(is_null) and bool(is_null()))


__all__ = [
    "OutputPreviewRejectionReason",
    "preview_can_follow_session",
    "preview_rejection_reason",
]
