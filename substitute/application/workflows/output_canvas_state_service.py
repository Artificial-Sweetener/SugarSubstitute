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

"""Own durable Output canvas workflow state and image registry mutation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.output_canvas_state_service")


@dataclass(frozen=True, slots=True)
class OutputFocusSnapshot:
    """Capture durable Output focus fields before or after a state mutation."""

    active_uuid: UUID | None
    set_index: int
    source_key: str | None
    scene_key: str | None
    scene_overview: bool
    focus_mode: OutputFocusMode

    @classmethod
    def from_workflow(cls, workflow: WorkflowState) -> "OutputFocusSnapshot":
        """Return the current durable Output focus for a workflow."""

        return cls(
            active_uuid=workflow.active_output_uuid,
            set_index=workflow.active_output_set_index,
            source_key=workflow.active_output_source_key,
            scene_key=workflow.active_output_scene_key,
            scene_overview=workflow.active_output_scene_overview,
            focus_mode=workflow.output_focus_mode,
        )


@dataclass(frozen=True, slots=True)
class OutputFocusMutationResult:
    """Describe whether one Output focus mutation changed workflow state."""

    before: OutputFocusSnapshot
    after: OutputFocusSnapshot

    @property
    def changed(self) -> bool:
        """Return whether focus fields changed."""

        return self.before != self.after


@dataclass(frozen=True, slots=True)
class OutputProjectionSchedulingIntent:
    """Describe generated-output projection work without routing display itself."""

    workflow_id: str
    registered_image_id: UUID | None
    should_schedule: bool

    @classmethod
    def none(cls, workflow_id: str = "") -> "OutputProjectionSchedulingIntent":
        """Return an empty scheduling intent."""

        return cls(
            workflow_id=workflow_id,
            registered_image_id=None,
            should_schedule=False,
        )


@dataclass(frozen=True, slots=True)
class OutputPreviewCloseIdentity:
    """Identify the transient preview lane replaced by one final output."""

    workflow_id: str
    image_id: UUID
    source_key: str
    source_label: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    node_id: str
    list_index: int | None
    scene_run_id: str | None
    scene_key: str | None
    scene_title: str | None
    scene_order: int | None
    scene_count: int | None


@dataclass(frozen=True, slots=True)
class OutputImageRegistrationResult:
    """Describe durable state changes from registering one final output image."""

    workflow_id: str
    image_id: UUID | None
    registered: bool
    focus_change: OutputFocusMutationResult
    preview_close_identity: OutputPreviewCloseIdentity | None
    projection_intent: OutputProjectionSchedulingIntent

    @property
    def active_output_changed(self) -> bool:
        """Return whether registration changed active Output focus."""

        return self.focus_change.changed


@dataclass(frozen=True, slots=True)
class OutputTimingUpdateResult:
    """Describe Output metadata timing updates."""

    workflow_id: str
    updated_image_ids: tuple[UUID, ...]
    projection_intent: OutputProjectionSchedulingIntent

    @property
    def changed(self) -> bool:
        """Return whether any Output metadata changed."""

        return bool(self.updated_image_ids)


@dataclass(frozen=True, slots=True)
class OutputPruneResult:
    """Describe registry records removed after Output membership changed."""

    workflow_id: str
    removed_image_ids: tuple[UUID, ...]
    focus_change: OutputFocusMutationResult | None = None


class OutputCanvasStateService:
    """Mutate durable Output workflow state and shared image records."""

    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        """Use one shared registry for Output payload and metadata records."""

        self._image_registry = image_registry
        self._uuid_factory = uuid_factory

    @property
    def image_registry(self) -> CanvasImageRegistry:
        """Return the shared Output payload and metadata registry."""

        return self._image_registry

    def begin_output_generation(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        *,
        scene_run_id: str | None = None,
        scene_count: int | None = None,
    ) -> OutputFocusMutationResult | None:
        """Prepare automatic scene overview focus at generation start."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return None
        before = OutputFocusSnapshot.from_workflow(workflow)
        should_prepare_scene_overview = bool(scene_run_id) and (
            scene_count is None or scene_count > 1
        )
        if should_prepare_scene_overview:
            workflow.output_focus_mode = OutputFocusMode.AUTOMATIC
            workflow.active_output_uuid = None
            workflow.active_output_source_key = None
            workflow.active_output_set_index = 1
            workflow.active_output_scene_key = None
            workflow.active_output_scene_overview = True
        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )

    def register_output_image(
        self,
        workflows: Mapping[str, WorkflowState],
        origin_workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: ImageMeta,
    ) -> OutputImageRegistrationResult:
        """Register final Output state without touching display widgets."""

        origin_workflow = workflows[origin_workflow_id]
        new_id = self._uuid_factory()
        previous_focus = OutputFocusSnapshot.from_workflow(origin_workflow)
        self._image_registry.store(new_id, payload=image, metadata=image_meta)
        origin_workflow.output_image_uuids.append(new_id)
        if origin_workflow.output_focus_mode == OutputFocusMode.AUTOMATIC:
            self._apply_automatic_registration_focus(
                origin_workflow, new_id, image_meta
            )
        focus_change = OutputFocusMutationResult(
            before=previous_focus,
            after=OutputFocusSnapshot.from_workflow(origin_workflow),
        )
        return OutputImageRegistrationResult(
            workflow_id=origin_workflow_id,
            image_id=new_id,
            registered=True,
            focus_change=focus_change,
            preview_close_identity=_preview_close_identity(
                workflow_id=origin_workflow_id,
                image_id=new_id,
                image_meta=image_meta,
            ),
            projection_intent=OutputProjectionSchedulingIntent(
                workflow_id=origin_workflow_id,
                registered_image_id=new_id,
                should_schedule=origin_workflow_id == active_workflow_id,
            ),
        )

    def register_generated_output(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        *,
        event: LiveFinalOutputEvent,
        image: object,
        image_meta: ImageMeta,
    ) -> OutputImageRegistrationResult:
        """Register a strict live final Output using backend identity."""

        origin_workflow_id = event.identity.workflow_id
        missing_focus = _empty_focus_result()
        if origin_workflow_id not in workflows:
            log_warning(
                _LOGGER,
                "Rejected live generated output for missing workflow",
                workflow_id=origin_workflow_id,
                generation_run_id=event.identity.generation_run_id,
                prompt_id=event.identity.prompt_id,
                client_id=event.identity.client_id,
                node_id=event.node_id,
                source_key=event.identity.source_key,
                reason="missing_workflow",
            )
            return OutputImageRegistrationResult(
                workflow_id=origin_workflow_id,
                image_id=None,
                registered=False,
                focus_change=missing_focus,
                preview_close_identity=None,
                projection_intent=OutputProjectionSchedulingIntent.none(
                    origin_workflow_id
                ),
            )
        rejection_reason = _live_metadata_rejection_reason(event, image_meta)
        if rejection_reason is not None:
            log_warning(
                _LOGGER,
                "Rejected live generated output with mismatched metadata",
                workflow_id=origin_workflow_id,
                generation_run_id=event.identity.generation_run_id,
                prompt_id=event.identity.prompt_id,
                client_id=event.identity.client_id,
                node_id=event.node_id,
                source_key=event.identity.source_key,
                reason=rejection_reason,
            )
            return OutputImageRegistrationResult(
                workflow_id=origin_workflow_id,
                image_id=None,
                registered=False,
                focus_change=missing_focus,
                preview_close_identity=None,
                projection_intent=OutputProjectionSchedulingIntent.none(
                    origin_workflow_id
                ),
            )
        return self.register_output_image(
            workflows,
            origin_workflow_id,
            active_workflow_id,
            image,
            image_meta,
        )

    def restore_output_image(
        self,
        *,
        workflow_id: str,
        image_id: UUID,
        image: object,
        image_meta: ImageMeta,
    ) -> OutputImageRegistrationResult:
        """Restore one Output image registry record under a snapshot UUID."""

        focus_change = _empty_focus_result()
        self._image_registry.store(image_id, payload=image, metadata=image_meta)
        return OutputImageRegistrationResult(
            workflow_id=workflow_id,
            image_id=image_id,
            registered=True,
            focus_change=focus_change,
            preview_close_identity=None,
            projection_intent=OutputProjectionSchedulingIntent.none(workflow_id),
        )

    def apply_output_source_timing(
        self,
        workflows: Mapping[str, WorkflowState],
        *,
        workflow_id: str,
        active_workflow_id: str,
        source_durations_ms: Mapping[str, float],
        cube_durations_ms: Mapping[str, float],
    ) -> OutputTimingUpdateResult:
        """Apply source timing to existing Output metadata records."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return OutputTimingUpdateResult(
                workflow_id=workflow_id,
                updated_image_ids=(),
                projection_intent=OutputProjectionSchedulingIntent.none(workflow_id),
            )
        updated_image_ids: list[UUID] = []
        for image_id in workflow.output_image_uuids:
            image_meta = self._image_registry.metadata_for(image_id)
            if image_meta is None:
                continue
            duration_ms = _duration_for_image_meta(
                image_meta,
                source_durations_ms=source_durations_ms,
                cube_durations_ms=cube_durations_ms,
            )
            if duration_ms is None:
                continue
            if image_meta.cube_execution_duration_ms == duration_ms:
                continue
            image_meta.cube_execution_duration_ms = duration_ms
            updated_image_ids.append(image_id)
        return OutputTimingUpdateResult(
            workflow_id=workflow_id,
            updated_image_ids=tuple(updated_image_ids),
            projection_intent=OutputProjectionSchedulingIntent(
                workflow_id=workflow_id,
                registered_image_id=None,
                should_schedule=bool(updated_image_ids)
                and workflow_id == active_workflow_id,
            ),
        )

    def clear_output_for_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
    ) -> OutputPruneResult:
        """Clear one workflow's durable Output aggregate and registry records."""

        workflow = workflows.get(workflow_id)
        if workflow is None or not workflow.output_image_uuids:
            return OutputPruneResult(workflow_id=workflow_id, removed_image_ids=())
        before = OutputFocusSnapshot.from_workflow(workflow)
        uuids_to_remove = tuple(workflow.output_image_uuids)
        workflow.output_image_uuids.clear()
        workflow.active_output_uuid = None
        workflow.active_output_set_index = 1
        workflow.active_output_source_key = None
        workflow.active_output_scene_key = None
        workflow.active_output_scene_overview = False
        workflow.output_focus_mode = OutputFocusMode.AUTOMATIC
        removed = tuple(
            image_id
            for image_id in uuids_to_remove
            if self._remove_output_record_if_unreferenced(image_id, workflows)
        )
        return OutputPruneResult(
            workflow_id=workflow_id,
            removed_image_ids=removed,
            focus_change=OutputFocusMutationResult(
                before=before,
                after=OutputFocusSnapshot.from_workflow(workflow),
            ),
        )

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> OutputPruneResult:
        """Remove unreferenced Output records after a workflow closes."""

        removed = tuple(
            image_id
            for image_id in closed_workflow.output_image_uuids
            if self._remove_output_record_if_unreferenced(
                image_id,
                remaining_workflows,
            )
        )
        return OutputPruneResult(
            workflow_id=closed_workflow_id,
            removed_image_ids=removed,
        )

    def set_active_output_uuid(
        self,
        workflow: WorkflowState,
        uuid_str: str,
    ) -> OutputFocusMutationResult | None:
        """Persist active Output UUID from an output-selection event payload."""

        try:
            selected_uuid = UUID(uuid_str)
        except (TypeError, ValueError):
            log_warning(
                _LOGGER,
                "Ignored invalid active output UUID payload",
                uuid=uuid_str,
            )
            return None
        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.output_focus_mode = OutputFocusMode.MANUAL
        workflow.active_output_uuid = selected_uuid
        workflow.active_output_scene_overview = False
        workflow.active_output_scene_key = self._scene_key_for_output_uuid(
            workflow,
            selected_uuid,
        )
        focus = self._output_focus_for_uuid(workflow, selected_uuid)
        if focus is None:
            workflow.active_output_set_index = 1
            workflow.active_output_source_key = None
        else:
            source_key, set_index = focus
            workflow.active_output_set_index = set_index
            workflow.active_output_source_key = source_key
        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )

    def set_active_output_grid(
        self,
        workflow: WorkflowState,
        source_key: str | None,
        scene_key: str | None = None,
    ) -> OutputFocusMutationResult:
        """Persist manual Output grid selection for a source."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.output_focus_mode = OutputFocusMode.MANUAL
        workflow.active_output_uuid = None
        workflow.active_output_set_index = 0
        workflow.active_output_source_key = source_key
        if scene_key is not None:
            workflow.active_output_scene_key = scene_key
        workflow.active_output_scene_overview = False
        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )

    def set_active_output_scene(
        self,
        workflow: WorkflowState,
        selection: OutputSceneNavigationSelection,
    ) -> OutputFocusMutationResult:
        """Persist one complete manual scene-level Output route selection."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.output_focus_mode = OutputFocusMode.MANUAL
        workflow.active_output_scene_key = selection.scene_key
        workflow.active_output_scene_overview = selection.overview
        workflow.active_output_source_key = selection.source_key
        workflow.active_output_set_index = selection.set_index
        workflow.active_output_uuid = selection.image_id
        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )

    def set_output_compare_state(
        self,
        workflow: WorkflowState,
        state: OutputCompareState,
    ) -> None:
        """Persist Output compare viewing state on a workflow."""

        workflow.output_compare_state = state

    def remember_projected_focus(
        self,
        workflow: WorkflowState,
        projection: OutputCanvasProjection,
    ) -> OutputFocusMutationResult:
        """Persist route memory derived from an Output projection."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.active_output_set_index = projection.active_set_index
        workflow.active_output_source_key = projection.active_source_key
        workflow.active_output_scene_key = (
            None if projection.active_scene_overview else projection.active_scene_key
        )
        workflow.active_output_scene_overview = projection.active_scene_overview
        if (
            projection.active_uuid is not None
            and workflow.active_output_uuid != projection.active_uuid
        ):
            workflow.active_output_uuid = projection.active_uuid
        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )

    def _remove_output_record_if_unreferenced(
        self,
        image_id: UUID,
        workflows: Mapping[str, WorkflowState],
    ) -> bool:
        """Remove one Output registry record if no workflow still references it."""

        is_referenced = any(
            image_id in workflow.output_image_uuids for workflow in workflows.values()
        )
        if is_referenced:
            return False
        return self._image_registry.remove(image_id)

    @staticmethod
    def _apply_automatic_registration_focus(
        workflow: WorkflowState,
        image_id: UUID,
        image_meta: ImageMeta,
    ) -> None:
        """Apply automatic focus policy after a final Output is registered."""

        if image_meta.scene_count is not None and image_meta.scene_count > 1:
            workflow.active_output_uuid = None
            workflow.active_output_set_index = 1
            workflow.active_output_source_key = None
            workflow.active_output_scene_key = None
            workflow.active_output_scene_overview = True
            return
        workflow.active_output_uuid = image_id
        workflow.active_output_set_index = 1
        workflow.active_output_source_key = _source_key_for_output(image_id, image_meta)
        workflow.active_output_scene_key = image_meta.scene_key or None
        workflow.active_output_scene_overview = False

    def _output_focus_for_uuid(
        self,
        workflow: WorkflowState,
        output_uuid: UUID,
    ) -> tuple[str, int] | None:
        """Return source key and scene-local set index for an Output UUID."""

        source_counts: dict[tuple[str, str], int] = {}
        for image_id in workflow.output_image_uuids:
            image_meta = self._image_registry.metadata_for(image_id)
            if image_meta is None:
                continue
            source_key = _source_key_for_output(image_id, image_meta)
            scene_key = image_meta.scene_key
            count_key = (scene_key, source_key)
            source_counts[count_key] = source_counts.get(count_key, 0) + 1
            if image_id == output_uuid:
                return source_key, source_counts[count_key]
        return None

    def _scene_key_for_output_uuid(
        self,
        workflow: WorkflowState,
        output_uuid: UUID,
    ) -> str | None:
        """Return scene key for an Output UUID when metadata has one."""

        if output_uuid not in workflow.output_image_uuids:
            return None
        image_meta = self._image_registry.metadata_for(output_uuid)
        if image_meta is None or not image_meta.scene_key:
            return None
        return image_meta.scene_key


def _empty_focus_result() -> OutputFocusMutationResult:
    """Return an unchanged empty focus result for rejected registrations."""

    empty = OutputFocusSnapshot(
        active_uuid=None,
        set_index=1,
        source_key=None,
        scene_key=None,
        scene_overview=False,
        focus_mode=OutputFocusMode.AUTOMATIC,
    )
    return OutputFocusMutationResult(before=empty, after=empty)


def _preview_close_identity(
    *,
    workflow_id: str,
    image_id: UUID,
    image_meta: ImageMeta,
) -> OutputPreviewCloseIdentity | None:
    """Return preview-close identity when metadata contains live identifiers."""

    if not (
        image_meta.source_key
        and image_meta.source_label
        and image_meta.generation_run_id
        and image_meta.prompt_id
        and image_meta.client_id
        and image_meta.node_id
    ):
        return None
    return OutputPreviewCloseIdentity(
        workflow_id=workflow_id,
        image_id=image_id,
        source_key=image_meta.source_key,
        source_label=image_meta.source_label,
        generation_run_id=image_meta.generation_run_id,
        prompt_id=image_meta.prompt_id,
        client_id=image_meta.client_id,
        node_id=image_meta.node_id,
        list_index=image_meta.list_index,
        scene_run_id=image_meta.scene_run_id or None,
        scene_key=image_meta.scene_key or None,
        scene_title=image_meta.scene_title or None,
        scene_order=image_meta.scene_order,
        scene_count=image_meta.scene_count,
    )


def _duration_for_image_meta(
    image_meta: ImageMeta,
    *,
    source_durations_ms: Mapping[str, float],
    cube_durations_ms: Mapping[str, float],
) -> float | None:
    """Return a matching timing duration for one Output metadata record."""

    if image_meta.source_key in source_durations_ms:
        return source_durations_ms[image_meta.source_key]
    if image_meta.source_label in cube_durations_ms:
        return cube_durations_ms[image_meta.source_label]
    if image_meta.cube_name in cube_durations_ms:
        return cube_durations_ms[image_meta.cube_name]
    return None


def _live_metadata_rejection_reason(
    event: LiveFinalOutputEvent,
    image_meta: ImageMeta,
) -> str | None:
    """Return why prepared metadata no longer matches a live final event."""

    if image_meta.source_key != event.identity.source_key:
        return "source_key_mismatch"
    if image_meta.source_label != event.identity.source_label:
        return "source_label_mismatch"
    if image_meta.prompt_id != event.identity.prompt_id:
        return "prompt_id_mismatch"
    if image_meta.client_id != event.identity.client_id:
        return "client_id_mismatch"
    if image_meta.generation_run_id != event.identity.generation_run_id:
        return "generation_run_id_mismatch"
    if image_meta.node_id != event.node_id:
        return "node_id_mismatch"
    if image_meta.list_index != event.position.list_index:
        return "list_index_mismatch"
    if (image_meta.batch_index or 0) != event.position.batch_index:
        return "batch_index_mismatch"
    if image_meta.width != event.artifact_width:
        return "artifact_width_mismatch"
    if image_meta.height != event.artifact_height:
        return "artifact_height_mismatch"
    if image_meta.path and Path(image_meta.path) != event.file_path:
        return "file_path_mismatch"
    scene = event.identity.scene
    if isinstance(scene, OutputSceneIdentity):
        if (
            image_meta.scene_run_id != scene.run_id
            or image_meta.scene_key != scene.key
            or image_meta.scene_title != scene.title
            or image_meta.scene_order != scene.order
            or image_meta.scene_count != scene.count
        ):
            return "scene_identity_mismatch"
        return None
    if (
        image_meta.scene_run_id
        or image_meta.scene_key
        or image_meta.scene_title
        or image_meta.scene_order is not None
        or image_meta.scene_count is not None
    ):
        return "scene_identity_mismatch"
    return None


def _source_key_for_output(image_id: UUID, image_meta: ImageMeta) -> str:
    """Return source identity for focus bookkeeping."""

    if image_meta.source_key:
        return image_meta.source_key
    if image_meta.cube_name:
        return image_meta.cube_name
    return str(image_id)


__all__ = [
    "OutputCanvasStateService",
    "OutputFocusMutationResult",
    "OutputFocusSnapshot",
    "OutputImageRegistrationResult",
    "OutputPreviewCloseIdentity",
    "OutputProjectionSchedulingIntent",
    "OutputPruneResult",
    "OutputTimingUpdateResult",
]
