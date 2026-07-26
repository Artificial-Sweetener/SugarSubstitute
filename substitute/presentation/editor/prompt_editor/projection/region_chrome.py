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

"""Prepare immutable accent chrome for regional prompt structure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QLineF, Qt
from PySide6.QtGui import QPen

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor.document.views import (
    PromptRegionPartitionView,
)
from substitute.domain.appearance import RgbColor

from .metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from ..layout.contracts import PromptLayoutOutput
from ..layout.models import PromptProjectionLineSnapshot
from .theme import qcolor_from_rgb
from .region_chrome_state import PromptRegionChromeSnapshot

_DIVIDER_MAX_WIDTH = 36.0
_DIVIDER_CONTENT_WIDTH_RATIO = 0.2
_STROKE_WIDTH = 2.0
_RAIL_CONTENT_GAP = 3.0


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

        self._entries_by_snapshot_id: dict[int, _RegionChromeCacheEntry] = {}
        self._prepare_count = 0
        self._active_snapshot: PromptRegionChromeSnapshot | None = None

    @property
    def prepare_count(self) -> int:
        """Return the number of explicit geometry preparation passes."""

        return self._prepare_count

    @property
    def active_snapshot(self) -> PromptRegionChromeSnapshot | None:
        """Return the regional layer explicitly published for current paint."""

        return self._active_snapshot

    def prepare(
        self,
        output: PromptLayoutOutput,
        *,
        semantic_palette: SemanticPalette,
    ) -> PromptRegionChromeSnapshot:
        """Build immutable divider and rail geometry in one visual-line pass."""

        metrics = output.configuration.metrics
        projection_document = output.projection_document
        cached_snapshot = self._matching_snapshot(
            output,
            semantic_palette=semantic_palette,
        )
        if cached_snapshot is not None:
            return cached_snapshot
        if projection_document.display_mode is PromptProjectionDisplayMode.RAW:
            return self._empty_snapshot(
                output,
                semantic_palette=semantic_palette,
                count_preparation=False,
            )
        structure = projection_document.region_structure
        if not structure.separators:
            return self._empty_snapshot(
                output,
                semantic_palette=semantic_palette,
                count_preparation=True,
            )
        self._prepare_count += 1
        regional_partitions = tuple(
            partition for partition in structure.partitions if not partition.is_global
        )
        line_probe = _RegionLineProbe(output.snapshot.lines)
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
            layout_snapshot_identity=id(output.snapshot),
            accent=semantic_palette.accent,
            divider_lines=tuple(divider_lines),
            rail_lines=rail_lines,
            paint_lines=paint_lines,
            pen=pen,
            visited_line_count=line_probe.visited_line_count,
        )
        self._store_snapshot(
            output,
            snapshot,
            semantic_palette=semantic_palette,
        )
        return snapshot

    def _empty_snapshot(
        self,
        output: PromptLayoutOutput,
        *,
        semantic_palette: SemanticPalette,
        count_preparation: bool,
    ) -> PromptRegionChromeSnapshot:
        """Return cached empty chrome without walking any layout lines."""

        if count_preparation:
            self._prepare_count += 1
        snapshot = PromptRegionChromeSnapshot(
            layout_snapshot_identity=id(output.snapshot),
            accent=semantic_palette.accent,
            divider_lines=(),
            rail_lines=(),
            paint_lines=(),
            pen=_accent_pen(semantic_palette),
            visited_line_count=0,
        )
        self._store_snapshot(
            output,
            snapshot,
            semantic_palette=semantic_palette,
        )
        return snapshot

    def _store_snapshot(
        self,
        output: PromptLayoutOutput,
        snapshot: PromptRegionChromeSnapshot,
        *,
        semantic_palette: SemanticPalette,
    ) -> None:
        """Store a bounded set of live and preview layout snapshots."""

        snapshot_id = id(output.snapshot)
        self._entries_by_snapshot_id[snapshot_id] = _RegionChromeCacheEntry(
            projection_document=output.projection_document,
            metrics=output.configuration.metrics,
            line_snapshots=output.snapshot.lines,
            accent=semantic_palette.accent,
            snapshot=snapshot,
        )
        while len(self._entries_by_snapshot_id) > 4:
            oldest_snapshot_id = next(iter(self._entries_by_snapshot_id))
            del self._entries_by_snapshot_id[oldest_snapshot_id]

    def _matching_snapshot(
        self,
        output: PromptLayoutOutput,
        *,
        semantic_palette: SemanticPalette,
    ) -> PromptRegionChromeSnapshot | None:
        """Return cached geometry only for the exact immutable layout owners."""

        entry = self._entries_by_snapshot_id.get(id(output.snapshot))
        if entry is None:
            return None
        if (
            entry.projection_document is not output.projection_document
            or entry.metrics is not output.configuration.metrics
            or entry.line_snapshots is not output.snapshot.lines
            or entry.accent != semantic_palette.accent
        ):
            return None
        return entry.snapshot

    def snapshot_for(
        self,
        output: PromptLayoutOutput,
    ) -> PromptRegionChromeSnapshot | None:
        """Return only explicitly prepared geometry for one layout."""

        entry = self._entries_by_snapshot_id.get(id(output.snapshot))
        if entry is None:
            return None
        if (
            entry.projection_document is not output.projection_document
            or entry.metrics is not output.configuration.metrics
            or entry.line_snapshots is not output.snapshot.lines
        ):
            return None
        return entry.snapshot

    def prepare_active(
        self,
        output: PromptLayoutOutput,
        *,
        semantic_palette: SemanticPalette,
    ) -> None:
        """Prepare only regional output and publish it as the active layer."""

        projection_document = output.projection_document
        if (
            projection_document.display_mode is PromptProjectionDisplayMode.RAW
            or not projection_document.region_structure.separators
        ):
            self._active_snapshot = None
            return
        self._active_snapshot = self.prepare(
            output,
            semantic_palette=semantic_palette,
        )


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
]
