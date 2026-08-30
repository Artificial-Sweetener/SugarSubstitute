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
from substitute.presentation.canvas.input.input_preview_binding import (
    InputDocumentPreviewBindings,
)
from substitute.presentation.canvas.input.input_document_view_lifetime import (
    InputDocumentViewLifetime,
)
from substitute.presentation.canvas.input.input_document_persistence import (
    InputDocumentPersistence,
)
from substitute.presentation.canvas.input.input_document_catalog import (
    InputDocumentCatalog,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContext,
)
from substitute.presentation.canvas.input.input_document_mask_opacity_history import (
    InputDocumentMaskOpacityHistory,
)
from substitute.presentation.canvas.input.input_document_tool_options import (
    InputDocumentToolOptions,
)
from substitute.presentation.canvas.input.input_generation_capture import (
    InputDocumentGenerationCapture,
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
            EditorCapability.TRANSFORM_LAYERS,
            EditorCapability.PAINT,
        }
    ),
    noneditable_paint=NonEditablePaintPolicy.REJECT,
)


class InputCanvasDocument(QObject):
    """Provide one long-lived CuteCanvas Input document to application services."""

    imageMaterialized = Signal(object, str)
    canvasToolChanged = Signal(str)
    brushPresetChanged = Signal()
    maskContentChanged = Signal()
    activeMaskChanged = Signal(object)

    def __init__(
        self,
        *,
        features: tuple[str, ...],
        execution_runtime: ExecutionRuntime,
    ) -> None:
        """Create the durable document, detached session, and editing surface."""

        super().__init__()
        self._document = CanvasDocument()
        self._runtime = CanvasDocumentRuntime(
            self._document,
            execution_runtime=execution_runtime,
        )
        self._closed = False
        self._view_lifetime = InputDocumentViewLifetime(self._finalize_close)
        self._session = CanvasViewSession()
        self._canvas = CuteCanvas(
            document=self._document,
            document_runtime=self._runtime,
            features=features,
            session=self._session,
        )
        self._canvas.setEditorPolicy(_EDITOR_POLICY)
        self._view_lifetime.register(self._canvas)
        self._catalog = InputDocumentCatalog(
            lambda composition_id: self._canvas.listMasksForComposition(composition_id),
        )
        self._tool_context = InputCanvasToolContext(
            canvas=self._canvas,
            catalog=self._catalog,
            current_image_id=self.current_image_id,
            parent=self,
        )
        self._mask_opacity_history = InputDocumentMaskOpacityHistory(
            document=self._document,
            catalog=self._catalog,
        )
        self._preview_bindings = InputDocumentPreviewBindings(
            document=self._document,
            runtime=self._runtime,
            composition_for_image=self._catalog.composition_for_image,
            mask_layer_for_image=self._catalog.mask_layer_for_image,
            view_lifetime=self._view_lifetime,
        )
        self._generation_capture = InputDocumentGenerationCapture(
            composition_for_image=self._catalog.composition_for_image,
            composition_for_mask=self._catalog.composition_for_mask,
            content_reference=self._document.content_reference,
            capture_image=self._canvas.captureEmbeddedImageExport,
            capture_mask=lambda mask_id, composition_id: self._canvas.captureMaskExport(
                mask_id,
                composition_id=composition_id,
            ),
        )
        self._editable_persistence = InputDocumentPersistence(
            document=self._document,
            canvas=self._canvas,
            install_restored_compositions=self._install_restored_compositions,
        )
        self._tool_options = InputDocumentToolOptions(
            canvas=self._canvas,
            brush_preset_changed=self.brushPresetChanged,
            mask_content_changed=self.maskContentChanged,
            parent=self,
        )
        self._canvas.controlModeChanged.connect(self._on_control_mode_changed)
        self._canvas.compositionSelectionChanged.connect(
            self._on_composition_selection_changed
        )
        self._canvas.selectedLayerChanged.connect(self._on_selected_layer_changed)
        self._canvas.brushPresetChanged.connect(
            lambda _preset: self.brushPresetChanged.emit()
        )
        self._canvas.maskUndoStackChanged.connect(self._on_mask_undo_stack_changed)
        self._canvas.layerPixelsChanged.connect(self._on_layer_pixels_changed)

    @property
    def canvas(self) -> CuteCanvas:
        """Return the single widget presenting this document."""

        return self._canvas

    def _on_selected_layer_changed(self, _selection: object) -> None:
        """Publish the active mask identity after CuteCanvas layer selection."""

        self._tool_options.publish_active_mask_changed()
        self.activeMaskChanged.emit(self.active_mask_id())

    @property
    def runtime(self) -> CanvasDocumentRuntime:
        """Return the document-scoped runtime bound to this Input document."""

        return self._runtime

    @property
    def preview_bindings(self) -> InputDocumentPreviewBindings:
        """Return the source resolver used by live editor-node previews."""
        return self._preview_bindings

    @property
    def generation_capture(self) -> InputDocumentGenerationCapture:
        """Return coherent Input generation capture without materialization policy."""
        return self._generation_capture

    @property
    def editable_persistence(self) -> InputDocumentPersistence:
        """Return complete editable document persistence."""
        return self._editable_persistence

    @property
    def tool_options(self) -> InputDocumentToolOptions:
        """Return the contextual brush and selection-operation adapter."""
        return self._tool_options

    @property
    def tool_context(self) -> InputCanvasToolContext:
        """Return the semantic capability context used by the tool palette."""

        return self._tool_context

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
        existing = self._catalog.record_for(image_id)
        if (
            existing is not None
            and existing.payload_revision == image.cacheKey()
            and existing.path == normalized_path
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
                composition_id=image_id,
            )
        self._catalog.record(
            image_id,
            composition_id,
            path=normalized_path,
            payload_revision=image.cacheKey(),
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

        return self._catalog.contains(image_id)

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the application-owned source path for one image."""

        return self._catalog.image_path(image_id)

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Remove an already-authorized unreferenced image composition."""

        record = self._catalog.remove(image_id)
        if record is None:
            return False
        self._canvas.removeComposition(record.composition_id)
        self._tool_context.refresh()
        self._tool_options.publish_composition_changed()
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
        record = self._catalog.record_for(image_id)
        if record is None:
            return False
        self._canvas.openComposition(record.composition_id)
        return True

    def current_image_id(self) -> UUID | None:
        """Resolve the active composition back to a SugarSubstitute image id."""

        composition_id = self._canvas.currentCompositionID()
        if composition_id is None:
            return None
        return self._catalog.image_id_for_composition(composition_id)

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Activate one mask through the supported CuteCanvas facade."""

        accepted = bool(self._canvas.setActiveMaskID(mask_id))
        return accepted

    def set_canvas_operation(self, operation_id: str) -> bool:
        """Activate one registry-selected CuteCanvas document operation."""

        if operation_id not in self._canvas.availableControlModes():
            return False
        return bool(self._canvas.setControlMode(operation_id))

    def current_canvas_operation(self) -> str | None:
        """Return the currently effective CuteCanvas document operation."""

        control_mode = self._canvas.getControlMode()
        return (
            control_mode
            if control_mode in self._canvas.availableControlModes()
            else None
        )

    def active_mask_id(self) -> UUID | None:
        """Return the authoritative active mask identity."""

        return self._canvas.activeMaskID()

    def set_mask_properties(self, mask_id: UUID, *, color: QColor) -> bool:
        """Apply host-selected presentation color to one mask."""

        changed = bool(self._canvas.setMaskProperties(mask_id, color=color))
        if changed:
            self._tool_options.publish_mask_properties_changed()
        return changed

    def set_mask_visual_opacity(self, mask_id: UUID, opacity: float) -> bool:
        """Apply presentation-only opacity without changing mask coverage."""

        return bool(self._canvas.setMaskProperties(mask_id, opacity=opacity))

    def commit_mask_visual_opacity_edit(
        self,
        mask_ids: tuple[UUID, ...],
        *,
        before: float,
        after: float,
    ) -> bool:
        """Commit one node's already-previewed opacity as one scene history edit."""

        return self._mask_opacity_history.commit(
            mask_ids,
            before=before,
            after=after,
        )

    def mask_visual_opacity(self, mask_id: UUID) -> float | None:
        """Return one materialized mask layer's current visual opacity."""

        composition_id = self._catalog.composition_for_mask(mask_id)
        if composition_id is None:
            return None
        mask = next(
            (
                candidate
                for candidate in self._canvas.listMasksForComposition(composition_id)
                if candidate.mask_id == mask_id
            ),
            None,
        )
        return None if mask is None or mask.opacity is None else float(mask.opacity)

    def create_blank_mask(self, image_id: UUID, size: object) -> UUID | None:
        """Create one restricted editable mask in an explicitly named image."""

        if not self.set_current_image_id(image_id) or not isinstance(size, QSize):
            return None
        mask_id = self._canvas.createBlankMask(size, undoable=False)
        if mask_id is not None:
            self._apply_mask_policy(image_id, mask_id)
            self._tool_context.refresh()
            self._tool_options.publish_mask_inventory_changed()
        return mask_id

    def load_mask_from_file(self, image_id: UUID, path: Path) -> UUID | None:
        """Load one mask into an explicitly named image composition."""

        if not self.set_current_image_id(image_id):
            return None
        mask_id = self._canvas.loadMaskFromFile(str(path), undoable=False)
        if mask_id is not None:
            self._apply_mask_policy(image_id, mask_id)
            self._tool_context.refresh()
            self._tool_options.publish_mask_inventory_changed()
        return mask_id

    def replace_mask_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Replace one live mask's pixels while retaining its identity."""

        return bool(self._canvas.replaceMaskFromFile(mask_id, str(path)))

    def remove_mask_from_image(self, image_id: UUID, mask_id: UUID) -> bool:
        """Remove a mask association from its explicitly named composition."""

        record = self._catalog.record_for(image_id)
        if record is None:
            return False
        removed = bool(
            self._canvas.removeMaskFromComposition(record.composition_id, mask_id)
        )
        if removed:
            self._tool_context.refresh()
            self._tool_options.publish_mask_inventory_changed()
        return removed

    def image_has_masks(self, image_id: UUID | None) -> bool:
        """Return whether one registered image currently contains masks."""

        if image_id is None:
            return False
        return self._catalog.has_masks(image_id)

    def export_mask_image(self, mask_id: UUID) -> QImage | None:
        """Export a requested mask without changing active document state."""

        return self._canvas.exportMaskImage(mask_id)

    def contains_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Return whether an exact mask identity belongs to one Input image."""

        return self._catalog.contains_mask(image_id, mask_id)

    def _install_restored_compositions(
        self,
        composition_ids: tuple[UUID, ...],
    ) -> None:
        """Install restored composition identities before file fallback hydration."""
        self._catalog.restore_compositions(composition_ids)
        self._tool_context.refresh()
        self._tool_options.publish_composition_changed()

    def close(self) -> None:
        """Release the Input view, document runtime, and durable document."""

        if self._closed:
            return
        self._closed = True
        self._view_lifetime.close()

    def _finalize_close(self) -> None:
        """Close document authority after every mounted view has been destroyed."""

        self._runtime.close()
        self._document.close()

    def _apply_mask_policy(self, image_id: UUID, mask_id: UUID) -> None:
        """Apply the fixed product mask policy to a newly created mask layer."""

        record = self._catalog.record_for(image_id)
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

        operation_id = self.current_canvas_operation()
        if operation_id is not None:
            self.canvasToolChanged.emit(operation_id)

    def _on_composition_selection_changed(self, _composition_id: object) -> None:
        """Publish presentation concerns derived from the active composition."""

        self._tool_options.publish_composition_changed()

    def _on_mask_undo_stack_changed(self, _mask_id: UUID) -> None:
        """Publish durable mask-history changes to Input document consumers."""

        self.maskContentChanged.emit()
        self._tool_options.publish_mask_content_changed()

    def _on_layer_pixels_changed(
        self,
        _scene_id: UUID,
        _layer_id: UUID,
        resource_id: UUID,
    ) -> None:
        """Publish generic pixel edits only for mask resources owned by Input."""
        if self._catalog.contains_mask_resource(resource_id):
            self.maskContentChanged.emit()
            self._tool_options.publish_mask_content_changed()


__all__ = ["InputCanvasDocument"]
