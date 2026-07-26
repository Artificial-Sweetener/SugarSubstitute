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

"""Define immutable contracts for reorder preview projection publication."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_preview import PromptReorderPreviewState


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionContext:
    """Identify viewport and target inputs for one preview publication."""

    source_revision: int
    layout_width: float
    viewport_width: int
    preview_layout_key: Hashable | None = None
    base_drag_layout_key: Hashable | None = None
    active_drop_target_identity: Hashable | None = None

    @classmethod
    def from_preview_state(
        cls,
        preview_state: PromptReorderPreviewState | None,
        *,
        source_revision: int,
        layout_width: float,
        viewport_width: int,
    ) -> PromptReorderPreviewProjectionContext:
        """Build context from one optional preview state and viewport identity."""

        return cls(
            source_revision=source_revision,
            layout_width=layout_width,
            viewport_width=viewport_width,
            preview_layout_key=(
                None if preview_state is None else preview_state.preview_layout_key
            ),
            base_drag_layout_key=(
                None if preview_state is None else preview_state.base_drag_layout_key
            ),
            active_drop_target_identity=(
                None
                if preview_state is None
                else preview_state.active_drop_target_identity
            ),
        )


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionInvalidation:
    """Describe geometry caches invalidated by one atomic publication."""

    clear_all_geometry_reason: str | None = None
    clear_base_drag_geometry_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshotCacheKey:
    """Identify one cached reorder projection document and prepared frame."""

    source_revision: int
    viewport_width: int
    layout_width_x100: int
    layout_key: Hashable | None
    active_drop_target_identity: Hashable | None
    render_plan_hash: str
    font_key: str
    palette_cache_key: int
    semantic_palette_hash: str
    snapshot_hash: str
    text_length: int
    rendered_ranges: tuple[tuple[int, tuple[int, int]], ...]
    owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, tuple[int, int]], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionPublication:
    """Publish all active reorder preview projection state atomically."""

    preview_state: PromptReorderPreviewState | None = None
    preview_document: PromptProjectionDocument | None = None
    preview_frame: PromptProjectionPreparedFrame | None = None
    preview_cache_key: PromptReorderProjectionSnapshotCacheKey | None = None
    base_drag_document: PromptProjectionDocument | None = None
    base_drag_frame: PromptProjectionPreparedFrame | None = None
    base_drag_cache_key: PromptReorderProjectionSnapshotCacheKey | None = None

    @property
    def is_active(self) -> bool:
        """Return whether this publication suppresses the live projection."""

        return self.preview_frame is not None


__all__ = [
    "PromptReorderPreviewProjectionContext",
    "PromptReorderPreviewProjectionInvalidation",
    "PromptReorderPreviewProjectionPublication",
    "PromptReorderProjectionSnapshotCacheKey",
]
