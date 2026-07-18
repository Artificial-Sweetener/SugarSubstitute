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

"""Define pure cube-stack presentation modes, targets, and animation frames."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.workflow import WorkflowDocumentKind
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)


class CubeStackPreference(StrEnum):
    """Store the user's durable cube-stack density preference."""

    EXPANDED = "expanded"
    COMPACT = "compact"


class CubeStackPresentationMode(StrEnum):
    """Name one derived visible or unavailable stack presentation target."""

    EXPANDED = "expanded"
    COMPACT = "compact"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CubeStackPresentationInput:
    """Carry authoritative facts used to derive one presentation target."""

    document_kind: WorkflowDocumentKind
    preference: CubeStackPreference
    temporary_expansion_count: int = 0


@dataclass(frozen=True, slots=True)
class CubeStackPresentationFrame:
    """Describe all interpolated geometry applied during one animation frame."""

    container_width: int
    item_width: int
    compact_progress: float
    material_progress: float
    editor_gutter_progress: float


def resolve_cube_stack_presentation_mode(
    state: CubeStackPresentationInput,
) -> CubeStackPresentationMode:
    """Derive the target without changing the durable preference."""

    if state.document_kind is WorkflowDocumentKind.DIRECT_COMFY:
        return CubeStackPresentationMode.UNAVAILABLE
    if state.temporary_expansion_count > 0:
        return CubeStackPresentationMode.EXPANDED
    return CubeStackPresentationMode(state.preference.value)


def target_frame_for_mode(
    mode: CubeStackPresentationMode,
    *,
    hidden_item_preference: CubeStackPreference,
) -> CubeStackPresentationFrame:
    """Return the exact endpoint frame for a derived presentation mode."""

    if mode is CubeStackPresentationMode.EXPANDED:
        return CubeStackPresentationFrame(
            container_width=CUBE_STACK_EXPANDED_WIDTH,
            item_width=CUBE_ITEM_EXPANDED_WIDTH,
            compact_progress=0.0,
            material_progress=0.0,
            editor_gutter_progress=0.0,
        )
    if mode is CubeStackPresentationMode.COMPACT:
        return CubeStackPresentationFrame(
            container_width=CUBE_STACK_COMPACT_WIDTH,
            item_width=CUBE_ITEM_COMPACT_WIDTH,
            compact_progress=1.0,
            material_progress=1.0,
            editor_gutter_progress=0.0,
        )
    hidden_item_width = (
        CUBE_ITEM_COMPACT_WIDTH
        if hidden_item_preference is CubeStackPreference.COMPACT
        else CUBE_ITEM_EXPANDED_WIDTH
    )
    return CubeStackPresentationFrame(
        container_width=0,
        item_width=hidden_item_width,
        compact_progress=(
            1.0 if hidden_item_preference is CubeStackPreference.COMPACT else 0.0
        ),
        material_progress=1.0,
        editor_gutter_progress=1.0,
    )


def interpolate_cube_stack_frame(
    start: CubeStackPresentationFrame,
    target: CubeStackPresentationFrame,
    progress: float,
) -> CubeStackPresentationFrame:
    """Interpolate one frame from fixed start geometry without accumulating drift."""

    clamped = max(0.0, min(1.0, float(progress)))
    return CubeStackPresentationFrame(
        container_width=_lerp_int(
            start.container_width,
            target.container_width,
            clamped,
        ),
        item_width=_lerp_int(start.item_width, target.item_width, clamped),
        compact_progress=_lerp_float(
            start.compact_progress,
            target.compact_progress,
            clamped,
        ),
        material_progress=_lerp_float(
            start.material_progress,
            target.material_progress,
            clamped,
        ),
        editor_gutter_progress=_lerp_float(
            start.editor_gutter_progress,
            target.editor_gutter_progress,
            clamped,
        ),
    )


def _lerp_int(start: int, target: int, progress: float) -> int:
    """Return one rounded integer interpolation."""

    return round(start + ((target - start) * progress))


def _lerp_float(start: float, target: float, progress: float) -> float:
    """Return one floating-point interpolation."""

    return start + ((target - start) * progress)


__all__ = [
    "CubeStackPreference",
    "CubeStackPresentationFrame",
    "CubeStackPresentationInput",
    "CubeStackPresentationMode",
    "interpolate_cube_stack_frame",
    "resolve_cube_stack_presentation_mode",
    "target_frame_for_mode",
]
