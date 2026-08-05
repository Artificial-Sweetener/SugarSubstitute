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

"""Adapt CuteCanvas brush and selection state to contextual Input options."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID

from PySide6.QtCore import QRect, QRectF, QSize
from PySide6.QtGui import QColor, QImage
from cutecanvas import (
    BrushPreset,
    CuteCanvas,
    EditorTransformCommand,
    EditorTransformSnapshot,
    EditorTransformTarget,
    FloatingPixelSnapshot,
    LayerEdgeOperation,
    MaskInfo,
)


class ToolOptionsSignalPort(Protocol):
    """Describe one host signal exposed to contextual tool controls."""

    def connect(self, callback: object) -> object:
        """Connect one options-state listener."""

    def emit(self, *args: object) -> None:
        """Publish one options-state change."""


class InputDocumentToolOptions:
    """Own the Input toolbar's focused CuteCanvas option operations."""

    def __init__(
        self,
        *,
        canvas: CuteCanvas,
        brush_preset_changed: ToolOptionsSignalPort,
        mask_content_changed: ToolOptionsSignalPort,
        tool_context_changed: ToolOptionsSignalPort,
    ) -> None:
        """Bind the editor surface and host-owned context signals."""
        self._canvas = canvas
        self.brushPresetChanged = brush_preset_changed
        self.maskContentChanged = mask_content_changed
        self.pixelSelectionChanged = cast(
            ToolOptionsSignalPort,
            canvas.pixelSelectionChanged,
        )
        self.floatingPixelEditChanged = cast(
            ToolOptionsSignalPort,
            canvas.floatingPixelEditChanged,
        )
        self.editorTransformChanged = cast(
            ToolOptionsSignalPort,
            canvas.editorTransformChanged,
        )
        self.canvasOperationChanged = cast(
            ToolOptionsSignalPort,
            canvas.controlModeChanged,
        )
        self.canvasViewChanged = cast(
            ToolOptionsSignalPort,
            canvas.zoomChanged,
        )
        self.selectionModificationCompleted = cast(
            ToolOptionsSignalPort,
            canvas.pixelSelectionModificationCompleted,
        )
        self.layerEdgeModificationCompleted = cast(
            ToolOptionsSignalPort,
            canvas.layerEdgeModificationCompleted,
        )
        self.toolContextChanged = tool_context_changed

    def active_mask_id(self) -> UUID | None:
        """Return the authoritative active mask identity."""
        return self._canvas.activeMaskID()

    def brush_preset(self) -> BrushPreset:
        """Return the active immutable CuteCanvas brush definition."""
        return self._canvas.brushPreset()

    def set_brush_preset(self, preset: BrushPreset) -> bool:
        """Replace the complete active CuteCanvas brush definition."""
        return bool(self._canvas.setBrushPreset(preset))

    def brush_preview_color(self) -> QColor:
        """Return the active editable mask color for brush presentation."""

        active_mask_id = self._canvas.activeMaskID()
        composition_id = self._canvas.currentCompositionID()
        if active_mask_id is not None and composition_id is not None:
            active_mask = next(
                (
                    mask
                    for mask in self._canvas.listMasksForComposition(composition_id)
                    if mask.mask_id == active_mask_id
                ),
                None,
            )
            if active_mask is not None and active_mask.color is not None:
                color = QColor(active_mask.color)
                if color.isValid():
                    return color
        return QColor(255, 255, 255)

    def render_brush_tip_preview(
        self,
        logical_size: QSize,
        *,
        device_pixel_ratio: float,
        color: QColor,
    ) -> QImage:
        """Render a compact DPR-aware preview from the active brush definition."""
        return self._canvas.renderBrushTipPreview(
            logical_size,
            device_pixel_ratio=device_pixel_ratio,
            color=color,
        )

    def has_pixel_selection(self) -> bool:
        """Return whether the active composition owns nonempty pixel selection."""

        state = self._canvas.pixelSelectionState()
        return state is not None and state.has_selection

    def clear_pixel_selection(self) -> bool:
        """Clear the active pixel selection through CuteCanvas history ownership."""
        return bool(self._canvas.clearPixelSelection())

    def clear_selected_pixels(self) -> bool:
        """Clear selected coverage through CuteCanvas pixel-edit ownership."""
        return bool(self._canvas.deleteSelectedPixels())

    def pixel_selection_panel_bounds(self) -> QRect | None:
        """Return active selection bounds mapped into logical canvas coordinates."""
        state = self._canvas.pixelSelectionState()
        if state is None or not state.has_selection or state.bounds is None:
            return None
        panel_bounds = self._canvas.sceneToPanelRect(QRectF(state.bounds))
        return None if panel_bounds is None else panel_bounds.toAlignedRect()

    def current_canvas_operation(self) -> str:
        """Return the active public CuteCanvas interaction mode."""
        return self._canvas.getControlMode()

    def set_canvas_operation(self, operation_id: str) -> bool:
        """Activate one public CuteCanvas interaction mode."""
        return bool(self._canvas.setControlMode(operation_id))

    def floating_pixel_edit_active(self) -> bool:
        """Return whether selected pixels currently own unresolved content."""
        return self._canvas.floatingPixelEditState() is not None

    def floating_pixel_panel_bounds(
        self,
        state: FloatingPixelSnapshot,
    ) -> QRect | None:
        """Map one floating selection frame into logical canvas coordinates."""

        if state.bounds is None:
            return None
        panel_bounds = self._canvas.sceneToPanelRect(QRectF(state.bounds))
        return None if panel_bounds is None else panel_bounds.toAlignedRect()

    def apply_floating_pixel_edit(self) -> bool:
        """Resolve selected floating pixels through the public document history."""
        return bool(self._canvas.anchorFloatingPixels())

    def cancel_floating_pixel_edit(self) -> bool:
        """Restore selected floating pixels through the public document owner."""
        return bool(self._canvas.cancelFloatingPixels())

    def transform_state(self, target: EditorTransformTarget) -> EditorTransformSnapshot:
        """Return current availability and frame for one explicit affine target."""
        return self._canvas.editorTransformState(target)

    def activate_transform(self, target: EditorTransformTarget) -> bool:
        """Activate the shared affine tool against one explicit content target."""
        return bool(self._canvas.activateEditorTransform(target))

    def apply_transform_command(self, command: EditorTransformCommand) -> bool:
        """Apply one frame-relative command to the cumulative affine preview."""
        return bool(self._canvas.applyEditorTransformCommand(command))

    def apply_transform(self) -> bool:
        """Commit the complete affine preview through CuteCanvas history."""
        return bool(self._canvas.applyEditorTransform())

    def cancel_transform(self) -> bool:
        """Discard the complete affine preview through CuteCanvas ownership."""
        return bool(self._canvas.cancelEditorTransform())

    def transform_panel_bounds(self, target: EditorTransformTarget) -> QRect | None:
        """Return one target's live affine frame in logical canvas coordinates."""
        state = self._canvas.editorTransformState(target)
        if not state.allowed or state.corners is None:
            return None
        xs = tuple(point.x() for point in state.corners)
        ys = tuple(point.y() for point in state.corners)
        scene_bounds = QRectF(
            min(xs),
            min(ys),
            max(xs) - min(xs),
            max(ys) - min(ys),
        )
        panel_bounds = self._canvas.sceneToPanelRect(scene_bounds)
        return None if panel_bounds is None else panel_bounds.toAlignedRect()

    def begin_pixel_selection_modification_preview(self) -> UUID | None:
        """Capture active selection as one reversible preview base."""

        return self._canvas.beginPixelSelectionModificationPreview()

    def update_pixel_selection_modification_preview(
        self,
        session_id: UUID,
        operation: LayerEdgeOperation,
        radius: float,
    ) -> UUID | None:
        """Replace selection preview from its captured original."""

        return self._canvas.updatePixelSelectionModificationPreview(
            session_id,
            operation,
            radius,
        )

    def settle_pixel_selection_modification_preview(self, session_id: UUID) -> bool:
        """Commit the current selection preview once."""

        return self._canvas.settlePixelSelectionModificationPreview(session_id)

    def cancel_pixel_selection_modification_preview(self, session_id: UUID) -> bool:
        """Restore the captured selection without recording history."""

        return self._canvas.cancelPixelSelectionModificationPreview(session_id)

    def mask_layers(self) -> tuple[MaskInfo, ...]:
        """Return mask layers in current composition stack order."""
        composition_id = self._canvas.currentCompositionID()
        return (
            ()
            if composition_id is None
            else self._canvas.listMasksForComposition(composition_id)
        )

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Activate one mask and notify contextual canvas consumers."""
        changed = bool(self._canvas.setActiveMaskID(mask_id))
        if changed:
            self.toolContextChanged.emit()
        return changed

    def set_mask_visual_opacity(self, mask_id: UUID, opacity: float) -> bool:
        """Set final visual-only opacity without changing mask coverage."""
        return bool(self._canvas.setMaskProperties(mask_id, opacity=opacity))

    def begin_mask_edge_preview(self, mask_id: UUID) -> UUID | None:
        """Begin one nonmodal whole-mask edge preview."""
        return self._canvas.beginMaskEdgePreview(mask_id)

    def update_layer_edge_preview(
        self,
        session_id: UUID,
        operation: LayerEdgeOperation,
        radius: float,
    ) -> UUID | None:
        """Replace a whole-layer preview with its latest requested value."""
        return self._canvas.updateLayerEdgePreview(session_id, operation, radius)

    def settle_layer_edge_preview(self, session_id: UUID) -> bool:
        """Commit the current whole-layer preview once."""
        return self._canvas.settleLayerEdgePreview(session_id)

    def cancel_layer_edge_preview(self, session_id: UUID) -> bool:
        """Discard a whole-layer preview without changing coverage."""
        return self._canvas.cancelLayerEdgePreview(session_id)


__all__ = ["InputDocumentToolOptions"]
