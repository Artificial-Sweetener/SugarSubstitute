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

"""Own transient Output preview lanes outside canvas widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

from substitute.application.ports import GenerationVisualIdentity
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_visual_events import (
    LivePreviewEvent,
    OutputSceneIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.domain.workflow import CanvasSessionRevision
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.output_preview_registry")


class OutputPreviewLanePlacement(StrEnum):
    """Identify whether a preview lane is source-level or scene-level."""

    SOURCE = "source"
    SCENE = "scene"


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


@dataclass(frozen=True, slots=True)
class OutputPreviewLaneKey:
    """Identify one transient preview lane using backend and session identity."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    source_key: str
    scene_run_id: str | None
    scene_key: str | None
    placement: OutputPreviewLanePlacement

    @classmethod
    def source(
        cls,
        *,
        workflow_id: str,
        generation_run_id: str,
        prompt_id: str,
        source_key: str,
        scene_run_id: str | None = None,
        scene_key: str | None = None,
    ) -> "OutputPreviewLaneKey":
        """Return a source-level lane key."""

        return cls(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            source_key=source_key,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            placement=OutputPreviewLanePlacement.SOURCE,
        )

    @classmethod
    def scene(
        cls,
        *,
        workflow_id: str,
        generation_run_id: str,
        prompt_id: str,
        source_key: str,
        scene_run_id: str,
        scene_key: str,
    ) -> "OutputPreviewLaneKey":
        """Return a scene-level lane key."""

        return cls(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            source_key=source_key,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            placement=OutputPreviewLanePlacement.SCENE,
        )


@dataclass(frozen=True, slots=True)
class OutputPreviewLane:
    """Store one accepted preview lane bound to an Output session revision."""

    key: OutputPreviewLaneKey
    preview_id: UUID
    image: object
    source_label: str
    client_id: str
    session_revision: CanvasSessionRevision
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None
    accepted_for_overview: bool = False


@dataclass(frozen=True, slots=True)
class OutputPreviewAcceptance:
    """Return the result of accepting or rejecting one preview event."""

    accepted: bool
    lanes: tuple[OutputPreviewLane, ...] = ()
    retired_preview_ids: tuple[UUID, ...] = ()
    rejection_reason: OutputPreviewRejectionReason | None = None

    @classmethod
    def rejected(
        cls,
        reason: OutputPreviewRejectionReason,
        *,
        retired_preview_ids: tuple[UUID, ...] = (),
    ) -> "OutputPreviewAcceptance":
        """Return a rejected preview result."""

        return cls(
            accepted=False,
            retired_preview_ids=retired_preview_ids,
            rejection_reason=reason,
        )


@dataclass(frozen=True, slots=True)
class OutputPreviewCloseResult:
    """Describe preview lanes closed by a matching final output."""

    closed_preview_ids: tuple[UUID, ...]
    completed_keys: tuple[OutputPreviewLaneKey, ...]

    @property
    def closed(self) -> bool:
        """Return whether any preview lane was closed."""

        return bool(self.closed_preview_ids)


