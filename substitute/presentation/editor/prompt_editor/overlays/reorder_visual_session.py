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

"""Own immutable presentation facts for one reorder visual session."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from substitute.application.prompt_editor.document.views import PromptReorderChipView

from ..core.state.revisions import PromptSourceIdentity

_EMPTY_SEGMENTS: Mapping[int, PromptReorderChipView] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class PromptReorderVisualSessionPublication:
    """Publish display-only segment metadata and source lineage atomically."""

    revision: int
    source_identity: PromptSourceIdentity | None
    segments_by_index: Mapping[int, PromptReorderChipView]
    ordered_indices: tuple[int, ...]


class PromptReorderVisualSessionOwner:
    """Retain one immutable display session without owning reorder truth."""

    def __init__(self) -> None:
        """Initialize an empty display session."""

        self._publication = PromptReorderVisualSessionPublication(
            revision=0,
            source_identity=None,
            segments_by_index=_EMPTY_SEGMENTS,
            ordered_indices=(),
        )

    @property
    def publication(self) -> PromptReorderVisualSessionPublication:
        """Return the current immutable visual-session publication."""

        return self._publication

    @property
    def segments_by_index(self) -> Mapping[int, PromptReorderChipView]:
        """Return semantic chip views keyed by stable segment index."""

        return self._publication.segments_by_index

    @property
    def source_revision(self) -> int | None:
        """Return source lineage for emitted interaction intents."""

        identity = self._publication.source_identity
        return None if identity is None else identity.source_revision

    def set_session(
        self,
        *,
        chips: tuple[PromptReorderChipView, ...],
        source_identity: PromptSourceIdentity | None,
    ) -> PromptReorderVisualSessionPublication:
        """Replace visual facts atomically from one application publication."""

        segments = {chip.index: chip for chip in chips}
        self._publication = PromptReorderVisualSessionPublication(
            revision=self._publication.revision + 1,
            source_identity=source_identity,
            segments_by_index=MappingProxyType(segments),
            ordered_indices=tuple(chip.index for chip in chips),
        )
        return self._publication

    def segment(self, segment_index: int) -> PromptReorderChipView | None:
        """Return one visual segment when it belongs to the current session."""

        return self._publication.segments_by_index.get(segment_index)


__all__ = [
    "PromptReorderVisualSessionOwner",
    "PromptReorderVisualSessionPublication",
]
