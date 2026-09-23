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

"""Index lazily composed prompt-layout snapshots for read-side consumers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import overload

from PySide6.QtCore import QRectF

from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .shifted_snapshot import ShiftedLineSnapshot


class LineTextFragmentSequence(Sequence[PromptProjectionTextFragment]):
    """Expose text fragments from line snapshots without eager flattening."""

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        fragment_count: int,
    ) -> None:
        """Store lines and their known text-fragment count."""

        self._lines = lines
        self._fragment_count = fragment_count
        self._cached: tuple[PromptProjectionTextFragment, ...] | None = None

    def __len__(self) -> int:
        """Return the known text-fragment count."""

        return self._fragment_count

    @overload
    def __getitem__(self, index: int) -> PromptProjectionTextFragment: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionTextFragment, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionTextFragment | tuple[PromptProjectionTextFragment, ...]:
        """Return one fragment or a concrete fragment slice."""

        return self._materialized()[index]

    def __iter__(self) -> Iterator[PromptProjectionTextFragment]:
        """Yield text fragments from visual lines only when requested."""

        for line in self._lines:
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionTextFragment):
                    yield fragment

    def _materialized(self) -> tuple[PromptProjectionTextFragment, ...]:
        """Return a cached concrete fragment tuple for random access."""

        if self._cached is None:
            self._cached = tuple(iter(self))
        return self._cached


class LineInlineObjectFragmentSequence(Sequence[PromptProjectionInlineObjectFragment]):
    """Expose inline fragments from line snapshots without eager flattening."""

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        fragment_count: int,
    ) -> None:
        """Store lines and their known inline-fragment count."""

        self._lines = lines
        self._fragment_count = fragment_count
        self._cached: tuple[PromptProjectionInlineObjectFragment, ...] | None = None

    def __len__(self) -> int:
        """Return the known inline-fragment count."""

        return self._fragment_count

    @overload
    def __getitem__(self, index: int) -> PromptProjectionInlineObjectFragment: ...

    @overload
    def __getitem__(
        self,
        index: slice,
    ) -> tuple[PromptProjectionInlineObjectFragment, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> (
        PromptProjectionInlineObjectFragment
        | tuple[PromptProjectionInlineObjectFragment, ...]
    ):
        """Return one fragment or a concrete fragment slice."""

        return self._materialized()[index]

    def __iter__(self) -> Iterator[PromptProjectionInlineObjectFragment]:
        """Yield inline fragments from visual lines only when requested."""

        for line in self._lines:
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionInlineObjectFragment):
                    yield fragment

    def _materialized(self) -> tuple[PromptProjectionInlineObjectFragment, ...]:
        """Return a cached concrete fragment tuple for random access."""

        if self._cached is None:
            self._cached = tuple(iter(self))
        return self._cached


class LineCaretRectMapping(Mapping[int, QRectF]):
    """Expose indexed caret rectangles without eagerly flattening every line."""

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        caret_count: int,
    ) -> None:
        """Store lines and their known unique caret count."""

        self._lines = lines
        self._caret_count = caret_count
        self._cached: dict[int, QRectF] = {}
        self._fully_indexed = False

    def __len__(self) -> int:
        """Return the known caret rect count."""

        return self._caret_count

    def __iter__(self) -> Iterator[int]:
        """Yield every unique indexed projection position."""

        return iter(self._materialized())

    def __getitem__(self, key: int) -> QRectF:
        """Return one caret rect through a memoized logarithmic line lookup."""

        try:
            return self._cached[key]
        except KeyError:
            pass
        if self._fully_indexed:
            raise KeyError(key)
        line_index = self._last_candidate_line_index(key)
        if line_index is not None:
            rect = _line_caret_rect(self._lines[line_index], key)
            if rect is not None:
                self._cached[key] = rect
                return rect
        for line in reversed(self._lines):
            rect = _line_caret_rect(line, key)
            if rect is not None:
                self._cached[key] = rect
                return rect
        raise KeyError(key)

    def _last_candidate_line_index(self, key: int) -> int | None:
        """Locate the last visual line whose leading caret does not exceed key."""

        low = 0
        high = len(self._lines)
        while low < high:
            middle = (low + high) // 2
            bounds = _line_caret_projection_bounds(self._lines[middle])
            if bounds is not None and bounds[0] <= key:
                low = middle + 1
            else:
                high = middle
        candidate = low - 1
        if candidate < 0:
            return None
        bounds = _line_caret_projection_bounds(self._lines[candidate])
        if bounds is None or key > bounds[1]:
            return None
        return candidate

    def _materialized(self) -> dict[int, QRectF]:
        """Return one cached complete index for whole-map consumers."""

        if not self._fully_indexed:
            self._cached.update(
                {
                    stop.projection_position: stop.rect
                    for line in self._lines
                    for stop in line.caret_stops
                }
            )
            self._fully_indexed = True
        return self._cached


def _line_caret_projection_bounds(
    line: PromptProjectionLineSnapshot,
) -> tuple[int, int] | None:
    """Return one line's inclusive projection bounds without needless proxies."""

    if isinstance(line, ShiftedLineSnapshot):
        return line.caret_projection_bounds()
    if not line.caret_stops:
        return None
    return (
        line.caret_stops[0].projection_position,
        line.caret_stops[-1].projection_position,
    )


def _line_caret_rect(
    line: PromptProjectionLineSnapshot,
    position: int,
) -> QRectF | None:
    """Return a line-local caret rect while preserving last-stop precedence."""

    if isinstance(line, ShiftedLineSnapshot):
        return line.caret_rect_for_projection_position(position)
    for stop in reversed(line.caret_stops):
        if stop.projection_position == position:
            return stop.rect
    return None


__all__ = [
    "LineCaretRectMapping",
    "LineInlineObjectFragmentSequence",
    "LineTextFragmentSequence",
]
