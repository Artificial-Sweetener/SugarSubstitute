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

"""Preserve lazy shifted prompt layout snapshots without eager materialization."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import overload

from PySide6.QtCore import QRectF

from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .reused_semantics import (
    PromptReusedFragmentIdentity,
    PromptReusedLineSemanticResolver,
)


class ShiftedSourcePositions(Sequence[int]):
    """Expose source positions shifted by a constant without copying every boundary."""

    __slots__ = ("_delta", "_positions")
    _positions: Sequence[int]
    _delta: int

    def __init__(self, positions: Sequence[int], delta: int) -> None:
        """Create a shifted view over an immutable source-position sequence."""

        if isinstance(positions, ShiftedSourcePositions):
            self._positions = positions._positions
            self._delta = positions._delta + delta
            return
        self._positions = positions
        self._delta = delta

    def __len__(self) -> int:
        """Return the number of shifted positions."""

        return len(self._positions)

    @overload
    def __getitem__(self, index: int) -> int: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[int, ...]: ...

    def __getitem__(self, index: int | slice) -> int | tuple[int, ...]:
        """Return one shifted position or a concrete shifted slice."""

        if isinstance(index, slice):
            return tuple(position + self._delta for position in self._positions[index])
        return self._positions[index] + self._delta

    def __iter__(self) -> Iterator[int]:
        """Yield shifted positions without materializing the whole sequence."""

        delta = self._delta
        for position in self._positions:
            yield position + delta

    def __contains__(self, value: object) -> bool:
        """Return whether a shifted source position is present."""

        if not isinstance(value, int):
            return False
        return (value - self._delta) in self._positions

    def index(
        self,
        value: int,
        start: int = 0,
        stop: int | None = None,
    ) -> int:
        """Return the index of one shifted source position."""

        target = value - self._delta
        position_count = len(self._positions)
        normalized_start = start + position_count if start < 0 else start
        normalized_start = max(0, min(normalized_start, position_count))
        if stop is None:
            normalized_stop = position_count
        else:
            normalized_stop = stop + position_count if stop < 0 else stop
            normalized_stop = max(0, min(normalized_stop, position_count))
        for index in range(normalized_start, normalized_stop):
            if self._positions[index] == target:
                return index
        raise ValueError(f"{value!r} is not in sequence")

    def __eq__(self, other: object) -> bool:
        """Compare shifted positions by visible sequence value."""

        if not isinstance(other, Sequence):
            return False
        return tuple(self) == tuple(other)


class ShiftedLineCaretStopSnapshot(PromptProjectionLineCaretStopSnapshot):
    """Expose a caret stop shifted by a constant projection delta."""

    __slots__ = ("_projection_delta", "_stop", "_y_delta")
    _projection_delta: int
    _stop: PromptProjectionLineCaretStopSnapshot
    _y_delta: float

    def __init__(
        self,
        stop: PromptProjectionLineCaretStopSnapshot,
        projection_delta: int,
        y_delta: float,
    ) -> None:
        """Create a lazy shifted caret stop view."""

        object.__setattr__(self, "_stop", stop)
        object.__setattr__(self, "_projection_delta", projection_delta)
        object.__setattr__(self, "_y_delta", y_delta)

    def __getattribute__(self, name: str) -> object:
        """Return shifted fields while preserving dataclass-like access."""

        if name == "projection_position":
            stop = object.__getattribute__(self, "_stop")
            projection_delta = object.__getattribute__(self, "_projection_delta")
            return stop.projection_position + projection_delta
        if name == "rect":
            stop = object.__getattribute__(self, "_stop")
            y_delta = object.__getattribute__(self, "_y_delta")
            if y_delta == 0.0:
                return stop.rect
            return QRectF(
                stop.rect.left(),
                stop.rect.top() + y_delta,
                stop.rect.width(),
                stop.rect.height(),
            )
        return object.__getattribute__(self, name)


class ShiftedTextFragment(PromptProjectionTextFragment):
    """Expose a text fragment shifted logically without copying its geometry."""

    __slots__ = (
        "_fragment",
        "_semantic_identity",
        "_projection_delta",
        "_source_delta",
        "_source_positions",
        "_y_delta",
    )
    _fragment: PromptProjectionTextFragment
    _semantic_identity: PromptReusedFragmentIdentity | None
    _projection_delta: int
    _source_delta: int
    _source_positions: ShiftedSourcePositions | None
    _y_delta: float

    def __init__(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
        semantic_identity: PromptReusedFragmentIdentity | None = None,
    ) -> None:
        """Create a lazy shifted text fragment view."""

        if isinstance(fragment, ShiftedTextFragment):
            if semantic_identity is None:
                semantic_identity = object.__getattribute__(
                    fragment,
                    "_semantic_identity",
                )
            source_delta += object.__getattribute__(fragment, "_source_delta")
            projection_delta += object.__getattribute__(
                fragment,
                "_projection_delta",
            )
            y_delta += object.__getattribute__(fragment, "_y_delta")
            fragment = object.__getattribute__(fragment, "_fragment")
        object.__setattr__(self, "_fragment", fragment)
        object.__setattr__(self, "_semantic_identity", semantic_identity)
        object.__setattr__(self, "_source_delta", source_delta)
        object.__setattr__(self, "_projection_delta", projection_delta)
        object.__setattr__(self, "_y_delta", y_delta)
        object.__setattr__(self, "_source_positions", None)

    def __getattribute__(self, name: str) -> object:
        """Return shifted fields while preserving fragment identity shape."""

        if name == "projection_start":
            fragment = object.__getattribute__(self, "_fragment")
            projection_delta = object.__getattribute__(self, "_projection_delta")
            return fragment.projection_start + projection_delta
        if name == "projection_end":
            fragment = object.__getattribute__(self, "_fragment")
            projection_delta = object.__getattribute__(self, "_projection_delta")
            return fragment.projection_end + projection_delta
        if name == "source_positions":
            source_positions = object.__getattribute__(self, "_source_positions")
            if source_positions is None:
                fragment = object.__getattribute__(self, "_fragment")
                source_delta = object.__getattribute__(self, "_source_delta")
                source_positions = ShiftedSourcePositions(
                    fragment.source_positions,
                    source_delta,
                )
                object.__setattr__(self, "_source_positions", source_positions)
            return source_positions
        if name == "rect":
            fragment = object.__getattribute__(self, "_fragment")
            y_delta = object.__getattribute__(self, "_y_delta")
            if y_delta == 0.0:
                return fragment.rect
            rect = QRectF(fragment.rect)
            rect.translate(0.0, y_delta)
            return rect
        if name == "baseline":
            fragment = object.__getattribute__(self, "_fragment")
            y_delta = object.__getattribute__(self, "_y_delta")
            return fragment.baseline + y_delta
        if name in {"run_id", "token_id"}:
            identity = object.__getattribute__(self, "_semantic_identity")
            if identity is not None:
                return getattr(identity, name)
            return getattr(object.__getattribute__(self, "_fragment"), name)
        if name in {
            "text",
            "boundary_offsets",
            "active",
        }:
            return getattr(object.__getattribute__(self, "_fragment"), name)
        return object.__getattribute__(self, name)


def concrete_text_fragment(
    fragment: PromptProjectionTextFragment,
) -> PromptProjectionTextFragment:
    """Return a dataclass text fragment suitable for replacement."""

    if not isinstance(fragment, ShiftedTextFragment):
        return fragment
    return PromptProjectionTextFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        projection_start=fragment.projection_start,
        projection_end=fragment.projection_end,
        text=fragment.text,
        source_positions=tuple(fragment.source_positions),
        rect=QRectF(fragment.rect),
        baseline=fragment.baseline,
        boundary_offsets=tuple(fragment.boundary_offsets),
        active=fragment.active,
    )


class ShiftedInlineObjectFragment(PromptProjectionInlineObjectFragment):
    """Expose an inline-object fragment shifted logically without copying geometry."""

    __slots__ = (
        "_fragment",
        "_semantic_identity",
        "_projection_delta",
        "_source_delta",
        "_source_positions",
        "_y_delta",
    )
    _fragment: PromptProjectionInlineObjectFragment
    _semantic_identity: PromptReusedFragmentIdentity | None
    _projection_delta: int
    _source_delta: int
    _source_positions: ShiftedSourcePositions | None
    _y_delta: float

    def __init__(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
        semantic_identity: PromptReusedFragmentIdentity | None = None,
    ) -> None:
        """Create a lazy shifted inline-object fragment view."""

        if isinstance(fragment, ShiftedInlineObjectFragment):
            if semantic_identity is None:
                semantic_identity = object.__getattribute__(
                    fragment,
                    "_semantic_identity",
                )
            source_delta += object.__getattribute__(fragment, "_source_delta")
            projection_delta += object.__getattribute__(
                fragment,
                "_projection_delta",
            )
            y_delta += object.__getattribute__(fragment, "_y_delta")
            fragment = object.__getattribute__(fragment, "_fragment")
        object.__setattr__(self, "_fragment", fragment)
        object.__setattr__(self, "_semantic_identity", semantic_identity)
        object.__setattr__(self, "_source_delta", source_delta)
        object.__setattr__(self, "_projection_delta", projection_delta)
        object.__setattr__(self, "_y_delta", y_delta)
        object.__setattr__(self, "_source_positions", None)

    def __getattribute__(self, name: str) -> object:
        """Return shifted fields while preserving fragment identity shape."""

        if name == "projection_start":
            fragment = object.__getattribute__(self, "_fragment")
            projection_delta = object.__getattribute__(self, "_projection_delta")
            return fragment.projection_start + projection_delta
        if name == "projection_end":
            fragment = object.__getattribute__(self, "_fragment")
            projection_delta = object.__getattribute__(self, "_projection_delta")
            return fragment.projection_end + projection_delta
        if name == "source_positions":
            source_positions = object.__getattribute__(self, "_source_positions")
            if source_positions is None:
                fragment = object.__getattribute__(self, "_fragment")
                source_delta = object.__getattribute__(self, "_source_delta")
                source_positions = ShiftedSourcePositions(
                    fragment.source_positions,
                    source_delta,
                )
                object.__setattr__(self, "_source_positions", source_positions)
            return source_positions
        if name == "rect":
            fragment = object.__getattribute__(self, "_fragment")
            y_delta = object.__getattribute__(self, "_y_delta")
            if y_delta == 0.0:
                return fragment.rect
            rect = QRectF(fragment.rect)
            rect.translate(0.0, y_delta)
            return rect
        if name in {"run_id", "token_id"}:
            identity = object.__getattribute__(self, "_semantic_identity")
            if identity is not None:
                return getattr(identity, name)
            return getattr(object.__getattribute__(self, "_fragment"), name)
        if name in {
            "renderer_key",
            "active",
        }:
            return getattr(object.__getattribute__(self, "_fragment"), name)
        return object.__getattribute__(self, name)


def shift_downstream_fragment(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    source_delta: int,
    projection_delta: int,
    y_delta: float,
    semantic_resolver: PromptReusedLineSemanticResolver | None = None,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one lazily shifted fragment with current semantic ownership."""

    semantic_identity = (
        None
        if semantic_resolver is None
        else semantic_resolver.identity_for(
            fragment,
            projection_delta=projection_delta,
        )
    )
    if isinstance(fragment, PromptProjectionTextFragment):
        return ShiftedTextFragment(
            fragment,
            source_delta=source_delta,
            projection_delta=projection_delta,
            y_delta=y_delta,
            semantic_identity=semantic_identity,
        )
    return ShiftedInlineObjectFragment(
        fragment,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=y_delta,
        semantic_identity=semantic_identity,
    )


