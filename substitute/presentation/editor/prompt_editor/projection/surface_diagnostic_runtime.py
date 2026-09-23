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

"""Compose diagnostic presentation for the prompt projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRectF
from PySide6.QtWidgets import QWidget

from ..core.projection.caret import PromptProjectionSelection
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionFrameStatePublisher
from .session import PromptProjectionSession
from .surface_graph_effects import PromptProjectionSurfaceGraphEffects
from .theme import qcolor_from_rgb, semantic_palette_from_theme


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceDiagnosticBindings:
    """Declare state and visual dependencies for diagnostic presentation."""

    parent: QObject
    viewport: QWidget
    session: PromptProjectionSession
    layout: PromptLayoutEditToFrameCoordinator
    frame_state: PromptProjectionFrameStatePublisher
    graph_effects: PromptProjectionSurfaceGraphEffects
    selection: Callable[[], PromptProjectionSelection]
    scroll_offset: Callable[[], float]
    is_alive: Callable[[], bool]


def build_prompt_projection_surface_diagnostics(
    bindings: PromptProjectionSurfaceDiagnosticBindings,
) -> PromptDiagnosticLayerOwner:
    """Build the diagnostic layer owner around authoritative surface state."""

    return PromptDiagnosticLayerOwner(
        parent=bindings.parent,
        diagnostics=lambda: bindings.session.diagnostics,
        replace_diagnostics=bindings.session.set_diagnostics,
        clear_diagnostics=bindings.session.clear_diagnostics,
        selection=bindings.selection,
        geometry=lambda: bindings.layout.frame.geometry,
        layout_identity=lambda: bindings.frame_state.current_layout_identity(
            bindings.layout.frame.output
        ),
        viewport_rect=lambda: QRectF(bindings.viewport.rect()),
        scroll_offset=bindings.scroll_offset,
        color_rgba=lambda: int(
            qcolor_from_rgb(semantic_palette_from_theme().error_foreground).rgba()
        ),
        device_pixel_ratio=lambda: float(bindings.viewport.devicePixelRatioF()),
        is_alive=bindings.is_alive,
        request_update=bindings.graph_effects.diagnostic_layer_changed,
    )


__all__ = [
    "PromptProjectionSurfaceDiagnosticBindings",
    "build_prompt_projection_surface_diagnostics",
]
