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

"""Define the focused document contract consumed by Input tool options."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage
from cutecanvas import (
    BrushPreset,
    EditorTransformCommand,
    EditorTransformSnapshot,
    EditorTransformTarget,
    FloatingPixelSnapshot,
    LayerEdgeOperation,
    MaskInfo,
)


class OptionsSignalPort(Protocol):
    """Describe Qt-compatible signal subscription used by options widgets."""

    def connect(self, callback: object) -> object:
        """Connect one callback."""

    def emit(self, *args: object) -> None:
        """Publish one state change."""


class InputToolOptionsDocumentPort(Protocol):
    """Describe brush and pixel-selection operations for contextual controls."""

    brushPresetChanged: OptionsSignalPort
    maskContentChanged: OptionsSignalPort
    pixelSelectionChanged: OptionsSignalPort
    floatingPixelEditChanged: OptionsSignalPort
    editorTransformChanged: OptionsSignalPort
    canvasOperationChanged: OptionsSignalPort
    canvasViewChanged: OptionsSignalPort
    selectionModificationCompleted: OptionsSignalPort
    layerEdgeModificationCompleted: OptionsSignalPort

    @property
    def maskLayersChanged(self) -> OptionsSignalPort:
        """Return mask-inventory change publication."""

    @property
    def brushContextChanged(self) -> OptionsSignalPort:
        """Return brush-presentation context publication."""

    @property
    def editorContextChanged(self) -> OptionsSignalPort:
        """Return non-selection editor-context publication."""

    def brush_preset(self) -> BrushPreset:
        """Return the active immutable brush definition."""

    def set_brush_preset(self, preset: BrushPreset) -> bool:
        """Replace the active immutable brush definition."""

    def brush_preview_color(self) -> QColor:
        """Return the detached color of the active editable layer."""

    def render_brush_tip_preview(
        self,
        logical_size: QSize,
        *,
        device_pixel_ratio: float,
        color: QColor,
    ) -> QImage:
        """Render a DPR-aware brush-tip image."""

    def has_pixel_selection(self) -> bool:
        """Return whether the active composition owns nonempty pixel selection."""

    def clear_pixel_selection(self) -> bool:
        """Clear the active composition pixel selection."""

    def clear_selected_pixels(self) -> bool:
        """Clear selected coverage from the active editable layer."""

    def pixel_selection_panel_bounds(self) -> QRect | None:
        """Return active selection bounds in logical canvas coordinates."""

    def canvas_content_panel_bounds(self) -> QRect | None:
        """Return active scene bounds in logical canvas coordinates."""

    def current_canvas_operation(self) -> str:
        """Return the active CuteCanvas interaction operation."""

    def set_canvas_operation(self, operation_id: str) -> bool:
        """Activate one public CuteCanvas interaction operation."""

    def floating_pixel_edit_active(self) -> bool:
        """Return whether selected pixels own unresolved content."""

    def floating_pixel_panel_bounds(
        self,
        state: FloatingPixelSnapshot,
    ) -> QRect | None:
        """Map one floating selection frame into logical canvas coordinates."""

    def apply_floating_pixel_edit(self) -> bool:
        """Resolve selected floating pixels as one history edit."""

    def cancel_floating_pixel_edit(self) -> bool:
        """Restore selected floating pixels without committing."""

    def transform_state(self, target: EditorTransformTarget) -> EditorTransformSnapshot:
        """Return current availability and scene-space frame for one target."""

    def activate_transform(self, target: EditorTransformTarget) -> bool:
        """Activate the shared affine tool against one explicit target."""

    def apply_transform_command(self, command: EditorTransformCommand) -> bool:
        """Apply one cumulative command to the live affine preview."""

    def apply_transform(self) -> bool:
        """Commit the complete affine preview."""

    def cancel_transform(self) -> bool:
        """Discard the complete affine preview."""

    def transform_panel_bounds(self, target: EditorTransformTarget) -> QRect | None:
        """Return one target's live affine frame in logical canvas coordinates."""

    def begin_pixel_selection_modification_preview(self) -> UUID | None:
        """Capture active selection as one reversible preview base."""

    def update_pixel_selection_modification_preview(
        self,
        session_id: UUID,
        operation: LayerEdgeOperation,
        radius: float,
    ) -> UUID | None:
        """Replace selection preview from its captured original."""

    def settle_pixel_selection_modification_preview(self, session_id: UUID) -> bool:
        """Commit the current selection preview once."""

    def cancel_pixel_selection_modification_preview(self, session_id: UUID) -> bool:
        """Restore the captured selection without recording history."""

    def mask_layers(self) -> tuple[MaskInfo, ...]:
        """Return current composition mask-layer presentation state."""

    def active_mask_id(self) -> UUID | None:
        """Return the active mask identity."""

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Activate one mask layer."""

    def begin_mask_edge_preview(self, mask_id: UUID) -> UUID | None:
        """Begin one nonmodal whole-mask edge preview."""

    def update_layer_edge_preview(
        self,
        session_id: UUID,
        operation: LayerEdgeOperation,
        radius: float,
    ) -> UUID | None:
        """Replace a whole-layer preview with its latest value."""

    def settle_layer_edge_preview(self, session_id: UUID) -> bool:
        """Commit one whole-layer preview after its current work finishes."""

    def cancel_layer_edge_preview(self, session_id: UUID) -> bool:
        """Discard one whole-layer preview without a durable edit."""


__all__ = ["InputToolOptionsDocumentPort", "OptionsSignalPort"]