@dataclass(slots=True)
class OutputPreviewRegistry:
    """Track transient Output preview lanes independently from widgets."""

    _uuid_factory: Callable[[], UUID] = uuid4
    _lanes: dict[OutputPreviewLaneKey, OutputPreviewLane] = field(default_factory=dict)
    _completed_keys: set[OutputPreviewLaneKey] = field(default_factory=set)

    def accept_preview(
        self,
        event: object,
        *,
        session: OutputCanvasSession,
        active_workflow_id: str,
        authorize_preview: Callable[[GenerationVisualIdentity], bool] | None,
        is_valid_scene_placeholder: Callable[
            [OutputSceneIdentity, GenerationVisualIdentity], bool
        ]
        | None = None,
    ) -> OutputPreviewAcceptance:
        """Accept one strict preview when backend and session authority agree."""

        if not isinstance(event, LivePreviewEvent):
            return OutputPreviewAcceptance.rejected(
                OutputPreviewRejectionReason.STRICT_EVENT_REQUIRED
            )
        identity = event.identity
        if _is_null_image(event.image):
            return OutputPreviewAcceptance.rejected(
                OutputPreviewRejectionReason.EMPTY_IMAGE
            )
        if identity.workflow_id != active_workflow_id:
            return self._reject(
                event,
                OutputPreviewRejectionReason.INACTIVE_WORKFLOW,
            )
        if identity.workflow_id != session.workflow_id.value:
            return self._reject(
                event,
                OutputPreviewRejectionReason.INACTIVE_WORKFLOW,
            )
        visual_identity = _generation_visual_identity(event)
        if not callable(authorize_preview):
            return self._reject(
                event,
                OutputPreviewRejectionReason.AUTHORIZATION_REQUIRED,
            )
        if not authorize_preview(visual_identity):
            return self._reject(
                event,
                OutputPreviewRejectionReason.UNAUTHORIZED_RUN,
            )
        if not _source_is_allowed(identity.source_key, session):
            return self._reject(
                event,
                OutputPreviewRejectionReason.SOURCE_OUTSIDE_SESSION,
            )
        scene = identity.scene
        if isinstance(scene, OutputSceneIdentity) and not _scene_is_allowed(
            scene,
            session,
            event=event,
            visual_identity=visual_identity,
            is_valid_scene_placeholder=is_valid_scene_placeholder,
        ):
            return self._reject(
                event,
                OutputPreviewRejectionReason.SCENE_OUTSIDE_SESSION,
            )

        retired_ids = self.retire_old_sessions(session)
        lanes = self._lanes_for_event(event, session=session)
        completed = [lane.key for lane in lanes if lane.key in self._completed_keys]
        if completed:
            return OutputPreviewAcceptance.rejected(
                OutputPreviewRejectionReason.COMPLETED_LANE,
                retired_preview_ids=retired_ids,
            )
        accepted_lanes = tuple(self._store_lane(lane) for lane in lanes)
        return OutputPreviewAcceptance(
            accepted=True,
            lanes=accepted_lanes,
            retired_preview_ids=retired_ids,
        )

    def close_final_output_lane(
        self,
        identity: OutputPreviewCloseIdentity,
    ) -> OutputPreviewCloseResult:
        """Close only preview lanes matching one final output identity."""

        matching_keys = tuple(
            key
            for key, lane in self._lanes.items()
            if _final_matches_lane(identity, lane)
        )
        closed_ids: list[UUID] = []
        completed_keys: list[OutputPreviewLaneKey] = []
        for key in matching_keys:
            lane = self._lanes.pop(key, None)
            if lane is None:
                continue
            closed_ids.append(lane.preview_id)
            completed_keys.append(key)
            self._completed_keys.add(key)
        return OutputPreviewCloseResult(
            closed_preview_ids=tuple(dict.fromkeys(closed_ids)),
            completed_keys=tuple(completed_keys),
        )

    def clear(self, *, source_key: str | None = None) -> tuple[UUID, ...]:
        """Remove transient preview lanes without changing durable membership."""

        keys = tuple(
            key
            for key in self._lanes
            if source_key is None or key.source_key == source_key
        )
        return self._remove_keys(keys)

    def retire_old_sessions(self, session: OutputCanvasSession) -> tuple[UUID, ...]:
        """Remove lanes from stale session revisions without changing QPane route."""

        keys = tuple(
            key
            for key, lane in self._lanes.items()
            if key.workflow_id == session.workflow_id.value
            and lane.session_revision != session.revision
        )
        return self._remove_keys(keys)

    def lanes_for_session(
        self,
        session: OutputCanvasSession,
    ) -> tuple[OutputPreviewLane, ...]:
        """Return lanes bound to the current session revision."""

        return tuple(
            lane
            for lane in self._lanes.values()
            if lane.key.workflow_id == session.workflow_id.value
            and lane.session_revision == session.revision
        )

    def lanes_for_session_like(self) -> tuple[OutputPreviewLane, ...]:
        """Return all lanes for legacy presentation diagnostics."""

        return tuple(self._lanes.values())

    def lane_for_id(self, preview_id: UUID) -> OutputPreviewLane | None:
        """Return a lane by preview image id."""

        for lane in self._lanes.values():
            if lane.preview_id == preview_id:
                return lane
        return None

    def retire_preview_id(self, preview_id: UUID) -> bool:
        """Remove every transient lane represented by one preview image id."""

        keys = tuple(
            key for key, lane in self._lanes.items() if lane.preview_id == preview_id
        )
        self._remove_keys(keys)
        return bool(keys)

    def image_for_id(self, preview_id: UUID) -> object | None:
        """Return a preview payload by image id."""

        lane = self.lane_for_id(preview_id)
        return None if lane is None else lane.image

    def store_accepted_lane(self, lane: OutputPreviewLane) -> None:
        """Store an already session-authorized preview lane."""

        self._lanes[lane.key] = lane

    def images_by_id(self) -> dict[UUID, object]:
        """Return a diagnostic snapshot of preview payloads by UUID."""

        return {lane.preview_id: lane.image for lane in self._lanes.values()}

    def source_preview_ids(self) -> dict[str, UUID]:
        """Return source-level preview ids for current diagnostics and tests."""

        return {
            lane.key.source_key: lane.preview_id
            for lane in self._lanes.values()
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
        }

    def scene_preview_lanes(self) -> dict[str, OutputPreviewLane]:
        """Return accepted scene-overview representative lanes by scene key."""

        return {
            lane.key.scene_key: lane
            for lane in self._lanes.values()
            if lane.key.placement is OutputPreviewLanePlacement.SCENE
            and lane.key.scene_key is not None
            and lane.accepted_for_overview
        }

    def preview_scene_groups(
        self,
        session: OutputCanvasSession | None = None,
    ) -> dict[str, OutputCanvasSceneGroup]:
        """Return preview-only scene groups derived from accepted lanes."""

        groups: dict[str, OutputCanvasSceneGroup] = {}
        lanes = (
            self.lanes_for_session(session)
            if session is not None
            else tuple(self._lanes.values())
        )
        for lane in lanes:
            if lane.key.placement is not OutputPreviewLanePlacement.SCENE:
                continue
            if lane.key.scene_run_id is None or lane.key.scene_key is None:
                continue
            groups[lane.key.scene_key] = OutputCanvasSceneGroup(
                scene_run_id=lane.key.scene_run_id,
                scene_key=lane.key.scene_key,
                title=lane.scene_title or lane.key.scene_key,
                order=lane.scene_order if lane.scene_order is not None else 0,
                sources=(),
                preview_image_id=lane.preview_id,
                primary_image_id=None,
                representative_source_key=lane.key.source_key,
                representative_set_index=None,
                status="running",
            )
        return groups

    def _lanes_for_event(
        self,
        event: LivePreviewEvent,
        *,
        session: OutputCanvasSession,
    ) -> tuple[OutputPreviewLane, ...]:
        """Build the source-level or scene-level lanes for one preview event."""

        identity = event.identity
        scene = identity.scene
        if isinstance(scene, SourceOnlyOutputIdentity):
            return (
                OutputPreviewLane(
                    key=OutputPreviewLaneKey.source(
                        workflow_id=identity.workflow_id,
                        generation_run_id=identity.generation_run_id,
                        prompt_id=identity.prompt_id,
                        source_key=identity.source_key,
                    ),
                    preview_id=self._preview_id_for_key(
                        OutputPreviewLaneKey.source(
                            workflow_id=identity.workflow_id,
                            generation_run_id=identity.generation_run_id,
                            prompt_id=identity.prompt_id,
                            source_key=identity.source_key,
                        )
                    ),
                    image=event.image,
                    source_label=identity.source_label,
                    client_id=identity.client_id,
                    session_revision=session.revision,
                ),
            )
        scene_key = OutputPreviewLaneKey.scene(
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
            source_key=identity.source_key,
            scene_run_id=scene.run_id,
            scene_key=scene.key,
        )
        source_key = OutputPreviewLaneKey.source(
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
            source_key=identity.source_key,
            scene_run_id=scene.run_id,
            scene_key=scene.key,
        )
        lanes = [
            OutputPreviewLane(
                key=scene_key,
                preview_id=self._preview_id_for_key(scene_key),
                image=event.image,
                source_label=identity.source_label,
                client_id=identity.client_id,
                session_revision=session.revision,
                scene_title=scene.title,
                scene_order=scene.order,
                scene_count=scene.count,
                accepted_for_overview=True,
            )
        ]
        if _preview_can_update_source_view(session.projection, scene.key):
            lanes.append(
                OutputPreviewLane(
                    key=source_key,
                    preview_id=self._preview_id_for_key(source_key),
                    image=event.image,
                    source_label=identity.source_label,
                    client_id=identity.client_id,
                    session_revision=session.revision,
                    scene_title=scene.title,
                    scene_order=scene.order,
                    scene_count=scene.count,
                )
            )
        return tuple(lanes)

    def _store_lane(self, lane: OutputPreviewLane) -> OutputPreviewLane:
        """Store a lane and return the accepted value."""

        self._lanes[lane.key] = lane
        return lane

    def _preview_id_for_key(self, key: OutputPreviewLaneKey) -> UUID:
        """Return a stable UUID for a preview lane key."""

        current = self._lanes.get(key)
        if current is not None:
            return current.preview_id
        return self._uuid_factory()

    def _remove_keys(self, keys: tuple[OutputPreviewLaneKey, ...]) -> tuple[UUID, ...]:
        """Remove keyed lanes and return unique preview ids to evict."""

        removed_ids: list[UUID] = []
        for key in keys:
            lane = self._lanes.pop(key, None)
            if lane is not None:
                removed_ids.append(lane.preview_id)
        return tuple(dict.fromkeys(removed_ids))

    def _reject(
        self,
        event: LivePreviewEvent,
        reason: OutputPreviewRejectionReason,
    ) -> OutputPreviewAcceptance:
        """Log and return one rejected preview event."""

        log_warning(
            _LOGGER,
            "Rejected Output preview",
            workflow_id=event.identity.workflow_id,
            generation_run_id=event.identity.generation_run_id,
            prompt_id=event.identity.prompt_id,
            client_id=event.identity.client_id,
            source_key=event.identity.source_key,
            reason=reason.value,
        )
        return OutputPreviewAcceptance.rejected(reason)