class ShiftedLineSnapshot(PromptProjectionLineSnapshot):
    """Expose a downstream visual line shifted after a same-line plain edit."""

    __slots__ = (
        "_caret_stops",
        "_fragments",
        "_line",
        "_projection_delta",
        "_semantic_resolver",
        "_source_delta",
        "_y_delta",
    )
    _caret_stops: tuple[PromptProjectionLineCaretStopSnapshot, ...] | None
    _fragments: (
        tuple[
            PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
            ...,
        ]
        | None
    )
    _line: PromptProjectionLineSnapshot
    _projection_delta: int
    _semantic_resolver: PromptReusedLineSemanticResolver | None
    _source_delta: int
    _y_delta: float

    def __init__(
        self,
        line: PromptProjectionLineSnapshot,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
        semantic_resolver: PromptReusedLineSemanticResolver | None = None,
    ) -> None:
        """Create a lazy shifted line view."""

        if isinstance(line, ShiftedLineSnapshot):
            if semantic_resolver is None:
                semantic_resolver = object.__getattribute__(
                    line,
                    "_semantic_resolver",
                )
            source_delta += object.__getattribute__(line, "_source_delta")
            projection_delta += object.__getattribute__(line, "_projection_delta")
            y_delta += object.__getattribute__(line, "_y_delta")
            line = object.__getattribute__(line, "_line")
        object.__setattr__(self, "_line", line)
        object.__setattr__(self, "_semantic_resolver", semantic_resolver)
        object.__setattr__(self, "_source_delta", source_delta)
        object.__setattr__(self, "_projection_delta", projection_delta)
        object.__setattr__(self, "_y_delta", y_delta)
        object.__setattr__(self, "_fragments", None)
        object.__setattr__(self, "_caret_stops", None)

    def __getattribute__(self, name: str) -> object:
        """Return shifted fields while preserving line snapshot access."""

        if name in {
            "source_start",
            "source_end",
            "source_content_start",
            "source_content_end",
        }:
            line = object.__getattribute__(self, "_line")
            source_delta = object.__getattribute__(self, "_source_delta")
            return getattr(line, name) + source_delta
        if name in {"line_break_start", "line_break_end"}:
            line = object.__getattribute__(self, "_line")
            value = getattr(line, name)
            if value is None:
                return None
            source_delta = object.__getattribute__(self, "_source_delta")
            return value + source_delta
        if name == "fragments":
            fragments = object.__getattribute__(self, "_fragments")
            if fragments is None:
                line = object.__getattribute__(self, "_line")
                source_delta = object.__getattribute__(self, "_source_delta")
                projection_delta = object.__getattribute__(self, "_projection_delta")
                semantic_resolver = object.__getattribute__(
                    self,
                    "_semantic_resolver",
                )
                fragments = tuple(
                    shift_downstream_fragment(
                        fragment,
                        source_delta=source_delta,
                        projection_delta=projection_delta,
                        y_delta=object.__getattribute__(self, "_y_delta"),
                        semantic_resolver=semantic_resolver,
                    )
                    for fragment in line.fragments
                )
                object.__setattr__(self, "_fragments", fragments)
            return fragments
        if name == "caret_stops":
            caret_stops = object.__getattribute__(self, "_caret_stops")
            if caret_stops is None:
                line = object.__getattribute__(self, "_line")
                projection_delta = object.__getattribute__(self, "_projection_delta")
                y_delta = object.__getattribute__(self, "_y_delta")
                caret_stops = tuple(
                    ShiftedLineCaretStopSnapshot(
                        caret_stop,
                        projection_delta,
                        y_delta,
                    )
                    for caret_stop in line.caret_stops
                )
                object.__setattr__(self, "_caret_stops", caret_stops)
            return caret_stops
        if name == "top":
            line = object.__getattribute__(self, "_line")
            y_delta = object.__getattribute__(self, "_y_delta")
            return line.top + y_delta
        if name == "height":
            return getattr(object.__getattribute__(self, "_line"), name)
        return object.__getattribute__(self, name)


