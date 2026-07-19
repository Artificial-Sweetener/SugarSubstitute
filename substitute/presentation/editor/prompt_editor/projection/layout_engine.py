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

"""Coordinate projection layout state and geometry helpers for the prompt surface."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import gc
from typing import TYPE_CHECKING, cast, overload

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPalette
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    blank_line_drop_offsets,
)
from substitute.application.appearance import SemanticPalette

from .line_layout import (
    PromptProjectionLineLayoutBuilder,
    tag_keep_source_range_at_position,
    tag_keep_source_ranges_in_source_line,
)
from .incremental_text_layout import (
    build_edited_text_fragment,
    editable_text_fragment,
    text_boundary_offsets,
)
from .metrics import PromptProjectionMetrics, PromptProjectionMetricsFactory
from .model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionSelection,
    PromptProjectionToken,
)
from .paint_state import (
    PromptProjectionPaintState,
    empty_projection_paint_state,
)
from .snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionLayoutSnapshot,
    PromptProjectionTextFragment,
)
from .text_style import projection_text_run_font
from .painter import PromptProjectionPainter
from .tokens import (
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)
from .reorder_chip_geometry import (
    PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
    PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
    PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
    PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
    chip_geometry_context,
    chrome_path_from_rects,
)
from .reorder_geometry import PromptProjectionReorderGeometry
from .observability import log_reorder_drag_event
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    rect_from_centerline,
    reorder_placement_id_for_target,
)
from .reorder_visual_snapshot import (
    PromptReorderInlineObjectPaintFragment,
    PromptReorderProjectionPaintFragment,
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
)
from .hit_testing import (
    PromptProjectionCaretHit,
    PromptProjectionDragSelectionTarget,
    PromptProjectionHitTester,
)
from .selection_geometry import (
    PromptProjectionHorizontalCaretTarget,
    PromptProjectionSelectionGeometry,
    PromptProjectionSourceLineRect,
    PromptProjectionVerticalCaretTarget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter, QRegion


@contextmanager
def _suspend_gc_for_hot_layout_path() -> Iterator[bool]:
    """Temporarily defer cyclic GC during short incremental layout edits."""

    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield was_enabled
    finally:
        if was_enabled:
            gc.enable()


class _ShiftedSourcePositions(Sequence[int]):
    """Expose source positions shifted by a constant without copying every boundary."""

    __slots__ = ("_delta", "_positions")
    _positions: Sequence[int]
    _delta: int

    def __init__(self, positions: Sequence[int], delta: int) -> None:
        """Create a shifted view over an immutable source-position sequence."""

        if isinstance(positions, _ShiftedSourcePositions):
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


class _ShiftedLineCaretStopSnapshot(PromptProjectionLineCaretStopSnapshot):
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


class _ShiftedTextFragment(PromptProjectionTextFragment):
    """Expose a text fragment shifted logically without copying its geometry."""

    __slots__ = (
        "_fragment",
        "_projection_delta",
        "_source_delta",
        "_source_positions",
        "_y_delta",
    )
    _fragment: PromptProjectionTextFragment
    _projection_delta: int
    _source_delta: int
    _source_positions: _ShiftedSourcePositions | None
    _y_delta: float

    def __init__(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
    ) -> None:
        """Create a lazy shifted text fragment view."""

        if isinstance(fragment, _ShiftedTextFragment):
            source_delta += object.__getattribute__(fragment, "_source_delta")
            projection_delta += object.__getattribute__(
                fragment,
                "_projection_delta",
            )
            y_delta += object.__getattribute__(fragment, "_y_delta")
            fragment = object.__getattribute__(fragment, "_fragment")
        object.__setattr__(self, "_fragment", fragment)
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
                source_positions = _ShiftedSourcePositions(
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
        if name in {
            "run_id",
            "token_id",
            "text",
            "boundary_offsets",
            "active",
        }:
            return getattr(object.__getattribute__(self, "_fragment"), name)
        return object.__getattribute__(self, name)


def _concrete_text_fragment(
    fragment: PromptProjectionTextFragment,
) -> PromptProjectionTextFragment:
    """Return a dataclass text fragment suitable for replacement."""

    if not isinstance(fragment, _ShiftedTextFragment):
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


class _ShiftedInlineObjectFragment(PromptProjectionInlineObjectFragment):
    """Expose an inline-object fragment shifted logically without copying geometry."""

    __slots__ = (
        "_fragment",
        "_projection_delta",
        "_source_delta",
        "_source_positions",
        "_y_delta",
    )
    _fragment: PromptProjectionInlineObjectFragment
    _projection_delta: int
    _source_delta: int
    _source_positions: _ShiftedSourcePositions | None
    _y_delta: float

    def __init__(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
    ) -> None:
        """Create a lazy shifted inline-object fragment view."""

        if isinstance(fragment, _ShiftedInlineObjectFragment):
            source_delta += object.__getattribute__(fragment, "_source_delta")
            projection_delta += object.__getattribute__(
                fragment,
                "_projection_delta",
            )
            y_delta += object.__getattribute__(fragment, "_y_delta")
            fragment = object.__getattribute__(fragment, "_fragment")
        object.__setattr__(self, "_fragment", fragment)
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
                source_positions = _ShiftedSourcePositions(
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
        if name in {
            "run_id",
            "token_id",
            "renderer_key",
            "active",
        }:
            return getattr(object.__getattribute__(self, "_fragment"), name)
        return object.__getattribute__(self, name)


class _ShiftedLineSnapshot(PromptProjectionLineSnapshot):
    """Expose a downstream visual line shifted after a same-line plain edit."""

    __slots__ = (
        "_caret_stops",
        "_fragments",
        "_line",
        "_projection_delta",
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
    _source_delta: int
    _y_delta: float

    def __init__(
        self,
        line: PromptProjectionLineSnapshot,
        *,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
    ) -> None:
        """Create a lazy shifted line view."""

        if isinstance(line, _ShiftedLineSnapshot):
            source_delta += object.__getattribute__(line, "_source_delta")
            projection_delta += object.__getattribute__(line, "_projection_delta")
            y_delta += object.__getattribute__(line, "_y_delta")
            line = object.__getattribute__(line, "_line")
        object.__setattr__(self, "_line", line)
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
                fragments = tuple(
                    _shift_downstream_fragment_after_plain_edit(
                        fragment,
                        source_delta=source_delta,
                        projection_delta=projection_delta,
                        y_delta=object.__getattribute__(self, "_y_delta"),
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
                    _ShiftedLineCaretStopSnapshot(
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


def _concrete_line_snapshot(
    line: PromptProjectionLineSnapshot,
) -> PromptProjectionLineSnapshot:
    """Return a dataclass line snapshot suitable for replacement."""

    if not isinstance(line, _ShiftedLineSnapshot):
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
        fragments=tuple(_concrete_fragment(fragment) for fragment in line.fragments),
        caret_stops=tuple(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=stop.projection_position,
                rect=QRectF(stop.rect),
            )
            for stop in line.caret_stops
        ),
    )


def _concrete_fragment(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return a concrete fragment for a shifted fragment view."""

    if isinstance(fragment, PromptProjectionTextFragment):
        return _concrete_text_fragment(fragment)
    if not isinstance(fragment, _ShiftedInlineObjectFragment):
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


class _LineTextFragmentSequence(Sequence[PromptProjectionTextFragment]):
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


class _LineInlineObjectFragmentSequence(Sequence[PromptProjectionInlineObjectFragment]):
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


class _LineCaretRectMapping(Mapping[int, QRectF]):
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


@dataclass(frozen=True, slots=True)
class PromptProjectionIncrementalLayoutResult:
    """Summarize one accepted incremental layout update."""

    content_height_changed: bool
    content_height_delta: float
    first_reflowed_line_index: int
    reflowed_line_count: int
    upstream_line_count: int


