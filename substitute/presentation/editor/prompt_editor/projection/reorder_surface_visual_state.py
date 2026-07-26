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

"""Own atomic reorder chrome and projection-suppression surface state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from PySide6.QtCore import QRect

from .reorder_surface_chrome import (
    PromptReorderSurfaceChromeChip,
    PromptReorderSurfaceChromeSnapshot,
)
from .reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot

type PromptReorderSurfaceVisualMode = Literal["live", "preview"]

_EMPTY_SUPPRESSION: Mapping[int, PromptReorderProjectionPaintSnapshot] = (
    MappingProxyType({})
)


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceVisualPublication:
    """Carry one prepared surface chrome and suppression publication."""

    mode: PromptReorderSurfaceVisualMode
    chips: tuple[PromptReorderSurfaceChromeChip, ...]
    suppression_snapshots_by_index: Mapping[
        int,
        PromptReorderProjectionPaintSnapshot,
    ]


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceVisualContext:
    """Identify the projection frame that receives prepared surface visuals."""

    source_revision: int
    viewport_rect: QRect
    scroll_offset: int
    preview_generation: int | None


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceVisualState:
    """Publish the current atomic surface visual state."""

    revision: int = 0
    mode: PromptReorderSurfaceVisualMode = "live"
    chips: tuple[PromptReorderSurfaceChromeChip, ...] = ()
    suppression_snapshots_by_index: Mapping[
        int,
        PromptReorderProjectionPaintSnapshot,
    ] = _EMPTY_SUPPRESSION
    chrome_snapshot: PromptReorderSurfaceChromeSnapshot | None = None


class PromptReorderSurfaceVisualStateOwner:
    """Apply combined reorder surface publications through one state owner."""

    def __init__(self) -> None:
        """Initialize an empty live surface publication."""

        self._state = PromptReorderSurfaceVisualState()

    @property
    def state(self) -> PromptReorderSurfaceVisualState:
        """Return the current immutable surface visual state."""

        return self._state

    def publish(
        self,
        publication: PromptReorderSurfaceVisualPublication,
        *,
        context: PromptReorderSurfaceVisualContext,
    ) -> bool:
        """Publish both surface concerns and report whether either changed."""

        next_chrome = _chrome_snapshot(publication, context=context)
        current = self._state
        suppression_changed = not _same_snapshot_identities(
            current.suppression_snapshots_by_index,
            publication.suppression_snapshots_by_index,
        )
        if (
            not suppression_changed
            and current.mode == publication.mode
            and current.chips == publication.chips
            and current.chrome_snapshot == next_chrome
        ):
            return False
        suppression = (
            MappingProxyType(dict(publication.suppression_snapshots_by_index))
            if suppression_changed
            else current.suppression_snapshots_by_index
        )
        self._state = PromptReorderSurfaceVisualState(
            revision=current.revision + 1,
            mode=publication.mode,
            chips=publication.chips,
            suppression_snapshots_by_index=suppression,
            chrome_snapshot=next_chrome,
        )
        return True


def empty_reorder_surface_visual_publication() -> PromptReorderSurfaceVisualPublication:
    """Return the canonical empty live surface visual publication."""

    return PromptReorderSurfaceVisualPublication(
        mode="live",
        chips=(),
        suppression_snapshots_by_index=_EMPTY_SUPPRESSION,
    )


def _chrome_snapshot(
    publication: PromptReorderSurfaceVisualPublication,
    *,
    context: PromptReorderSurfaceVisualContext,
) -> PromptReorderSurfaceChromeSnapshot | None:
    """Bind prepared chrome to the exact receiving projection context."""

    if not publication.chips:
        return None
    return PromptReorderSurfaceChromeSnapshot(
        source_revision=context.source_revision,
        viewport_rect=QRect(context.viewport_rect),
        scroll_offset=context.scroll_offset,
        preview_generation=(
            context.preview_generation if publication.mode == "preview" else None
        ),
        mode=publication.mode,
        chips=publication.chips,
    )


def _same_snapshot_identities(
    current: Mapping[int, PromptReorderProjectionPaintSnapshot],
    candidate: Mapping[int, PromptReorderProjectionPaintSnapshot],
) -> bool:
    """Compare exact suppression ownership without deep snapshot equality."""

    return current.keys() == candidate.keys() and all(
        current[index] is snapshot for index, snapshot in candidate.items()
    )


__all__ = [
    "PromptReorderSurfaceVisualContext",
    "PromptReorderSurfaceVisualMode",
    "PromptReorderSurfaceVisualPublication",
    "PromptReorderSurfaceVisualState",
    "PromptReorderSurfaceVisualStateOwner",
    "empty_reorder_surface_visual_publication",
]
