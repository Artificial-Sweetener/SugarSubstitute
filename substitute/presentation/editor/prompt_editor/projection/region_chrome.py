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

"""Prepare and paint immutable accent chrome for regional prompt structure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from PySide6.QtCore import QLineF, Qt
from PySide6.QtGui import QPainter, QPen

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor import PromptRegionPartitionView
from substitute.domain.appearance import RgbColor

from .metrics import PromptProjectionMetrics
from .model import PromptProjectionDisplayMode, PromptProjectionDocument
from .snapshot import PromptProjectionLineSnapshot
from .theme import qcolor_from_rgb

_DIVIDER_MAX_WIDTH = 36.0
_DIVIDER_CONTENT_WIDTH_RATIO = 0.2
_STROKE_WIDTH = 2.0
_RAIL_CONTENT_GAP = 3.0


class PromptRegionChromeLayout(Protocol):
    """Expose immutable layout state needed to prepare regional chrome."""

    @property
    def projection_document(self) -> PromptProjectionDocument:
        """Return the projection document owning regional structure."""
        ...

    @property
    def metrics(self) -> PromptProjectionMetrics:
        """Return the geometry metrics used by the layout snapshot."""
        ...

    @property
    def line_snapshots(self) -> Sequence[PromptProjectionLineSnapshot]:
        """Return the immutable visual lines in document order."""
        ...


@dataclass(frozen=True, slots=True)
class PromptRegionChromeSnapshot:
    """Store paint-ready separator and regional rail geometry."""

    divider_lines: tuple[QLineF, ...]
    rail_lines: tuple[QLineF, ...]
    paint_lines: tuple[QLineF, ...]
    pen: QPen
    visited_line_count: int


@dataclass(frozen=True, slots=True)
class _RegionChromeCacheEntry:
    """Bind paint geometry to the immutable owners that produced it."""

    projection_document: PromptProjectionDocument
    metrics: PromptProjectionMetrics
    line_snapshots: Sequence[PromptProjectionLineSnapshot]
    accent: RgbColor
    snapshot: PromptRegionChromeSnapshot


@dataclass(slots=True)
class _RegionLineProbe:
    """Index source-ordered layout lines while counting bounded lookups."""

    lines: Sequence[PromptProjectionLineSnapshot]
    _visited_indices: set[int] = field(default_factory=set)

    @property
    def visited_line_count(self) -> int:
        """Return the number of distinct lines consulted by boundary searches."""

        return len(self._visited_indices)

    def line(self, index: int) -> PromptProjectionLineSnapshot:
        """Return one line and record the geometry lookup."""

        self._visited_indices.add(index)
        return self.lines[index]


class PromptRegionChrome:
    """Own cached regional chrome geometry and its allocation-free paint loop."""

    def __init__(self) -> None:
        """Initialize empty snapshots keyed by live layout identity."""

        self._entries_by_layout_id: dict[int, _RegionChromeCacheEntry] = {}
        self._prepare_count = 0

    @property
    def prepare_count(self) -> int:
        """Return the number of explicit geometry preparation passes."""

        return self._prepare_count

    def prepare(
        self,
        layout: PromptRegionChromeLayout,
        *,
        semantic_palette: SemanticPalette,
    ) -> PromptRegionChromeSnapshot:
        """Build immutable divider and rail geometry in one visual-line pass."""

        metrics = layout.metrics
        projection_document = layout.projection_document
        cached_snapshot = self._matching_snapshot(
            layout,
            semantic_palette=semantic_palette,
        )
        if cached_snapshot is not None:
            return cached_snapshot
        if projection_document.display_mode is PromptProjectionDisplayMode.RAW:
            return self._empty_snapshot(
                layout,
                semantic_palette=semantic_palette,
                count_preparation=False,
            )
        structure = projection_document.region_structure
        if not structure.separators:
            return self._empty_snapshot(
                layout,
                semantic_palette=semantic_palette,
                count_preparation=True,
            )
        self._prepare_count += 1
        regional_partitions = tuple(
            partition for partition in structure.partitions if not partition.is_global
        )
        line_probe = _RegionLineProbe(layout.line_snapshots)
        divider_lines: list[QLineF] = []
        divider_width = min(
            _DIVIDER_MAX_WIDTH,
            metrics.content_width * _DIVIDER_CONTENT_WIDTH_RATIO,
        )
        divider_left = (
            metrics.content_left + (metrics.content_width - divider_width) / 2.0
        )
        for separator in structure.separators:
            line = _line_for_exact_source_range(
                line_probe,
                source_start=separator.line_start,
                source_end=separator.line_end,
            )
            if line is None:
                continue
            divider_y = line.top + line.height / 2.0
            divider_lines.append(
                QLineF(
                    divider_left,
                    divider_y,
                    divider_left + divider_width,
                    divider_y,
                )
            )

        rail_x = max(1.0, metrics.content_left - _RAIL_CONTENT_GAP)
        rail_lines_list: list[QLineF] = []
        for partition in regional_partitions:
            extent = _partition_line_extent(line_probe, partition)
            if extent is None:
                continue
            rail_lines_list.append(QLineF(rail_x, extent[0], rail_x, extent[1]))
        rail_lines = tuple(rail_lines_list)
        pen = _accent_pen(semantic_palette)
        paint_lines = (*rail_lines, *divider_lines)
        snapshot = PromptRegionChromeSnapshot(
            divider_lines=tuple(divider_lines),
            rail_lines=rail_lines,
            paint_lines=paint_lines,
            pen=pen,
            visited_line_count=line_probe.visited_line_count,
        )
        self._store_snapshot(
            layout,
            snapshot,
            semantic_palette=semantic_palette,
        )
        return snapshot

    def _empty_snapshot(
        self,
        layout: PromptRegionChromeLayout,
        *,
        semantic_palette: SemanticPalette,
        count_preparation: bool,
    ) -> PromptRegionChromeSnapshot:
        """Return cached empty chrome without walking any layout lines."""

        if count_preparation:
            self._prepare_count += 1
        snapshot = PromptRegionChromeSnapshot(
            divider_lines=(),
            rail_lines=(),
            paint_lines=(),
            pen=_accent_pen(semantic_palette),
            visited_line_count=0,
        )
        self._store_snapshot(
            layout,
            snapshot,
            semantic_palette=semantic_palette,
        )
        return snapshot

    def _store_snapshot(
        self,
        layout: PromptRegionChromeLayout,
        snapshot: PromptRegionChromeSnapshot,
        *,
        semantic_palette: SemanticPalette,
    ) -> None:
        """Store a bounded set of live and preview layout snapshots."""

        layout_id = id(layout)
        self._entries_by_layout_id[layout_id] = _RegionChromeCacheEntry(
            projection_document=layout.projection_document,
            metrics=layout.metrics,
            line_snapshots=layout.line_snapshots,
            accent=semantic_palette.accent,
            snapshot=snapshot,
        )
        while len(self._entries_by_layout_id) > 4:
            oldest_layout_id = next(iter(self._entries_by_layout_id))
            del self._entries_by_layout_id[oldest_layout_id]

    def _matching_snapshot(
        self,
        layout: PromptRegionChromeLayout,
        *,
        semantic_palette: SemanticPalette,
    ) -> PromptRegionChromeSnapshot | None:
        """Return cached geometry only for the exact immutable layout owners."""

        entry = self._entries_by_layout_id.get(id(layout))
        if entry is None:
            return None
        if (
            entry.projection_document is not layout.projection_document
            or entry.metrics is not layout.metrics
            or entry.line_snapshots is not layout.line_snapshots
            or entry.accent != semantic_palette.accent
        ):
            return None
        return entry.snapshot

    def snapshot_for(
        self,
        layout: PromptRegionChromeLayout,
    ) -> PromptRegionChromeSnapshot | None:
        """Return only explicitly prepared geometry for one layout."""

        entry = self._entries_by_layout_id.get(id(layout))
        if entry is None:
            return None
        if (
            entry.projection_document is not layout.projection_document
            or entry.metrics is not layout.metrics
            or entry.line_snapshots is not layout.line_snapshots
        ):
            return None
        return entry.snapshot

    def paint(
        self,
        painter: QPainter,
        *,
        layout: PromptRegionChromeLayout,
        scroll_offset: float,
    ) -> None:
        """Paint cached document-local geometry without deriving or copying it."""

        snapshot = self.snapshot_for(layout)
        if snapshot is None or not snapshot.paint_lines:
            return
        painter.save()
        try:
            painter.translate(0.0, -scroll_offset)
            painter.setPen(snapshot.pen)
            painter.drawLines(snapshot.paint_lines)
        finally:
            painter.restore()


def _line_intersects_partition(
    line: PromptProjectionLineSnapshot,
    partition: PromptRegionPartitionView,
) -> bool:
    """Return whether a visual content or blank line belongs to one partition."""

    if partition.source_start == partition.source_end:
        return (
            line.source_start == partition.source_start
            and line.source_end == partition.source_end
        )
    if line.source_end > line.source_start:
        return (
            line.source_start < partition.source_end
            and line.source_end > partition.source_start
        )
    return partition.source_start <= line.source_start <= partition.source_end


def _partition_line_extent(
    probe: _RegionLineProbe,
    partition: PromptRegionPartitionView,
) -> tuple[float, float] | None:
    """Return the first and last row extent for one regional partition."""

    if not probe.lines:
        return None
    if partition.source_start == partition.source_end:
        line = _line_for_exact_source_range(
            probe,
            source_start=partition.source_start,
            source_end=partition.source_end,
        )
        if line is None:
            return None
        return line.top, line.top + line.height

    first_index = _first_line_ending_after(probe, partition.source_start)
    end_index = _first_line_starting_at_or_after(probe, partition.source_end)
    last_index = end_index - 1
    if first_index >= len(probe.lines) or last_index < first_index:
        return None
    first_line = probe.line(first_index)
    last_line = probe.line(last_index)
    if not _line_intersects_partition(first_line, partition):
        return None
    if not _line_intersects_partition(last_line, partition):
        return None
    return first_line.top, last_line.top + last_line.height


def _line_for_exact_source_range(
    probe: _RegionLineProbe,
    *,
    source_start: int,
    source_end: int,
) -> PromptProjectionLineSnapshot | None:
    """Return an exact structural or empty line without scanning the document."""

    line_index = _first_line_starting_at_or_after(probe, source_start)
    while line_index < len(probe.lines):
        line = probe.line(line_index)
        if line.source_start != source_start:
            return None
        if line.source_end == source_end:
            return line
        line_index += 1
    return None


def _first_line_ending_after(probe: _RegionLineProbe, source_position: int) -> int:
    """Return the first line whose source end exceeds one boundary."""

    lower = 0
    upper = len(probe.lines)
    while lower < upper:
        middle = (lower + upper) // 2
        if probe.line(middle).source_end <= source_position:
            lower = middle + 1
        else:
            upper = middle
    return lower


def _first_line_starting_at_or_after(
    probe: _RegionLineProbe,
    source_position: int,
) -> int:
    """Return the first line whose source start reaches one boundary."""

    lower = 0
    upper = len(probe.lines)
    while lower < upper:
        middle = (lower + upper) // 2
        if probe.line(middle).source_start < source_position:
            lower = middle + 1
        else:
            upper = middle
    return lower


def _accent_pen(semantic_palette: SemanticPalette) -> QPen:
    """Return the immutable accent stroke shared by one prepared snapshot."""

    pen = QPen(qcolor_from_rgb(semantic_palette.accent))
    pen.setWidthF(_STROKE_WIDTH)
    pen.setStyle(Qt.PenStyle.SolidLine)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


__all__ = [
    "PromptRegionChrome",
    "PromptRegionChromeLayout",
    "PromptRegionChromeSnapshot",
]
