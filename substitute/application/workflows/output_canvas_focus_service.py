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

"""Own durable Output route fields independently from navigation session mode."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_projection_model import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.output_canvas_focus_service")


@dataclass(frozen=True, slots=True)
class OutputFocusSnapshot:
    """Capture durable Output focus fields before or after a mutation."""

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


class OutputCanvasFocusService:
    """Mutate Output route intent while projection owns route interpretation."""

    def __init__(self, *, image_registry: CanvasImageRegistry) -> None:
        """Store metadata lookup used to persist concrete user selections."""

        self._image_registry = image_registry

    def set_active_output_uuid(
        self,
        workflow: WorkflowState,
        uuid_str: str,
    ) -> OutputFocusMutationResult | None:
        """Persist a user-selected concrete Output image."""

        try:
            selected_uuid = UUID(uuid_str)
        except (TypeError, ValueError):
            log_warning(
                _LOGGER, "Ignored invalid active output UUID payload", uuid=uuid_str
            )
            return None
        before = OutputFocusSnapshot.from_workflow(workflow)
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
        return self._result(before, workflow)

    @staticmethod
    def set_active_output_grid(
        workflow: WorkflowState,
        source_key: str | None,
        scene_key: str | None = None,
    ) -> OutputFocusMutationResult:
        """Persist a user-selected Output batch grid."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.active_output_uuid = None
        workflow.active_output_set_index = 0
        workflow.active_output_source_key = source_key
        if scene_key is not None:
            workflow.active_output_scene_key = scene_key
        workflow.active_output_scene_overview = False
        return OutputCanvasFocusService._result(before, workflow)

    @staticmethod
    def set_active_output_scene(
        workflow: WorkflowState,
        selection: OutputSceneNavigationSelection,
    ) -> OutputFocusMutationResult:
        """Persist one complete user-selected scene-level route."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.active_output_scene_key = selection.scene_key
        workflow.active_output_scene_overview = selection.overview
        workflow.active_output_source_key = selection.source_key
        workflow.active_output_set_index = selection.set_index
        workflow.active_output_uuid = selection.image_id
        return OutputCanvasFocusService._result(before, workflow)

    @staticmethod
    def set_output_compare_state(
        workflow: WorkflowState,
        state: OutputCompareState,
    ) -> None:
        """Persist Output comparison viewing state."""

        workflow.output_compare_state = state

    @staticmethod
    def remember_projected_focus(
        workflow: WorkflowState,
        projection: OutputCanvasProjection,
    ) -> OutputFocusMutationResult:
        """Persist the authoritative route resolved from presentable content."""

        before = OutputFocusSnapshot.from_workflow(workflow)
        workflow.active_output_set_index = projection.active_set_index
        workflow.active_output_source_key = projection.active_source_key
        workflow.active_output_scene_key = (
            None if projection.active_scene_overview else projection.active_scene_key
        )
        workflow.active_output_scene_overview = projection.active_scene_overview
        workflow.active_output_uuid = projection.active_uuid
        return OutputCanvasFocusService._result(before, workflow)

    def _output_focus_for_uuid(
        self,
        workflow: WorkflowState,
        output_uuid: UUID,
    ) -> tuple[str, int] | None:
        """Return source key and scene-local batch index for an Output UUID."""

        source_counts: dict[tuple[str, str], int] = {}
        for image_id in workflow.output_image_uuids:
            image_meta = self._image_registry.metadata_for(image_id)
            if image_meta is None:
                continue
            source_key = _source_key_for_output(image_id, image_meta)
            count_key = (image_meta.scene_key, source_key)
            source_counts[count_key] = source_counts.get(count_key, 0) + 1
            if image_id == output_uuid:
                return source_key, source_counts[count_key]
        return None

    def _scene_key_for_output_uuid(
        self,
        workflow: WorkflowState,
        output_uuid: UUID,
    ) -> str | None:
        """Return scene key for an Output UUID when present."""

        if output_uuid not in workflow.output_image_uuids:
            return None
        image_meta = self._image_registry.metadata_for(output_uuid)
        if image_meta is None or not image_meta.scene_key:
            return None
        return image_meta.scene_key

    @staticmethod
    def _result(
        before: OutputFocusSnapshot,
        workflow: WorkflowState,
    ) -> OutputFocusMutationResult:
        """Return a focus mutation result for the updated workflow."""

        return OutputFocusMutationResult(
            before=before,
            after=OutputFocusSnapshot.from_workflow(workflow),
        )


def empty_output_focus_result() -> OutputFocusMutationResult:
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


def _source_key_for_output(image_id: UUID, image_meta: ImageMeta) -> str:
    """Return source identity for focus bookkeeping."""

    if image_meta.source_key:
        return image_meta.source_key
    if image_meta.cube_name:
        return image_meta.cube_name
    return str(image_id)


__all__ = [
    "OutputCanvasFocusService",
    "OutputFocusMutationResult",
    "OutputFocusSnapshot",
    "empty_output_focus_result",
]
