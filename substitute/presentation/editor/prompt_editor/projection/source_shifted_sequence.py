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

"""Represent source-coordinate remaps as compact lazy immutable sequences."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Generic, TypeVar, overload

TSourceItem = TypeVar("TSourceItem")
type SourceRange[T] = Callable[[T], tuple[int, int]]
type SourceShift[T] = Callable[[T, int], T]


@dataclass(frozen=True, slots=True)
class _SourceSegment(Generic[TSourceItem]):
    """Reference a contiguous base-item range with one uniform source shift."""

    base: Sequence[TSourceItem]
    start: int
    length: int
    delta: int
    shift_item: SourceShift[TSourceItem]


class PromptSourceShiftedSequence(Sequence[TSourceItem], Generic[TSourceItem]):
    """Expose remapped source items without allocating an eager shifted suffix."""

    __slots__ = ("_cache", "_length", "_segment_starts", "_segments")

    def __init__(self, segments: Sequence[_SourceSegment[TSourceItem]]) -> None:
        """Store coalesced coordinate segments and their prefix indexes."""

        self._segments = _coalesced_segments(segments)
        segment_starts: list[int] = []
        length = 0
        for segment in self._segments:
            segment_starts.append(length)
            length += segment.length
        self._segment_starts = tuple(segment_starts)
        self._length = length
        self._cache: dict[int, TSourceItem] = {}

    def __len__(self) -> int:
        """Return the remapped item count."""

        return self._length

    @overload
    def __getitem__(self, index: int) -> TSourceItem: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[TSourceItem]: ...

    def __getitem__(self, index: int | slice) -> TSourceItem | Sequence[TSourceItem]:
        """Return one shifted item or a compact sliced view."""

        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                return tuple(self[position] for position in range(start, stop, step))
            return PromptSourceShiftedSequence(
                _segments_for_range(self, start=start, stop=stop)
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        cached = self._cache.get(normalized_index)
        if cached is not None:
            return cached
        segment_index = bisect_right(self._segment_starts, normalized_index) - 1
        segment = self._segments[segment_index]
        local_index = normalized_index - self._segment_starts[segment_index]
        return self._item_from_segment(normalized_index, segment, local_index)

    def _item_from_segment(
        self,
        sequence_index: int,
        segment: _SourceSegment[TSourceItem],
        local_index: int,
    ) -> TSourceItem:
        """Return one segment item while retaining any required coordinate shift."""

        cached = self._cache.get(sequence_index)
        if cached is not None:
            return cached
        base_item = segment.base[segment.start + local_index]
        if segment.delta == 0:
            return base_item
        shifted_item = segment.shift_item(base_item, segment.delta)
        self._cache[sequence_index] = shifted_item
        return shifted_item

    def __iter__(self) -> Iterator[TSourceItem]:
        """Yield remapped segments without repeating indexed segment lookup."""

        sequence_index = 0
        for segment in self._segments:
            for local_index in range(segment.length):
                yield self._item_from_segment(
                    sequence_index,
                    segment,
                    local_index,
                )
                sequence_index += 1

    def __reversed__(self) -> Iterator[TSourceItem]:
        """Yield remapped segments backward without per-item binary searches."""

        sequence_index = self._length - 1
        for segment in reversed(self._segments):
            for local_index in range(segment.length - 1, -1, -1):
                yield self._item_from_segment(
                    sequence_index,
                    segment,
                    local_index,
                )
                sequence_index -= 1

    def __eq__(self, other: object) -> bool:
        """Compare semantically with any finite source-item sequence."""

        if not isinstance(other, Sequence):
            return False
        return len(self) == len(other) and all(
            left == right for left, right in zip(self, other, strict=True)
        )

    def segments(self) -> tuple[_SourceSegment[TSourceItem], ...]:
        """Return compact segments for further remap composition."""

        return self._segments


def remap_source_sequence(
    items: Sequence[TSourceItem],
    *,
    start: int,
    end: int,
    delta: int,
    source_range: SourceRange[TSourceItem],
    shift_item: SourceShift[TSourceItem],
) -> Sequence[TSourceItem]:
    """Drop edit overlaps and lazily shift the unchanged sorted suffix."""

    wrapped_items = source_sequence(items, shift_item=shift_item)
    prefix_end = 0
    suffix_start = len(wrapped_items)
    for index, item in enumerate(wrapped_items):
        range_start, range_end = source_range(item)
        overlaps = (
            range_start < start < range_end
            if start == end
            else range_start < end and start < range_end
        )
        if range_end <= start:
            prefix_end = index + 1
            continue
        if overlaps:
            suffix_start = index + 1
            continue
        suffix_start = index
        break
    segments = list(_segments_for_range(wrapped_items, start=0, stop=prefix_end))
    segments.extend(
        replace(segment, delta=segment.delta + delta)
        for segment in _segments_for_range(
            wrapped_items,
            start=suffix_start,
            stop=len(wrapped_items),
        )
    )
    if not segments:
        return ()
    return PromptSourceShiftedSequence(segments)


def _segments_for_range(
    items: Sequence[TSourceItem],
    *,
    start: int,
    stop: int,
) -> tuple[_SourceSegment[TSourceItem], ...]:
    """Return clipped compact segments for one normalized item range."""

    if stop <= start:
        return ()
    segment_source = getattr(items, "segments", None)
    if callable(segment_source):
        segments = tuple(segment_source())
    else:
        raise TypeError("Raw source sequences require an explicit shift function.")
    clipped: list[_SourceSegment[TSourceItem]] = []
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


def _coalesced_segments(
    segments: Sequence[_SourceSegment[TSourceItem]],
) -> tuple[_SourceSegment[TSourceItem], ...]:
    """Merge adjacent ranges sharing a base, shift, and item transformer."""

    coalesced: list[_SourceSegment[TSourceItem]] = []
    for segment in segments:
        if segment.length <= 0:
            continue
        previous = coalesced[-1] if coalesced else None
        if (
            previous is not None
            and previous.base is segment.base
            and previous.start + previous.length == segment.start
            and previous.delta == segment.delta
            and previous.shift_item is segment.shift_item
        ):
            coalesced[-1] = replace(
                previous,
                length=previous.length + segment.length,
            )
            continue
        coalesced.append(segment)
    return tuple(coalesced)


def source_sequence(
    items: Sequence[TSourceItem],
    *,
    shift_item: SourceShift[TSourceItem],
) -> Sequence[TSourceItem]:
    """Wrap one raw immutable item sequence for future lazy source remaps."""

    if not items:
        return ()
    if isinstance(items, PromptSourceShiftedSequence):
        return items
    return PromptSourceShiftedSequence(
        (
            _SourceSegment(
                base=items,
                start=0,
                length=len(items),
                delta=0,
                shift_item=shift_item,
            ),
        )
    )


__all__ = ["PromptSourceShiftedSequence", "remap_source_sequence", "source_sequence"]