def concrete_line_snapshot(
    line: PromptProjectionLineSnapshot,
) -> PromptProjectionLineSnapshot:
    """Return a dataclass line snapshot suitable for replacement."""

    if not isinstance(line, ShiftedLineSnapshot):
        return line
    return PromptProjectionLineSnapshot(
        top=line.top,
        height=line.height,
        source_start=line.source_start,
        source_end=line.source_end,
        source_content_start=line.source_content_start,
        source_content_end=line.source_content_end,
        line_break_start=line.line_break_start,
        line_break_end=line.line_break_end,
        fragments=tuple(concrete_fragment(fragment) for fragment in line.fragments),
        caret_stops=tuple(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=stop.projection_position,
                rect=QRectF(stop.rect),
            )
            for stop in line.caret_stops
        ),
    )


def concrete_fragment(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return a concrete fragment for a shifted fragment view."""

    if isinstance(fragment, PromptProjectionTextFragment):
        return concrete_text_fragment(fragment)
    if not isinstance(fragment, ShiftedInlineObjectFragment):
        return fragment
    return PromptProjectionInlineObjectFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        renderer_key=fragment.renderer_key,
        projection_start=fragment.projection_start,
        projection_end=fragment.projection_end,
        source_positions=tuple(fragment.source_positions),
        rect=QRectF(fragment.rect),
        active=fragment.active,
    )


class LineTextFragmentSequence(Sequence[PromptProjectionTextFragment]):
    """Expose text fragments from line snapshots without eager flattening."""

    __slots__ = ("_cached", "_fragment_count", "_lines")
    _cached: tuple[PromptProjectionTextFragment, ...] | None
    _fragment_count: int
    _lines: Sequence[PromptProjectionLineSnapshot]

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        fragment_count: int,
    ) -> None:
        """Store line snapshots and the known text-fragment count."""

        self._lines = lines
        self._fragment_count = fragment_count
        self._cached = None

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

    __slots__ = ("_cached", "_fragment_count", "_lines")
    _cached: tuple[PromptProjectionInlineObjectFragment, ...] | None
    _fragment_count: int
    _lines: Sequence[PromptProjectionLineSnapshot]

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        fragment_count: int,
    ) -> None:
        """Store line snapshots and the known inline-fragment count."""

        self._lines = lines
        self._fragment_count = fragment_count
        self._cached = None

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
        | tuple[
            PromptProjectionInlineObjectFragment,
            ...,
        ]
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
    """Expose caret rects from line snapshots without eager dictionary rebuilds."""

    __slots__ = ("_cached", "_caret_count", "_lines")
    _cached: dict[int, QRectF] | None
    _caret_count: int
    _lines: Sequence[PromptProjectionLineSnapshot]

    def __init__(
        self,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        caret_count: int,
    ) -> None:
        """Store line snapshots and the known caret-rect count."""

        self._lines = lines
        self._caret_count = caret_count
        self._cached = None

    def __len__(self) -> int:
        """Return the known caret rect count."""

        return self._caret_count

    def __iter__(self) -> Iterator[int]:
        """Yield projection positions represented by line caret stops."""

        for line in self._lines:
            for caret_stop in line.caret_stops:
                yield caret_stop.projection_position

    def __getitem__(self, key: int) -> QRectF:
        """Return the caret rect for one projection position."""

        if self._cached is not None:
            return self._cached[key]
        for line in self._lines:
            for caret_stop in line.caret_stops:
                if caret_stop.projection_position == key:
                    return caret_stop.rect
        raise KeyError(key)


__all__ = [
    "LineCaretRectMapping",
    "LineInlineObjectFragmentSequence",
    "LineTextFragmentSequence",
    "ShiftedInlineObjectFragment",
    "ShiftedLineSnapshot",
    "ShiftedTextFragment",
    "concrete_line_snapshot",
    "concrete_text_fragment",
    "shift_downstream_fragment",
]
