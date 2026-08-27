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

"""Capture prepared prompt-projection layout state from a mounted editor."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QLineF, QRect, QRectF

from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
)
from tests.support.prompt_editor.real_shell.fragments import fragment_source_range
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorVisibleLayoutRow,
    PromptEditorVisibleTextFragment,
)
from tests.support.prompt_editor.real_shell.projection_transients import (
    _qrectf_sequence,
)


def _layout_count(layout_output: object | None, metric_name: str) -> int:
    """Return one prepared geometry count from the public layout snapshot."""

    snapshot = getattr(layout_output, "snapshot", None)
    metric = getattr(snapshot, metric_name, None)
    result = metric() if callable(metric) else None
    return int(result) if isinstance(result, int) else 0


def _layout_content_size(layout_output: object | None) -> tuple[float, float]:
    """Return layout content width and height without painting."""

    snapshot = getattr(layout_output, "snapshot", None)
    size = getattr(snapshot, "content_size", None)
    if size is None:
        return (0.0, 0.0)
    width = getattr(size, "width", None)
    height = getattr(size, "height", None)
    return (
        float(width()) if callable(width) else 0.0,
        float(height()) if callable(height) else 0.0,
    )


def _visible_layout_rows(
    *,
    layout_output: object | None,
    metrics: object | None,
    source_text: str,
    viewport_rect: QRect,
    scroll_offset: float,
) -> tuple[PromptEditorVisibleLayoutRow, ...]:
    """Return projection rows that should be visible in the current viewport."""

    snapshot = getattr(layout_output, "snapshot", None)
    lines = getattr(snapshot, "lines", ())
    if not isinstance(lines, Sequence):
        return ()
    viewport_top = float(viewport_rect.top())
    viewport_bottom = float(viewport_rect.bottom())
    rows: list[PromptEditorVisibleLayoutRow] = []
    projection_document = getattr(layout_output, "projection_document", None)
    region_structure = getattr(projection_document, "region_structure", None)
    projection_display_mode = _safeenum_value(
        getattr(projection_document, "display_mode", "")
    )
    structural_ranges = (
        {
            (separator.line_start, separator.line_end)
            for separator in getattr(region_structure, "separators", ())
        }
        if projection_display_mode == "projected"
        else set()
    )
    for row_index, line in enumerate(lines):
        document_top = _optional_float(getattr(line, "top", None))
        height = _optional_float(getattr(line, "height", None))
        source_start = _optional_int(getattr(line, "source_start", None))
        source_end = _optional_int(getattr(line, "source_end", None))
        if (
            document_top is None
            or height is None
            or source_start is None
            or source_end is None
        ):
            continue
        row_viewport_top = document_top - scroll_offset
        row_viewport_bottom = row_viewport_top + height
        if row_viewport_bottom < viewport_top - 2.0:
            continue
        if row_viewport_top > viewport_bottom + 2.0:
            continue
        safe_start = max(0, min(source_start, len(source_text)))
        safe_end = max(safe_start, min(source_end, len(source_text)))
        fragments = getattr(line, "fragments", ())
        has_inline_object = any(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in fragments
        )
        is_structural = (source_start, source_end) in structural_ranges
        expected_height = _expected_row_height(
            line=line,
            metrics=metrics,
            is_structural=is_structural,
        )
        expected_baseline = (
            None
            if is_structural
            else _metrics_text_baseline(
                metrics=metrics,
                row_top=document_top,
                row_height=height,
            )
        )
        rows.append(
            PromptEditorVisibleLayoutRow(
                row_index=row_index,
                source_start=source_start,
                source_end=source_end,
                document_top=document_top,
                viewport_top=row_viewport_top,
                height=height,
                text=source_text[safe_start:safe_end],
                has_inline_object=has_inline_object,
                is_structural=is_structural,
                expected_height=expected_height,
                expected_text_baseline=expected_baseline,
            )
        )
    return tuple(rows)


def _visible_text_fragments(
    *,
    layout_output: object | None,
    metrics: object | None,
    source_text: str,
    viewport_rect: QRect,
    scroll_offset: float,
) -> tuple[PromptEditorVisibleTextFragment, ...]:
    """Return projection text fragments visible in the current viewport."""

    snapshot = getattr(layout_output, "snapshot", None)
    fragments = getattr(snapshot, "text_fragments", ())
    if not isinstance(fragments, Sequence):
        return ()
    viewport_top = float(viewport_rect.top())
    viewport_bottom = float(viewport_rect.bottom())
    visible_fragments: list[PromptEditorVisibleTextFragment] = []
    for fragment_index, fragment in enumerate(fragments):
        rect = getattr(fragment, "rect", None)
        if not isinstance(rect, QRectF):
            continue
        fragment_viewport_top = rect.top() - scroll_offset
        fragment_viewport_bottom = rect.bottom() - scroll_offset
        if fragment_viewport_bottom < viewport_top - 2.0:
            continue
        if fragment_viewport_top > viewport_bottom + 2.0:
            continue
        source_start, source_end = fragment_source_range(
            getattr(fragment, "source_positions", ())
        )
        safe_start = max(0, min(source_start, len(source_text)))
        safe_end = max(safe_start, min(source_end, len(source_text)))
        baseline = _optional_float(getattr(fragment, "baseline", None))
        if baseline is None:
            continue
        expected_height = _optional_float(getattr(metrics, "text_line_height", None))
        expected_baseline = _metrics_text_baseline(
            metrics=metrics,
            row_top=rect.top(),
            row_height=rect.height(),
        )
        visible_fragments.append(
            PromptEditorVisibleTextFragment(
                fragment_index=fragment_index,
                source_start=source_start,
                source_end=source_end,
                document_rect=_qrectf_tuple(rect),
                viewport_rect=(
                    rect.left(),
                    fragment_viewport_top,
                    rect.width(),
                    rect.height(),
                ),
                document_baseline=baseline,
                viewport_baseline=baseline - scroll_offset,
                text=source_text[safe_start:safe_end],
                expected_document_baseline=expected_baseline,
                expected_viewport_baseline=None
                if expected_baseline is None
                else expected_baseline - scroll_offset,
                expected_height=expected_height,
            )
        )
    return tuple(visible_fragments)


def _expected_row_height(
    *,
    line: object,
    metrics: object | None,
    is_structural: bool = False,
) -> float | None:
    """Return the row height expected by the projection metrics contract."""

    text_line_height = _optional_float(getattr(metrics, "text_line_height", None))
    if text_line_height is None:
        return None
    if is_structural:
        return text_line_height
    expected_height = text_line_height
    fragments = getattr(line, "fragments", ())
    if isinstance(fragments, Sequence):
        for fragment in fragments:
            if not isinstance(fragment, PromptProjectionInlineObjectFragment):
                continue
            rect = getattr(fragment, "rect", None)
            if isinstance(rect, QRectF):
                expected_height = max(expected_height, float(rect.height()))
    return expected_height


def _metrics_text_baseline(
    *,
    metrics: object | None,
    row_top: float,
    row_height: float,
) -> float | None:
    """Return the expected baseline from a projection metrics object."""

    baseline_for_row = getattr(metrics, "text_baseline_for_row", None)
    if not callable(baseline_for_row):
        return None
    result = baseline_for_row(row_top=row_top, row_height=row_height)
    return _optional_float(result)


def _projection_metrics_content_height(
    *,
    layout_output: object | None,
    metrics: object | None,
) -> float | None:
    """Return the content height implied by metrics and current layout rows."""

    snapshot = getattr(layout_output, "snapshot", None)
    lines = getattr(snapshot, "lines", ())
    content_height_for_rows = getattr(metrics, "content_height_for_rows", None)
    if not isinstance(lines, Sequence) or not callable(content_height_for_rows):
        return None
    row_heights: list[float] = []
    for line in lines:
        height = _optional_float(getattr(line, "height", None))
        if height is None:
            return None
        row_heights.append(height)
    return _optional_float(content_height_for_rows(tuple(row_heights)))


def _shell_minimum_editor_height(shell_sizing: object | None) -> int | None:
    """Return the shell controller minimum editor height when available."""

    minimum_editor_height = getattr(shell_sizing, "minimum_editor_height", None)
    if not callable(minimum_editor_height):
        return None
    result = minimum_editor_height()
    return result if isinstance(result, int) else None


def _shell_outer_vertical_padding(shell_sizing: object | None) -> int | None:
    """Return shell-owned outer vertical padding from the sizing controller."""

    outer_vertical_padding = getattr(shell_sizing, "_outer_vertical_padding", None)
    if not callable(outer_vertical_padding):
        return None
    result = outer_vertical_padding()
    return result if isinstance(result, int) else None


def _shell_document_vertical_padding(shell_sizing: object | None) -> int | None:
    """Return document vertical padding from the sizing controller."""

    document_vertical_padding = getattr(
        shell_sizing,
        "_document_vertical_padding",
        None,
    )
    if not callable(document_vertical_padding):
        return None
    result = document_vertical_padding()
    return result if isinstance(result, int) else None


def _qrectf_tuple(rect: QRectF) -> tuple[float, float, float, float]:
    """Return a stable tuple for one floating-point Qt rect."""

    return (rect.left(), rect.top(), rect.width(), rect.height())


def _qlinef_tuple(line: QLineF) -> tuple[float, float, float, float]:
    """Return stable endpoints for one floating-point Qt line."""

    return (line.x1(), line.y1(), line.x2(), line.y2())


def _surface_selection(surface: object | None) -> object | None:
    """Return the projection-owned source selection model from the surface."""

    selection = getattr(surface, "_selection", None)
    if not callable(selection):
        return None
    result: object = selection()
    return result


def _layout_selection_rects(
    geometry: object | None,
    selection: object | None,
) -> tuple[QRectF, ...]:
    """Return document-local selection rects from the geometry owner."""

    selection_geometry = getattr(geometry, "selection", None)
    selection_rects = getattr(selection_geometry, "selection_rects", None)
    if not callable(selection_rects):
        return ()
    return _qrectf_sequence(selection_rects(selection))


def _token_id_resolves(
    projection_document: object | None,
    token_id: object,
) -> bool:
    """Return whether an optional caret token id resolves in the projection document."""

    if not isinstance(token_id, str):
        return True
    token_by_id = getattr(projection_document, "token_by_id", None)
    if not callable(token_by_id):
        return False
    return token_by_id(token_id) is not None


def _safeenum_value(value: object) -> str:
    """Return a stable string for enum-like values."""

    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _optional_int(value: object) -> int | None:
    """Return value when it is an int, otherwise None."""

    return value if isinstance(value, int) else None


def _position_inside_any_range(
    position: int | None,
    ranges: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether one caret boundary lies inside hidden source content."""

    return position is not None and any(start < position < end for start, end in ranges)


def _optional_float(value: object) -> float | None:
    """Return value as a float when it is numeric, otherwise None."""

    return float(value) if isinstance(value, int | float) else None
