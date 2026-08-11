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

"""Publish semantic Input tool-capability transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import QObject, QTimer, Signal
from cutecanvas import CuteCanvas, EditorIntent, EditorTransformTarget

from .input_document_catalog import InputDocumentCatalog


@dataclass(frozen=True, slots=True)
class InputCanvasToolContextSnapshot:
    """Describe the capability inputs used by the Input tool palette."""

    image_id: UUID | None
    has_active_mask: bool
    smart_segmentation_ready: bool
    has_pixel_selection: bool
    selection_transform_available: bool
    layer_transform_available: bool
    selection_clear_available: bool
    edit_session_active: bool


class InputCanvasToolContext(QObject):
    """Own derived tool capability state and change publication."""

    changed = Signal()

    def __init__(
        self,
        *,
        canvas: CuteCanvas,
        catalog: InputDocumentCatalog,
        current_image_id: Callable[[], UUID | None],
        parent: QObject,
    ) -> None:
        """Bind public editor state needed for capability derivation."""

        super().__init__(parent)
        self._canvas = canvas
        self._catalog = catalog
        self._current_image_id = current_image_id
        self._snapshot = self._capture_snapshot()
        self._published_snapshot = self._snapshot
        self._publication_timer = QTimer(self)
        self._publication_timer.setSingleShot(True)
        self._publication_timer.setInterval(0)
        self._publication_timer.timeout.connect(self._publish_change)
        canvas.samCheckpointStatusChanged.connect(self.refresh)
        canvas.compositionSelectionChanged.connect(self.refresh)
        canvas.selectedLayerChanged.connect(self.refresh)
        canvas.pixelSelectionChanged.connect(self.refresh)
        canvas.layerPixelsChanged.connect(self.refresh)
        canvas.maskUndoStackChanged.connect(self.refresh)
        canvas.editorPolicyChanged.connect(self.refresh)
        canvas.editSessionChanged.connect(self.refresh)

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return the latest semantic capability snapshot."""

        return self._snapshot

    def refresh(self, *_args: object) -> bool:
        """Publish only when capability-relevant state actually changes."""

        snapshot = self._capture_snapshot()
        if snapshot == self._snapshot:
            return False
        self._snapshot = snapshot
        self._publication_timer.start()
        return True

    def activate_transform(self, target: EditorTransformTarget) -> bool:
        """Activate the shared affine mode against one explicit target."""

        return bool(self._canvas.activateEditorTransform(target))

    def _capture_snapshot(self) -> InputCanvasToolContextSnapshot:
        """Derive one detached capability snapshot from public editor state."""

        image_id = self._current_image_id()
        has_active_mask = self._has_active_mask(image_id)
        selection = self._canvas.pixelSelectionState()
        has_selection = selection is not None and selection.has_selection
        return InputCanvasToolContextSnapshot(
            image_id=image_id,
            has_active_mask=has_active_mask,
            smart_segmentation_ready=bool(self._canvas.samCheckpointReady()),
            has_pixel_selection=has_selection,
            selection_transform_available=bool(
                has_selection
                and self._canvas.editorOperationState(EditorIntent.TRANSFORM).allowed
            ),
            layer_transform_available=bool(
                has_active_mask
                and self._canvas.editorTransformState(
                    EditorTransformTarget.LAYER_CONTENT
                ).allowed
            ),
            selection_clear_available=bool(
                has_selection
                and self._canvas.editorOperationState(
                    EditorIntent.DELETE_PIXELS
                ).allowed
            ),
            edit_session_active=self._canvas.activeEditSession() is not None,
        )

    def _publish_change(self) -> None:
        """Publish the final semantic state once after synchronous editor observers."""

        if self._snapshot == self._published_snapshot:
            return
        self._published_snapshot = self._snapshot
        self.changed.emit()

    def _has_active_mask(self, image_id: UUID | None) -> bool:
        """Return whether the routed image owns the active editable mask."""

        if image_id is None:
            return False
        record = self._catalog.record_for(image_id)
        active_mask_id = self._canvas.activeMaskID()
        if record is None or active_mask_id is None:
            return False
        return any(
            mask.mask_id == active_mask_id
            for mask in self._canvas.listMasksForComposition(record.composition_id)
        )


__all__ = ["InputCanvasToolContext", "InputCanvasToolContextSnapshot"]