@dataclass
class PromptProjectionLayout:
    """Lay out projection runs and expose one snapshot-backed geometry surface."""

    inline_object_renderers: PromptProjectionInlineObjectRendererRegistry
    _hit_tester: PromptProjectionHitTester = field(init=False)
    _painter: PromptProjectionPainter = field(init=False)
    _reorder_geometry: PromptProjectionReorderGeometry = field(init=False)
    _selection_geometry: PromptProjectionSelectionGeometry = field(init=False)
    _metrics_factory: PromptProjectionMetricsFactory = field(init=False)
    _metrics: PromptProjectionMetrics = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the reusable layout state for the visible projection."""

        empty_caret_map = PromptProjectionCaretMap(
            stops=(),
            tokens=(),
            source_length=0,
            projection_length=0,
        )
        self._projection_document = PromptProjectionDocument(
            display_mode=PromptProjectionDisplayMode.RAW,
            source_text="",
            projection_text="",
            runs=(),
            tokens=(),
            mapping=PromptProjectionMapping((), 0, 0),
            caret_map=empty_caret_map,
        )
        self._paint_state = empty_projection_paint_state()
        self._base_font = QFont()
        self._palette = QPalette()
        self._semantic_palette: SemanticPalette | None = None
        self._document_margin = 4.0
        self._text_width = 1.0
        self._content_left_inset = 0.0
        self._prompt_document_view: PromptDocumentView | None = None
        self.last_incremental_reflow_rejection_reason = ""
        self._metrics_factory = PromptProjectionMetricsFactory()
        self._metrics = self._build_metrics()
        self._line_layout_builder = PromptProjectionLineLayoutBuilder(
            self.inline_object_renderers
        )
        self._selection_geometry = PromptProjectionSelectionGeometry(self)
        self._painter = PromptProjectionPainter(self)
        self._hit_tester = PromptProjectionHitTester(self)
        self._reorder_geometry = PromptProjectionReorderGeometry(self)
        self._snapshot = self._line_layout_builder.build_snapshot(
            self._projection_document,
            wrap_width=self._text_width,
            base_font=self._base_font,
            document_margin=self._document_margin,
            content_left_inset=self._content_left_inset,
            metrics=self._metrics,
        )

    @property
    def projection_document(self) -> PromptProjectionDocument:
        """Return the current token-aware prompt projection."""

        return self._projection_document

    @property
    def paint_state(self) -> PromptProjectionPaintState:
        """Return the geometry-neutral visual state layered over the projection."""

        return self._paint_state

    def effective_run_for_paint(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return one projection run with geometry-neutral paint flags applied."""

        run = self._projection_document.run_by_id(run_id)
        if run is None:
            return None
        active = run.active or self._paint_state.is_run_active(run.run_id)
        ghosted = run.ghosted or self._paint_state.is_run_ghosted(run.run_id)
        text_style_variant = (
            "scene_error"
            if self._paint_state.is_run_scene_error(run.run_id)
            else run.text_style_variant
        )
        if (
            active == run.active
            and ghosted == run.ghosted
            and text_style_variant == run.text_style_variant
        ):
            return run
        return replace(
            run,
            active=active,
            ghosted=ghosted,
            text_style_variant=text_style_variant,
        )

    def effective_token_for_paint(
        self,
        token_id: str | None,
    ) -> PromptProjectionToken | None:
        """Return one projection token with geometry-neutral paint flags applied."""

        token = self._projection_document.token_by_id(token_id)
        if token is None:
            return None
        active = token.active or self._paint_state.is_token_active(token.token_id)
        decoration_accented = (
            token.decoration_accented
            or self._paint_state.is_token_decoration_accented(token.token_id)
        )
        if active == token.active and decoration_accented == token.decoration_accented:
            return token
        return replace(
            token,
            active=active,
            decoration_accented=decoration_accented,
        )

    @property
    def document_margin(self) -> float:
        """Return the current document inset used by the projection layout."""

        return self._document_margin

    @property
    def metrics(self) -> PromptProjectionMetrics:
        """Return the metrics authority for the current projection snapshot."""

        return self._metrics

    def set_base_font(self, font: QFont) -> None:
        """Apply the base font used by plain text and inline object renderers."""

        if self._base_font == font or self._base_font.toString() == font.toString():
            return
        self._base_font = QFont(font)
        self._rebuild_snapshot()

    def set_palette(self, palette: QPalette) -> None:
        """Store the palette used for visible projection painting."""

        self._palette = QPalette(palette)

    def set_semantic_palette(self, palette: SemanticPalette | None) -> None:
        """Store optional semantic colors used by prompt diagnostics."""

        self._semantic_palette = palette

    def set_projection(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Replace the laid-out projection document and rebuild the geometry snapshot."""

        self._projection_document = projection_document
        self._paint_state = empty_projection_paint_state()
        self._prompt_document_view = prompt_document_view
        self._rebuild_snapshot()

    def set_projection_and_text_width(
        self,
        projection_document: PromptProjectionDocument,
        text_width: float,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Replace projection and wrapping width with one geometry rebuild."""

        text_width = self._clamped_text_width(text_width)
        self._projection_document = projection_document
        self._paint_state = empty_projection_paint_state()
        self._prompt_document_view = prompt_document_view
        self._text_width = text_width
        self._rebuild_snapshot()

    def try_apply_same_line_plain_text_edit(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
        edit_start: int,
        edit_end: int,
        replacement_text: str,
        first_dirty_projection_position: int,
        editable_token_id: str | None = None,
        projection_edit_start: int | None = None,
        projection_edit_end: int | None = None,
        projection_replacement_text: str | None = None,
    ) -> PromptProjectionIncrementalLayoutResult | None:
        """Apply a one-character non-wrapping source-backed text edit locally."""

        line_index: int | None = None
        dirty_line_inline_fragment_count = 0

        def reject(
            reason: str,
        ) -> PromptProjectionIncrementalLayoutResult | None:
            return self._reject_incremental_reflow(reason)

        self.last_incremental_reflow_rejection_reason = ""
        previous_document = self._projection_document
        previous_snapshot = self._snapshot
        source_delta = len(replacement_text) - (edit_end - edit_start)
        projection_delta = (
            projection_document.mapping.projection_length
            - previous_document.mapping.projection_length
        )
        if (
            source_delta > 1
            or (projection_delta != source_delta and editable_token_id is None)
        ) or (source_delta == 0 and edit_start == edit_end):
            return reject("unsupported_edit_delta")
        if "\n" in replacement_text or "\r" in replacement_text:
            return reject("newline_edit")
        line_index = _line_index_for_plain_edit(
            previous_snapshot.lines,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
        )
        if line_index is None:
            return reject("dirty_line_not_found")
        previous_line = previous_snapshot.lines[line_index]
        dirty_line_inline_fragment_count = sum(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in previous_line.fragments
        )
        if dirty_line_inline_fragment_count:
            return reject("dirty_line_has_inline_object")
        tag_keep_ranges_changed = (
            prompt_document_view is not None
            and _plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=edit_start,
                edit_end=edit_end,
                replacement_text=replacement_text,
            )
        )
        affected_fragment = editable_text_fragment(
            previous_line.fragments,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
            editable_token_id=editable_token_id,
            projection_edit_start=projection_edit_start,
            projection_edit_end=projection_edit_end,
        )
        empty_line_insert_fragment: PromptProjectionTextFragment | None = None
        if affected_fragment is None and replacement_text:
            next_run = _plain_text_run_for_empty_line_insert(
                projection_document,
                line=previous_line,
                edit_start=edit_start,
                replacement_text=replacement_text,
            )
            if next_run is not None:
                empty_line_insert_fragment = _text_fragment_for_empty_line_insert(
                    previous_line,
                    next_run=next_run,
                    edit_start=edit_start,
                    replacement_text=replacement_text,
                    content_left=(
                        self._document_margin + max(0.0, self._content_left_inset)
                    ),
                    base_font=self._base_font,
                )
        if affected_fragment is None and empty_line_insert_fragment is None:
            return reject("affected_fragment_not_found")
        if affected_fragment is not None:
            next_run = projection_document.run_by_id(affected_fragment.run_id)
            if next_run is None:
                return reject("updated_run_not_found")
            next_fragment = build_edited_text_fragment(
                affected_fragment,
                next_run=next_run,
                edit_start=edit_start,
                edit_end=edit_end,
                replacement_text=replacement_text,
                base_font=self._base_font,
                projection_edit_start=projection_edit_start,
                projection_edit_end=projection_edit_end,
                projection_replacement_text=projection_replacement_text,
            )
            if next_fragment is None:
                return reject("fragment_edit_not_supported")
        else:
            next_fragment = empty_line_insert_fragment
            if next_fragment is None:
                return reject("empty_line_insert_not_supported")
        editable_run = (
            None
            if affected_fragment is None
            else previous_document.run_by_id(affected_fragment.run_id)
        )
        editable_token_stays_in_one_fragment = bool(
            editable_token_id is not None
            and affected_fragment is not None
            and editable_run is not None
            and affected_fragment.projection_start == editable_run.projection_start
            and affected_fragment.projection_end == editable_run.projection_end
        )
        if (
            not editable_token_stays_in_one_fragment
            and _plain_edit_touches_visual_word_wrap_boundary(
                previous_snapshot.lines,
                dirty_line_index=line_index,
                line=previous_line,
                next_source_text=projection_document.source_text,
                edit_start=edit_start,
                edit_end=edit_end,
                replacement_text=replacement_text,
                source_delta=source_delta,
            )
        ):
            return reject("word_wrap_boundary")

        width_delta = (
            next_fragment.rect.width()
            if affected_fragment is None
            else next_fragment.rect.width() - affected_fragment.rect.width()
        )
        content_right = _content_right(
            text_width=self._text_width,
            document_margin=self._document_margin,
            content_left_inset=self._content_left_inset,
        )
        if (
            replacement_text
            and previous_line.rect.right() + width_delta > content_right + 0.01
        ):
            return reject("edit_would_wrap")
        if prompt_document_view is not None and _plain_edit_requires_tag_keep_reflow(
            prompt_document_view,
            previous_source_text=previous_document.source_text,
            lines=previous_snapshot.lines,
            line=previous_line,
            line_index=line_index,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
            source_delta=source_delta,
            width_delta=width_delta,
            content_right=content_right,
            tag_keep_ranges_changed=tag_keep_ranges_changed,
        ):
            return reject("tag_keep_group")

        if affected_fragment is None:
            next_lines = _remap_lines_for_empty_line_plain_insert(
                previous_snapshot.lines,
                projection_document=projection_document,
                dirty_line_index=line_index,
                next_fragment=next_fragment,
                edit_start=edit_start,
                edit_end=edit_end,
                source_delta=source_delta,
                projection_delta=projection_delta,
            )
        else:
            next_lines = _remap_lines_for_same_line_plain_edit(
                previous_snapshot.lines,
                projection_document=projection_document,
                dirty_line_index=line_index,
                affected_fragment=affected_fragment,
                next_fragment=next_fragment,
                edit_start=edit_start,
                edit_end=edit_end,
                source_delta=source_delta,
                projection_delta=projection_delta,
                width_delta=width_delta,
            )
        next_text_fragments = _LineTextFragmentSequence(
            next_lines,
            fragment_count=(
                len(previous_snapshot.text_fragments)
                + (1 if affected_fragment is None else 0)
            ),
        )
        next_inline_fragments = _LineInlineObjectFragmentSequence(
            next_lines,
            fragment_count=len(previous_snapshot.inline_object_fragments),
        )
        next_caret_rects = _LineCaretRectMapping(
            next_lines,
            caret_count=max(
                0,
                len(previous_snapshot.caret_rects_by_projection_position)
                + projection_delta,
            ),
        )
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(previous_snapshot.content_size),
            lines=next_lines,
            text_fragments=next_text_fragments,
            inline_object_fragments=next_inline_fragments,
            caret_rects_by_projection_position=next_caret_rects,
        )
        result = PromptProjectionIncrementalLayoutResult(
            content_height_changed=False,
            content_height_delta=0.0,
            first_reflowed_line_index=line_index,
            reflowed_line_count=1,
            upstream_line_count=line_index,
        )
        return result

    def try_apply_hard_line_break_edit(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
        edit_start: int,
        edit_end: int,
        replacement_text: str,
        first_dirty_projection_position: int,
    ) -> PromptProjectionIncrementalLayoutResult | None:
        """Apply a safe hard-line insert/delete without rebuilding all layout."""

        self.last_incremental_reflow_rejection_reason = ""
        previous_document = self._projection_document
        source_delta = len(replacement_text) - (edit_end - edit_start)
        projection_delta = (
            projection_document.mapping.projection_length
            - previous_document.mapping.projection_length
        )
        if source_delta not in {-1, 1} or projection_delta != source_delta:
            return self._reject_incremental_reflow("unsupported_edit_delta")
        if (
            prompt_document_view is not None
            and _plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=edit_start,
                edit_end=edit_end,
                replacement_text=replacement_text,
            )
        ):
            return self._reject_incremental_reflow("tag_keep_group")
        if replacement_text == "\n" and edit_start == edit_end:
            return self._try_apply_middle_newline_insert(
                projection_document,
                prompt_document_view=prompt_document_view,
                edit_start=edit_start,
                first_dirty_projection_position=first_dirty_projection_position,
            )
        if (
            replacement_text == ""
            and edit_end == edit_start + 1
            and previous_document.source_text[edit_start:edit_end] == "\n"
        ):
            return self._try_apply_middle_newline_delete(
                projection_document,
                prompt_document_view=prompt_document_view,
                edit_start=edit_start,
            )
        return self._reject_incremental_reflow("not_hard_line_break_edit")

    def _try_apply_middle_newline_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None,
        edit_start: int,
        first_dirty_projection_position: int,
    ) -> PromptProjectionIncrementalLayoutResult | None:
        """Split one plain visual line for an inserted hard line break."""

        previous_snapshot = self._snapshot
        line_index = _line_index_for_hard_line_insert(
            previous_snapshot.lines,
            edit_start=edit_start,
        )
        if line_index is None:
            return self._reject_incremental_reflow("dirty_line_not_found")
        previous_line = _concrete_line_snapshot(previous_snapshot.lines[line_index])
        if any(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in previous_line.fragments
        ):
            return self._reject_incremental_reflow("dirty_line_has_inline_object")

        content_left = self._document_margin + max(0.0, self._content_left_inset)
        content_right = _content_right(
            text_width=self._text_width,
            document_margin=self._document_margin,
            content_left_inset=self._content_left_inset,
        )
        split_result = _split_plain_line_for_newline_insert(
            previous_line,
            projection_document=projection_document,
            edit_start=edit_start,
            first_dirty_projection_position=first_dirty_projection_position,
            content_left=content_left,
            content_right=content_right,
        )
        if split_result is None:
            return self._reject_incremental_reflow("line_split_not_supported")
        left_line, right_line = split_result
        line_height_delta = right_line.height
        downstream_lines = tuple(
            _remap_downstream_line_after_hard_line_edit(
                line,
                source_delta=1,
                projection_delta=1,
                y_delta=line_height_delta,
            )
            for line in previous_snapshot.lines[line_index + 1 :]
        )
        next_lines = (
            previous_snapshot.lines[:line_index]
            + (left_line, right_line)
            + downstream_lines
        )
        self._install_incremental_line_break_snapshot(
            projection_document,
            prompt_document_view=prompt_document_view,
            lines=next_lines,
            content_height_delta=line_height_delta,
        )
        return PromptProjectionIncrementalLayoutResult(
            content_height_changed=True,
            content_height_delta=line_height_delta,
            first_reflowed_line_index=line_index,
            reflowed_line_count=max(1, len(next_lines) - line_index),
            upstream_line_count=line_index,
        )

    def _try_apply_middle_newline_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None,
        edit_start: int,
    ) -> PromptProjectionIncrementalLayoutResult | None:
        """Join two adjacent plain visual lines after deleting a hard line break."""

        previous_snapshot = self._snapshot
        line_index = _line_index_for_hard_line_delete(
            previous_snapshot.lines,
            edit_start=edit_start,
        )
        if line_index is None or line_index + 1 >= len(previous_snapshot.lines):
            return self._reject_incremental_reflow("dirty_line_not_found")
        first_line = _concrete_line_snapshot(previous_snapshot.lines[line_index])
        second_line = _concrete_line_snapshot(previous_snapshot.lines[line_index + 1])
        if any(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in first_line.fragments + second_line.fragments
        ):
            return self._reject_incremental_reflow("dirty_line_has_inline_object")

        content_left = self._document_margin + max(0.0, self._content_left_inset)
        content_right = _content_right(
            text_width=self._text_width,
            document_margin=self._document_margin,
            content_left_inset=self._content_left_inset,
        )
        joined_line = _join_plain_lines_after_newline_delete(
            first_line,
            second_line,
            projection_document=projection_document,
            edit_start=edit_start,
            content_left=content_left,
            content_right=content_right,
        )
        if joined_line is None:
            return self._reject_incremental_reflow("line_join_not_supported")
        line_height_delta = -second_line.height
        downstream_lines = tuple(
            _remap_downstream_line_after_hard_line_edit(
                line,
                source_delta=-1,
                projection_delta=-1,
                y_delta=line_height_delta,
            )
            for line in previous_snapshot.lines[line_index + 2 :]
        )
        next_lines = (
            previous_snapshot.lines[:line_index] + (joined_line,) + downstream_lines
        )
        self._install_incremental_line_break_snapshot(
            projection_document,
            prompt_document_view=prompt_document_view,
            lines=next_lines,
            content_height_delta=line_height_delta,
        )
        return PromptProjectionIncrementalLayoutResult(
            content_height_changed=True,
            content_height_delta=line_height_delta,
            first_reflowed_line_index=line_index,
            reflowed_line_count=max(1, len(next_lines) - line_index),
            upstream_line_count=line_index,
        )

    def _install_incremental_line_break_snapshot(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None,
        lines: tuple[PromptProjectionLineSnapshot, ...],
        content_height_delta: float,
    ) -> None:
        """Install a line-break incremental snapshot derived from visual lines."""

        previous_snapshot = self._snapshot
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(
                previous_snapshot.content_size.width(),
                max(
                    1.0, previous_snapshot.content_size.height() + content_height_delta
                ),
            ),
            lines=lines,
            text_fragments=_LineTextFragmentSequence(
                lines,
                fragment_count=sum(_line_text_fragment_count(line) for line in lines),
            ),
            inline_object_fragments=_LineInlineObjectFragmentSequence(
                lines,
                fragment_count=sum(_line_inline_fragment_count(line) for line in lines),
            ),
            caret_rects_by_projection_position=_LineCaretRectMapping(
                lines,
                caret_count=projection_document.mapping.projection_length + 1,
            ),
        )

    def _reject_incremental_reflow(
        self,
        reason: str,
    ) -> PromptProjectionIncrementalLayoutResult | None:
        """Record why a same-line incremental reflow attempt was refused."""

        self.last_incremental_reflow_rejection_reason = reason
        return None

    def set_projection_paint_state(
        self,
        paint_state: PromptProjectionPaintState,
    ) -> None:
        """Replace geometry-neutral paint state without touching layout geometry."""

        if not self.can_apply_paint_state(paint_state):
            raise ValueError("paint state references unknown projection ids")
        self._paint_state = paint_state

    def prewarm_geometry_reuse_indexes(self) -> None:
        """Populate snapshot indexes used by emphasis geometry-reuse checks."""

        for run in self._projection_document.runs:
            if run.kind is PromptProjectionRunKind.INLINE_OBJECT:
                self._snapshot.inline_object_fragments_for_run(run.run_id)

    def can_apply_paint_state(
        self,
        paint_state: PromptProjectionPaintState,
    ) -> bool:
        """Return whether paint state references only canonical layout ids."""

        token_ids = frozenset(
            token.token_id for token in self._projection_document.tokens
        )
        run_ids = frozenset(run.run_id for run in self._projection_document.runs)
        return paint_state.references_only(token_ids=token_ids, run_ids=run_ids)

    def _inline_object_fragment_size(
        self,
        run: PromptProjectionRun,
    ) -> QSizeF | None:
        """Return the current laid-out inline size for one existing run."""

        fragments = self._snapshot.inline_object_fragments_for_run(run.run_id)
        if len(fragments) != 1:
            return None
        return QSizeF(fragments[0].rect.size())

    def try_apply_trailing_plain_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Apply a one-character trailing plain-text delete without relayout."""

        previous_document = self._projection_document
        previous_snapshot = self._snapshot
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length - 1
            or next_projection_length != previous_projection_length - 1
            or projection_document.source_text
            != previous_document.source_text[:next_source_length]
            or projection_document.projection_text
            != previous_document.projection_text[:next_projection_length]
            or not previous_snapshot.lines
            or not previous_snapshot.text_fragments
        ):
            return False

        previous_fragment = previous_snapshot.text_fragments[-1]
        previous_line = previous_snapshot.lines[-1]
        if (
            previous_fragment.projection_end != previous_projection_length
            or previous_fragment.source_positions[-1] != previous_source_length
            or not previous_fragment.text
            or not previous_line.fragments
            or previous_line.fragments[-1] != previous_fragment
        ):
            return False

        previous_fragment = _concrete_text_fragment(previous_fragment)
        previous_line = _concrete_line_snapshot(previous_line)
        next_fragment_text = previous_fragment.text[:-1]
        next_fragment_source_positions = tuple(previous_fragment.source_positions[:-1])
        next_fragment_boundary_offsets = previous_fragment.boundary_offsets[:-1]
        if not next_fragment_boundary_offsets:
            return False

        next_fragment_rect = QRectF(previous_fragment.rect)
        next_fragment_rect.setWidth(max(1.0, next_fragment_boundary_offsets[-1]))
        next_fragment = replace(
            previous_fragment,
            projection_end=next_projection_length,
            text=next_fragment_text,
            source_positions=next_fragment_source_positions,
            rect=next_fragment_rect,
            boundary_offsets=next_fragment_boundary_offsets,
        )
        if next_fragment_text:
            next_line_fragments = previous_line.fragments[:-1] + (next_fragment,)
            next_text_fragments = tuple(previous_snapshot.text_fragments[:-1]) + (
                next_fragment,
            )
        else:
            next_line_fragments = previous_line.fragments[:-1]
            next_text_fragments = tuple(previous_snapshot.text_fragments[:-1])

        next_line = replace(
            previous_line,
            source_end=min(previous_line.source_end, next_source_length),
            source_content_end=min(
                previous_line.source_content_end,
                next_source_length,
            ),
            fragments=next_line_fragments,
            caret_stops=tuple(
                stop
                for stop in previous_line.caret_stops
                if stop.projection_position <= next_projection_length
            ),
        )
        next_lines = previous_snapshot.lines[:-1] + (next_line,)
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(previous_snapshot.content_size),
            lines=next_lines,
            text_fragments=next_text_fragments,
            inline_object_fragments=previous_snapshot.inline_object_fragments,
            caret_rects_by_projection_position=_LineCaretRectMapping(
                next_lines,
                caret_count=next_projection_length + 1,
            ),
        )
        return True

    def try_apply_trailing_newline_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Apply a trailing hard-line delete without full relayout."""

        previous_document = self._projection_document
        previous_snapshot = self._snapshot
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length - 1
            or next_projection_length != previous_projection_length - 1
            or not previous_document.source_text.endswith("\n")
            or projection_document.source_text != previous_document.source_text[:-1]
            or projection_document.projection_text
            != previous_document.projection_text[:-1]
            or len(previous_snapshot.lines) < 2
        ):
            return False

        previous_content_line = previous_snapshot.lines[-2]
        previous_empty_line = previous_snapshot.lines[-1]
        if (
            previous_empty_line.fragments
            or previous_empty_line.line_break_start is not None
            or previous_empty_line.source_start != previous_source_length
            or previous_empty_line.source_end != previous_source_length
            or previous_content_line.line_break_start != next_source_length
            or previous_content_line.line_break_end != previous_source_length
        ):
            return False

        previous_content_line = _concrete_line_snapshot(previous_content_line)
        next_content_line = replace(
            previous_content_line,
            source_end=next_source_length,
            line_break_start=None,
            line_break_end=None,
            caret_stops=tuple(
                stop
                for stop in previous_content_line.caret_stops
                if stop.projection_position <= next_projection_length
            ),
        )
        last_stop = (
            next_content_line.caret_stops[-1] if next_content_line.caret_stops else None
        )
        if last_stop is not None and all(
            stop.projection_position != next_projection_length
            for stop in next_content_line.caret_stops
        ):
            next_content_line = replace(
                next_content_line,
                caret_stops=next_content_line.caret_stops
                + (
                    PromptProjectionLineCaretStopSnapshot(
                        projection_position=next_projection_length,
                        rect=QRectF(last_stop.rect),
                    ),
                ),
            )
        content_height = max(
            1.0,
            previous_snapshot.content_size.height() - previous_empty_line.height,
        )
        next_lines = previous_snapshot.lines[:-2] + (next_content_line,)
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(previous_snapshot.content_size.width(), content_height),
            lines=next_lines,
            text_fragments=previous_snapshot.text_fragments,
            inline_object_fragments=previous_snapshot.inline_object_fragments,
            caret_rects_by_projection_position=_LineCaretRectMapping(
                next_lines,
                caret_count=next_projection_length + 1,
            ),
        )
        return True

    def try_apply_trailing_plain_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Apply a trailing plain-text insert that preserves canonical grouping."""

        previous_document = self._projection_document
        previous_snapshot = self._snapshot
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        appended_length = next_source_length - previous_source_length
        if (
            appended_length <= 0
            or next_projection_length != previous_projection_length + appended_length
            or projection_document.source_text[:previous_source_length]
            != previous_document.source_text
            or projection_document.projection_text[:previous_projection_length]
            != previous_document.projection_text
            or not previous_snapshot.lines
            or not previous_snapshot.text_fragments
        ):
            return False

        previous_fragment = previous_snapshot.text_fragments[-1]
        previous_line = previous_snapshot.lines[-1]
        if (
            previous_fragment.projection_end != previous_projection_length
            or previous_fragment.source_positions[-1] != previous_source_length
            or not previous_line.fragments
            or previous_line.fragments[-1] != previous_fragment
        ):
            return False

        previous_fragment = _concrete_text_fragment(previous_fragment)
        previous_line = _concrete_line_snapshot(previous_line)
        appended_text = projection_document.projection_text[previous_projection_length:]
        if len(appended_text) != appended_length or any(
            character in {"\n", "\r"} for character in appended_text
        ):
            return False
        if (
            prompt_document_view is not None
            and _plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=previous_source_length,
                edit_end=previous_source_length,
                replacement_text=appended_text,
            )
        ):
            return False
        next_fragment_text = previous_fragment.text + appended_text
        next_fragment_source_positions = tuple(
            previous_fragment.source_positions
        ) + tuple(range(previous_source_length + 1, next_source_length + 1))
        next_fragment_boundary_offsets = text_boundary_offsets(
            next_fragment_text,
            self._base_font,
        )
        if len(next_fragment_boundary_offsets) != len(next_fragment_text) + 1:
            return False

        next_width = next_fragment_boundary_offsets[-1]
        content_right = (
            self._document_margin
            + max(0.0, self._content_left_inset)
            + max(
                1.0,
                self._text_width
                - (self._document_margin * 2.0)
                - max(0.0, self._content_left_inset),
            )
        )
        if previous_fragment.rect.left() + next_width > content_right + 0.01:
            return False

        next_fragment_rect = QRectF(previous_fragment.rect)
        next_fragment_rect.setWidth(max(1.0, next_width))
        next_fragment = replace(
            previous_fragment,
            projection_end=next_projection_length,
            text=next_fragment_text,
            source_positions=next_fragment_source_positions,
            rect=next_fragment_rect,
            boundary_offsets=next_fragment_boundary_offsets,
        )
        first_appended_boundary_index = len(previous_fragment.text) + 1
        appended_caret_stops = tuple(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=(
                    previous_fragment.projection_start + boundary_index
                ),
                rect=QRectF(
                    previous_fragment.rect.left()
                    + next_fragment_boundary_offsets[boundary_index],
                    previous_line.top,
                    1.0,
                    previous_line.height,
                ),
            )
            for boundary_index in range(
                first_appended_boundary_index,
                len(next_fragment_boundary_offsets),
            )
        )
        next_line = replace(
            previous_line,
            source_end=next_source_length,
            source_content_end=next_source_length,
            fragments=previous_line.fragments[:-1] + (next_fragment,),
            caret_stops=previous_line.caret_stops + appended_caret_stops,
        )
        next_lines = previous_snapshot.lines[:-1] + (next_line,)
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(previous_snapshot.content_size),
            lines=next_lines,
            text_fragments=tuple(previous_snapshot.text_fragments[:-1])
            + (next_fragment,),
            inline_object_fragments=previous_snapshot.inline_object_fragments,
            caret_rects_by_projection_position=_LineCaretRectMapping(
                next_lines,
                caret_count=next_projection_length + 1,
            ),
        )
        return True

    def try_apply_trailing_newline_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Apply a trailing hard-line insert without full relayout."""

        previous_document = self._projection_document
        previous_snapshot = self._snapshot
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length + 1
            or next_projection_length != previous_projection_length + 1
            or projection_document.source_text != previous_document.source_text + "\n"
            or projection_document.projection_text
            != previous_document.projection_text + "\n"
            or not previous_snapshot.lines
        ):
            return False

        previous_line = previous_snapshot.lines[-1]
        previous_line = _concrete_line_snapshot(previous_line)
        base_line_height = self._metrics.text_line_height
        content_left = self._metrics.content_left
        next_line_top = previous_line.top + previous_line.height
        next_line_caret_rect = self._metrics.caret_rect(
            x_left=content_left,
            row_top=next_line_top,
            row_height=base_line_height,
        )
        next_line = PromptProjectionLineSnapshot(
            top=next_line_top,
            height=base_line_height,
            source_start=next_source_length,
            source_end=next_source_length,
            source_content_start=next_source_length,
            source_content_end=next_source_length,
            line_break_start=None,
            line_break_end=None,
            fragments=(),
            caret_stops=(
                PromptProjectionLineCaretStopSnapshot(
                    projection_position=next_projection_length,
                    rect=QRectF(next_line_caret_rect),
                ),
            ),
        )
        next_previous_line = replace(
            previous_line,
            source_end=next_source_length,
            line_break_start=previous_source_length,
            line_break_end=next_source_length,
        )
        next_lines = previous_snapshot.lines[:-1] + (next_previous_line, next_line)
        self._projection_document = projection_document
        self._prompt_document_view = prompt_document_view
        self._snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(
                previous_snapshot.content_size.width(),
                previous_snapshot.content_size.height() + base_line_height,
            ),
            lines=next_lines,
            text_fragments=previous_snapshot.text_fragments,
            inline_object_fragments=previous_snapshot.inline_object_fragments,
            caret_rects_by_projection_position=_LineCaretRectMapping(
                next_lines,
                caret_count=next_projection_length + 1,
            ),
        )
        return True

    def set_text_width(self, width: float) -> None:
        """Set the wrapping width used by the prompt projection layout."""

        width = self._clamped_text_width(width)
        if abs(self._text_width - width) < 0.01:
            return
        self._text_width = width
        self._rebuild_snapshot()

    def set_content_left_inset(self, inset: float) -> None:
        """Reserve horizontal space before projected prompt content."""

        inset = max(0.0, inset)
        if abs(self._content_left_inset - inset) < 0.01:
            return
        self._content_left_inset = inset
        self._rebuild_snapshot()

    def content_size(self) -> QSizeF:
        """Return the laid-out content size of the visible projection."""

        return self._snapshot.content_size

    def text_fragment_count(self) -> int:
        """Return the number of text fragments in the current layout snapshot."""

        return len(self._snapshot.text_fragments)

    def inline_object_fragment_count(self) -> int:
        """Return the number of inline-object fragments in the current layout snapshot."""

        return len(self._snapshot.inline_object_fragments)

    def line_count(self) -> int:
        """Return the number of wrapped lines in the current layout snapshot."""

        return len(self._snapshot.lines)

    def occupied_content_size(self) -> QSizeF:
        """Return the visible projection size occupied by painted content plus margins."""

        occupied_right = self._document_margin
        occupied_bottom = self._document_margin
        for line in self._snapshot.lines:
            if not line.fragments:
                occupied_bottom = max(occupied_bottom, line.top + line.height)
                continue
            occupied_right = max(occupied_right, line.rect.right())
            occupied_bottom = max(occupied_bottom, line.top + line.height)
        return QSizeF(
            max(1.0, occupied_right + self._document_margin),
            max(1.0, occupied_bottom + self._document_margin),
        )

    def draw(
        self,
        painter: QPainter,
        *,
        selection: PromptProjectionSelection | None,
        scroll_offset: float,
        clip_rect: QRectF,
        excluded_region: QRegion | None = None,
    ) -> None:
        """Delegate visible projection painting to the projection painter."""

        self._painter.draw(
            painter,
            selection=selection,
            scroll_offset=scroll_offset,
            clip_rect=clip_rect,
            excluded_region=excluded_region,
        )

    def paint_selection(
        self,
        selection: PromptProjectionSelection | None,
        painter: QPainter,
    ) -> None:
        """Delegate source-backed selection painting to the projection painter."""

        self._painter.paint_selection(selection, painter)

    def selection_rects(
        self,
        selection: PromptProjectionSelection | None,
    ) -> tuple[QRectF, ...]:
        """Return projection-aligned document rects for one source-backed selection."""

        return self._selection_geometry.selection_rects(selection)

    def cursor_rect(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF:
        """Return the viewport-local caret rect for one logical caret state."""

        return self._selection_geometry.cursor_rect(
            caret_state,
            scroll_offset=scroll_offset,
        )

    def horizontal_soft_wrap_transition(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return a same-source horizontal move across a soft-wrap boundary."""

        return self._selection_geometry.horizontal_soft_wrap_transition(
            caret_state,
            direction=direction,
            current_rect=current_rect,
        )

    def horizontal_line_edge_affinity(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        origin_rect: QRectF,
    ) -> QRectF | None:
        """Return the origin row's edge rect when a source move lands on a wrap edge."""

        return self._selection_geometry.horizontal_line_edge_affinity(
            caret_state,
            direction=direction,
            origin_rect=origin_rect,
        )

    def horizontal_line_local_adjacent_target(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return the adjacent caret stop on the current visual line."""

        return self._selection_geometry.horizontal_line_local_adjacent_target(
            caret_state,
            direction=direction,
            current_rect=current_rect,
        )

    def source_line_rects(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible viewport rects for newline-delimited source lines."""

        return self._selection_geometry.source_line_rects(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def vertical_caret_target(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        preferred_x: float,
        current_line_index: int | None = None,
    ) -> PromptProjectionVerticalCaretTarget | None:
        """Resolve one vertical caret target using adjacent-line or edge-clamp rules."""

        return self._selection_geometry.vertical_caret_target(
            caret_state,
            direction=direction,
            preferred_x=preferred_x,
            current_line_index=current_line_index,
        )

    def hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Return the logical caret state implied by one viewport-local pointer point."""

        return self._hit_tester.hit_test(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def caret_hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Return the logical and visual caret target for one pointer point."""

        return self._hit_tester.caret_hit_test(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def resolve_drag_selection_endpoint(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Resolve one drag-selection endpoint using wrapped-line row progression."""

        return self._hit_tester.resolve_drag_selection_endpoint(
            viewport_position,
            scroll_offset=scroll_offset,
            anchor_line_index=anchor_line_index,
            preferred_line_index=preferred_line_index,
        )

    def source_range_fragments(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments for one raw source range."""

        return self._selection_geometry.source_range_fragments(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def reorder_projection_paint_snapshot(
        self,
        *,
        key: PromptReorderProjectionSnapshotKey,
        source_ranges: Sequence[tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderProjectionPaintSnapshot:
        """Return cached-paint-ready projection fragments for one reorder chip."""

        document_clip = viewport_rect.translated(0.0, scroll_offset)
        normalized_ranges = _normalized_source_ranges(source_ranges)
        fragments: list[PromptReorderProjectionPaintFragment] = []
        for line in _reorder_visible_lines(
            self._snapshot.lines,
            document_clip=document_clip,
        ):
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionTextFragment):
                    fragments.extend(
                        self._reorder_text_paint_fragments(
                            fragment,
                            source_ranges=normalized_ranges,
                            scroll_offset=scroll_offset,
                        )
                    )
                    continue
                inline_fragment = self._reorder_inline_object_paint_fragment(
                    fragment,
                    source_ranges=normalized_ranges,
                    scroll_offset=scroll_offset,
                )
                if inline_fragment is not None:
                    fragments.append(inline_fragment)
        return PromptReorderProjectionPaintSnapshot(
            key=key,
            fragments=tuple(fragments),
            source_ranges=normalized_ranges,
        )

    def _reorder_text_paint_fragments(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        source_ranges: tuple[tuple[int, int], ...],
        scroll_offset: float,
    ) -> tuple[PromptReorderTextPaintFragment, ...]:
        """Return chip-owned slices from one prepared projection text fragment."""

        if not fragment.source_positions:
            return ()
        font = self._painter.font_for_fragment(fragment)
        color = self._painter.text_color_for_fragment(fragment)
        text_fragments: list[PromptReorderTextPaintFragment] = []
        for chunk_start, chunk_end in _source_position_chunks(
            fragment.source_positions[: len(fragment.text)],
            source_ranges=source_ranges,
        ):
            if chunk_end <= chunk_start:
                continue
            left = fragment.rect.left() + fragment.boundary_offsets[chunk_start]
            right = fragment.rect.left() + fragment.boundary_offsets[chunk_end]
            text_fragments.append(
                PromptReorderTextPaintFragment(
                    text=fragment.text[chunk_start:chunk_end],
                    font=QFont(font),
                    baseline=QPointF(left, fragment.baseline - scroll_offset),
                    text_rect=QRectF(
                        left,
                        fragment.rect.top() - scroll_offset,
                        max(0.0, right - left),
                        fragment.rect.height(),
                    ),
                    color=QColor(color),
                )
            )
        return tuple(text_fragments)

    def _reorder_inline_object_paint_fragment(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        source_ranges: tuple[tuple[int, int], ...],
        scroll_offset: float,
    ) -> PromptReorderInlineObjectPaintFragment | None:
        """Return a chip-owned inline object fragment from prepared projection state."""

        if not _source_positions_overlap(fragment.source_positions, source_ranges):
            return None
        run = self._projection_document.run_by_id(fragment.run_id)
        token = self._projection_document.token_by_id(fragment.token_id)
        renderer = self.inline_object_renderers.renderer_for(fragment.renderer_key)
        if run is None or token is None or renderer is None:
            return None
        return PromptReorderInlineObjectPaintFragment(
            renderer=renderer,
            rect=fragment.rect.translated(0.0, -scroll_offset),
            run=run,
            token=token,
            base_font=QFont(self._base_font),
            palette=QPalette(self._palette),
        )

    def _selection_rects_from_geometry(
        self,
        selection: PromptProjectionSelection | None,
    ) -> tuple[QRectF, ...]:
        """Return projection-aligned document rects for one source-backed selection."""

        if selection is None or selection.is_empty:
            return ()
        return self._merged_rects(self._selection_rects_for_selection(selection))

    def _cursor_rect_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF:
        """Return the viewport-local caret rect for one logical caret state."""

        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        rect = self._caret_rect_for_projection_position(projection_position)
        return rect.translated(0.0, -scroll_offset)

    def line_index_for_document_y(self, y_position: float) -> int | None:
        """Return the wrapped-line index owning one document-local y coordinate."""

        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if (line.top - 1.0) <= y_position <= (line_bottom + 1.0):
                return line_index
        return None

    def visual_line_range_viewport_rect(
        self,
        *,
        first_line_index: int,
        line_count: int,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> QRectF | None:
        """Return the viewport rect covering one contiguous visual-line range."""

        if line_count <= 0 or viewport_rect.isEmpty():
            return None
        start_index = max(0, first_line_index)
        end_index = min(len(self._snapshot.lines), start_index + line_count)
        if start_index >= end_index:
            return None
        repaint_rect: QRectF | None = None
        for line in self._snapshot.lines[start_index:end_index]:
            line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            )
            repaint_rect = (
                line_rect if repaint_rect is None else repaint_rect.united(line_rect)
            )
        if repaint_rect is None:
            return None
        clipped_rect = repaint_rect.intersected(viewport_rect)
        if not clipped_rect.isValid() or clipped_rect.isEmpty():
            return None
        return clipped_rect

    def source_position_at_visual_line_content_end(self, source_position: int) -> bool:
        """Return whether a source position sits at a visual line content end."""

        for line in self._snapshot.lines:
            if line.source_content_end == source_position:
                return True
        return False

    def _horizontal_soft_wrap_transition_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return a same-source horizontal move across a soft-wrap boundary."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(current_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        current_stop = self._line_caret_stop_for_projection_position(
            line,
            projection_position,
        )
        if current_stop is None:
            return None
        if direction > 0:
            if current_stop is not line.caret_stops[-1]:
                return None
            if line_index + 1 >= len(self._snapshot.lines):
                return None
            next_line = self._snapshot.lines[line_index + 1]
            if (
                not next_line.caret_stops
                or next_line.caret_stops[0].projection_position != projection_position
            ):
                return None
            return PromptProjectionHorizontalCaretTarget(
                state=resolved_state,
                rect=QRectF(next_line.caret_stops[0].rect),
            )

        if current_stop is not line.caret_stops[0] or line_index <= 0:
            return None
        previous_line = self._snapshot.lines[line_index - 1]
        if (
            not previous_line.caret_stops
            or previous_line.caret_stops[-1].projection_position != projection_position
        ):
            return None
        return PromptProjectionHorizontalCaretTarget(
            state=resolved_state,
            rect=QRectF(previous_line.caret_stops[-1].rect),
        )

    def _horizontal_line_edge_affinity_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        origin_rect: QRectF,
    ) -> QRectF | None:
        """Return the origin row's edge rect when a source move lands on a wrap edge."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(origin_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        if (
            direction > 0
            and line.caret_stops[-1].projection_position == projection_position
        ):
            return QRectF(line.caret_stops[-1].rect)
        if (
            direction < 0
            and line.caret_stops[0].projection_position == projection_position
        ):
            return QRectF(line.caret_stops[0].rect)
        return None

    def _horizontal_line_local_adjacent_target_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return the adjacent caret stop on the current visual line."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(current_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        adjacent_state = (
            self._projection_document.caret_map.next_state(resolved_state)
            if direction > 0
            else self._projection_document.caret_map.previous_state(resolved_state)
        )
        # Token edges and content boundaries can share one visible x-position.
        if (
            adjacent_state != resolved_state
            and self._projection_document.caret_map.projection_position_for_state(
                adjacent_state
            )
            == projection_position
        ):
            return PromptProjectionHorizontalCaretTarget(
                state=adjacent_state,
                rect=self.cursor_rect(adjacent_state, scroll_offset=0.0),
            )
        current_stop_index = self._line_caret_stop_index_for_projection_position(
            line,
            projection_position,
            current_rect=current_rect,
        )
        if current_stop_index is None:
            return None
        target_stop_index = current_stop_index + direction
        if target_stop_index < 0 or target_stop_index >= len(line.caret_stops):
            return None
        target_stop = line.caret_stops[target_stop_index]
        target_state = (
            self._projection_document.caret_map.state_for_projection_position(
                target_stop.projection_position,
                prefer_after=direction > 0,
            )
        )
        return PromptProjectionHorizontalCaretTarget(
            state=self._projection_document.caret_map.resolve_state(target_state),
            rect=QRectF(target_stop.rect),
        )

    def _source_line_rects_from_geometry(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible viewport rects for newline-delimited source lines."""

        source_text = self._projection_document.source_text
        line_ranges = _source_line_ranges(source_text)
        visible_rects: list[PromptProjectionSourceLineRect] = []
        for line_index, (source_start, source_end) in enumerate(line_ranges):
            document_rect = self._source_line_document_rect(
                source_start=source_start,
                source_end=source_end,
            )
            if document_rect is None:
                continue
            viewport_line_rect = QRectF(
                viewport_rect.left(),
                document_rect.top() - scroll_offset,
                viewport_rect.width(),
                document_rect.height(),
            )
            clipped_rect = viewport_line_rect.intersected(viewport_rect)
            if clipped_rect.isValid() and not clipped_rect.isEmpty():
                visible_rects.append(
                    PromptProjectionSourceLineRect(
                        line_index=line_index,
                        rect=viewport_line_rect,
                    )
                )
        return tuple(visible_rects)

    def _caret_rect_for_projection_position(self, projection_position: int) -> QRectF:
        """Return a caret rect without falling back to document origin for live lines."""

        try:
            return QRectF(
                self._snapshot.caret_rects_by_projection_position[projection_position]
            )
        except KeyError:
            pass
        nearest_stop = self._nearest_line_caret_stop_for_projection_position(
            projection_position
        )
        if nearest_stop is not None:
            return QRectF(nearest_stop.rect)
        return QRectF(
            0.0,
            self._document_margin,
            1.0,
            self._metrics.text_line_height,
        )

    @staticmethod
    def _line_caret_stop_for_projection_position(
        line: PromptProjectionLineSnapshot,
        projection_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the line-local caret stop for one projection boundary."""

        for caret_stop in line.caret_stops:
            if caret_stop.projection_position == projection_position:
                return caret_stop
        return None

    @staticmethod
    def _line_caret_stop_index_for_projection_position(
        line: PromptProjectionLineSnapshot,
        projection_position: int,
        *,
        current_rect: QRectF,
    ) -> int | None:
        """Return the line-local stop index nearest to the current visual rect."""

        nearest_index: int | None = None
        nearest_distance: float | None = None
        for index, caret_stop in enumerate(line.caret_stops):
            if caret_stop.projection_position != projection_position:
                continue
            distance = abs(caret_stop.rect.center().x() - current_rect.center().x())
            if nearest_distance is None or distance < nearest_distance:
                nearest_index = index
                nearest_distance = distance
        return nearest_index

    def _nearest_line_caret_stop_for_projection_position(
        self,
        projection_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the nearest line-local caret stop by projection distance."""

        nearest_stop: PromptProjectionLineCaretStopSnapshot | None = None
        nearest_distance: int | None = None
        for line in self._snapshot.lines:
            for caret_stop in line.caret_stops:
                distance = abs(caret_stop.projection_position - projection_position)
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    nearest_stop = caret_stop
        return nearest_stop

    def source_line_index_for_position(self, source_position: int) -> int:
        """Return the newline-delimited source line containing one cursor position."""

        source_text = self._projection_document.source_text
        clamped_position = max(0, min(source_position, len(source_text)))
        for line_index, (source_start, source_end) in enumerate(
            _source_line_ranges(source_text)
        ):
            if source_start <= clamped_position < source_end:
                return line_index
            if source_start == source_end == clamped_position:
                return line_index
        return max(0, len(_source_line_ranges(source_text)) - 1)

    def _vertical_caret_target_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        preferred_x: float,
        current_line_index: int | None = None,
    ) -> PromptProjectionVerticalCaretTarget | None:
        """Resolve one vertical caret target using adjacent-line or edge-clamp rules."""

        if direction not in (-1, 1):
            raise ValueError("Vertical caret movement direction must be -1 or 1.")

        if not self._snapshot.lines:
            return None

        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        if current_line_index is None:
            current_line_index = self.line_index_for_document_y(
                self.cursor_rect(resolved_state, scroll_offset=0.0).center().y()
            )
        if current_line_index is None:
            return None

        target_line_index = current_line_index + direction
        if target_line_index < 0:
            target_line_index = 0
        elif target_line_index >= len(self._snapshot.lines):
            target_line_index = len(self._snapshot.lines) - 1

        target_line = self._snapshot.lines[target_line_index]
        if not target_line.caret_stops:
            return None

        if target_line_index == current_line_index:
            target_stop = (
                target_line.caret_stops[0]
                if direction < 0
                else target_line.caret_stops[-1]
            )
        else:
            target_stop = min(
                target_line.caret_stops,
                key=lambda caret_stop: abs(caret_stop.rect.center().x() - preferred_x),
            )
        target_state = (
            self._projection_document.caret_map.state_for_projection_position(
                target_stop.projection_position,
                prefer_after=preferred_x >= target_stop.rect.center().x(),
            )
        )
        return PromptProjectionVerticalCaretTarget(
            state=self._projection_document.caret_map.resolve_state(target_state),
            rect=QRectF(target_stop.rect),
        )

    def token_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the viewport-local union rect occupied by one semantic token."""

        token_fragments = self._token_fragments(token)
        if not token_fragments:
            return None
        token_rect = QRectF(token_fragments[0].rect)
        for fragment in token_fragments[1:]:
            token_rect = token_rect.united(fragment.rect)
        return token_rect.translated(0.0, -scroll_offset)

    def token_anchor_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the renderer-defined anchor rect for one projected token."""

        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is not PromptProjectionRunKind.INLINE_OBJECT:
                continue
            renderer = self.inline_object_renderers.renderer_for(run.renderer_key)
            if renderer is None:
                continue
            object_fragments = self._snapshot.inline_object_fragments_for_run(
                run.run_id
            )
            if not object_fragments:
                continue
            anchor_rect = renderer.anchor_rect(
                run,
                token,
                object_fragments[-1].rect.translated(0.0, -scroll_offset),
                base_font=self._base_font,
            )
            if anchor_rect is not None:
                return anchor_rect
        return None

    def token_weight_text_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the viewport-local slot rect of one emphasis token weight label."""

        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is not PromptProjectionRunKind.INLINE_OBJECT:
                continue
            renderer = self.inline_object_renderers.renderer_for(run.renderer_key)
            if not isinstance(
                renderer,
                PromptEmphasisSuffixRenderer
                | PromptLoraInlineObjectRenderer
                | PromptWildcardInlineObjectRenderer,
            ):
                continue
            object_fragments = self._snapshot.inline_object_fragments_for_run(
                run.run_id
            )
            if not object_fragments:
                continue
            weight_rect = renderer.weight_text_rect(
                run,
                token,
                object_fragments[-1].rect.translated(0.0, -scroll_offset),
                base_font=self._base_font,
            )
            if weight_rect is not None:
                return weight_rect
        return None

    def _hit_test_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Return the logical caret state implied by one viewport-local pointer point."""

        return self.caret_hit_test(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        ).state

    def _caret_hit_test_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Return the logical and visual caret target for one pointer point."""

        document_position = QPointF(
            viewport_position.x(),
            viewport_position.y() + scroll_offset,
        )
        object_fragment = self._snapshot.inline_object_fragment_at(document_position)
        if object_fragment is not None:
            run = self._projection_document.run_by_id(object_fragment.run_id)
            token = self._projection_document.token_by_id(object_fragment.token_id)
            if run is not None and token is not None:
                renderer = self.inline_object_renderers.renderer_for(
                    object_fragment.renderer_key
                )
                if renderer is not None:
                    state = self._projection_document.caret_map.resolve_state(
                        renderer.hit_test_caret_state(
                            run,
                            token,
                            object_fragment.rect,
                            document_position,
                            base_font=self._base_font,
                        )
                    )
                    return PromptProjectionCaretHit(
                        state=state,
                        document_rect=self._inline_object_caret_rect_for_state(
                            object_fragment,
                            state,
                        ),
                    )

        line_index = self._line_index_for_pointer_y(
            document_position.y(),
            preferred_line_index=preferred_line_index,
        )
        if line_index is None:
            return PromptProjectionCaretHit(
                state=PromptProjectionCaretState(source_position=0),
                document_rect=QRectF(
                    0.0,
                    self._document_margin,
                    1.0,
                    self._metrics.text_line_height,
                ),
            )

        line = self._snapshot.lines[line_index]
        line_hit = self._line_text_fragment_caret_hit(line, document_position)
        if line_hit is not None:
            return line_hit

        line_caret_stop = self._line_caret_stop_nearest_x(line, document_position.x())
        if line_caret_stop is not None:
            return self._line_caret_stop_hit(
                line_caret_stop,
                x_position=document_position.x(),
            )

        return self._nearest_document_caret_hit(document_position)

    def _resolve_drag_selection_endpoint_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Resolve one drag-selection endpoint using wrapped-line row progression."""

        document_position = QPointF(
            viewport_position.x(),
            viewport_position.y() + scroll_offset,
        )
        line_index = self._drag_line_index_for_pointer_y(
            document_position.y(),
            anchor_line_index=anchor_line_index,
            preferred_line_index=preferred_line_index,
        )
        if line_index is None:
            return PromptProjectionDragSelectionTarget(
                state=self._nearest_document_caret_state(document_position),
                line_index=None,
            )

        line = self._snapshot.lines[line_index]
        line_caret_stop = self._drag_line_caret_stop_for_x(
            line,
            document_position.x(),
            direction=_drag_direction(
                anchor_line_index=anchor_line_index,
                line_index=line_index,
            ),
        )
        if line_caret_stop is None:
            return PromptProjectionDragSelectionTarget(
                state=self._nearest_document_caret_state(document_position),
                line_index=line_index,
            )

        return PromptProjectionDragSelectionTarget(
            state=self._projection_document.caret_map.resolve_state(
                self._projection_document.caret_map.state_for_projection_position(
                    line_caret_stop.projection_position
                )
            ),
            line_index=line_index,
        )

    def _source_range_fragments_from_geometry(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments for one raw source range."""

        translated_rects = tuple(
            rect.translated(0.0, -scroll_offset)
            for rect in self._merged_rects(
                self._content_rects_for_source_range(start=start, end=end)
            )
        )
        return tuple(
            rect.intersected(viewport_rect)
            for rect in translated_rects
            if rect.intersected(viewport_rect).isValid()
            and not rect.intersected(viewport_rect).isEmpty()
        )

    def _visible_source_range_fragments(
        self,
        start: int,
        end: int,
        *,
        visible_lines: tuple[PromptProjectionLineSnapshot, ...],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return viewport fragments by scanning visible lines only."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()

        selection = PromptProjectionSelection(range_start, range_end)
        content_rects: list[QRectF] = []
        for line in visible_lines:
            if not _source_range_intersects_visual_line(
                source_start=range_start,
                source_end=range_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            ):
                continue
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionTextFragment):
                    selection_bounds = self._text_fragment_selection_bounds(
                        fragment,
                        selection,
                    )
                    if selection_bounds is None:
                        continue
                    start_index, end_index = selection_bounds
                    content_rects.append(
                        QRectF(
                            fragment.rect.left()
                            + fragment.boundary_offsets[start_index],
                            fragment.rect.top(),
                            max(
                                1.0,
                                fragment.boundary_offsets[end_index]
                                - fragment.boundary_offsets[start_index],
                            ),
                            fragment.rect.height(),
                        )
                    )
                    continue
                run = self._projection_document.run_by_id(fragment.run_id)
                projection_token = self._projection_document.token_by_id(
                    fragment.token_id
                )
                if run is None or projection_token is None:
                    continue
                renderer = self.inline_object_renderers.renderer_for(
                    fragment.renderer_key
                )
                if renderer is None:
                    continue
                content_rects.extend(
                    renderer.selection_rects(
                        run,
                        projection_token,
                        fragment.rect,
                        selection_start=range_start,
                        selection_end=range_end,
                        base_font=self._base_font,
                    )
                )

        translated_rects = tuple(
            rect.translated(0.0, -scroll_offset)
            for rect in self._merged_rects(tuple(content_rects))
        )
        return tuple(
            rect.intersected(viewport_rect)
            for rect in translated_rects
            if rect.intersected(viewport_rect).isValid()
            and not rect.intersected(viewport_rect).isEmpty()
        )

    def _visible_reorder_geometry_lines(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionLineSnapshot, ...]:
        """Return projection lines that can contribute reorder chip geometry."""

        visible_lines: list[PromptProjectionLineSnapshot] = []
        for line in self._snapshot.lines:
            line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            )
            if line_rect.intersects(viewport_rect):
                visible_lines.append(line)
        return tuple(visible_lines)

    def reorder_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return one projection-owned geometry object per semantic reorder chip."""

        return self._reorder_geometry.reorder_chip_geometry_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def _reorder_chip_geometry_snapshot_from_geometry(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return one projection-owned geometry object per semantic reorder chip."""

        _ = chip_owned_ranges_by_index
        line_rects = self._viewport_line_rects(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        visible_lines = self._visible_reorder_geometry_lines(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        ordered_chip_indices = tuple(
            chip_index for row in layout_view.rows for chip_index in row.chip_indices
        )
        geometries: dict[int, PromptReorderChipGeometry] = {}
        for visual_revision, chip_index in enumerate(ordered_chip_indices):
            rendered_range = chip_rendered_ranges_by_index.get(chip_index)
            if rendered_range is None:
                log_reorder_drag_event(
                    "anomaly.chip_geometry_missing_range",
                    chip_index=chip_index,
                )
                continue
            range_start, range_end = rendered_range
            fragments = self._visible_source_range_fragments(
                range_start,
                range_end,
                visible_lines=visible_lines,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
            log_reorder_drag_event(
                "chip_geometry.fragment_inputs",
                chip_index=chip_index,
                rendered_start=range_start,
                rendered_end=range_end,
                fragment_count=len(fragments),
            )
            if not fragments:
                log_reorder_drag_event(
                    "anomaly.chip_geometry_missing",
                    chip_index=chip_index,
                    rendered_start=range_start,
                    rendered_end=range_end,
                )
                continue
            geometry = self._reorder_chip_geometry_from_fragments(
                chip_index=chip_index,
                visual_revision=visual_revision,
                rendered_start=range_start,
                rendered_end=range_end,
                fragments=fragments,
                viewport_rect=viewport_rect,
                line_rects=line_rects,
                scroll_offset=scroll_offset,
            )
            if geometry.chrome_path.isEmpty():
                log_reorder_drag_event(
                    "anomaly.chip_geometry_empty_path",
                    chip_index=chip_index,
                    rendered_start=range_start,
                    rendered_end=range_end,
                )
            geometries[chip_index] = geometry
            log_reorder_drag_event(
                "chip_geometry.chip",
                **chip_geometry_context(geometry),
            )

        duplicate_chip_count = len(ordered_chip_indices) - len(
            set(ordered_chip_indices)
        )
        if duplicate_chip_count:
            log_reorder_drag_event(
                "anomaly.chip_geometry_duplicate",
                geometry_count=len(geometries),
                duplicate_chip_count=duplicate_chip_count,
            )
        log_reorder_drag_event(
            "chip_geometry.snapshot",
            geometry_count=len(geometries),
            ordered_count=len(ordered_chip_indices),
            visual_line_count=len(self._snapshot.lines),
            layout_width=f"{viewport_rect.width():.2f}",
            content_height=f"{self.content_size().height():.2f}",
            scroll_offset=f"{scroll_offset:.2f}",
        )
        return PromptReorderChipGeometrySnapshot(
            geometries_by_chip_index=geometries,
            ordered_chip_indices=ordered_chip_indices,
            visual_line_count=len(self._snapshot.lines),
            layout_width=float(viewport_rect.width()),
            content_height=float(self.content_size().height()),
            scroll_offset=float(scroll_offset),
        )

    def reorder_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderPlacementSnapshot:
        """Return placement geometry derived from projection-owned chip geometry."""

        return self._reorder_geometry.reorder_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def _reorder_placement_snapshot_from_geometry(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderPlacementSnapshot:
        """Return placement geometry derived from projection-owned chip geometry."""

        placements: list[PromptReorderPlacementGeometry] = []
        ordinal = 0
        line_rects = self._viewport_line_rects(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        log_reorder_drag_event(
            "placement_geometry.uses_chip_geometry_snapshot",
            chip_geometry_count=len(chip_geometry_snapshot.geometries_by_chip_index),
            ordered_chip_count=len(chip_geometry_snapshot.ordered_chip_indices),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )

        for row in layout_view.rows:
            row_line_items: dict[
                int,
                list[
                    tuple[
                        int,
                        PromptReorderChipGeometry,
                        PromptReorderChipLineGeometry,
                    ]
                ],
            ] = {}
            for segment_index in row.chip_indices:
                geometry = chip_geometry_snapshot.geometries_by_chip_index.get(
                    segment_index
                )
                if geometry is None:
                    log_reorder_drag_event(
                        "anomaly.placement_missing_chip_geometry",
                        row_index=row.row_index,
                        chip_index=segment_index,
                        chip_geometry_count=len(
                            chip_geometry_snapshot.geometries_by_chip_index
                        ),
                    )
                    continue
                for line_geometry in geometry.visual_lines:
                    row_line_items.setdefault(
                        line_geometry.visual_line_index,
                        [],
                    ).append((segment_index, geometry, line_geometry))

            for visual_line_index, line_items in sorted(row_line_items.items()):
                line_rect = line_rects.get(visual_line_index)
                if line_rect is None or line_rect.isEmpty():
                    continue
                line_items.sort(key=lambda item: item[2].content_rect.center().x())
                placement_items = self._row_placement_items(
                    row_indices=row.chip_indices,
                    line_items=line_items,
                    row_index=row.row_index,
                    visual_line_index=visual_line_index,
                    visual_line_rect=line_rect,
                    viewport_rect=viewport_rect,
                    ordinal_start=ordinal,
                )
                placements.extend(placement_items)
                ordinal += len(placement_items)

        for gap in layout_view.gaps:
            gap_range = gap_ranges_by_index.get(gap.gap_index)
            if gap_range is None:
                continue
            gap_start, _gap_end = gap_range
            for blank_line_index in range(gap.blank_line_count):
                caret_rect = self.cursor_rect(
                    self._projection_document.caret_map.state_for_source_position(
                        gap_start + self._gap_blank_line_offset(gap, blank_line_index)
                    ),
                    scroll_offset=scroll_offset,
                )
                if caret_rect.isEmpty():
                    continue
                visual_line_index_or_none = self._visual_line_index_for_viewport_y(
                    caret_rect.center().y(),
                    scroll_offset=scroll_offset,
                )
                if visual_line_index_or_none is None:
                    visual_line_index = max(0, len(self._snapshot.lines) - 1)
                else:
                    visual_line_index = visual_line_index_or_none
                visual_line_rect = line_rects.get(
                    visual_line_index,
                    QRectF(
                        viewport_rect.left(),
                        caret_rect.top(),
                        viewport_rect.width(),
                        max(1.0, caret_rect.height()),
                    ),
                )
                hit_rect = QRectF(
                    viewport_rect.left(),
                    caret_rect.top(),
                    viewport_rect.width(),
                    max(1.0, caret_rect.height()),
                ).intersected(viewport_rect)
                if hit_rect.isEmpty():
                    continue
                target = PromptGapBlankLineDropTarget(
                    gap_index=gap.gap_index,
                    blank_line_index=blank_line_index,
                )
                placements.append(
                    PromptReorderPlacementGeometry(
                        placement_id=reorder_placement_id_for_target(
                            target,
                            visual_line_index=visual_line_index,
                            ordinal=ordinal,
                        ),
                        target=target,
                        hit_rect=hit_rect,
                        insertion_anchor_rect=caret_rect,
                        visual_line_rect=visual_line_rect,
                        expected_landing_rect=None,
                        source_before=gap_start,
                        source_after=gap_start,
                    )
                )
                ordinal += 1

        return PromptReorderPlacementSnapshot(
            placements=tuple(placements),
            visual_line_count=len(self._snapshot.lines),
            layout_width=float(viewport_rect.width()),
            content_height=float(self.content_size().height()),
        )

    def source_range_row_rects(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return full-width visible row rects intersecting one source range."""

        return self._reorder_geometry.source_range_row_rects(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def _source_range_row_rects_from_reorder_geometry(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return full-width visible row rects intersecting one source range."""

        range_start = max(0, min(start, end))
        range_end = max(0, max(start, end))
        row_rects: list[QRectF] = []
        for line in self._snapshot.lines:
            if not _source_range_intersects_visual_line(
                source_start=range_start,
                source_end=range_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            ):
                continue
            viewport_line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            )
            clipped_rect = viewport_line_rect.intersected(viewport_rect)
            if clipped_rect.isValid() and not clipped_rect.isEmpty():
                row_rects.append(viewport_line_rect)
        return tuple(row_rects)

    def _reorder_chip_geometry_from_fragments(
        self,
        *,
        chip_index: int,
        visual_revision: int,
        rendered_start: int,
        rendered_end: int,
        fragments: tuple[QRectF, ...],
        viewport_rect: QRectF,
        line_rects: dict[int, QRectF],
        scroll_offset: float,
    ) -> PromptReorderChipGeometry:
        """Build one semantic chip geometry from projection-internal fragments."""

        line_content_rects: dict[int, list[QRectF]] = {}
        for fragment in fragments:
            visual_line_index = self._visual_line_index_for_viewport_y(
                fragment.center().y(),
                scroll_offset=scroll_offset,
            )
            if visual_line_index is None:
                visual_line_index = 0
            line_content_rects.setdefault(visual_line_index, []).append(
                self._chip_content_rect_for_fragment(
                    fragment,
                    viewport_rect=viewport_rect,
                )
            )

        line_geometries: list[PromptReorderChipLineGeometry] = []
        for visual_line_index, content_rects in sorted(line_content_rects.items()):
            content_rect = QRectF(content_rects[0])
            for rect in content_rects[1:]:
                content_rect = content_rect.united(rect)
            line_rect = line_rects.get(
                visual_line_index,
                QRectF(
                    viewport_rect.left(),
                    content_rect.top(),
                    viewport_rect.width(),
                    max(1.0, content_rect.height()),
                ),
            )
            line_geometries.append(
                PromptReorderChipLineGeometry(
                    visual_line_index=visual_line_index,
                    line_rect=QRectF(line_rect),
                    content_rect=content_rect,
                    leading_anchor=QPointF(
                        content_rect.left(), content_rect.center().y()
                    ),
                    trailing_anchor=QPointF(
                        content_rect.right(),
                        content_rect.center().y(),
                    ),
                )
            )

        outline_bounds = QRectF(line_geometries[0].content_rect)
        for line_geometry in line_geometries[1:]:
            outline_bounds = outline_bounds.united(line_geometry.content_rect)
        hotspot_rect = outline_bounds.adjusted(
            -PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
            -PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
            PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
            PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
        ).toAlignedRect()
        return PromptReorderChipGeometry(
            geometry_id=PromptReorderChipGeometryId(
                chip_index=chip_index,
                visual_revision=visual_revision,
            ),
            chip_index=chip_index,
            source_start=rendered_start,
            source_end=rendered_end,
            rendered_start=rendered_start,
            rendered_end=rendered_end,
            visual_lines=tuple(line_geometries),
            hotspot_rect=hotspot_rect,
            chrome_path=chrome_path_from_rects(
                tuple(line.content_rect for line in line_geometries)
            ),
            outline_bounds=outline_bounds,
            slot_before=QPointF(
                line_geometries[0].content_rect.left(),
                line_geometries[0].content_rect.center().y(),
            ),
            slot_after=QPointF(
                line_geometries[-1].content_rect.right(),
                line_geometries[-1].content_rect.center().y(),
            ),
            marker_height=max(line.content_rect.height() for line in line_geometries),
        )

    @staticmethod
    def _chip_content_rect_for_fragment(
        fragment: QRectF,
        *,
        viewport_rect: QRectF,
    ) -> QRectF:
        """Inflate one projection fragment into semantic chip chrome content."""

        return QRectF(
            QPointF(
                max(
                    viewport_rect.left(),
                    fragment.left() - PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
                ),
                max(
                    viewport_rect.top(),
                    fragment.top() - PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
                ),
            ),
            QPointF(
                min(
                    viewport_rect.right(),
                    fragment.right() + PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
                ),
                min(
                    viewport_rect.bottom(),
                    fragment.bottom() + PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
                ),
            ),
        )

    def _row_placement_items(
        self,
        *,
        row_indices: tuple[int, ...],
        line_items: list[
            tuple[int, PromptReorderChipGeometry, PromptReorderChipLineGeometry]
        ],
        row_index: int,
        visual_line_index: int,
        visual_line_rect: QRectF,
        viewport_rect: QRectF,
        ordinal_start: int,
    ) -> list[PromptReorderPlacementGeometry]:
        """Return projection-owned placements for one visual row of chips."""

        placements: list[PromptReorderPlacementGeometry] = []
        visual_rects = tuple(
            line.content_rect for _index, _geometry, line in line_items
        )
        row_top = min(
            (rect.top() for rect in visual_rects), default=visual_line_rect.top()
        )
        row_bottom = max(
            (rect.bottom() for rect in visual_rects),
            default=visual_line_rect.bottom(),
        )
        placement_line_rect = QRectF(
            viewport_rect.left(),
            min(visual_line_rect.top(), row_top),
            viewport_rect.width(),
            max(
                1.0,
                max(visual_line_rect.bottom(), row_bottom)
                - min(visual_line_rect.top(), row_top),
            ),
        ).intersected(viewport_rect)
        if placement_line_rect.isEmpty():
            return placements
        line_top = placement_line_rect.top()
        line_height = max(1.0, placement_line_rect.height())

        def append_placement(
            *,
            insertion_index: int,
            hit_left: float,
            hit_right: float,
            anchor_x: float,
            source_before: int | None,
            source_after: int | None,
            adjacent_chip_indices: tuple[int, ...],
        ) -> None:
            target = PromptLineDropTarget(
                row_index=row_index,
                insertion_index=insertion_index,
            )
            ordinal = ordinal_start + len(placements)
            placements.append(
                PromptReorderPlacementGeometry(
                    placement_id=reorder_placement_id_for_target(
                        target,
                        visual_line_index=visual_line_index,
                        ordinal=ordinal,
                    ),
                    target=target,
                    hit_rect=QRectF(
                        hit_left,
                        line_top,
                        max(8.0, hit_right - hit_left),
                        line_height,
                    ).intersected(viewport_rect),
                    insertion_anchor_rect=rect_from_centerline(
                        x=anchor_x,
                        y=placement_line_rect.center().y(),
                        height=line_height,
                    ),
                    visual_line_rect=placement_line_rect,
                    expected_landing_rect=None,
                    source_before=source_before,
                    source_after=source_after,
                    adjacent_chip_indices=adjacent_chip_indices,
                )
            )

        first_segment_index, first_geometry, first_line = line_items[0]
        first_rect = QRectF(first_line.content_rect)
        first_logical_index = row_indices.index(first_segment_index)
        append_placement(
            insertion_index=first_logical_index,
            hit_left=viewport_rect.left(),
            hit_right=first_rect.center().x(),
            anchor_x=first_line.leading_anchor.x(),
            source_before=None,
            source_after=first_geometry.rendered_start,
            adjacent_chip_indices=(first_segment_index,),
        )

        for visual_insertion_index, (
            left_segment_index,
            _left_geometry,
            left_line,
        ) in enumerate(
            line_items[:-1],
            start=1,
        ):
            right_segment_index, right_geometry, right_line = line_items[
                visual_insertion_index
            ]
            left_rect = QRectF(left_line.content_rect)
            right_rect = QRectF(right_line.content_rect)
            right_logical_index = row_indices.index(right_segment_index)
            append_placement(
                insertion_index=right_logical_index,
                hit_left=left_rect.center().x(),
                hit_right=right_rect.center().x(),
                anchor_x=right_line.leading_anchor.x(),
                source_before=_left_geometry.rendered_end,
                source_after=right_geometry.rendered_start,
                adjacent_chip_indices=(left_segment_index, right_segment_index),
            )

        last_segment_index, last_geometry, last_line = line_items[-1]
        last_rect = QRectF(last_line.content_rect)
        last_logical_index = row_indices.index(last_segment_index)
        append_placement(
            insertion_index=last_logical_index + 1,
            hit_left=last_rect.center().x(),
            hit_right=viewport_rect.right(),
            anchor_x=last_line.trailing_anchor.x(),
            source_before=last_geometry.rendered_end,
            source_after=None,
            adjacent_chip_indices=(last_segment_index,),
        )
        return placements

    def _viewport_line_rects(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> dict[int, QRectF]:
        """Return viewport-local full-width rects for visible projection lines."""

        line_rects: dict[int, QRectF] = {}
        for line_index, line in enumerate(self._snapshot.lines):
            line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            ).intersected(viewport_rect)
            if line_rect.isValid() and not line_rect.isEmpty():
                line_rects[line_index] = line_rect
        return line_rects

    def _visual_line_index_for_viewport_y(
        self,
        y_position: float,
        *,
        scroll_offset: float,
    ) -> int | None:
        """Return the projection visual line that owns one viewport-local Y value."""

        document_y = y_position + scroll_offset
        return self._line_index_for_pointer_y(
            document_y,
            preferred_line_index=None,
        )

    @staticmethod
    def _gap_blank_line_offset(
        gap: PromptReorderGapView,
        blank_line_index: int,
    ) -> int:
        """Return the source offset for one blank-line target inside a gap."""

        offsets = blank_line_drop_offsets(gap.separator_text)
        if not 0 <= blank_line_index < len(offsets):
            return 0
        return offsets[blank_line_index]

    def measure_token(self, token: PromptProjectionToken) -> QSizeF:
        """Measure the visible presentation owned by one semantic token."""

        runs = self._projection_document.runs_for_token(token.token_id)
        if not runs:
            return QSizeF(0.0, 0.0)
        width = 0.0
        height = 0.0
        for run in runs:
            if run.kind is PromptProjectionRunKind.TEXT:
                metrics = QFontMetricsF(projection_text_run_font(run, self._base_font))
                width += metrics.horizontalAdvance(run.display_text)
                height = max(height, self._metrics.text_line_height)
                continue
            renderer = self.inline_object_renderers.renderer_for(run.renderer_key)
            if renderer is None:
                continue
            size = renderer.measure_inline_object(
                run,
                token,
                base_font=self._base_font,
            )
            width += size.width()
            height = max(height, size.height())
        return QSizeF(width, height)

    def token_fragments(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> tuple[QRectF, ...]:
        """Return the viewport-local visible fragments owned by one token."""

        return tuple(
            fragment.rect.translated(0.0, -scroll_offset)
            for fragment in self._token_fragments(token)
        )

    def paint_inline_object_fragment(
        self,
        painter: QPainter,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        selection: PromptProjectionSelection | None = None,
    ) -> None:
        """Delegate inline object fragment painting to the projection painter."""

        self._painter.paint_inline_object_fragment(
            painter,
            fragment,
            selection=selection,
        )

    def _inline_object_fragment_is_selected(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        selection: PromptProjectionSelection | None,
    ) -> bool:
        """Return whether one inline object should use selected foreground colors."""

        if selection is None or selection.is_empty:
            return False

        if fragment.token_id is not None:
            token = self._projection_document.token_by_id(fragment.token_id)
            if (
                token is not None
                and selection.start <= token.source_start
                and token.source_end <= selection.end
            ):
                return True

        if len(fragment.source_positions) < 2:
            return False
        source_start = fragment.source_positions[0]
        source_end = fragment.source_positions[-1]
        return selection.start < source_end and source_start < selection.end

    def _rebuild_snapshot(self) -> None:
        """Rebuild the immutable snapshot after projection or width changes."""

        self._metrics = self._build_metrics()
        self._snapshot = self._line_layout_builder.build_snapshot(
            self._projection_document,
            wrap_width=self._text_width,
            base_font=self._base_font,
            document_margin=self._document_margin,
            content_left_inset=self._content_left_inset,
            prompt_document_view=self._prompt_document_view,
            metrics=self._metrics,
        )

    def _build_metrics(self) -> PromptProjectionMetrics:
        """Return metrics for the current projection font and geometry inputs."""

        return self._metrics_factory.create(
            base_font=self._base_font,
            document_margin=self._document_margin,
            wrap_width=self._text_width,
            content_left_inset=self._content_left_inset,
        )

    @staticmethod
    def _clamped_text_width(width: float) -> float:
        """Return a safe projection wrapping width."""

        return max(1.0, width)

    def _line_index_for_pointer_y(
        self,
        y_position: float,
        *,
        preferred_line_index: int | None,
    ) -> int | None:
        """Resolve one pointer y-coordinate to the best matching visual line index."""

        containing_indices = [
            line_index
            for line_index, line in enumerate(self._snapshot.lines)
            if (line.top - 1.0) <= y_position <= ((line.top + line.height) + 1.0)
        ]
        if containing_indices:
            if (
                preferred_line_index is not None
                and preferred_line_index in containing_indices
            ):
                return preferred_line_index
            return containing_indices[0]

        best_line_index: int | None = None
        best_distance: float | None = None
        for line_index, line in enumerate(self._snapshot.lines):
            distance = self._axis_distance(
                axis_value=y_position,
                start=line.top,
                end=line.top + line.height,
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_line_index = line_index
                continue
            if (
                distance == best_distance
                and preferred_line_index is not None
                and line_index == preferred_line_index
            ):
                best_line_index = line_index
        return best_line_index

    def _drag_line_index_for_pointer_y(
        self,
        y_position: float,
        *,
        anchor_line_index: int | None,
        preferred_line_index: int | None,
    ) -> int | None:
        """Resolve the wrapped line that should own one drag-selection pointer y."""

        if not self._snapshot.lines:
            return None
        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if line.top <= y_position < line_bottom:
                return line_index
            if (
                line_index == len(self._snapshot.lines) - 1
                and y_position == line_bottom
            ):
                return line_index

        best_line_index: int | None = None
        best_distance: float | None = None
        best_center_distance: float | None = None
        direction = _drag_direction(
            anchor_line_index=anchor_line_index,
            line_index=preferred_line_index,
        )
        for line_index, line in enumerate(self._snapshot.lines):
            distance = self._axis_distance(
                axis_value=y_position,
                start=line.top,
                end=line.top + line.height,
            )
            center_distance = abs((line.top + (line.height / 2.0)) - y_position)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_center_distance = center_distance
                best_line_index = line_index
                continue
            if distance > best_distance:
                continue
            if (
                best_center_distance is not None
                and center_distance < best_center_distance
            ):
                best_center_distance = center_distance
                best_line_index = line_index
                continue
            if (
                center_distance == best_center_distance
                and preferred_line_index is not None
                and line_index == preferred_line_index
            ):
                best_line_index = line_index
                continue
            if (
                center_distance == best_center_distance
                and direction is not None
                and best_line_index is not None
                and (
                    (direction > 0 and line_index > best_line_index)
                    or (direction < 0 and line_index < best_line_index)
                )
            ):
                best_line_index = line_index
        return best_line_index

    def _inline_object_caret_rect_for_state(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        state: PromptProjectionCaretState,
    ) -> QRectF:
        """Return the fragment-local caret rect matching one renderer hit state."""

        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(state)
        )
        line_index = self.line_index_for_document_y(fragment.rect.center().y())
        if line_index is not None:
            for caret_stop in self._snapshot.lines[line_index].caret_stops:
                if caret_stop.projection_position == projection_position:
                    return QRectF(caret_stop.rect)
        return self.cursor_rect(state, scroll_offset=0.0)

    def _line_text_fragment_caret_hit(
        self,
        line: PromptProjectionLineSnapshot,
        document_position: QPointF,
    ) -> PromptProjectionCaretHit | None:
        """Return the source-backed text-fragment caret hit inside one resolved line."""

        for fragment in line.fragments:
            if not isinstance(fragment, PromptProjectionTextFragment):
                continue
            if not fragment.rect.contains(document_position):
                continue
            run = self._projection_document.run_by_id(fragment.run_id)
            if run is None or not run.source_backed:
                continue
            slot_index = self._nearest_boundary_index(fragment, document_position.x())
            document_rect = QRectF(
                fragment.rect.left() + fragment.boundary_offsets[slot_index],
                line.top,
                1.0,
                line.height,
            )
            if fragment.token_id is not None:
                state = self._projection_document.caret_map.resolve_state(
                    PromptProjectionCaretState(
                        source_position=fragment.source_positions[slot_index],
                        placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                        token_id=fragment.token_id,
                        run_id=run.run_id,
                        token_slot=self._token_slot_for_text_fragment(
                            run,
                            fragment,
                            slot_index,
                        ),
                    )
                )
                return PromptProjectionCaretHit(
                    state=state,
                    document_rect=document_rect,
                )
            state = self._projection_document.caret_map.resolve_state(
                self._projection_document.caret_map.state_for_projection_position(
                    fragment.projection_start + slot_index,
                    prefer_after=document_position.x()
                    >= (fragment.rect.left() + fragment.boundary_offsets[slot_index]),
                )
            )
            return PromptProjectionCaretHit(
                state=state,
                document_rect=document_rect,
            )
        return None

    def _line_caret_stop_hit(
        self,
        caret_stop: PromptProjectionLineCaretStopSnapshot,
        *,
        x_position: float,
    ) -> PromptProjectionCaretHit:
        """Return the caret hit represented by one line-local caret stop."""

        state = self._projection_document.caret_map.resolve_state(
            self._projection_document.caret_map.state_for_projection_position(
                caret_stop.projection_position,
                prefer_after=x_position >= caret_stop.rect.center().x(),
            )
        )
        return PromptProjectionCaretHit(
            state=state,
            document_rect=QRectF(caret_stop.rect),
        )

    @staticmethod
    def _line_caret_stop_nearest_x(
        line: PromptProjectionLineSnapshot,
        x_position: float,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the closest line-local caret stop to one document x-coordinate."""

        if not line.caret_stops:
            return None
        return min(
            line.caret_stops,
            key=lambda caret_stop: abs(caret_stop.rect.center().x() - x_position),
        )

    @staticmethod
    def _drag_line_caret_stop_for_x(
        line: PromptProjectionLineSnapshot,
        x_position: float,
        *,
        direction: int | None,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the drag caret stop that matches the row-transition direction."""

        if not line.caret_stops:
            return None
        if direction is None or direction == 0:
            return PromptProjectionLayout._line_caret_stop_nearest_x(line, x_position)
        if direction > 0:
            last_caret_stop = line.caret_stops[-1]
            if x_position > last_caret_stop.rect.left():
                return last_caret_stop
            downward_stops = (
                line.caret_stops[:-1] if len(line.caret_stops) > 1 else line.caret_stops
            )
            for caret_stop in reversed(downward_stops):
                if x_position >= caret_stop.rect.left():
                    return caret_stop
            return downward_stops[0]
        for caret_stop in line.caret_stops:
            if x_position <= caret_stop.rect.left():
                return caret_stop
        return line.caret_stops[-1]

    def _nearest_document_caret_state(
        self,
        document_position: QPointF,
    ) -> PromptProjectionCaretState:
        """Return the globally nearest caret state when no visual line can resolve the point."""

        return self._nearest_document_caret_hit(document_position).state

    def _nearest_document_caret_hit(
        self,
        document_position: QPointF,
    ) -> PromptProjectionCaretHit:
        """Return the globally nearest caret hit when no visual line can resolve the point."""

        nearest_projection_position: int | None = None
        nearest_distance: float | None = None
        for (
            projection_position,
            caret_rect,
        ) in self._snapshot.caret_rects_by_projection_position.items():
            dx = caret_rect.center().x() - document_position.x()
            dy = caret_rect.center().y() - document_position.y()
            distance = (dx * dx) + (dy * dy)
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_projection_position = projection_position
        if nearest_projection_position is None:
            return PromptProjectionCaretHit(
                state=PromptProjectionCaretState(source_position=0),
                document_rect=QRectF(
                    0.0,
                    self._document_margin,
                    1.0,
                    self._metrics.text_line_height,
                ),
            )
        nearest_rect = self._snapshot.caret_rects_by_projection_position[
            nearest_projection_position
        ]
        state = self._projection_document.caret_map.resolve_state(
            self._projection_document.caret_map.state_for_projection_position(
                nearest_projection_position,
                prefer_after=document_position.x() >= nearest_rect.center().x(),
            )
        )
        return PromptProjectionCaretHit(
            state=state,
            document_rect=QRectF(nearest_rect),
        )

    @staticmethod
    def _axis_distance(*, axis_value: float, start: float, end: float) -> float:
        """Return the distance from one axis coordinate to one closed interval."""

        if axis_value < start:
            return start - axis_value
        if axis_value > end:
            return axis_value - end
        return 0.0

    def _text_fragment_selection_bounds(
        self,
        fragment: PromptProjectionTextFragment,
        selection: PromptProjectionSelection | None,
    ) -> tuple[int, int] | None:
        """Return the selected local text indices for one text fragment."""

        if selection is None or selection.is_empty:
            return None
        fragment_source_start = fragment.source_positions[0]
        fragment_source_end = fragment.source_positions[-1]
        selected_start = max(selection.start, fragment_source_start)
        selected_end = min(selection.end, fragment_source_end)
        if selected_end <= selected_start:
            return None
        start_index = fragment.source_positions.index(selected_start)
        end_index = fragment.source_positions.index(selected_end)
        return (start_index, end_index)

    def _selection_rects_for_selection(
        self,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return the unmerged selection rects covering one raw source range."""

        selection_rects = list(
            self._content_rects_for_source_range(
                start=selection.start,
                end=selection.end,
            )
        )
        selection_rects.extend(
            self._empty_line_selection_rects(
                selection=selection,
            )
        )
        selection_rects.extend(
            self._line_break_selection_rects(
                selection=selection,
            )
        )
        return tuple(selection_rects)

    def _content_rects_for_source_range(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return only visible content rects for one raw source range."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()

        content_rects: list[QRectF] = []
        fully_selected_token_ids = {
            token.token_id
            for token in self._projection_document.tokens
            if range_start <= token.source_start and token.source_end <= range_end
        }
        for token in self._projection_document.tokens:
            if token.token_id not in fully_selected_token_ids:
                continue
            content_rects.extend(
                QRectF(fragment.rect) for fragment in self._token_fragments(token)
            )

        for fragment in self._snapshot.text_fragments:
            if fragment.token_id in fully_selected_token_ids:
                continue
            selection_bounds = self._text_fragment_selection_bounds(
                fragment,
                PromptProjectionSelection(range_start, range_end),
            )
            if selection_bounds is None:
                continue
            start_index, end_index = selection_bounds
            content_rects.append(
                QRectF(
                    fragment.rect.left() + fragment.boundary_offsets[start_index],
                    fragment.rect.top(),
                    max(
                        1.0,
                        fragment.boundary_offsets[end_index]
                        - fragment.boundary_offsets[start_index],
                    ),
                    fragment.rect.height(),
                )
            )

        for object_fragment in self._snapshot.inline_object_fragments:
            if object_fragment.token_id in fully_selected_token_ids:
                continue
            run = self._projection_document.run_by_id(object_fragment.run_id)
            projection_token = self._projection_document.token_by_id(
                object_fragment.token_id
            )
            if run is None or projection_token is None:
                continue
            renderer = self.inline_object_renderers.renderer_for(
                object_fragment.renderer_key
            )
            if renderer is None:
                continue
            content_rects.extend(
                renderer.selection_rects(
                    run,
                    projection_token,
                    object_fragment.rect,
                    selection_start=range_start,
                    selection_end=range_end,
                    base_font=self._base_font,
                )
            )
        return tuple(content_rects)

    def _empty_line_selection_rects(
        self,
        *,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return synthetic selection rects for empty wrapped lines in one source range."""

        selection_start = selection.start
        selection_end = selection.end
        if selection_end <= selection_start:
            return ()

        empty_line_highlight_width = self._selection_affordance_width()
        empty_line_rects: list[QRectF] = []
        for line in self._snapshot.lines:
            if line.fragments:
                continue
            if line.source_end <= line.source_start:
                continue
            if not self._empty_line_is_visibly_selected(
                line=line,
                selection=selection,
            ):
                continue
            line_left = (
                line.caret_stops[0].rect.left()
                if line.caret_stops
                else self._document_margin
            )
            empty_line_rects.append(
                QRectF(
                    line_left,
                    line.top,
                    empty_line_highlight_width,
                    line.height,
                )
            )
        return tuple(empty_line_rects)

    def _line_break_selection_rects(
        self,
        *,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return explicit selection rects for selected hard line breaks."""

        selection_start = selection.start
        selection_end = selection.end
        if selection_end <= selection_start:
            return ()

        line_break_rects: list[QRectF] = []
        line_break_width = self._selection_affordance_width()
        for line in self._snapshot.lines:
            if not line.fragments:
                continue
            if line.line_break_start is None or line.line_break_end is None:
                continue
            if (
                selection_end <= line.line_break_start
                or line.line_break_end <= selection_start
            ):
                continue
            content_end_stop = self._line_caret_stop_for_source_position(
                line,
                line.source_content_end,
            )
            line_break_left = (
                content_end_stop.rect.left()
                if content_end_stop is not None
                else line.rect.right()
            )
            line_break_rects.append(
                QRectF(
                    line_break_left,
                    line.top,
                    line_break_width,
                    line.height,
                )
            )
        return tuple(line_break_rects)

    def _line_caret_stop_for_source_position(
        self,
        line: PromptProjectionLineSnapshot,
        source_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the line-local caret stop matching one source position."""

        for caret_stop in line.caret_stops:
            state = self._projection_document.caret_map.state_for_projection_position(
                caret_stop.projection_position
            )
            if state.source_position == source_position:
                return caret_stop
        return None

    def _selection_affordance_width(self) -> float:
        """Return the compact width used for invisible selected source spans."""

        return max(
            8.0,
            float(QFontMetricsF(self._base_font).horizontalAdvance(" ")),
        )

    def _empty_line_is_visibly_selected(
        self,
        *,
        line: PromptProjectionLineSnapshot,
        selection: PromptProjectionSelection,
    ) -> bool:
        """Return whether one empty visual line should show selection feedback.

        Empty line feedback follows the moving selection endpoint. A fixed anchor
        at an empty line boundary does not by itself make that line selected.
        """

        if selection.start < line.source_end and line.source_start < selection.end:
            return True
        return (
            selection.anchor_position < line.source_start
            and selection.cursor_position == line.source_start
        )

    def _merged_rects(self, rects: tuple[QRectF, ...]) -> tuple[QRectF, ...]:
        """Merge rects that share one wrapped line and visually touch each other."""

        if not rects:
            return ()
        rects_by_line_index: dict[int, list[QRectF]] = {}
        unassigned_rects: list[QRectF] = []
        for rect in rects:
            line_index = self._line_index_for_rect(rect)
            if line_index is None:
                unassigned_rects.append(QRectF(rect))
                continue
            rects_by_line_index.setdefault(line_index, []).append(QRectF(rect))

        merged_rects: list[QRectF] = []
        for line_index in range(len(self._snapshot.lines)):
            line_rects = rects_by_line_index.get(line_index)
            if not line_rects:
                continue
            merged_rects.extend(self._merge_horizontally_touching_rects(line_rects))
        if unassigned_rects:
            merged_rects.extend(self._merge_rects_by_top_band(unassigned_rects))
        return tuple(merged_rects)

    def _line_index_for_rect(self, rect: QRectF) -> int | None:
        """Return the wrapped-line index that owns the supplied selection rect."""

        rect_center_y = rect.center().y()
        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if (line.top - 1.0) <= rect_center_y <= (line_bottom + 1.0):
                return line_index
        return None

    def _source_line_document_rect(
        self,
        *,
        source_start: int,
        source_end: int,
    ) -> QRectF | None:
        """Return the document rect covering every visual row for one source line."""

        matching_lines = tuple(
            line
            for line in self._snapshot.lines
            if _source_line_intersects_visual_line(
                source_start=source_start,
                source_end=source_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            )
        )
        if not matching_lines:
            return None
        top = min(line.top for line in matching_lines)
        bottom = max(line.top + line.height for line in matching_lines)
        return QRectF(0.0, top, self._text_width, max(1.0, bottom - top))

    def _merge_horizontally_touching_rects(
        self,
        rects: Sequence[QRectF],
    ) -> tuple[QRectF, ...]:
        """Merge one line's rects when they touch or overlap horizontally."""

        if not rects:
            return ()
        ordered_rects = sorted(rects, key=lambda rect: rect.left())
        merged_rects: list[QRectF] = [QRectF(ordered_rects[0])]
        for rect in ordered_rects[1:]:
            current_rect = merged_rects[-1]
            if rect.left() <= current_rect.right() + 1.0:
                merged_rects[-1] = current_rect.united(rect)
                continue
            merged_rects.append(QRectF(rect))
        return tuple(merged_rects)

    def _merge_rects_by_top_band(
        self,
        rects: Sequence[QRectF],
    ) -> tuple[QRectF, ...]:
        """Merge fallback rects that cannot be assigned to a wrapped line."""

        if not rects:
            return ()
        ordered_rects = sorted(rects, key=lambda rect: (rect.top(), rect.left()))
        merged_rects: list[QRectF] = [QRectF(ordered_rects[0])]
        for rect in ordered_rects[1:]:
            current_rect = merged_rects[-1]
            same_band = (
                abs(current_rect.top() - rect.top()) < 1.0
                and abs(current_rect.height() - rect.height()) < 1.0
            )
            if same_band and rect.left() <= current_rect.right() + 1.0:
                merged_rects[-1] = current_rect.united(rect)
                continue
            merged_rects.append(QRectF(rect))
        return tuple(merged_rects)

    def _nearest_boundary_index(
        self,
        fragment: PromptProjectionTextFragment,
        x_position: float,
    ) -> int:
        """Return the nearest boundary index inside one text fragment."""

        return min(
            range(len(fragment.boundary_offsets)),
            key=lambda boundary_index: abs(
                (fragment.rect.left() + fragment.boundary_offsets[boundary_index])
                - x_position
            ),
        )

    def _token_slot_for_text_fragment(
        self,
        run: PromptProjectionRun,
        fragment: PromptProjectionTextFragment,
        slot_index: int,
    ) -> int:
        """Return the token-content slot implied by one text-fragment boundary."""

        return (fragment.projection_start - run.projection_start) + slot_index

    def _token_fragments(
        self,
        token: PromptProjectionToken,
    ) -> tuple[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
        ...,
    ]:
        """Return every visible fragment owned by one semantic token."""

        fragments: list[
            PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
        ] = []
        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is PromptProjectionRunKind.TEXT:
                fragments.extend(self._snapshot.text_fragments_for_run(run.run_id))
                continue
            fragments.extend(self._snapshot.inline_object_fragments_for_run(run.run_id))
        return tuple(fragments)


__all__ = [
    "PromptProjectionDragSelectionTarget",
    "PromptProjectionIncrementalLayoutResult",
    "PromptProjectionLayout",
    "PromptProjectionSourceLineRect",
    "PromptProjectionVerticalCaretTarget",
]


def _line_index_for_plain_edit(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> int | None:
    """Return the visual line that owns one plain source edit."""

    if replacement_text:
        candidate_index: int | None = None
        for line_index, line in enumerate(lines):
            if line.source_start <= edit_start <= line.source_end:
                candidate_index = line_index
                if edit_start < line.source_end:
                    break
        return candidate_index
    for line_index, line in enumerate(lines):
        if line.source_start <= edit_start and edit_end <= line.source_end:
            return line_index
    return None


def _line_index_for_hard_line_insert(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    edit_start: int,
) -> int | None:
    """Return the visual line that can be split by an inserted hard break."""

    candidate_index: int | None = None
    for line_index, line in enumerate(lines):
        if line.source_content_start <= edit_start <= line.source_content_end:
            candidate_index = line_index
            if edit_start < line.source_content_end:
                break
    return candidate_index


def _line_index_for_hard_line_delete(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    edit_start: int,
) -> int | None:
    """Return the line whose hard break is being deleted."""

    for line_index, line in enumerate(lines):
        if (
            line.line_break_start == edit_start
            and line.line_break_end == edit_start + 1
        ):
            return line_index
    return None


def _plain_edit_requires_tag_keep_reflow(
    prompt_document_view: PromptDocumentView,
    *,
    previous_source_text: str,
    lines: tuple[PromptProjectionLineSnapshot, ...],
    line: PromptProjectionLineSnapshot,
    line_index: int,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
    width_delta: float,
    content_right: float,
    tag_keep_ranges_changed: bool | None = None,
) -> bool:
    """Return whether a kept tag edit needs authoritative line-group layout."""

    expected_next_text = (
        previous_source_text[:edit_start]
        + replacement_text
        + previous_source_text[edit_end:]
    )
    if expected_next_text != prompt_document_view.source_text:
        return True

    next_line_content_end = line.source_content_end + source_delta
    if tag_keep_ranges_changed is None:
        tag_keep_ranges_changed = _plain_edit_changes_local_tag_keep_ranges(
            previous_source_text,
            prompt_document_view.source_text,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
        )
    if tag_keep_ranges_changed and not _changed_tag_keep_ranges_are_local_to_line(
        previous_source_text,
        prompt_document_view.source_text,
        line=line,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
        source_delta=source_delta,
    ):
        return True
    touched_range = _tag_keep_range_for_plain_edit(
        prompt_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )
    if touched_range is None:
        return False
    range_start, range_end = touched_range
    if range_start < line.source_content_start or range_end > next_line_content_end:
        return True
    if (
        line_index > 0
        and not replacement_text
        and range_start == line.source_start
        and edit_start <= range_start
    ):
        return True
    if line.rect.right() + width_delta > content_right + 0.01:
        return True
    return False


def _changed_tag_keep_ranges_are_local_to_line(
    previous_source_text: str,
    next_source_text: str,
    *,
    line: PromptProjectionLineSnapshot,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
) -> bool:
    """Return whether changed comma keep groups stay within one visual line."""

    previous_line_start, previous_line_end = _hard_line_bounds_for_source_edit(
        previous_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
    )
    next_line_start, next_line_end = _hard_line_bounds_for_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_start + len(replacement_text),
    )
    previous_ranges = tag_keep_source_ranges_in_source_line(
        previous_source_text,
        line_start=previous_line_start,
        line_end=previous_line_end,
    )
    remapped_previous_ranges = tuple(
        _remap_tag_keep_range_for_plain_edit(
            source_start,
            source_end,
            edit_start=edit_start,
            edit_end=edit_end,
            source_delta=source_delta,
        )
        for source_start, source_end in previous_ranges
    )
    next_ranges = tag_keep_source_ranges_in_source_line(
        next_source_text,
        line_start=next_line_start,
        line_end=next_line_end,
    )
    if remapped_previous_ranges == next_ranges:
        return True
    changed_ranges = frozenset(remapped_previous_ranges) ^ frozenset(next_ranges)
    if not changed_ranges:
        return True
    next_line_content_start = line.source_content_start
    next_line_content_end = line.source_content_end + source_delta
    return all(
        next_line_content_start <= range_start <= range_end <= next_line_content_end
        for range_start, range_end in changed_ranges
    )


def _plain_edit_changes_local_tag_keep_ranges(
    previous_source_text: str,
    next_source_text: str,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> bool:
    """Return whether a comma edit changes hard-line tag keep ranges."""

    deleted_text = previous_source_text[edit_start:edit_end]
    if "," not in replacement_text and "," not in deleted_text:
        return False
    if (
        edit_start < 0
        or edit_end < edit_start
        or edit_end > len(previous_source_text)
        or previous_source_text[:edit_start]
        + replacement_text
        + previous_source_text[edit_end:]
        != next_source_text
    ):
        return True

    source_delta = len(replacement_text) - (edit_end - edit_start)
    previous_line_start, previous_line_end = _hard_line_bounds_for_source_edit(
        previous_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
    )
    next_line_start, next_line_end = _hard_line_bounds_for_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_start + len(replacement_text),
    )
    previous_ranges = tag_keep_source_ranges_in_source_line(
        previous_source_text,
        line_start=previous_line_start,
        line_end=previous_line_end,
    )
    remapped_previous_ranges = tuple(
        _remap_tag_keep_range_for_plain_edit(
            source_start,
            source_end,
            edit_start=edit_start,
            edit_end=edit_end,
            source_delta=source_delta,
        )
        for source_start, source_end in previous_ranges
    )
    next_ranges = tag_keep_source_ranges_in_source_line(
        next_source_text,
        line_start=next_line_start,
        line_end=next_line_end,
    )
    return remapped_previous_ranges != next_ranges


def _hard_line_bounds_for_source_edit(
    source_text: str,
    *,
    edit_start: int,
    edit_end: int,
) -> tuple[int, int]:
    """Return the hard source-line bounds around one edit range."""

    anchor_start = max(0, min(edit_start, len(source_text)))
    anchor_end = max(anchor_start, min(edit_end, len(source_text)))
    line_start = source_text.rfind("\n", 0, anchor_start) + 1
    line_end_search_start = max(anchor_start, anchor_end - 1)
    line_end = source_text.find("\n", line_end_search_start)
    if line_end < 0:
        line_end = len(source_text)
    return line_start, line_end


def _remap_tag_keep_range_for_plain_edit(
    source_start: int,
    source_end: int,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
) -> tuple[int, int]:
    """Return one old tag-keep range in post-edit source coordinates."""

    if source_end <= edit_start:
        return source_start, source_end
    if source_start >= edit_end:
        return source_start + source_delta, source_end + source_delta
    return source_start, max(source_start, source_end + source_delta)


def _tag_keep_range_for_plain_edit(
    prompt_document_view: PromptDocumentView,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the edited kept-tag range using only local source context."""

    anchor = edit_start if replacement_text else max(0, edit_start - 1)
    candidate_range = tag_keep_source_range_at_position(
        prompt_document_view.source_text,
        anchor,
    )
    if candidate_range is None:
        return None
    range_start, range_end = candidate_range
    if not _edit_touches_source_range(
        range_start=range_start,
        range_end=range_end,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    ):
        return None
    return candidate_range


def _edit_touches_source_range(
    *,
    range_start: int,
    range_end: int,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> bool:
    """Return whether a source edit touches one half-open source range."""

    if replacement_text:
        return range_start <= edit_start <= range_end
    return edit_start < range_end and range_start < edit_end


def _plain_text_run_for_empty_line_insert(
    projection_document: PromptProjectionDocument,
    *,
    line: PromptProjectionLineSnapshot,
    edit_start: int,
    replacement_text: str,
) -> PromptProjectionRun | None:
    """Return the new plain text run created by typing into an empty line."""

    if (
        not replacement_text
        or line.fragments
        or line.source_content_start != edit_start
        or line.source_content_end != edit_start
    ):
        return None
    for run in projection_document.runs:
        if run.kind is not PromptProjectionRunKind.TEXT or run.token_id is not None:
            continue
        try:
            local_start = run.source_positions.index(edit_start)
        except ValueError:
            continue
        local_end = local_start + len(replacement_text)
        if run.display_text[local_start:local_end] == replacement_text and tuple(
            run.source_positions[local_start : local_end + 1]
        ) == tuple(range(edit_start, edit_start + len(replacement_text) + 1)):
            return run
    return None


def _text_fragment_for_empty_line_insert(
    line: PromptProjectionLineSnapshot,
    *,
    next_run: PromptProjectionRun,
    edit_start: int,
    replacement_text: str,
    content_left: float,
    base_font: QFont,
) -> PromptProjectionTextFragment | None:
    """Return a laid-out text fragment for the first character in an empty line."""

    if (
        line.fragments
        or next_run.kind is not PromptProjectionRunKind.TEXT
        or next_run.token_id is not None
    ):
        return None
    try:
        local_start = next_run.source_positions.index(edit_start)
    except ValueError:
        return None
    local_end = local_start + len(replacement_text)
    if next_run.display_text[local_start:local_end] != replacement_text or tuple(
        next_run.source_positions[local_start : local_end + 1]
    ) != tuple(range(edit_start, edit_start + len(replacement_text) + 1)):
        return None
    fragment_font = projection_text_run_font(next_run, base_font)
    boundary_offsets = text_boundary_offsets(replacement_text, fragment_font)
    if len(boundary_offsets) != len(replacement_text) + 1:
        return None
    font_metrics = QFontMetricsF(fragment_font)
    text_height = float(font_metrics.height())
    text_top = line.top + max(0.0, (line.height - text_height) / 2.0)
    return PromptProjectionTextFragment(
        run_id=next_run.run_id,
        token_id=None,
        projection_start=next_run.projection_start + local_start,
        projection_end=next_run.projection_start + local_end,
        text=replacement_text,
        source_positions=next_run.source_positions[local_start : local_end + 1],
        rect=QRectF(
            content_left,
            text_top,
            max(1.0, boundary_offsets[-1]),
            max(1.0, text_height),
        ),
        baseline=text_top + float(font_metrics.ascent()),
        boundary_offsets=boundary_offsets,
        active=next_run.active,
    )


def _plain_edit_touches_visual_word_wrap_boundary(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    dirty_line_index: int,
    line: PromptProjectionLineSnapshot,
    next_source_text: str,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
) -> bool:
    """Return whether an edit needs the full word-wrap policy to decide layout."""

    word_span = _word_span_for_plain_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )
    if word_span is None:
        return False
    word_start, word_end = word_span
    next_line_content_start = line.source_content_start
    next_line_content_end = line.source_content_end + source_delta
    if word_start < next_line_content_start or word_end > next_line_content_end:
        return True
    del lines, dirty_line_index
    return False


def _split_plain_line_for_newline_insert(
    line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    edit_start: int,
    first_dirty_projection_position: int,
    content_left: float,
    content_right: float,
) -> tuple[PromptProjectionLineSnapshot, PromptProjectionLineSnapshot] | None:
    """Return two visual lines produced by inserting one hard line break."""

    split_x = _x_position_for_source_boundary(line, edit_start)
    if split_x is None:
        return None
    left_fragments: list[PromptProjectionTextFragment] = []
    right_fragments: list[PromptProjectionTextFragment] = []
    right_x_delta = content_left - split_x
    y_delta = line.height
    for fragment in line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            return None
        split_fragments = _split_text_fragment_for_newline_insert(
            fragment,
            edit_start=edit_start,
            right_x_delta=right_x_delta,
            y_delta=y_delta,
        )
        if split_fragments is None:
            return None
        left_fragment, right_fragment = split_fragments
        if left_fragment is not None:
            left_fragments.append(left_fragment)
        if right_fragment is not None:
            right_fragments.append(right_fragment)
    right_line_right = max(
        (fragment.rect.right() for fragment in right_fragments),
        default=content_left,
    )
    if right_line_right > content_right + 0.01:
        return None
    left_line = PromptProjectionLineSnapshot(
        top=line.top,
        height=line.height,
        source_start=line.source_start,
        source_end=edit_start + 1,
        source_content_start=line.source_content_start,
        source_content_end=edit_start,
        line_break_start=edit_start,
        line_break_end=edit_start + 1,
        fragments=tuple(left_fragments),
        caret_stops=_caret_stops_for_line_fragments(
            left_fragments,
            projection_document=projection_document,
            line_top=line.top,
            line_height=line.height,
            extra_boundaries=((first_dirty_projection_position, split_x),),
        ),
    )
    right_line = PromptProjectionLineSnapshot(
        top=line.top + line.height,
        height=line.height,
        source_start=edit_start + 1,
        source_end=_remap_source_position_for_layout(
            line.source_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        source_content_start=edit_start + 1,
        source_content_end=_remap_source_position_for_layout(
            line.source_content_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        line_break_start=_remap_optional_source_position_for_layout(
            line.line_break_start,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        line_break_end=_remap_optional_source_position_for_layout(
            line.line_break_end,
            edit_start=edit_start,
            edit_end=edit_start,
            delta=1,
        ),
        fragments=tuple(right_fragments),
        caret_stops=_caret_stops_for_line_fragments(
            right_fragments,
            projection_document=projection_document,
            line_top=line.top + line.height,
            line_height=line.height,
            extra_boundaries=((first_dirty_projection_position + 1, content_left),),
        ),
    )
    return left_line, right_line


def _join_plain_lines_after_newline_delete(
    first_line: PromptProjectionLineSnapshot,
    second_line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    edit_start: int,
    content_left: float,
    content_right: float,
) -> PromptProjectionLineSnapshot | None:
    """Return one visual line produced by deleting a hard line break."""

    if first_line.line_break_start != edit_start:
        return None
    join_x = _line_content_right(first_line, default=content_left)
    second_x_delta = join_x - content_left
    next_fragments: list[PromptProjectionTextFragment] = [
        fragment
        for fragment in first_line.fragments
        if isinstance(fragment, PromptProjectionTextFragment)
    ]
    if len(next_fragments) != len(first_line.fragments):
        return None
    for fragment in second_line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            return None
        next_fragments.append(
            cast(
                PromptProjectionTextFragment,
                _remap_fragment_after_hard_line_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_start + 1,
                    source_delta=-1,
                    projection_delta=-1,
                    x_delta=second_x_delta,
                    y_delta=-second_line.height,
                ),
            )
        )
    if _line_content_right_for_fragments(next_fragments, default=content_left) > (
        content_right + 0.01
    ):
        return None
    line_break_start = _remap_optional_source_position_for_layout(
        second_line.line_break_start,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        delta=-1,
    )
    line_break_end = _remap_optional_source_position_for_layout(
        second_line.line_break_end,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        delta=-1,
    )
    return PromptProjectionLineSnapshot(
        top=first_line.top,
        height=max(first_line.height, second_line.height),
        source_start=first_line.source_start,
        source_end=_remap_source_position_for_layout(
            second_line.source_end,
            edit_start=edit_start,
            edit_end=edit_start + 1,
            delta=-1,
        ),
        source_content_start=first_line.source_content_start,
        source_content_end=_remap_source_position_for_layout(
            second_line.source_content_end,
            edit_start=edit_start,
            edit_end=edit_start + 1,
            delta=-1,
        ),
        line_break_start=line_break_start,
        line_break_end=line_break_end,
        fragments=tuple(next_fragments),
        caret_stops=_caret_stops_for_line_fragments(
            next_fragments,
            projection_document=projection_document,
            line_top=first_line.top,
            line_height=max(first_line.height, second_line.height),
            extra_boundaries=_empty_joined_line_caret_boundaries(
                first_line,
                next_fragments=next_fragments,
                content_left=content_left,
            ),
        ),
    )


def _empty_joined_line_caret_boundaries(
    first_line: PromptProjectionLineSnapshot,
    *,
    next_fragments: Sequence[PromptProjectionTextFragment],
    content_left: float,
) -> tuple[tuple[int, float], ...]:
    """Return a synthetic caret boundary when a line join leaves an empty line."""

    if next_fragments or not first_line.caret_stops:
        return ()
    return ((first_line.caret_stops[0].projection_position, content_left),)


def _x_position_for_source_boundary(
    line: PromptProjectionLineSnapshot,
    source_position: int,
) -> float | None:
    """Return the x coordinate for a source boundary on one visual line."""

    for fragment in line.fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            continue
        try:
            boundary_index = fragment.source_positions.index(source_position)
        except ValueError:
            continue
        return fragment.rect.left() + fragment.boundary_offsets[boundary_index]
    line_start_x = _line_start_x(line)
    if source_position == line.source_content_end:
        return _line_content_right(line, default=line_start_x)
    if source_position == line.source_content_start:
        return line_start_x
    return None


def _line_start_x(line: PromptProjectionLineSnapshot) -> float:
    """Return the editable start x coordinate for one visual line."""

    if line.fragments:
        return line.rect.left()
    if line.caret_stops:
        return line.caret_stops[0].rect.left()
    return line.rect.left()


def _split_text_fragment_for_newline_insert(
    fragment: PromptProjectionTextFragment,
    *,
    edit_start: int,
    right_x_delta: float,
    y_delta: float,
) -> (
    tuple[PromptProjectionTextFragment | None, PromptProjectionTextFragment | None]
    | None
):
    """Split one text fragment around an inserted hard line break."""

    try:
        split_index = fragment.source_positions.index(edit_start)
    except ValueError:
        if fragment.source_positions[-1] <= edit_start:
            return fragment, None
        if fragment.source_positions[0] >= edit_start:
            return None, cast(
                PromptProjectionTextFragment,
                _remap_fragment_after_hard_line_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_start,
                    source_delta=1,
                    projection_delta=1,
                    x_delta=right_x_delta,
                    y_delta=y_delta,
                ),
            )
        return None

    left_fragment: PromptProjectionTextFragment | None = None
    right_fragment: PromptProjectionTextFragment | None = None
    if split_index > 0:
        left_fragment = _slice_text_fragment(
            fragment,
            local_start=0,
            local_end=split_index,
            source_delta=0,
            projection_delta=0,
            x_delta=0.0,
            y_delta=0.0,
        )
    if split_index < len(fragment.text):
        split_x = fragment.rect.left() + fragment.boundary_offsets[split_index]
        right_fragment = _slice_text_fragment(
            fragment,
            local_start=split_index,
            local_end=len(fragment.text),
            source_delta=1,
            projection_delta=1,
            x_delta=right_x_delta,
            y_delta=y_delta,
            rect_left_override=split_x + right_x_delta,
        )
    return left_fragment, right_fragment


def _slice_text_fragment(
    fragment: PromptProjectionTextFragment,
    *,
    local_start: int,
    local_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
    y_delta: float,
    rect_left_override: float | None = None,
) -> PromptProjectionTextFragment:
    """Return a concrete slice of one text fragment with shifted coordinates."""

    boundary_offsets = fragment.boundary_offsets[local_start : local_end + 1]
    normalized_offsets = tuple(
        offset - boundary_offsets[0] for offset in boundary_offsets
    )
    rect = QRectF(fragment.rect)
    rect.setLeft(
        rect_left_override
        if rect_left_override is not None
        else fragment.rect.left() + boundary_offsets[0] + x_delta
    )
    rect.setTop(fragment.rect.top() + y_delta)
    rect.setWidth(max(1.0, normalized_offsets[-1]))
    return PromptProjectionTextFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        projection_start=fragment.projection_start + local_start + projection_delta,
        projection_end=fragment.projection_start + local_end + projection_delta,
        text=fragment.text[local_start:local_end],
        source_positions=tuple(
            position + source_delta
            for position in fragment.source_positions[local_start : local_end + 1]
        ),
        rect=rect,
        baseline=fragment.baseline + y_delta,
        boundary_offsets=normalized_offsets,
        active=fragment.active,
    )


def _line_content_right(
    line: PromptProjectionLineSnapshot,
    *,
    default: float,
) -> float:
    """Return the right edge of visible content on one line."""

    return _line_content_right_for_fragments(line.fragments, default=default)


def _line_content_right_for_fragments(
    fragments: Sequence[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ],
    *,
    default: float,
) -> float:
    """Return the right edge of a fragment sequence."""

    return max((fragment.rect.right() for fragment in fragments), default=default)


def _word_span_for_plain_source_edit(
    text: str,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the source word affected by one plain edit when present."""

    if not text:
        return None
    if replacement_text:
        anchor = max(0, min(len(text) - 1, edit_start + len(replacement_text) - 1))
    else:
        anchor = max(0, min(len(text) - 1, edit_start))
        if not _is_incremental_word_character(text[anchor]) and anchor > 0:
            anchor -= 1
    if not _is_incremental_word_character(text[anchor]):
        return None
    word_start = anchor
    while word_start > 0 and _is_incremental_word_character(text[word_start - 1]):
        word_start -= 1
    word_end = anchor + 1
    while word_end < len(text) and _is_incremental_word_character(text[word_end]):
        word_end += 1
    return (word_start, word_end)


def _is_incremental_word_character(character: str) -> bool:
    """Return whether a character participates in word-integrity wrapping."""

    return character.isalnum() or character in {"_", "-", "."}


def _content_right(
    *,
    text_width: float,
    document_margin: float,
    content_left_inset: float,
) -> float:
    """Return the right edge available to wrapped prompt content."""

    content_left = document_margin + max(0.0, content_left_inset)
    content_width = max(
        1.0,
        text_width - (document_margin * 2.0) - max(0.0, content_left_inset),
    )
    return content_left + content_width


def _remap_lines_for_same_line_plain_edit(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    projection_document: PromptProjectionDocument,
    dirty_line_index: int,
    affected_fragment: PromptProjectionTextFragment,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    width_delta: float,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return lines remapped after a same-line plain text edit."""

    next_lines: list[PromptProjectionLineSnapshot] = list(lines[:dirty_line_index])
    if dirty_line_index < len(lines):
        dirty_line = lines[dirty_line_index]
        next_lines.append(
            _remap_dirty_line_for_same_line_plain_edit(
                dirty_line,
                projection_document=projection_document,
                affected_fragment=affected_fragment,
                next_fragment=next_fragment,
                edit_start=edit_start,
                edit_end=edit_end,
                source_delta=source_delta,
                projection_delta=projection_delta,
                width_delta=width_delta,
            )
        )
    downstream_lines = lines[dirty_line_index + 1 :]
    if downstream_lines:
        with _suspend_gc_for_hot_layout_path():
            next_lines.extend(
                _remap_downstream_line_after_plain_edit(
                    line,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    source_delta=source_delta,
                    projection_delta=projection_delta,
                )
                for line in downstream_lines
            )
    return tuple(next_lines)


def _remap_lines_for_empty_line_plain_insert(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    projection_document: PromptProjectionDocument,
    dirty_line_index: int,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return lines remapped after adding the first text fragment to an empty line."""

    next_lines: list[PromptProjectionLineSnapshot] = list(lines[:dirty_line_index])
    if dirty_line_index < len(lines):
        line = lines[dirty_line_index]
        next_fragments = (next_fragment,)
        next_lines.append(
            PromptProjectionLineSnapshot(
                top=line.top,
                height=line.height,
                source_start=line.source_start,
                source_end=line.source_end + source_delta,
                source_content_start=line.source_content_start,
                source_content_end=line.source_content_end + source_delta,
                line_break_start=_remap_optional_source_position_for_layout(
                    line.line_break_start,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    delta=source_delta,
                ),
                line_break_end=_remap_optional_source_position_for_layout(
                    line.line_break_end,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    delta=source_delta,
                ),
                fragments=next_fragments,
                caret_stops=_caret_stops_for_line_fragments(
                    next_fragments,
                    projection_document=projection_document,
                    line_top=line.top,
                    line_height=line.height,
                ),
            )
        )
    next_lines.extend(
        _remap_downstream_line_after_plain_edit(
            line,
            edit_start=edit_start,
            edit_end=edit_end,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
        for line in lines[dirty_line_index + 1 :]
    )
    return tuple(next_lines)


def _line_fragment_count_without_materializing(
    line: PromptProjectionLineSnapshot,
) -> int:
    """Return a line fragment count without expanding lazy shifted fragments."""

    if isinstance(line, _ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is not None:
            return len(fragments)
        base_line = object.__getattribute__(line, "_line")
        return _line_fragment_count_without_materializing(base_line)
    return len(line.fragments)


def _line_text_fragment_count(line: PromptProjectionLineSnapshot) -> int:
    """Return the number of text fragments on one line."""

    if isinstance(line, _ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is None:
            base_line = object.__getattribute__(line, "_line")
            return _line_text_fragment_count(base_line)
    return sum(
        isinstance(fragment, PromptProjectionTextFragment)
        for fragment in line.fragments
    )


def _line_inline_fragment_count(line: PromptProjectionLineSnapshot) -> int:
    """Return the number of inline object fragments on one line."""

    if isinstance(line, _ShiftedLineSnapshot):
        fragments = object.__getattribute__(line, "_fragments")
        if fragments is None:
            base_line = object.__getattribute__(line, "_line")
            return _line_inline_fragment_count(base_line)
    return sum(
        isinstance(fragment, PromptProjectionInlineObjectFragment)
        for fragment in line.fragments
    )


def _remap_dirty_line_for_same_line_plain_edit(
    line: PromptProjectionLineSnapshot,
    *,
    projection_document: PromptProjectionDocument,
    affected_fragment: PromptProjectionTextFragment,
    next_fragment: PromptProjectionTextFragment,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    width_delta: float,
) -> PromptProjectionLineSnapshot:
    """Return the visual line that directly contains the edit."""

    next_fragments: list[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ] = []
    seen_affected = False
    for fragment in line.fragments:
        if fragment == affected_fragment:
            next_fragments.append(next_fragment)
            seen_affected = True
            continue
        if seen_affected:
            next_fragments.append(
                _remap_fragment_after_plain_edit(
                    fragment,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    source_delta=source_delta,
                    projection_delta=projection_delta,
                    x_delta=width_delta,
                )
            )
            continue
        next_fragments.append(fragment)
    return PromptProjectionLineSnapshot(
        top=line.top,
        height=line.height,
        source_start=line.source_start,
        source_end=line.source_end + source_delta,
        source_content_start=line.source_content_start,
        source_content_end=line.source_content_end + source_delta,
        line_break_start=_remap_optional_source_position_for_layout(
            line.line_break_start,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        ),
        line_break_end=_remap_optional_source_position_for_layout(
            line.line_break_end,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        ),
        fragments=tuple(next_fragments),
        caret_stops=_caret_stops_for_line_fragments(
            next_fragments,
            projection_document=projection_document,
            line_top=line.top,
            line_height=line.height,
        ),
    )


def _remap_downstream_line_after_plain_edit(
    line: PromptProjectionLineSnapshot,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
) -> PromptProjectionLineSnapshot:
    """Return a downstream line shifted logically but not geometrically."""

    del edit_start, edit_end
    return _ShiftedLineSnapshot(
        line,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=0.0,
    )


def _remap_downstream_line_after_hard_line_edit(
    line: PromptProjectionLineSnapshot,
    *,
    source_delta: int,
    projection_delta: int,
    y_delta: float,
) -> PromptProjectionLineSnapshot:
    """Return a downstream line shifted lazily after a hard-line insert/delete."""

    return _ShiftedLineSnapshot(
        line,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=y_delta,
    )


def _shift_downstream_fragment_after_plain_edit(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    source_delta: int,
    projection_delta: int,
    y_delta: float,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one downstream fragment shifted after an upstream edit."""

    if isinstance(fragment, PromptProjectionTextFragment):
        return _ShiftedTextFragment(
            fragment,
            source_delta=source_delta,
            projection_delta=projection_delta,
            y_delta=y_delta,
        )
    return _ShiftedInlineObjectFragment(
        fragment,
        source_delta=source_delta,
        projection_delta=projection_delta,
        y_delta=y_delta,
    )


def _remap_fragment_after_plain_edit(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one fragment shifted after an edit."""

    next_rect = QRectF(fragment.rect)
    next_rect.translate(x_delta, 0.0)
    source_positions = tuple(
        _remap_source_position_for_layout(
            position,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        )
        for position in fragment.source_positions
    )
    if isinstance(fragment, PromptProjectionTextFragment):
        return PromptProjectionTextFragment(
            run_id=fragment.run_id,
            token_id=fragment.token_id,
            projection_start=fragment.projection_start + projection_delta,
            projection_end=fragment.projection_end + projection_delta,
            text=fragment.text,
            source_positions=source_positions,
            rect=next_rect,
            baseline=fragment.baseline,
            boundary_offsets=fragment.boundary_offsets,
            active=fragment.active,
        )
    return PromptProjectionInlineObjectFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        renderer_key=fragment.renderer_key,
        projection_start=fragment.projection_start + projection_delta,
        projection_end=fragment.projection_end + projection_delta,
        source_positions=source_positions,
        rect=next_rect,
        active=fragment.active,
    )


def _remap_fragment_after_hard_line_edit(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
    projection_delta: int,
    x_delta: float,
    y_delta: float,
) -> PromptProjectionTextFragment | PromptProjectionInlineObjectFragment:
    """Return one fragment shifted logically and geometrically across a line edit."""

    next_rect = QRectF(fragment.rect)
    next_rect.translate(x_delta, y_delta)
    source_positions = tuple(
        _remap_source_position_for_layout(
            position,
            edit_start=edit_start,
            edit_end=edit_end,
            delta=source_delta,
        )
        for position in fragment.source_positions
    )
    if isinstance(fragment, PromptProjectionTextFragment):
        return PromptProjectionTextFragment(
            run_id=fragment.run_id,
            token_id=fragment.token_id,
            projection_start=fragment.projection_start + projection_delta,
            projection_end=fragment.projection_end + projection_delta,
            text=fragment.text,
            source_positions=source_positions,
            rect=next_rect,
            baseline=fragment.baseline + y_delta,
            boundary_offsets=fragment.boundary_offsets,
            active=fragment.active,
        )
    return PromptProjectionInlineObjectFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        renderer_key=fragment.renderer_key,
        projection_start=fragment.projection_start + projection_delta,
        projection_end=fragment.projection_end + projection_delta,
        source_positions=source_positions,
        rect=next_rect,
        active=fragment.active,
    )


def _caret_stops_for_line_fragments(
    fragments: Sequence[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ],
    *,
    projection_document: PromptProjectionDocument,
    line_top: float,
    line_height: float,
    extra_boundaries: Sequence[tuple[int, float]] = (),
) -> tuple[PromptProjectionLineCaretStopSnapshot, ...]:
    """Return source-ordered caret stops implied by one visual line."""

    caret_stops: list[PromptProjectionLineCaretStopSnapshot] = []
    seen_positions: set[int] = set()
    for projection_position, x_position in extra_boundaries:
        if not projection_document.caret_map.has_projection_position(
            projection_position
        ):
            continue
        seen_positions.add(projection_position)
        caret_stops.append(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=projection_position,
                rect=QRectF(x_position, line_top, 1.0, line_height),
            )
        )
    for fragment in fragments:
        if isinstance(fragment, PromptProjectionTextFragment):
            for boundary_index, boundary_offset in enumerate(fragment.boundary_offsets):
                projection_position = fragment.projection_start + boundary_index
                if (
                    projection_position in seen_positions
                    or not projection_document.caret_map.has_projection_position(
                        projection_position
                    )
                ):
                    continue
                seen_positions.add(projection_position)
                caret_stops.append(
                    PromptProjectionLineCaretStopSnapshot(
                        projection_position=projection_position,
                        rect=QRectF(
                            fragment.rect.left() + boundary_offset,
                            line_top,
                            1.0,
                            line_height,
                        ),
                    )
                )
            continue
        for projection_position, x_position in (
            (fragment.projection_start, fragment.rect.left()),
            (fragment.projection_end, fragment.rect.right()),
        ):
            if projection_position in seen_positions:
                continue
            seen_positions.add(projection_position)
            caret_stops.append(
                PromptProjectionLineCaretStopSnapshot(
                    projection_position=projection_position,
                    rect=QRectF(x_position, line_top, 1.0, line_height),
                )
            )
    return tuple(
        sorted(
            caret_stops,
            key=lambda caret_stop: caret_stop.projection_position,
        )
    )


def _normalized_source_ranges(
    source_ranges: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Return non-empty source ranges in deterministic order."""

    return tuple(sorted((start, end) for start, end in source_ranges if end > start))


def _reorder_visible_lines(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    document_clip: QRectF,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return projection lines intersecting one reorder paint snapshot clip."""

    clip_top = document_clip.top()
    clip_bottom = document_clip.bottom()
    return tuple(
        line
        for line in lines
        if line.top <= clip_bottom and line.top + line.height >= clip_top
    )


def _source_positions_overlap(
    source_positions: Sequence[int],
    source_ranges: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether any source position belongs to the supplied ranges."""

    for source_position in source_positions:
        for start, end in source_ranges:
            if start <= source_position < end:
                return True
    return False


def _source_position_chunks(
    source_positions: Sequence[int],
    *,
    source_ranges: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """Return contiguous fragment-local chunks owned by the supplied source ranges."""

    chunks: list[tuple[int, int]] = []
    chunk_start: int | None = None
    previous_index: int | None = None
    for index, source_position in enumerate(source_positions):
        owned = any(start <= source_position < end for start, end in source_ranges)
        if owned and chunk_start is None:
            chunk_start = index
        if not owned and chunk_start is not None:
            chunks.append((chunk_start, index))
            chunk_start = None
        previous_index = index
    if chunk_start is not None:
        chunks.append(
            (chunk_start, 0 if previous_index is None else previous_index + 1)
        )
    return tuple(chunks)


def _remap_optional_source_position_for_layout(
    position: int | None,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
) -> int | None:
    """Return an optional source position shifted across a layout edit."""

    if position is None:
        return None
    return _remap_source_position_for_layout(
        position,
        edit_start=edit_start,
        edit_end=edit_end,
        delta=delta,
    )


def _remap_source_position_for_layout(
    position: int,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
) -> int:
    """Return a source position shifted across a non-overlapping edit."""

    if edit_start == edit_end:
        if position >= edit_start:
            return position + delta
        return position
    if position >= edit_end:
        return position + delta
    if position > edit_start:
        return edit_start
    return position


def _drag_direction(
    *, anchor_line_index: int | None, line_index: int | None
) -> int | None:
    """Return the wrapped-line drag direction implied by one anchor and target line."""

    if anchor_line_index is None or line_index is None:
        return None
    if line_index > anchor_line_index:
        return 1
    if line_index < anchor_line_index:
        return -1
    return 0


def _source_line_ranges(source_text: str) -> tuple[tuple[int, int], ...]:
    """Return newline-delimited source ranges including trailing empty lines."""

    ranges: list[tuple[int, int]] = []
    line_start = 0
    for index, character in enumerate(source_text):
        if character != "\n":
            continue
        ranges.append((line_start, index + 1))
        line_start = index + 1
    ranges.append((line_start, len(source_text)))
    return tuple(ranges)


def _source_line_intersects_visual_line(
    *,
    source_start: int,
    source_end: int,
    visual_start: int,
    visual_end: int,
) -> bool:
    """Return whether a source logical line owns one wrapped visual line."""

    if source_start == source_end:
        return visual_start == source_start and visual_end == source_start
    return visual_start < source_end and source_start < visual_end


def _source_range_intersects_visual_line(
    *,
    source_start: int,
    source_end: int,
    visual_start: int,
    visual_end: int,
) -> bool:
    """Return whether one source range owns any part of a visual line."""

    if source_start == source_end:
        return visual_start <= source_start <= visual_end
    if visual_start == visual_end:
        return source_start <= visual_start < source_end
    return visual_start < source_end and source_start < visual_end
