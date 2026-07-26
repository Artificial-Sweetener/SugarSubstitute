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

"""Prepare reorder landing paint state from explicit visual style policy."""

from __future__ import annotations

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from .chip_visuals import PromptChipVisual
from .reorder_render_state import PromptReorderLandingPreviewPaintState
from .reorder_visual_style import PromptReorderVisualStyle

_LANDING_PREVIEW_OUTLINE_OPACITY = 0.82
_LANDING_PREVIEW_OUTLINE_WIDTH = 1.25
_PENDING_LANDING_PREVIEW_OUTLINE_OPACITY = 0.52


def prompt_reorder_landing_geometry_paint_state(
    visual_style: PromptReorderVisualStyle,
    geometry: PromptReorderChipGeometry,
) -> PromptReorderLandingPreviewPaintState:
    """Prepare authoritative landing geometry with active outline policy."""

    return PromptReorderLandingPreviewPaintState(
        style=visual_style.outline_style(
            outline_width=_LANDING_PREVIEW_OUTLINE_WIDTH,
            opacity=_LANDING_PREVIEW_OUTLINE_OPACITY,
        ),
        geometry=geometry,
    )


def prompt_reorder_pending_landing_paint_state(
    visual_style: PromptReorderVisualStyle,
    visual: PromptChipVisual,
) -> PromptReorderLandingPreviewPaintState:
    """Prepare pending held-shadow chrome with provisional outline policy."""

    return PromptReorderLandingPreviewPaintState(
        style=visual_style.outline_style(
            outline_width=_LANDING_PREVIEW_OUTLINE_WIDTH,
            opacity=_PENDING_LANDING_PREVIEW_OUTLINE_OPACITY,
        ),
        visual=visual,
    )


__all__ = [
    "prompt_reorder_landing_geometry_paint_state",
    "prompt_reorder_pending_landing_paint_state",
]
