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

"""Own the Input CuteCanvas document and application-to-document identities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QColor, QImage
from cutecanvas import (
    CanvasDocument,
    CanvasDocumentRuntime,
    CanvasViewSession,
    CuteCanvas,
    EditorCapability,
    EditorPolicy,
    ExecutionRuntime,
    LayerPolicy,
    NonEditablePaintPolicy,
)

from substitute.application.workflows.input_canvas_document_port import (
    CanvasDocumentMutation,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_document")
_PRODUCT_TOOL_TO_CONTROL_MODE = {
    InputCanvasToolId.MOVE: CuteCanvas.CONTROL_MODE_MOVE,
    InputCanvasToolId.MASK_RECTANGLE: CuteCanvas.CONTROL_MODE_MASK_RECTANGLE,
    InputCanvasToolId.MASK_ELLIPSE: CuteCanvas.CONTROL_MODE_MASK_ELLIPSE,
    InputCanvasToolId.MASK_LASSO: CuteCanvas.CONTROL_MODE_MASK_LASSO,
    InputCanvasToolId.SMART_SELECT: CuteCanvas.CONTROL_MODE_SMART_SELECT,
    InputCanvasToolId.BRUSH: CuteCanvas.CONTROL_MODE_DRAW_BRUSH,
    InputCanvasToolId.PAN_ZOOM: CuteCanvas.CONTROL_MODE_PANZOOM,
}
_CONTROL_MODE_TO_PRODUCT_TOOL = {
    control_mode: tool_id
    for tool_id, control_mode in _PRODUCT_TOOL_TO_CONTROL_MODE.items()
}

_BASE_LAYER_POLICY = LayerPolicy(
    selectable=False,
    movable=False,
    pixel_editable=False,
    reorderable=False,
    removable=False,
)
_MASK_LAYER_POLICY = LayerPolicy(
    selectable=True,
    movable=True,
    pixel_editable=True,
    reorderable=False,
    removable=False,
)
_EDITOR_POLICY = EditorPolicy(
    capabilities=frozenset(
        {
            EditorCapability.SELECT_PIXELS,
            EditorCapability.EDIT_PIXELS,
            EditorCapability.MOVE_LAYERS,
            EditorCapability.PAINT,
        }
    ),
    noneditable_paint=NonEditablePaintPolicy.REJECT,
)


@dataclass(frozen=True, slots=True)
class InputDocumentImage:
    """Map one SugarSubstitute Input image identity to document content."""

    image_id: UUID
    composition_id: UUID
    path: Path | None
    payload_identity: int


class InputCanvasDocument(QObject):
    """Provide one long-lived CuteCanvas Input document to application services."""

    imageMaterialized = Signal(object, str)
    toolContextChanged = Signal()
    canvasToolChanged = Signal(str)

    def __init__(
        self,
        *,
        features: tuple[str, ...],
        execution_runtime: ExecutionRuntime | None = None,
    ) -> None:
        """Create the durable document, detached session, and editing surface."""

        super().__init__()
        self._document = CanvasDocument()
        self._runtime = CanvasDocumentRuntime(
            self._document,
            execution_runtime=execution_runtime,
        )
        self._session = CanvasViewSession()
        self._canvas = CuteCanvas(
            document=self._document,
            document_runtime=self._runtime,
            features=features,
            session=self._session,
        )
        self._canvas.setEditorPolicy(_EDITOR_POLICY)
        self._images: dict[UUID, InputDocumentImage] = {}
        self._canvas.controlModeChanged.connect(self._on_control_mode_changed)
        self._canvas.samCheckpointStatusChanged.connect(
            lambda _status, _path: self.toolContextChanged.emit()
        )
        self._canvas.compositionSelectionChanged.connect(
            lambda _composition_id: self.toolContextChanged.emit()
        )
        self._canvas.selectedLayerChanged.connect(
            lambda _selection: self.toolContextChanged.emit()
        )

    @property
    def canvas(self) -> CuteCanvas:
        """Return the single widget presenting this document."""

        return self._canvas

    @property
    def runtime(self) -> CanvasDocumentRuntime:
        """Return the document-scoped runtime bound to this Input document."""

        return self._runtime

    def ensure_image_cached(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> CanvasDocumentMutation:
        """Admit an image as one fixed document composition without routing it."""

        if not isinstance(image, QImage) or image.isNull():
            log_warning(
                _LOGGER,
                "Input document image admission rejected invalid payload",
                image_id=str(image_id),
                path=str(path) if path is not None else "",
            )
            return CanvasDocumentMutation.UNCHANGED
        normalized_path = Path(path) if path is not None else None
        existing = self._images.get(image_id)
        if existing is not None and self._same_payload(
            existing, image, normalized_path
        ):
            return CanvasDocumentMutation.UNCHANGED
        if existing is not None:
            self._document.replace_composition_image(existing.composition_id, image)
            composition_id = existing.composition_id
        else:
            composition_id = self._document.create_composition_from_image(
                image,
                title="Input image",
                interaction=_BASE_LAYER_POLICY,
            )
        self._images[image_id] = InputDocumentImage(
            image_id=image_id,
            composition_id=composition_id,
            path=normalized_path,
            payload_identity=id(image),
        )
        mutation = (
            CanvasDocumentMutation.REPLACED
            if existing is not None
            else CanvasDocumentMutation.ADDED
        )
        self.imageMaterialized.emit(image_id, str(normalized_path or ""))
        log_debug(
            _LOGGER,
            "Input document image admitted",
            image_id=str(image_id),
            composition_id=str(composition_id),
            path=str(normalized_path) if normalized_path is not None else "",
            mutation=mutation.value,
        )
        return mutation

    def contains(self, image_id: UUID) -> bool:
        """Return whether an application image owns a live composition."""

        return image_id in self._images

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the application-owned source path for one image."""

        record = self._images.get(image_id)
        return None if record is None else record.path

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Remove an already-authorized unreferenced image composition."""

        record = self._images.pop(image_id, None)
        if record is None:
            return False
        self._canvas.removeComposition(record.composition_id)
        self.toolContextChanged.emit()
        log_debug(
            _LOGGER,
            "Input document image retired",
            image_id=str(image_id),
            composition_id=str(record.composition_id),
        )
        return True

    def payload_for_route_preparation(self, image_id: UUID) -> object | None:
        """Return no payload because document routes need no cache hydration."""

        del image_id
        return None

    def snapshot_for_cache_diagnostics(self) -> object:
        """Return the supported document snapshot for cache diagnostics."""

        return self._canvas.getCompositionSnapshot()

    def set_current_image_id(self, image_id: UUID | None) -> bool:
        """Open one registered composition or clear active presentation state."""

        if image_id is None:
            self._session.clear_activation()
            self.toolContextChanged.emit()
            return True
        record = self._images.get(image_id)
        if record is None:
            return False
        self._canvas.openComposition(record.composition_id)
        self.toolContextChanged.emit()
        return True

    def current_image_id(self) -> UUID | None:
        """Resolve the active composition back to a SugarSubstitute image id."""

        composition_id = self._canvas.currentCompositionID()
        if composition_id is None:
            return None
        for image_id, record in self._images.items():
            if record.composition_id == composition_id:
                return image_id
        return None

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Activate one mask through the supported CuteCanvas facade."""

        accepted = bool(self._canvas.setActiveMaskID(mask_id))
        if accepted:
            self.toolContextChanged.emit()
        return accepted

    def set_canvas_tool_mode(self, tool_id: str) -> bool:
        """Apply one built-in or runtime-registered tool through CuteCanvas."""

        resolved = _PRODUCT_TOOL_TO_CONTROL_MODE.get(tool_id, tool_id)
        if resolved not in self._canvas.availableControlModes():
            return False
        return bool(self._canvas.setControlMode(resolved))

    def current_canvas_tool_id(self) -> str | None:
        """Return the built-in product ID or registered native mode identity."""

        control_mode = self._canvas.getControlMode()
        if control_mode in _CONTROL_MODE_TO_PRODUCT_TOOL:
            return _CONTROL_MODE_TO_PRODUCT_TOOL[control_mode]
        return (
            control_mode
            if control_mode in self._canvas.availableControlModes()
            else None
        )

    def active_image_has_mask_target(self, image_id: UUID | None) -> bool:
        """Return whether the routed image owns the active editable mask."""

        if image_id is None or image_id != self.current_image_id():
            return False
        record = self._images.get(image_id)
        active_mask_id = self._canvas.activeMaskID()
        if record is None or active_mask_id is None:
            return False
        return any(
            mask.mask_id == active_mask_id
            for mask in self._canvas.listMasksForComposition(record.composition_id)
        )

    def smart_select_ready(self) -> bool:
        """Return whether CuteCanvas reports its Smart Select model ready."""

        return bool(self._canvas.samCheckpointReady())

    def set_mask_properties(self, mask_id: UUID, *, color: QColor) -> bool:
        """Apply host-selected presentation color to one mask."""

        return bool(self._canvas.setMaskProperties(mask_id, color=color))

    def create_blank_mask(self, image_id: UUID, size: object) -> UUID | None:
        """Create one restricted editable mask in an explicitly named image."""

        if not self.set_current_image_id(image_id) or not isinstance(size, QSize):
            return None
        mask_id = self._canvas.createBlankMask(size)
        if mask_id is not None:
            self._apply_mask_policy(image_id, mask_id)
            self.toolContextChanged.emit()
        return mask_id

    def load_mask_from_file(self, image_id: UUID, path: Path) -> UUID | None:
        """Load one mask into an explicitly named image composition."""

        if not self.set_current_image_id(image_id):
            return None
        mask_id = self._canvas.loadMaskFromFile(str(path))
        if mask_id is not None:
            self._apply_mask_policy(image_id, mask_id)
            self.toolContextChanged.emit()
        return mask_id

    def replace_mask_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Replace one live mask's pixels while retaining its identity."""

        return bool(self._canvas.replaceMaskFromFile(mask_id, str(path)))

    def remove_mask_from_image(self, image_id: UUID, mask_id: UUID) -> bool:
        """Remove a mask association from its explicitly named composition."""

        record = self._images.get(image_id)
        if record is None:
            return False
        removed = bool(
            self._canvas.removeMaskFromComposition(record.composition_id, mask_id)
        )
        if removed:
            self.toolContextChanged.emit()
        return removed

    def image_has_masks(self, image_id: UUID | None) -> bool:
        """Return whether one registered image currently contains masks."""

        if image_id is None:
            return False
        record = self._images.get(image_id)
        return record is not None and bool(
            self._canvas.listMasksForComposition(record.composition_id)
        )

    def export_mask_image(self, mask_id: UUID) -> QImage | None:
        """Export a requested mask without changing active document state."""

        return self._canvas.exportMaskImage(mask_id)

    @staticmethod
    def _same_payload(
        record: InputDocumentImage,
        image: QImage,
        path: Path | None,
    ) -> bool:
        """Compare host cache identity without relying on document internals."""

        return record.payload_identity == id(image) and record.path == path

    def _apply_mask_policy(self, image_id: UUID, mask_id: UUID) -> None:
        """Apply the fixed product mask policy to a newly created mask layer."""

        record = self._images.get(image_id)
        if record is None:
            return
        for mask in self._canvas.listMasksForComposition(record.composition_id):
            if (
                mask.mask_id == mask_id
                and mask.scene_id is not None
                and mask.layer_id is not None
            ):
                self._canvas.setLayerInteractionPolicy(
                    mask.scene_id,
                    mask.layer_id,
                    _MASK_LAYER_POLICY,
                )
                return

    def _on_control_mode_changed(self, _control_mode: str) -> None:
        """Publish CuteCanvas mode changes using stable product tool identities."""

        tool_id = self.current_canvas_tool_id()
        if tool_id is not None:
            self.canvasToolChanged.emit(tool_id)


__all__ = ["InputCanvasDocument", "InputDocumentImage"]
