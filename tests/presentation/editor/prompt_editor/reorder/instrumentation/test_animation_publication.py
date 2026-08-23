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

"""Verify prompt reorder animation publication instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)

from tests.support.prompt_editor.projection_engine_support import surface_for

from .support import (
    _create_prompt_editor,
    _editor_reorder_preview_text,
    _ensure_qapp,
    _flush_preview_sync,
    _open_reorder_overlay,
    _overlay_chip_by_segment_index,
    _performance_counters,
    _process_events,
)


def test_reorder_animation_frame_syncs_suppression_without_raster_churn(
    widgets: list[QWidget],
) -> None:
    """Animation frames should own suppression without rebuilding prepared rasters."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    surface = surface_for(box)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    current_surface_state = surface._reorder_surface_visual_state.state  # noqa: SLF001
    box.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode=current_surface_state.mode,
            chips=current_surface_state.chips,
            suppression_snapshots_by_index={},
        )
    )
    before = _performance_counters(overlay)
    before_surface_revision = (
        surface._reorder_surface_visual_state.state.revision  # noqa: SLF001
    )
    cast(Any, overlay)._handle_reorder_animation_frame()
    after = _performance_counters(overlay)
    after_first_surface_revision = (
        surface._reorder_surface_visual_state.state.revision  # noqa: SLF001
    )
    cast(Any, overlay)._handle_reorder_animation_frame()
    after_second_surface_revision = (
        surface._reorder_surface_visual_state.state.revision  # noqa: SLF001
    )

    assert after["raster_build_count"] == before["raster_build_count"]
    assert after_first_surface_revision == before_surface_revision + 1
    assert set(
        surface._reorder_surface_visual_state.state.suppression_snapshots_by_index  # noqa: SLF001
    ) == {0, 1}
    assert after_second_surface_revision == after_first_surface_revision

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_animation_frame_keeps_surface_text_for_chrome_only_preview_chips(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chrome-only overlay chips should leave surface projection text visible."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    monkeypatch.setattr(
        cast(Any, overlay)._raster_publication_owner,
        "entries_for",
        lambda _lane, **_kwargs: {},
    )

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    cast(Any, overlay)._preview_paint_snapshots.clear()
    surface = surface_for(box)
    current_surface_state = surface._reorder_surface_visual_state.state  # noqa: SLF001
    box.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode=current_surface_state.mode,
            chips=current_surface_state.chips,
            suppression_snapshots_by_index={},
        )
    )
    cast(Any, overlay)._handle_reorder_animation_frame()

    assert (
        surface._reorder_surface_visual_state.state.suppression_snapshots_by_index  # noqa: SLF001
        == {}
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_animation_fallback_keeps_final_preview_correct(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Animation presentation may no-op while settled preview placement remains correct."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=220,
        height=180,
        text="alpha, beta, gamma, delta",
    )
    overlay = _open_reorder_overlay(editor)
    dragged_chip = _overlay_chip_by_segment_index(overlay, 3)
    target_chip = _overlay_chip_by_segment_index(overlay, 1)
    animation_owner = cast(Any, overlay)._animation_presentation
    applied_generations: list[int] = []

    def no_op_apply_plan(plan: Any, **_context: Any) -> None:
        """Simulate an animation presenter that cannot run animations."""

        applied_generations.append(plan.generation)

    monkeypatch.setattr(animation_owner, "apply_plan", no_op_apply_plan)
    target_global = target_chip.leading_global_point()

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(target_global), 10)
    _flush_preview_sync(editor)

    assert applied_generations
    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert _editor_reorder_preview_text(editor) == "alpha, delta, beta, gamma"
    assert overlay.preview_rect_for_segment(1) is not None

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    _process_events(app)

    assert editor.toPlainText() == "alpha, delta, beta, gamma"
