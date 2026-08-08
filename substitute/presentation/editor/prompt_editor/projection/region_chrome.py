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
from PySide6.QtGui import QColor, QPen

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
from .region_separator_geometry import (
    prepare_separator_draft_geometry,
    prepare_separator_paint_geometry,
)
from .region_chrome_state import (
    PromptRegionChromeEditTarget,
    PromptRegionChromeLabel,
    PromptRegionChromeSnapshot,
    PromptRegionChromeStroke,
)

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
    text_color: QColor
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
        self._editing_region_index: int | None = None
        self._editing_region_draft: str | None = None
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
        text_color: QColor,
    ) -> PromptRegionChromeSnapshot:
        """Build immutable divider and rail geometry in one visual-line pass."""

        metrics = output.configuration.metrics
        projection_document = output.projection_document
        cached_snapshot = self._matching_snapshot(
            output,
            semantic_palette=semantic_palette,
            text_color=text_color,
        )
        if cached_snapshot is not None:
            return cached_snapshot
        if projection_document.display_mode is PromptProjectionDisplayMode.RAW:
            return self._empty_snapshot(
                output,
                semantic_palette=semantic_palette,
                text_color=text_color,
                count_preparation=False,
            )
        structure = projection_document.region_structure
        if not structure.separators:
            return self._empty_snapshot(
                output,
                semantic_palette=semantic_palette,
                text_color=text_color,
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
        edit_targets: list[PromptRegionChromeEditTarget] = []
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
            region_lines, label, edit_target = prepare_separator_paint_geometry(
                region_index=index,
                separator_name=separator.name,
                divider_y=divider_y,
                row_height=line.height,
                metrics=metrics,
                base_font=output.configuration.base_font,
                color=text_color,
                plain_divider=conceptual_divider,
            )
            separator_stroke_lines.append(region_lines)
            paint_lines.extend(region_lines)
            if label is not None:
                labels.append(label)
            edit_targets.append(edit_target)

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
            edit_targets=tuple(edit_targets),
            visited_line_count=line_probe.visited_line_count,
        )
        self._store_snapshot(
            output,
            snapshot,
            semantic_palette=semantic_palette,
            text_color=text_color,
        )
        return snapshot

    def _empty_snapshot(
        self,
        output: PromptLayoutOutput,
        *,
        semantic_palette: SemanticPalette,
        text_color: QColor,
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
            edit_targets=(),
            visited_line_count=0,
        )
        self._store_snapshot(
            output,
            snapshot,
            semantic_palette=semantic_palette,
            text_color=text_color,
        )
        return snapshot

    def _store_snapshot(
        self,
        output: PromptLayoutOutput,
        snapshot: PromptRegionChromeSnapshot,
        *,
        semantic_palette: SemanticPalette,
        text_color: QColor,
    ) -> None:
        """Store a bounded set of live and preview layout snapshots."""

        snapshot_id = id(output.snapshot)
        self._entries_by_snapshot_id[snapshot_id] = _RegionChromeCacheEntry(
            projection_document=output.projection_document,
            metrics=output.configuration.metrics,
            line_snapshots=output.snapshot.lines,
            accent=semantic_palette.accent,
            text_color=QColor(text_color),
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
        text_color: QColor,
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
            or entry.text_color != text_color
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
        text_color: QColor,
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
            text_color=text_color,
        )
        self._active_snapshot = _snapshot_with_transients(
            self._active_base_snapshot,
            hovered_region_index=self._hovered_region_index,
            editing_region_index=self._editing_region_index,
            editing_region_draft=self._editing_region_draft,
        )

    def set_hovered_region(self, region_index: int | None) -> bool:
        """Publish transient emphasis without recomputing layout geometry."""

        if region_index == self._hovered_region_index:
            return False
        self._hovered_region_index = region_index
        if self._active_base_snapshot is None:
            return False
        self._active_snapshot = _snapshot_with_transients(
            self._active_base_snapshot,
            hovered_region_index=region_index,
            editing_region_index=self._editing_region_index,
            editing_region_draft=self._editing_region_draft,
        )
        return True

    def set_editing_region(self, region_index: int | None) -> bool:
        """Hide a painted label while its in-place editor owns the row."""

        if region_index == self._editing_region_index:
            return False
        self._editing_region_index = region_index
        self._editing_region_draft = None
        if self._active_base_snapshot is None:
            return False
        self._active_snapshot = _snapshot_with_transients(
            self._active_base_snapshot,
            hovered_region_index=self._hovered_region_index,
            editing_region_index=region_index,
            editing_region_draft=None,
        )
        return True

    def set_editing_region_draft(self, region_index: int, text: str) -> bool:
        """Reflow active separator framing around an uncommitted authored name."""

        if region_index != self._editing_region_index:
            return False
        if text == self._editing_region_draft:
            return False
        self._editing_region_draft = text
        if self._active_base_snapshot is None:
            return False
        self._active_snapshot = _snapshot_with_transients(
            self._active_base_snapshot,
            hovered_region_index=self._hovered_region_index,
            editing_region_index=region_index,
            editing_region_draft=text,
        )
        return True

    def edit_target(self, region_index: int) -> PromptRegionChromeEditTarget | None:
        """Return prepared in-place edit geometry for one regional separator."""

        snapshot = self._active_snapshot or self._active_base_snapshot
        if snapshot is None:
            return None
        return next(
            (
                target
                for target in snapshot.edit_targets
                if target.region_index == region_index
            ),
            None,
        )