def _generation_visual_identity(event: LivePreviewEvent) -> GenerationVisualIdentity:
    """Return generation authorization identity for one strict preview."""

    scene = event.identity.scene
    if isinstance(scene, OutputSceneIdentity):
        return GenerationVisualIdentity(
            workflow_id=event.identity.workflow_id,
            generation_run_id=event.identity.generation_run_id,
            prompt_id=event.identity.prompt_id,
            client_id=event.identity.client_id,
            source_key=event.identity.source_key,
            source_label=event.identity.source_label,
            scene_run_id=scene.run_id,
            scene_key=scene.key,
            scene_title=scene.title,
            scene_order=scene.order,
            scene_count=scene.count,
            node_id=event.node_identity.resolved_node_id,
            display_node_id=event.node_identity.display_node_id,
        )
    return GenerationVisualIdentity(
        workflow_id=event.identity.workflow_id,
        generation_run_id=event.identity.generation_run_id,
        prompt_id=event.identity.prompt_id,
        client_id=event.identity.client_id,
        source_key=event.identity.source_key,
        source_label=event.identity.source_label,
        node_id=event.node_identity.resolved_node_id,
        display_node_id=event.node_identity.display_node_id,
    )


def _source_is_allowed(source_key: str, session: OutputCanvasSession) -> bool:
    """Return whether the active session can accept the preview source."""

    return source_key in session.allowed_source_keys


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


