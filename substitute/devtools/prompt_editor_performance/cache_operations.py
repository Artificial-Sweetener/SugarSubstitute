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

"""Measure prompt-editor paint, diagnostic, and fill-band caches."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import cast

from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    next_layout_revision,
)

from .editing_operations import set_cursor_position, time_key_click
from .event_loop import process_events
from .reorder_measurements import surface_for


def time_projection_paint_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure projection content cache reuse through normal viewport rendering."""

    surface = surface_for(editor)
    timings: list[float] = []
    for _ in range(count):
        image = QImage(
            surface.viewport().size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(0)
        painter = QPainter(image)
        started_at = perf_counter()
        try:
            surface.viewport().render(painter, QPoint(0, 0))
        finally:
            painter.end()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_diagnostic_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure diagnostic fragment cache lookup and incremental preservation."""

    surface = surface_for(editor)
    diagnostic = spelling_diagnostic_for_text(editor.toPlainText())
    surface.set_diagnostics((diagnostic,))
    process_events(app)

    def fragment_reader(
        diagnostic: PromptDiagnostic,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Read retained fragments through the diagnostic cache owner."""

        layout_snapshot = surface._editor_state.layout  # noqa: SLF001
        if layout_snapshot is None:
            raise RuntimeError("Diagnostic cache timing requires a published layout.")
        return surface._diagnostic_layer_owner.fragments(  # noqa: SLF001
            diagnostic,
            geometry=surface._layout.frame.geometry,  # noqa: SLF001
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_identity=layout_snapshot.identity,
        )

    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        fragment_reader(
            diagnostic,
            viewport_rect=QRectF(surface.viewport().rect()),
            scroll_offset=float(surface.verticalScrollBar().value()),
        )
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)

    preserver = cast(
        Callable[..., None],
        surface._diagnostic_layer_owner.preserve_fragment_cache_for_incremental_edit,
    )
    layout_snapshot = surface._editor_state.layout  # noqa: SLF001
    if layout_snapshot is None:
        raise RuntimeError("Diagnostic cache timing requires a published layout.")
    previous_layout_identity = layout_snapshot.identity
    next_layout_identity = PromptLayoutIdentity(
        projection=previous_layout_identity.projection,
        layout_revision=next_layout_revision(previous_layout_identity.layout_revision),
    )
    started_at = perf_counter()
    preserver(
        start=len(editor.toPlainText()),
        end=len(editor.toPlainText()),
        replacement_text="",
        previous_layout_identity=previous_layout_identity,
        next_layout_identity=next_layout_identity,
    )
    process_events(app)
    timings.append((perf_counter() - started_at) * 1000.0)

    set_cursor_position(editor, len(editor.toPlainText()))
    timings.append(time_key_click(app, editor, character="x"))
    return timings


def spelling_diagnostic_for_text(text: str) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic for cache measurement."""

    word = "mispelled"
    source_start = text.find(word)
    if source_start < 0:
        source_start = 0
    source_end = source_start + len(word)
    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.WARNING,
        source_start=source_start,
        source_end=source_end,
        message="Spelling issue",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def time_fill_band_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure source-line chrome fill-band cache lookup and reuse."""

    editor.set_source_line_chrome_enabled(True)
    editor.set_source_line_content_left_inset(32.0)
    process_events(app)
    surface = surface_for(editor)
    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        surface.visible_prompt_fill_band_rects()
        surface.source_line_rects()
        surface.current_source_line_index()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


__all__ = [
    "spelling_diagnostic_for_text",
    "time_diagnostic_cache_operations",
    "time_fill_band_cache_operations",
    "time_projection_paint_cache_operations",
]
