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
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_document")

_BASE_LAYER_POLICY = LayerPolicy(
    selectable=False,
    movable=False,
    pixel_editable=False,
    reorderable=False,
    removable=False,
)
_MASK_LAYER_POLICY = LayerPolicy(
    selectable=True,
    movable=False,
    pixel_editable=True,
    reorderable=False,
    removable=False,
)
_EDITOR_POLICY = EditorPolicy(
    capabilities=frozenset(
        {
            EditorCapability.SELECT_PIXELS,
            EditorCapability.EDIT_PIXELS,
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
            return True
        record = self._images.get(image_id)
        if record is None:
            return False
        self._canvas.openComposition(record.composition_id)
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

        return bool(self._canvas.setActiveMaskID(mask_id))

    def set_mask_tool_mode(self, mode: str) -> None:
        """Apply one product-approved mask tool mode to the canvas."""

        control_modes = {
            "pan_zoom": CuteCanvas.CONTROL_MODE_PANZOOM,
            "brush": CuteCanvas.CONTROL_MODE_DRAW_BRUSH,
            "smart_select": CuteCanvas.CONTROL_MODE_SMART_SELECT,
        }
        resolved = control_modes.get(mode)
        if resolved is None:
            raise ValueError(f"Unsupported Input mask tool mode: {mode}")
        self._canvas.setControlMode(resolved)

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
        return mask_id

    def load_mask_from_file(self, image_id: UUID, path: Path) -> UUID | None:
        """Load one mask into an explicitly named image composition."""

        if not self.set_current_image_id(image_id):
            return None
        mask_id = self._canvas.loadMaskFromFile(str(path))
        if mask_id is not None:
            self._apply_mask_policy(image_id, mask_id)
        return mask_id

    def replace_mask_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Replace one live mask's pixels while retaining its identity."""

        return bool(self._canvas.replaceMaskFromFile(mask_id, str(path)))

    def remove_mask_from_image(self, image_id: UUID, mask_id: UUID) -> bool:
        """Remove a mask association from its explicitly named composition."""

        record = self._images.get(image_id)
        if record is None:
            return False
        return bool(
            self._canvas.removeMaskFromComposition(record.composition_id, mask_id)
        )

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


__all__ = ["InputCanvasDocument", "InputDocumentImage"]
