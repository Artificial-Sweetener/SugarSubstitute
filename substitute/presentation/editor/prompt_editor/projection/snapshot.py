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

"""Define immutable layout snapshot types for the unified prompt projection engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, QSizeF


@dataclass(frozen=True, slots=True)
class PromptProjectionTextFragment:
    """Describe one laid-out text fragment inside the visible projection."""

    run_id: str
    token_id: str | None
    projection_start: int
    projection_end: int
    text: str
    source_positions: Sequence[int]
    rect: QRectF
    baseline: float
    boundary_offsets: tuple[float, ...]
    active: bool = False


@dataclass(frozen=True, slots=True)
class PromptProjectionInlineObjectFragment:
    """Describe one laid-out inline object inside the visible projection."""

    run_id: str
    token_id: str | None
    renderer_key: str
    projection_start: int
    projection_end: int
    source_positions: Sequence[int]
    rect: QRectF
    active: bool = False


PromptProjectionFragment = (
    PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
)


@dataclass(frozen=True, slots=True)
class PromptProjectionLineCaretStopSnapshot:
    """Describe one line-local caret stop used for visual-line navigation."""

    projection_position: int
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionLineSnapshot:
    """Describe one wrapped line inside the visible projection."""

    top: float
    height: float
    source_start: int
    source_end: int
    source_content_start: int
    source_content_end: int
    line_break_start: int | None
    line_break_end: int | None
    fragments: tuple[PromptProjectionFragment, ...]
    caret_stops: tuple[PromptProjectionLineCaretStopSnapshot, ...]

    @property
    def rect(self) -> QRectF:
        """Return the full line rect covering every fragment in this line."""

        if not self.fragments:
            return QRectF(0.0, self.top, 0.0, self.height)
        line_rect = QRectF(self.fragments[0].rect)
        for fragment in self.fragments[1:]:
            line_rect = line_rect.united(fragment.rect)
        return QRectF(line_rect.left(), self.top, line_rect.width(), self.height)


@dataclass(frozen=True, slots=True)
class PromptProjectionLayoutSnapshot:
    """Describe the immutable geometry snapshot used by paint and interaction."""

    content_size: QSizeF
    lines: tuple[PromptProjectionLineSnapshot, ...]
    text_fragments: Sequence[PromptProjectionTextFragment]
    inline_object_fragments: Sequence[PromptProjectionInlineObjectFragment]
    caret_rects_by_projection_position: Mapping[int, QRectF]
    _text_fragments_by_run_id: (
        dict[str, tuple[PromptProjectionTextFragment, ...]] | None
    ) = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _inline_fragments_by_run_id: (
        dict[
            str,
            tuple[PromptProjectionInlineObjectFragment, ...],
        ]
        | None
    ) = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Leave run-fragment indexes lazy so typing does not pay for hit-test caches."""

    def text_fragments_for_run(
        self,
        run_id: str | None,
    ) -> tuple[PromptProjectionTextFragment, ...]:
        """Return the visible text fragments belonging to one run."""

        if run_id is None:
            return ()
        fragments_by_run_id = self._text_fragment_index()
        return fragments_by_run_id.get(run_id, ())

    def inline_object_fragments_for_run(
        self,
        run_id: str | None,
    ) -> tuple[PromptProjectionInlineObjectFragment, ...]:
        """Return the visible object fragments belonging to one run."""

        if run_id is None:
            return ()
        fragments_by_run_id = self._inline_fragment_index()
        return fragments_by_run_id.get(run_id, ())

    def inline_object_fragment_at(
        self,
        point: QPointF,
    ) -> PromptProjectionInlineObjectFragment | None:
        """Return the topmost inline object fragment containing one document-local point."""

        for fragment in reversed(self.inline_object_fragments):
            if fragment.rect.contains(point):
                return fragment
        return None

    def _text_fragment_index(
        self,
    ) -> dict[str, tuple[PromptProjectionTextFragment, ...]]:
        """Return a lazily-built text-fragment index by run id."""

        fragments_by_run_id = self._text_fragments_by_run_id
        if fragments_by_run_id is not None:
            return fragments_by_run_id
        grouped: dict[str, list[PromptProjectionTextFragment]] = {}
        for text_fragment in self.text_fragments:
            grouped.setdefault(text_fragment.run_id, []).append(text_fragment)
        fragments_by_run_id = _freeze_text_fragments_by_run_id(grouped)
        object.__setattr__(self, "_text_fragments_by_run_id", fragments_by_run_id)
        return fragments_by_run_id

    def _inline_fragment_index(
        self,
    ) -> dict[str, tuple[PromptProjectionInlineObjectFragment, ...]]:
        """Return a lazily-built inline-fragment index by run id."""

        fragments_by_run_id = self._inline_fragments_by_run_id
        if fragments_by_run_id is not None:
            return fragments_by_run_id
        grouped: dict[str, list[PromptProjectionInlineObjectFragment]] = {}
        for object_fragment in self.inline_object_fragments:
            grouped.setdefault(object_fragment.run_id, []).append(object_fragment)
        fragments_by_run_id = _freeze_inline_fragments_by_run_id(grouped)
        object.__setattr__(self, "_inline_fragments_by_run_id", fragments_by_run_id)
        return fragments_by_run_id


__all__ = [
    "PromptProjectionFragment",
    "PromptProjectionInlineObjectFragment",
    "PromptProjectionLineCaretStopSnapshot",
    "PromptProjectionLayoutSnapshot",
    "PromptProjectionLineSnapshot",
    "PromptProjectionTextFragment",
]


def _freeze_text_fragments_by_run_id(
    fragments_by_run_id: dict[str, list[PromptProjectionTextFragment]],
) -> dict[str, tuple[PromptProjectionTextFragment, ...]]:
    """Freeze the text-fragment index stored on one layout snapshot."""

    return {
        run_id: tuple(fragments) for run_id, fragments in fragments_by_run_id.items()
    }


def _freeze_inline_fragments_by_run_id(
    fragments_by_run_id: dict[str, list[PromptProjectionInlineObjectFragment]],
) -> dict[str, tuple[PromptProjectionInlineObjectFragment, ...]]:
    """Freeze the object-fragment index stored on one layout snapshot."""

    return {
        run_id: tuple(fragments) for run_id, fragments in fragments_by_run_id.items()
    }
