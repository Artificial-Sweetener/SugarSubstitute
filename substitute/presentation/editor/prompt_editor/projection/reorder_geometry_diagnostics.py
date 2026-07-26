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

"""Build prompt-safe diagnostic context for reorder geometry operations."""

from __future__ import annotations

import hashlib

from .reorder_geometry_cache_keys import (
    PromptReorderChipGeometryCacheKey,
    PromptReorderPlacementGeometryCacheKey,
)
from .reorder_placement_geometry import PromptReorderPlacementSnapshot
from .reorder_preview import PromptReorderPreviewState


def reorder_geometry_cache_context(
    key: PromptReorderChipGeometryCacheKey | PromptReorderPlacementGeometryCacheKey,
    *,
    prefix: str = "geometry_cache",
) -> dict[str, object]:
    """Return hashed identity and structural counts without exposing prompt text."""

    snapshot_key = key.snapshot
    layout_key = key.layout
    viewport_key = key.viewport
    return {
        f"{prefix}_text_length": len(snapshot_key.text),
        f"{prefix}_snapshot_hash": _safe_key_hash(snapshot_key),
        f"{prefix}_chip_range_count": len(snapshot_key.chip_rendered_ranges),
        f"{prefix}_owned_range_count": len(snapshot_key.chip_owned_ranges),
        f"{prefix}_gap_range_count": len(snapshot_key.gap_ranges),
        f"{prefix}_layout_hash": _safe_key_hash(layout_key),
        f"{prefix}_row_count": len(layout_key.rows),
        f"{prefix}_gap_count": len(layout_key.gaps),
        f"{prefix}_viewport_width": viewport_key.viewport_width,
        f"{prefix}_viewport_height": viewport_key.viewport_height,
        f"{prefix}_scroll_offset": viewport_key.scroll_offset,
        f"{prefix}_layout_width_x100": viewport_key.layout_width_x100,
    }


def reorder_geometry_gesture_id(
    preview_state: PromptReorderPreviewState | None,
) -> int | None:
    """Return the active gesture identity for geometry diagnostics."""

    return None if preview_state is None else preview_state.instrumentation_gesture_id


def reorder_geometry_event_id(
    preview_state: PromptReorderPreviewState | None,
) -> int | None:
    """Return the active input-event identity for geometry diagnostics."""

    return None if preview_state is None else preview_state.instrumentation_event_id


def reorder_geometry_reason(preview_state: PromptReorderPreviewState | None) -> str:
    """Return the active preview reason for geometry diagnostics."""

    return "" if preview_state is None else preview_state.instrumentation_reason


def reorder_placement_context(
    snapshot: PromptReorderPlacementSnapshot,
) -> dict[str, object]:
    """Return stable structural diagnostics for one placement publication."""

    return {
        "placement_count": len(snapshot.placements),
        "visual_line_count": snapshot.visual_line_count,
        "layout_width": f"{snapshot.layout_width:.2f}",
        "content_height": f"{snapshot.content_height:.2f}",
    }


def _safe_key_hash(key: object) -> str:
    """Return a compact diagnostic hash without logging prompt text."""

    return hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]


__all__ = [
    "reorder_geometry_cache_context",
    "reorder_geometry_event_id",
    "reorder_geometry_gesture_id",
    "reorder_geometry_reason",
    "reorder_placement_context",
]