def _preview_can_update_source_view(
    projection: OutputCanvasProjection,
    scene_key: str,
) -> bool:
    """Return whether a scene preview may also update source-level display."""

    if projection.scene_count <= 1:
        return True
    if projection.active_scene_overview:
        return False
    return projection.active_scene_key == scene_key


def _final_matches_lane(
    identity: OutputPreviewCloseIdentity,
    lane: OutputPreviewLane,
) -> bool:
    """Return whether one final output supersedes one preview lane."""

    key = lane.key
    if key.workflow_id != identity.workflow_id:
        return False
    if key.generation_run_id and key.generation_run_id != identity.generation_run_id:
        return False
    if key.prompt_id and key.prompt_id != identity.prompt_id:
        return False
    if lane.client_id and lane.client_id != identity.client_id:
        return False
    if key.scene_run_id != (identity.scene_run_id or None):
        return False
    if key.scene_key != (identity.scene_key or None):
        return False
    return key.source_key == identity.source_key


def _is_null_image(image: object) -> bool:
    """Return whether a preview image is absent or explicitly null."""

    is_null = getattr(image, "isNull", None)
    return image is None or (callable(is_null) and bool(is_null()))


__all__ = [
    "OutputPreviewAcceptance",
    "OutputPreviewCloseResult",
    "OutputPreviewLane",
    "OutputPreviewLaneKey",
    "OutputPreviewLanePlacement",
    "OutputPreviewRegistry",
    "OutputPreviewRejectionReason",
]
