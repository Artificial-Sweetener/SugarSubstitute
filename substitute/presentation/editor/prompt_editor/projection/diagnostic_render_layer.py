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

"""Define immutable diagnostic underline commands consumed by painting."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QPixmap

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)


@dataclass(frozen=True, slots=True)
class PromptDiagnosticViewportIdentity:
    """Identify one exact layout and quantized diagnostic viewport."""

    layout_identity: PromptLayoutIdentity
    viewport_x: int
    viewport_y: int
    viewport_width: int
    viewport_height: int
    scroll_offset: int


@dataclass(frozen=True, slots=True)
class PromptDiagnosticFragmentKey:
    """Identify fragment geometry for one diagnostic and viewport revision."""

    diagnostic_id: str
    source_start: int
    source_end: int
    viewport: PromptDiagnosticViewportIdentity


@dataclass(frozen=True, slots=True)
class PromptDiagnosticLayerKey:
    """Identify one exact diagnostic, selection, viewport, and asset revision."""

    viewport: PromptDiagnosticViewportIdentity
    diagnostics: tuple[tuple[str, int, int], ...]
    anchor_position: int
    cursor_position: int
    color_rgba: int
    device_pixel_ratio_x100: int


@dataclass(frozen=True, slots=True)
class PromptDiagnosticUnderline:
    """Describe one viewport-local diagnostic underline fragment."""

    left: float
    bottom: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class PromptDiagnosticRenderLayer:
    """Contain the complete prepared diagnostic layer for one paint."""

    color_rgba: int
    underlines: tuple[PromptDiagnosticUnderline, ...]
    revision: PromptDiagnosticLayerKey | None = None
    wave_tile: QPixmap | None = None
    wave_height: float = 0.0


EMPTY_DIAGNOSTIC_RENDER_LAYER = PromptDiagnosticRenderLayer(
    color_rgba=0,
    underlines=(),
)


__all__ = [
    "EMPTY_DIAGNOSTIC_RENDER_LAYER",
    "PromptDiagnosticFragmentKey",
    "PromptDiagnosticLayerKey",
    "PromptDiagnosticRenderLayer",
    "PromptDiagnosticUnderline",
    "PromptDiagnosticViewportIdentity",
]
