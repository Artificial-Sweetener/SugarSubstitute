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

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPen

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor.document.views import (
    PromptRegionPartitionView,
)
from substitute.domain.appearance import RgbColor
from substitute.presentation.regional import region_color

from .metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from ..layout.contracts import PromptLayoutOutput
from ..layout.models import PromptProjectionLineSnapshot
from .theme import qcolor_from_rgb
from .region_chrome_state import (
    PromptRegionChromeLabel,
    PromptRegionChromeSnapshot,
    PromptRegionChromeStroke,
)

_DIVIDER_MAX_WIDTH = 36.0
_DIVIDER_CONTENT_WIDTH_RATIO = 0.2
_STROKE_WIDTH = 2.0
_RAIL_CONTENT_GAP = 3.0
_NAMED_DIVIDER_MAX_WIDTH = 240.0
_NAMED_DIVIDER_CONTENT_WIDTH_RATIO = 0.72
_LABEL_RULE_GAP = 8.0


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
        self._hovered_region_index: int | None = None
        self._active_base_snapshot: PromptRegionChromeSnapshot | None = None
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
        paint_lines: list[QLineF] = []
        labels: list[PromptRegionChromeLabel] = []
        strokes: list[PromptRegionChromeStroke] = []
        divider_width = min(
            _DIVIDER_MAX_WIDTH,
            metrics.content_width * _DIVIDER_CONTENT_WIDTH_RATIO,
        )
        divider_left = (
            metrics.content_left + (metrics.content_width - divider_width) / 2.0
        )
        total_regions = len(structure.separators)
        region_pens = tuple(
            _region_pen(
                region_color(
                    index,
                    total_regions,
                    base_color=qcolor_from_rgb(semantic_palette.accent),
                )
            )
            for index in range(total_regions)
        )
        separator_stroke_lines: list[tuple[QLineF, ...]] = []
        for index, separator in enumerate(structure.separators):
            line = _line_for_exact_source_range(
                line_probe,
                source_start=separator.line_start,
                source_end=separator.line_end,
            )
            if line is None:
                continue
            divider_y = line.top + line.height / 2.0
            conceptual_divider = QLineF(
                divider_left,
                divider_y,
                divider_left + divider_width,
                divider_y,
            )
            divider_lines.append(conceptual_divider)
            region_lines, label = _separator_paint_geometry(
                separator_name=separator.name,
                divider_y=divider_y,
                metrics=metrics,
                base_font=output.configuration.base_font,
                color=region_pens[index].color(),
                plain_divider=conceptual_divider,
            )
            separator_stroke_lines.append(region_lines)
            paint_lines.extend(region_lines)
            if label is not None:
                labels.append(label)

        rail_x = max(1.0, metrics.content_left - _RAIL_CONTENT_GAP)
        rail_lines_list: list[QLineF] = []
        rail_lines_by_region: list[QLineF | None] = []
        for partition in regional_partitions:
            extent = _partition_line_extent(line_probe, partition)
            if extent is None:
                rail_lines_by_region.append(None)
                continue
            rail = QLineF(rail_x, extent[0], rail_x, extent[1])
            rail_lines_list.append(rail)
            rail_lines_by_region.append(rail)
        rail_lines = tuple(rail_lines_list)
        pen = _accent_pen(semantic_palette)
        for index, separator_lines in enumerate(separator_stroke_lines):
            lines = list(separator_lines)
            if index < len(rail_lines_by_region):
                region_rail = rail_lines_by_region[index]
                if region_rail is not None:
                    lines.insert(0, region_rail)
                    paint_lines.append(region_rail)
            strokes.append(
                PromptRegionChromeStroke(
                    region_index=index,
                    lines=tuple(lines),
                    pen=region_pens[index],
                )
            )
        snapshot = PromptRegionChromeSnapshot(
            layout_snapshot_identity=id(output.snapshot),
            accent=semantic_palette.accent,
            divider_lines=tuple(divider_lines),
            rail_lines=rail_lines,
            paint_lines=tuple(paint_lines),
            pen=pen,
            strokes=tuple(strokes),
            labels=tuple(labels),
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
            strokes=(),
            labels=(),
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
            self._active_base_snapshot = None
            self._active_snapshot = None
            return
        self._active_base_snapshot = self.prepare(
            output,
            semantic_palette=semantic_palette,
        )
        self._active_snapshot = _snapshot_with_hover(
            self._active_base_snapshot,
            self._hovered_region_index,
        )

    def set_hovered_region(self, region_index: int | None) -> bool:
        """Publish transient emphasis without recomputing layout geometry."""

        if region_index == self._hovered_region_index:
            return False
        self._hovered_region_index = region_index
        if self._active_base_snapshot is None:
            return False
        self._active_snapshot = _snapshot_with_hover(
            self._active_base_snapshot,
            region_index,
        )
        return True


def _snapshot_with_hover(
    snapshot: PromptRegionChromeSnapshot,
    region_index: int | None,
) -> PromptRegionChromeSnapshot:
    """Return paint-ready hover emphasis while reusing prepared geometry."""

    if region_index is None:
        return snapshot
    strokes: list[PromptRegionChromeStroke] = []
    for stroke in snapshot.strokes:
        if stroke.region_index != region_index:
            strokes.append(stroke)
            continue
        pen = QPen(stroke.pen)
        pen.setWidthF(stroke.pen.widthF() + 1.5)
        pen.setColor(stroke.pen.color().lighter(135))
        strokes.append(
            PromptRegionChromeStroke(
                region_index=stroke.region_index,
                lines=stroke.lines,
                pen=pen,
            )
        )
    return PromptRegionChromeSnapshot(
        layout_snapshot_identity=snapshot.layout_snapshot_identity,
        accent=snapshot.accent,
        divider_lines=snapshot.divider_lines,
        rail_lines=snapshot.rail_lines,
        paint_lines=snapshot.paint_lines,
        pen=snapshot.pen,
        strokes=tuple(strokes),
        labels=snapshot.labels,
        visited_line_count=snapshot.visited_line_count,
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

    return _region_pen(qcolor_from_rgb(semantic_palette.accent))


def _region_pen(color: QColor) -> QPen:
    """Return one immutable solid stroke for a regional identity color."""

    pen = QPen(color)
    pen.setWidthF(_STROKE_WIDTH)
    pen.setStyle(Qt.PenStyle.SolidLine)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


def _separator_paint_geometry(
    *,
    separator_name: str | None,
    divider_y: float,
    metrics: PromptProjectionMetrics,
    base_font: QFont,
    color: QColor,
    plain_divider: QLineF,
) -> tuple[tuple[QLineF, ...], PromptRegionChromeLabel | None]:
    """Prepare a plain rule or a centered named rule without changing source."""

    if separator_name is None:
        return (plain_divider,), None
    label_font = QFont(base_font)
    label_font.setBold(True)
    font_metrics = QFontMetricsF(label_font)
    available_width = min(
        _NAMED_DIVIDER_MAX_WIDTH,
        metrics.content_width * _NAMED_DIVIDER_CONTENT_WIDTH_RATIO,
    )
    maximum_label_width = max(1.0, available_width - (2.0 * _LABEL_RULE_GAP))
    label_text = font_metrics.elidedText(
        separator_name,
        Qt.TextElideMode.ElideRight,
        int(maximum_label_width),
    )
    label_width = font_metrics.horizontalAdvance(label_text)
    content_center = metrics.content_left + metrics.content_width / 2.0
    label_left = content_center - label_width / 2.0
    label_right = content_center + label_width / 2.0
    rule_left = content_center - available_width / 2.0
    rule_right = content_center + available_width / 2.0
    lines = tuple(
        line
        for line in (
            QLineF(rule_left, divider_y, label_left - _LABEL_RULE_GAP, divider_y),
            QLineF(label_right + _LABEL_RULE_GAP, divider_y, rule_right, divider_y),
        )
        if line.length() > 0.0
    )
    baseline_y = divider_y + (font_metrics.ascent() - font_metrics.descent()) / 2.0
    return lines, PromptRegionChromeLabel(
        text=label_text,
        baseline=QPointF(label_left, baseline_y),
        color=QColor(color),
        font=label_font,
    )


__all__ = [
    "PromptRegionChrome",
]
