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

"""Adapt application synthetic resize intent to CuteCanvas geometry workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from PySide6.QtCore import QObject, QSize, QTimer, Signal
from cutecanvas import (
    CanvasAnchor,
    CanvasContentReference,
    CanvasResamplingMode,
    CuteCanvas,
)

from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasResizeRequest,
    SyntheticCanvasResizeScope,
)


class SyntheticCanvasGeometryStatus(StrEnum):
    """Normalize terminal CuteCanvas outcomes for shell orchestration."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class SyntheticCanvasGeometryOperation:
    """Identify one in-flight canvas geometry request."""

    operation_id: UUID
    composition_id: UUID


@dataclass(frozen=True, slots=True)
class SyntheticCanvasGeometryResult:
    """Describe one normalized terminal geometry result."""

    operation: SyntheticCanvasGeometryOperation
    status: SyntheticCanvasGeometryStatus
    dimensions: CanvasDimensions
    changed: bool
    message: str = ""
    mask_id_remap: tuple[tuple[UUID, UUID], ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return whether CuteCanvas committed the requested geometry."""

        return self.status is SyntheticCanvasGeometryStatus.COMPLETED


class SyntheticCanvasGeometryAdapter(QObject):
    """Own CuteCanvas revision checks, operations, cancellation, and rollback."""

    operationCompleted = Signal(object)
    geometryChanged = Signal(object, object, object)

    def __init__(self, canvas: CuteCanvas, parent: QObject | None = None) -> None:
        """Bind one Input CuteCanvas and its terminal geometry signals."""

        super().__init__(parent)
        self._canvas = canvas
        self._pending: dict[
            UUID,
            tuple[SyntheticCanvasGeometryOperation, dict[UUID, UUID]],
        ] = {}
        self._known_masks: dict[UUID, dict[UUID, UUID]] = {}
        canvas.canvasResamplingCompleted.connect(self._on_resampling_completed)
        canvas.sceneChanged.connect(self._on_scene_changed)

    def capture_revision(self, composition_id: UUID) -> CanvasContentReference:
        """Capture the exact composition revision shown when a dialog opens."""

        self._known_masks[composition_id] = self._mask_ids_by_layer(composition_id)
        return self._canvas.document().content_reference(composition_id)

    def revision_is_current(self, reference: CanvasContentReference) -> bool:
        """Return whether canvas content still matches an observed revision."""

        return not self._canvas.document().resolve_content(reference).stale

    def begin(
        self,
        *,
        composition_id: UUID,
        expected_revision: CanvasContentReference,
        request: SyntheticCanvasResizeRequest,
    ) -> SyntheticCanvasGeometryOperation:
        """Begin one guarded bounds resize or whole-layer resampling operation."""

        operation = SyntheticCanvasGeometryOperation(uuid4(), composition_id)
        if (
            expected_revision.composition_id != composition_id
            or not self.revision_is_current(expected_revision)
        ):
            self._publish_later(
                SyntheticCanvasGeometryResult(
                    operation=operation,
                    status=SyntheticCanvasGeometryStatus.STALE,
                    dimensions=request.dimensions,
                    changed=False,
                    message="canvas content changed",
                )
            )
            return operation
        target = QSize(request.dimensions.width, request.dimensions.height)
        if request.scope is SyntheticCanvasResizeScope.CANVAS_ONLY:
            try:
                changed = bool(
                    self._canvas.resizeCanvasBounds(
                        composition_id,
                        target,
                        anchor=CanvasAnchor(request.anchor.value),
                    )
                )
            except (RuntimeError, TypeError, ValueError) as error:
                self._publish_later(
                    SyntheticCanvasGeometryResult(
                        operation=operation,
                        status=SyntheticCanvasGeometryStatus.FAILED,
                        dimensions=request.dimensions,
                        changed=False,
                        message=str(error),
                    )
                )
                return operation
            self._publish_later(
                SyntheticCanvasGeometryResult(
                    operation=operation,
                    status=SyntheticCanvasGeometryStatus.COMPLETED,
                    dimensions=request.dimensions,
                    changed=changed,
                )
            )
            return operation

        try:
            request_id = self._canvas.requestCanvasResampling(
                composition_id,
                target,
                mode=CanvasResamplingMode(request.resampling_mode.value),
            )
        except (RuntimeError, TypeError, ValueError) as error:
            self._publish_later(
                SyntheticCanvasGeometryResult(
                    operation=operation,
                    status=SyntheticCanvasGeometryStatus.FAILED,
                    dimensions=request.dimensions,
                    changed=False,
                    message=str(error),
                )
            )
            return operation
        operation = SyntheticCanvasGeometryOperation(request_id, composition_id)
        self._pending[request_id] = (
            operation,
            self._mask_ids_by_layer(composition_id),
        )
        return operation

    def cancel(self, operation: SyntheticCanvasGeometryOperation) -> bool:
        """Cancel an in-flight whole-layer resampling request."""

        if operation.operation_id not in self._pending:
            return False
        return bool(self._canvas.cancelCanvasResampling(operation.operation_id))

    def undo_last_geometry_edit(self) -> bool:
        """Undo the latest scene edit after graph projection failure."""

        return bool(self._canvas.undoSceneEdit())

    def current_dimensions(self, composition_id: UUID) -> CanvasDimensions | None:
        """Return current integer canvas bounds for one composition."""

        entry = self._canvas.getCompositionSnapshot().compositions.get(composition_id)
        bounds = entry.scene_bounds if entry is not None else None
        if bounds is None:
            return None
        return CanvasDimensions(
            width=round(bounds.width()), height=round(bounds.height())
        )

    def _on_resampling_completed(self, raw_result: object) -> None:
        """Translate one CuteCanvas terminal result owned by this adapter."""

        request_id = getattr(raw_result, "request_id", None)
        if not isinstance(request_id, UUID):
            return
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return
        operation, masks_before = pending
        target_size = getattr(raw_result, "target_size", QSize())
        dimensions = CanvasDimensions(
            width=max(1, int(target_size.width())),
            height=max(1, int(target_size.height())),
        )
        raw_status = str(getattr(raw_result, "status", "failed")).rsplit(".", 1)[-1]
        mask_id_remap = self._mask_remap(
            masks_before,
            self._mask_ids_by_layer(operation.composition_id),
        )
        if bool(getattr(raw_result, "succeeded", False)) and mask_id_remap is not None:
            status = SyntheticCanvasGeometryStatus.COMPLETED
        elif raw_status.casefold() == "cancelled":
            status = SyntheticCanvasGeometryStatus.CANCELLED
        elif raw_status.casefold() == "stale":
            status = SyntheticCanvasGeometryStatus.STALE
        else:
            status = SyntheticCanvasGeometryStatus.FAILED
        self.operationCompleted.emit(
            SyntheticCanvasGeometryResult(
                operation=operation,
                status=status,
                dimensions=dimensions,
                changed=bool(getattr(raw_result, "changed", False)),
                message=str(getattr(raw_result, "message", "")),
                mask_id_remap=mask_id_remap or (),
            )
        )

    def _on_scene_changed(self, _scene: object) -> None:
        """Publish active composition bounds after edits and undo/redo."""

        composition_id = self._canvas.currentCompositionID()
        if composition_id is None:
            return
        dimensions = self.current_dimensions(composition_id)
        if dimensions is not None:
            current_masks = self._mask_ids_by_layer(composition_id)
            previous_masks = self._known_masks.get(composition_id, current_masks)
            mask_id_remap = self._mask_remap(previous_masks, current_masks) or ()
            self._known_masks[composition_id] = current_masks
            self.geometryChanged.emit(composition_id, dimensions, mask_id_remap)

    def _mask_ids_by_layer(self, composition_id: UUID) -> dict[UUID, UUID]:
        """Return mask resources keyed by their stable composition layer identity."""

        return {
            mask.layer_id: mask.mask_id
            for mask in self._canvas.listMasksForComposition(composition_id)
            if mask.layer_id is not None
        }

    @staticmethod
    def _mask_remap(
        before: dict[UUID, UUID],
        after: dict[UUID, UUID],
    ) -> tuple[tuple[UUID, UUID], ...] | None:
        """Map changed mask resources only when the complete layer set is stable."""

        if before.keys() != after.keys():
            return None
        return tuple(
            (before[layer_id], after[layer_id])
            for layer_id in before
            if before[layer_id] != after[layer_id]
        )

    def _publish_later(self, result: SyntheticCanvasGeometryResult) -> None:
        """Publish synchronous geometry outcomes after the initiating signal unwinds."""

        QTimer.singleShot(0, lambda: self.operationCompleted.emit(result))


__all__ = [
    "SyntheticCanvasGeometryAdapter",
    "SyntheticCanvasGeometryOperation",
    "SyntheticCanvasGeometryResult",
    "SyntheticCanvasGeometryStatus",
]