def _snapshot_with_transients(
    snapshot: PromptRegionChromeSnapshot,
    *,
    hovered_region_index: int | None,
    editing_region_index: int | None,
    editing_region_draft: str | None,
) -> PromptRegionChromeSnapshot:
    """Apply hover and inline-edit presentation without recomputing geometry."""

    if hovered_region_index is None and editing_region_index is None:
        return snapshot
    edit_targets = snapshot.edit_targets
    transient_strokes = snapshot.strokes
    if editing_region_index is not None and editing_region_draft is not None:
        edit_targets, transient_strokes = _chrome_with_editing_draft(
            snapshot,
            region_index=editing_region_index,
            draft=editing_region_draft,
        )
    strokes: list[PromptRegionChromeStroke] = []
    for stroke in transient_strokes:
        if stroke.region_index != hovered_region_index:
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
        paint_lines=tuple(line for stroke in strokes for line in stroke.lines),
        pen=snapshot.pen,
        strokes=tuple(strokes),
        labels=tuple(
            label
            for label in snapshot.labels
            if label.region_index != editing_region_index
        ),
        edit_targets=edit_targets,
        visited_line_count=snapshot.visited_line_count,
    )


def _chrome_with_editing_draft(
    snapshot: PromptRegionChromeSnapshot,
    *,
    region_index: int,
    draft: str,
) -> tuple[
    tuple[PromptRegionChromeEditTarget, ...],
    tuple[PromptRegionChromeStroke, ...],
]:
    """Return editor width and framing rules derived from one transient draft."""

    base_target = next(
        (
            target
            for target in snapshot.edit_targets
            if target.region_index == region_index
        ),
        None,
    )
    if base_target is None:
        return snapshot.edit_targets, snapshot.strokes
    draft_target, separator_lines = prepare_separator_draft_geometry(
        base_target,
        draft,
    )
    edit_targets = tuple(
        draft_target if target.region_index == region_index else target
        for target in snapshot.edit_targets
    )
    strokes = tuple(
        _stroke_with_separator_lines(
            stroke,
            base_line_count=base_target.separator_line_count,
            separator_lines=separator_lines,
        )
        if stroke.region_index == region_index
        else stroke
        for stroke in snapshot.strokes
    )
    return edit_targets, strokes


def _stroke_with_separator_lines(
    stroke: PromptRegionChromeStroke,
    *,
    base_line_count: int,
    separator_lines: tuple[QLineF, ...],
) -> PromptRegionChromeStroke:
    """Replace the separator-line suffix while preserving its regional rail."""

    retained_count = max(0, len(stroke.lines) - base_line_count)
    return PromptRegionChromeStroke(
        region_index=stroke.region_index,
        lines=(*stroke.lines[:retained_count], *separator_lines),
        pen=stroke.pen,
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


__all__ = [
    "PromptRegionChrome",
]
