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

"""Compose rebuilt projection lines with a lazily shifted stable suffix."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import overload

from .snapshot import PromptProjectionLineSnapshot

type PromptProjectionLineShift = Callable[
    [PromptProjectionLineSnapshot, int, int, float], PromptProjectionLineSnapshot
]


@dataclass(frozen=True, slots=True)
class _LineSegment:
    """Reference a contiguous base-line range with uniform coordinate shifts."""

    base: Sequence[PromptProjectionLineSnapshot]
    start: int
    length: int
    source_delta: int = 0
    projection_delta: int = 0
    y_delta: float = 0.0
    requires_rebind: bool = False


class _PromptProjectionLineSlice(Sequence[PromptProjectionLineSnapshot]):
    """Expose a bounded line slice without materializing its entries."""

    __slots__ = ("_base", "_start", "_stop")

    def __init__(
        self,
        base: Sequence[PromptProjectionLineSnapshot],
        *,
        start: int,
        stop: int,
    ) -> None:
        """Store normalized slice boundaries over the base sequence."""

        self._base = base
        self._start = start
        self._stop = stop

    def __len__(self) -> int:
        """Return the bounded slice length."""

        return self._stop - self._start

    @overload
    def __getitem__(self, index: int) -> PromptProjectionLineSnapshot: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[PromptProjectionLineSnapshot]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionLineSnapshot | Sequence[PromptProjectionLineSnapshot]:
        """Return one base line or another bounded lazy slice."""

        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                return tuple(self[position] for position in range(start, stop, step))
            return _PromptProjectionLineSlice(
                self._base,
                start=self._start + start,
                stop=self._start + stop,
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        return self._base[self._start + normalized_index]

    def segments(self) -> tuple[_LineSegment, ...]:
        """Return clipped line segments without materializing their lines."""

        return _segments_for_range(self._base, self._start, self._stop)


class PromptProjectionReusedLineSequence(Sequence[PromptProjectionLineSnapshot]):
    """Expose rebuilt and shifted line segments without recursive view chains."""

    __slots__ = ("_cache", "_length", "_segment_starts", "_segments", "_shift_line")

    def __init__(
        self,
        prefix: Sequence[PromptProjectionLineSnapshot],
        suffix: Sequence[PromptProjectionLineSnapshot],
        *,
        shift_line: PromptProjectionLineShift,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
    ) -> None:
        """Store compact base ranges for the rebuilt prefix and stable suffix."""

        prefix_tuple = tuple(prefix)
        segments: list[_LineSegment] = []
        if prefix_tuple:
            segments.append(
                _LineSegment(
                    base=prefix_tuple,
                    start=0,
                    length=len(prefix_tuple),
                )
            )
        segments.extend(
            replace(
                segment,
                source_delta=segment.source_delta + source_delta,
                projection_delta=segment.projection_delta + projection_delta,
                y_delta=segment.y_delta + y_delta,
                requires_rebind=True,
            )
            for segment in _segments_for_range(suffix, 0, len(suffix))
        )
        self._segments = _coalesced_segments(segments)
        segment_starts: list[int] = []
        length = 0
        for segment in self._segments:
            segment_starts.append(length)
            length += segment.length
        self._segment_starts = tuple(segment_starts)
        self._length = length
        self._shift_line = shift_line
        self._cache: dict[int, PromptProjectionLineSnapshot] = {}

    def __len__(self) -> int:
        """Return the combined line count."""

        return self._length

    @overload
    def __getitem__(self, index: int) -> PromptProjectionLineSnapshot: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[PromptProjectionLineSnapshot]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionLineSnapshot | Sequence[PromptProjectionLineSnapshot]:
        """Return one shifted line or expose a lazy slice."""

        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                return tuple(self[position] for position in range(start, stop, step))
            return _PromptProjectionLineSlice(self, start=start, stop=stop)
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        cached = self._cache.get(normalized_index)
        if cached is not None:
            return cached
        segment_index = bisect_right(self._segment_starts, normalized_index) - 1
        segment = self._segments[segment_index]
        local_index = normalized_index - self._segment_starts[segment_index]
        return self._line_from_segment(normalized_index, segment, local_index)

    def _line_from_segment(
        self,
        sequence_index: int,
        segment: _LineSegment,
        local_index: int,
    ) -> PromptProjectionLineSnapshot:
        """Return one segment line while retaining any required coordinate shift."""

        cached = self._cache.get(sequence_index)
        if cached is not None:
            return cached
        base_line = segment.base[segment.start + local_index]
        if (
            not segment.requires_rebind
            and segment.source_delta == 0
            and segment.projection_delta == 0
            and abs(segment.y_delta) <= 0.0001
        ):
            return base_line
        shifted_line = self._shift_line(
            base_line,
            segment.source_delta,
            segment.projection_delta,
            segment.y_delta,
        )
        self._cache[sequence_index] = shifted_line
        return shifted_line

    def __iter__(self) -> Iterator[PromptProjectionLineSnapshot]:
        """Yield line segments without repeating indexed segment lookup."""

        sequence_index = 0
        for segment in self._segments:
            for local_index in range(segment.length):
                yield self._line_from_segment(
                    sequence_index,
                    segment,
                    local_index,
                )
                sequence_index += 1

    def __reversed__(self) -> Iterator[PromptProjectionLineSnapshot]:
        """Yield line segments backward without per-line binary searches."""

        sequence_index = self._length - 1
        for segment in reversed(self._segments):
            for local_index in range(segment.length - 1, -1, -1):
                yield self._line_from_segment(
                    sequence_index,
                    segment,
                    local_index,
                )
                sequence_index -= 1

    def segments(self) -> tuple[_LineSegment, ...]:
        """Return the compact line segments backing this sequence."""

        return self._segments


def _segments_for_range(
    lines: Sequence[PromptProjectionLineSnapshot],
    start: int,
    stop: int,
) -> tuple[_LineSegment, ...]:
    """Return clipped compact segments for one normalized line range."""

    if stop <= start:
        return ()
    segment_source = getattr(lines, "segments", None)
    if callable(segment_source):
        segments = tuple(segment_source())
    else:
        segments = (_LineSegment(base=lines, start=0, length=len(lines)),)
    clipped: list[_LineSegment] = []
    segment_offset = 0
    for segment in segments:
        segment_end = segment_offset + segment.length
        overlap_start = max(start, segment_offset)
        overlap_end = min(stop, segment_end)
        if overlap_end > overlap_start:
            clipped.append(
                replace(
                    segment,
                    start=segment.start + overlap_start - segment_offset,
                    length=overlap_end - overlap_start,
                )
            )
        if segment_end >= stop:
            break
        segment_offset = segment_end
    return tuple(clipped)


def _coalesced_segments(segments: Sequence[_LineSegment]) -> tuple[_LineSegment, ...]:
    """Merge adjacent ranges sharing one base and coordinate transform."""

    coalesced: list[_LineSegment] = []
    for segment in segments:
        if segment.length <= 0:
            continue
        previous = coalesced[-1] if coalesced else None
        if (
            previous is not None
            and previous.base is segment.base
            and previous.start + previous.length == segment.start
            and previous.source_delta == segment.source_delta
            and previous.projection_delta == segment.projection_delta
            and abs(previous.y_delta - segment.y_delta) <= 0.0001
            and previous.requires_rebind == segment.requires_rebind
        ):
            coalesced[-1] = replace(
                previous,
                length=previous.length + segment.length,
            )
            continue
        coalesced.append(segment)
    return tuple(coalesced)


__all__ = ["PromptProjectionReusedLineSequence"]
