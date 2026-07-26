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

"""Define exact immutable inputs for diagnostic-layer publication."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.aggregate import (
    PromptProjectionGeometry,
)

from .diagnostic_render_layer import (
    PromptDiagnosticLayerKey,
    PromptDiagnosticViewportIdentity,
)


@dataclass(frozen=True, slots=True)
class PromptDiagnosticLayerSnapshot:
    """Capture every input consumed by one diagnostic command publication."""

    key: PromptDiagnosticLayerKey
    visible_diagnostics: tuple[PromptDiagnostic, ...]
    selection: PromptProjectionSelection
    geometry: PromptProjectionGeometry
    viewport_rect: QRectF
    scroll_offset: float
    layout_identity: PromptLayoutIdentity
    color_rgba: int
    device_pixel_ratio: float

    @classmethod
    def capture(
        cls,
        *,
        visible_diagnostics: tuple[PromptDiagnostic, ...],
        selection: PromptProjectionSelection,
        geometry: PromptProjectionGeometry,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_identity: PromptLayoutIdentity,
        viewport_identity: PromptDiagnosticViewportIdentity,
        color_rgba: int,
        device_pixel_ratio: float,
    ) -> "PromptDiagnosticLayerSnapshot":
        """Capture detached Qt geometry and its exact revision key."""

        normalized_ratio = max(1.0, device_pixel_ratio)
        return cls(
            key=PromptDiagnosticLayerKey(
                viewport=viewport_identity,
                diagnostics=tuple(
                    (
                        diagnostic.diagnostic_id,
                        diagnostic.source_start,
                        diagnostic.source_end,
                    )
                    for diagnostic in visible_diagnostics
                ),
                anchor_position=selection.anchor_position,
                cursor_position=selection.cursor_position,
                color_rgba=color_rgba,
                device_pixel_ratio_x100=round(normalized_ratio * 100.0),
            ),
            visible_diagnostics=visible_diagnostics,
            selection=selection,
            geometry=geometry,
            viewport_rect=QRectF(viewport_rect),
            scroll_offset=scroll_offset,
            layout_identity=layout_identity,
            color_rgba=color_rgba,
            device_pixel_ratio=normalized_ratio,
        )


@dataclass(frozen=True, slots=True)
class PromptDiagnosticWarmState:
    """Bind cache misses to the exact snapshot that requested their work."""

    snapshot: PromptDiagnosticLayerSnapshot
    missing_diagnostics: tuple[PromptDiagnostic, ...]


__all__ = [
    "PromptDiagnosticLayerSnapshot",
    "PromptDiagnosticWarmState",
]
