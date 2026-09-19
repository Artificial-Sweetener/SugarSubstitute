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
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_focus_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
    empty_output_focus_result,
)
from substitute.domain.workflow import (
    ImageMeta,
    WorkflowState,
)


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
    batch_index: int | None
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
    retired_image_ids: tuple[UUID, ...] = ()

    @property
    def active_output_changed(self) -> bool:
        """Return whether registration changed active Output focus."""

        return self.focus_change.changed


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

    def restore_output_image(
        self,
        *,
        workflow_id: str,
        image_id: UUID,
        image: object,
        image_meta: ImageMeta,
    ) -> OutputImageRegistrationResult:
        """Restore one Output image registry record under a snapshot UUID."""

        focus_change = empty_output_focus_result()
        self._image_registry.store(image_id, payload=image, metadata=image_meta)
        return OutputImageRegistrationResult(
            workflow_id=workflow_id,
            image_id=image_id,
            registered=True,
            focus_change=focus_change,
            preview_close_identity=None,
            projection_intent=OutputProjectionSchedulingIntent.none(workflow_id),
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
        batch_index=image_meta.batch_index,
        scene_run_id=image_meta.scene_run_id or None,
        scene_key=image_meta.scene_key or None,
        scene_title=image_meta.scene_title or None,
        scene_order=image_meta.scene_order,
        scene_count=image_meta.scene_count,
    )


__all__ = [
    "OutputCanvasStateService",
    "OutputImageRegistrationResult",
    "OutputPreviewCloseIdentity",
    "OutputProjectionSchedulingIntent",
    "OutputPruneResult",
]
