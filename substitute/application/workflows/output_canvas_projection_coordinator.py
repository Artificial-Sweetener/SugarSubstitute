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

"""Coordinate Output canvas projection without owning durable workflow state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
    build_output_canvas_projection,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareState,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.workflows.output_canvas_projection_coordinator")


class OutputProjectionSessionSink(Protocol):
    """Receive active Output projection sessions for visible presentation sync."""

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Bind one Output projection session to the visible canvas."""

    def clear_previews(self, source_key: str | None = None) -> None:
        """Retire transient preview rendering for the visible Output canvas."""


class OutputProjectionContentSynchronizer(Protocol):
    """Synchronize projected Output image payloads with the presentation document."""

    def synchronize_projection(self, projection: OutputCanvasProjection) -> None:
        """Admit every present payload required by one Output projection."""

    def retire_unreferenced(self, image_ids: tuple[UUID, ...]) -> None:
        """Retire document content after workflow ownership proves it unused."""


@dataclass(frozen=True, slots=True)
class _OutputProjectionSyncSignature:
    """Capture immutable projection state used to skip duplicate view syncs."""

    workflow_id: str
    projection_state: tuple[object, ...]
    payload_identities: tuple[tuple[UUID, int | None], ...]


class OutputCanvasProjectionCoordinator:
    """Project workflow Output state through content, session, and route owners."""

    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        output_canvas_state_service: OutputCanvasStateService,
        output_canvas_focus_service: OutputCanvasFocusService,
        output_navigation_session_service: OutputNavigationSessionService,
        canvas_session_boundary: CanvasRouteSessionBoundaryPort,
        content_synchronizer: OutputProjectionContentSynchronizer,
        projection_sink: OutputProjectionSessionSink | None = None,
    ) -> None:
        """Store named Output owners used during projection."""

        self._image_registry = image_registry
        self._output_canvas_state_service = output_canvas_state_service
        self._output_canvas_focus_service = output_canvas_focus_service
        self._output_navigation_session_service = output_navigation_session_service
        self._canvas_session_boundary = canvas_session_boundary
        self._content_synchronizer = content_synchronizer
        self._projection_sink = projection_sink
        self._projected_workflow_id: str | None = None
        self._last_sync_signature: _OutputProjectionSyncSignature | None = None
        self._last_output_session: OutputCanvasSession | None = None

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        registered_image_id: UUID | None = None,
    ) -> None:
        """Project the active workflow's Output state into an authorized session."""

        _ = registered_image_id
        active_workflow = workflows.get(active_workflow_id)
        log_debug(
            _LOGGER,
            "output canvas project workflow started",
            active_workflow_id=active_workflow_id,
            active_workflow_found=active_workflow is not None,
            workflow_ids=tuple(workflows.keys()),
            output_projection_workflow_id=self._projected_workflow_id,
        )
        if active_workflow is None:
            output_session = self._bind_canvas_session(
                active_workflow_id,
                _empty_projection(),
            )
            self._sync_projection(output_session)
            return

        output_metadata = self._image_registry.metadata_for_ids(
            active_workflow.output_image_uuids
        )
        output_projection = build_output_canvas_projection(
            active_workflow,
            output_metadata,
        )
        self._content_synchronizer.synchronize_projection(output_projection)
        sync_signature = self._projection_sync_signature_for_projection(
            active_workflow_id,
            output_projection,
        )
        if (
            self._projection_sink is not None
            and sync_signature == self._last_sync_signature
            and self._last_output_session is not None
        ):
            log_debug(
                _LOGGER,
                "output canvas skipped unchanged projection session",
                active_workflow_id=active_workflow_id,
                projected_output_workflow_id=self._projected_workflow_id,
            )
            return
        output_session = self._bind_canvas_session(
            active_workflow_id,
            output_projection,
            image_metadata_lookup=output_metadata,
        )
        if active_workflow.output_image_uuids:
            self._output_canvas_focus_service.remember_projected_focus(
                active_workflow,
                output_projection,
            )
        else:
            if active_workflow_id == self._projected_workflow_id:
                self._clear_previews()

        self._sync_projection(output_session)
        log_debug(
            _LOGGER,
            "output canvas project workflow completed",
            active_workflow_id=active_workflow_id,
            projected_output_workflow_id=self._projected_workflow_id,
        )

    def clear_output_for_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
    ) -> None:
        """Clear one workflow's Output aggregate and visible Output route."""

        active_workflow = workflows.get(workflow_id)
        if active_workflow is None:
            return
        self._output_navigation_session_service.reset_workflow(
            workflow_id,
            active_workflow,
        )
        if not active_workflow.output_image_uuids:
            return
        prune_result = self._output_canvas_state_service.clear_output_for_workflow(
            workflows,
            workflow_id,
        )
        self._content_synchronizer.retire_unreferenced(prune_result.removed_image_ids)
        if workflow_id != self._projected_workflow_id:
            log_debug(
                _LOGGER,
                "output canvas skipped visible clear for inactive workflow",
                workflow_id=workflow_id,
                projected_output_workflow_id=self._projected_workflow_id,
            )
            return
        cleared_projection = build_output_canvas_projection(
            active_workflow,
            self._image_registry.metadata_for_ids(active_workflow.output_image_uuids),
        )
        output_session = self._bind_canvas_session(workflow_id, cleared_projection)
        self._clear_previews()
        self._projected_workflow_id = workflow_id
        self._last_sync_signature = None
        self._sync_projection(output_session)

    def retire_replaced_output_images(self, image_ids: tuple[UUID, ...]) -> None:
        """Retire document content released by an atomic result replacement."""

        self._content_synchronizer.retire_unreferenced(image_ids)

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Prune unreferenced Output catalog images after workflow close."""

        self._output_navigation_session_service.discard_workflow(closed_workflow_id)
        output_prune_result = (
            self._output_canvas_state_service.prune_closed_workflow_images(
                closed_workflow_id,
                closed_workflow,
                remaining_workflows,
            )
        )
        self._content_synchronizer.retire_unreferenced(
            output_prune_result.removed_image_ids
        )

    def _bind_canvas_session(
        self,
        workflow_id: str,
        projection: OutputCanvasProjection,
        *,
        image_metadata_lookup: Mapping[UUID, ImageMeta] | None = None,
    ) -> OutputCanvasSession:
        """Bind shared Output session identity for one projection."""

        output_session = bind_output_canvas_session(
            self._canvas_session_boundary,
            workflow_id=workflow_id,
            projection=projection,
            image_metadata_lookup=image_metadata_lookup or {},
        )
        return output_session

    def _sync_projection(self, session: OutputCanvasSession) -> None:
        """Update output selector labels/state when a sink is present."""

        workflow_id = session.workflow_id.value
        if self._projection_sink is None:
            self._projected_workflow_id = workflow_id
            self._last_sync_signature = None
            self._last_output_session = session
            return
        sync_signature = self._projection_sync_signature(session)
        if sync_signature == self._last_sync_signature:
            self._last_output_session = session
            return
        self._clear_previews_for_workflow_projection(workflow_id)
        self._projection_sink.bind_projection_session(session)
        self._last_sync_signature = sync_signature
        self._last_output_session = session

    def _clear_previews_for_workflow_projection(self, workflow_id: str) -> None:
        """Retire visible previews when the shared output canvas changes workflow."""

        if workflow_id == self._projected_workflow_id:
            return
        self._clear_previews()
        self._projected_workflow_id = workflow_id

    def _clear_previews(self) -> None:
        """Clear transient output previews through the Output presentation sink."""

        if self._projection_sink is not None:
            self._projection_sink.clear_previews()

    def _projection_sync_signature(
        self,
        session: OutputCanvasSession,
    ) -> _OutputProjectionSyncSignature:
        """Return immutable projection and payload identity state."""

        return self._projection_sync_signature_for_projection(
            session.workflow_id.value,
            session.projection,
        )

    def _projection_sync_signature_for_projection(
        self,
        workflow_id: str,
        projection: OutputCanvasProjection,
    ) -> _OutputProjectionSyncSignature:
        """Return immutable sync state before or after session binding."""

        projected_image_ids = _projected_image_ids(projection)
        return _OutputProjectionSyncSignature(
            workflow_id=workflow_id,
            projection_state=self._projection_state_signature(projection),
            payload_identities=self._image_registry.payload_identities_for(
                projected_image_ids
            ),
        )

    @classmethod
    def _projection_state_signature(
        cls,
        projection: OutputCanvasProjection,
    ) -> tuple[object, ...]:
        """Return immutable, value-based state for one output projection."""

        return (
            tuple(cls._source_group_signature(source) for source in projection.sources),
            projection.active_source_key,
            projection.active_set_index,
            projection.active_uuid,
            projection.set_count,
            tuple(
                cls._scene_group_signature(scene) for scene in projection.scene_groups
            ),
            projection.active_scene_key,
            projection.active_scene_overview,
            projection.scene_count,
            cls._compare_state_signature(projection.compare_state),
        )

    @classmethod
    def _source_group_signature(
        cls,
        source: OutputCanvasSourceGroup,
    ) -> tuple[object, ...]:
        """Return immutable source-group state relevant to output rendering."""

        return (
            source.source_key,
            source.label,
            tuple(
                (
                    set_index,
                    item.image_id,
                    item.set_index,
                    cls._image_meta_signature(item.image_meta),
                )
                for set_index, item in sorted(source.images_by_set.items())
            ),
        )

    @classmethod
    def _scene_group_signature(
        cls,
        scene: OutputCanvasSceneGroup,
    ) -> tuple[object, ...]:
        """Return immutable scene-group state relevant to output rendering."""

        return (
            scene.scene_run_id,
            scene.scene_key,
            scene.title,
            scene.order,
            tuple(cls._source_group_signature(source) for source in scene.sources),
            scene.preview_image_id,
            scene.primary_image_id,
            scene.representative_source_key,
            scene.representative_set_index,
            scene.status,
        )

    @staticmethod
    def _image_meta_signature(image_meta: ImageMeta) -> tuple[object, ...]:
        """Return scalar image metadata used by output selectors and tooltips."""

        return (
            image_meta.workflow_name,
            image_meta.cube_name,
            image_meta.image_number,
            image_meta.suffix,
            image_meta.path,
            image_meta.source_key,
            image_meta.source_label,
            image_meta.node_id,
            image_meta.generation_run_id,
            image_meta.prompt_id,
            image_meta.client_id,
            image_meta.scene_run_id,
            image_meta.scene_key,
            image_meta.scene_title,
            image_meta.scene_order,
            image_meta.scene_count,
            image_meta.width,
            image_meta.height,
            image_meta.list_index,
            image_meta.cube_execution_duration_ms,
        )

    @staticmethod
    def _compare_state_signature(
        compare_state: OutputCompareState,
    ) -> tuple[object, ...]:
        """Return immutable compare state that affects output projection display."""

        return (
            compare_state.enabled,
            compare_state.base,
            compare_state.comparison,
            compare_state.split_position,
            compare_state.orientation,
        )


def _projected_image_ids(projection: OutputCanvasProjection) -> tuple[UUID, ...]:
    """Return ordered unique final image IDs referenced by a projection."""

    image_ids: list[UUID] = []
    for source in projection.sources:
        image_ids.extend(
            item.image_id for _set_index, item in sorted(source.images_by_set.items())
        )
    for scene in projection.scene_groups:
        if scene.primary_image_id is not None:
            image_ids.append(scene.primary_image_id)
        for source in scene.sources:
            image_ids.extend(
                item.image_id
                for _set_index, item in sorted(source.images_by_set.items())
            )
    return tuple(dict.fromkeys(image_ids))


def _empty_projection() -> OutputCanvasProjection:
    """Return an empty Output projection for a missing active workflow."""

    return OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
    )


__all__ = [
    "OutputCanvasProjectionCoordinator",
    "OutputProjectionContentSynchronizer",
    "OutputProjectionSessionSink",
]
