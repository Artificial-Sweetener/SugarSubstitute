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

"""Phase 23 verification tests for prompt reorder performance counters."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt
from PySide6.QtGui import QFont, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "prompt reorder QWidget performance tests require non-xdist execution on Windows",
        allow_module_level=True,
    )
from tests.prompt_projection_test_helpers import surface_for

_REDUCED_MOTION_PROPERTY = "substitute.reduce_motion"


class _EmptyPromptAutocompleteGateway:
    """Return deterministic empty autocomplete rows for reorder tests."""

    @staticmethod
    def search(
        _prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions."""

        _ = limit
        return ()


class _EmptyPromptWildcardCatalogGateway:
    """Return deterministic missing wildcard rows for reorder tests."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return missing wildcard resolution rows."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one reorder performance test."""

    created: list[QWidget] = []
    app = _ensure_qapp()
    previous_override = app.property(_REDUCED_MOTION_PROPERTY)
    app.setProperty(_REDUCED_MOTION_PROPERTY, False)
    try:
        yield created
    finally:
        for widget in reversed(created):
            widget.close()
            widget.deleteLater()
        app.setProperty(_REDUCED_MOTION_PROPERTY, previous_override)
        _process_events(app)


def _ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder performance tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush a few event-loop turns so Qt widget state settles."""

    for _ in range(cycles):
        app.processEvents()


def _wait_for_preview_sync(app: QApplication) -> None:
    """Wait long enough for the coalesced reorder preview timer to run."""

    QTest.qWait(140)
    _process_events(app)


def _create_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int = 420,
    height: int = 220,
) -> PromptEditor:
    """Create one real prompt editor with empty prompt feature gateways."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(width, height)
    layout = QVBoxLayout(host)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=_EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    layout.addWidget(box)
    box.setPlainText(text)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    _process_events(app)
    return box


def _overlay_chip_by_segment_index(overlay: QWidget, segment_index: int) -> QWidget:
    """Return one real-widget overlay chip by segment index."""

    for chip in overlay.findChildren(QWidget, "segmentChip"):
        if chip.property("segmentIndex") == segment_index:
            return chip
    raise AssertionError(f"Missing chip for segment index {segment_index}.")


def _editor_reorder_preview_document(
    box: PromptEditor,
) -> PromptProjectionDocument | None:
    """Return the surface-owned reorder preview projection document."""

    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(box), "_reorder_preview_projection").preview_document,
    )


def _editor_reorder_preview_text(box: PromptEditor) -> str:
    """Return the active reorder preview text without reading source state."""

    preview_document = _editor_reorder_preview_document(box)
    if preview_document is None:
        return ""
    return preview_document.source_text


def _performance_counters(overlay: SegmentReorderOverlay) -> dict[str, object]:
    """Return the current overlay performance counter snapshot."""

    return overlay.reorder_performance_counters()


def _painted_preview_rect(
    overlay: SegmentReorderOverlay,
    segment_index: int,
) -> QRectF:
    """Return the passive view's current painted preview rect for one chip."""

    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    for chip in view.render_state.preview_chips:
        if chip.segment_index != segment_index:
            continue
        if chip.geometry is not None:
            return QRectF(chip.geometry.hotspot_rect)
        assert chip.visual is not None
        return QRectF(chip.visual.hotspot_rect)
    raise AssertionError(f"Missing painted preview chip for segment {segment_index}.")


def _open_reorder_overlay(box: PromptEditor) -> SegmentReorderOverlay:
    """Enter reorder mode and return the real editor-owned overlay."""

    app = _ensure_qapp()
    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    return cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))


def _assert_plain_alt_live_rasters(overlay: SegmentReorderOverlay) -> None:
    """Assert plain Alt reorder chips carry overlay-owned text rasters."""

    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    state = view.render_state
    assert state.preview_active is False
    assert state.live_chips
    assert state.raster_paint_count == len(state.live_chips)
    assert all(chip.raster_entry is not None for chip in state.live_chips)
    assert len(cast(Any, overlay)._live_visual_snapshots_by_index) == len(
        state.live_chips
    )


def _counter_delta(
    before: dict[str, object],
    after: dict[str, object],
    counter_name: str,
) -> int:
    """Return a typed integer counter delta from two counter snapshots."""

    return cast(int, after[counter_name]) - cast(int, before[counter_name])


def _assert_timing_observed(
    counters: dict[str, object],
    counter_name: str,
) -> None:
    """Assert one GUI timing counter captured a real elapsed observation."""

    value = counters[counter_name]
    assert isinstance(value, float)
    assert value > 0.0


def _build_reorder_preview_state(
    text: str,
    *,
    dragged_chip_index: int,
    drop_target: PromptLineDropTarget,
) -> PromptReorderPreviewState:
    """Build one reorder preview state without importing skipped Qt contract tests."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(_EmptyPromptWildcardCatalogGateway())
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
        drop_target=drop_target,
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    preview_render_plan = syntax_service.build_render_plan(
        preview_document_view,
        syntax_profile,
    )
    base_drag_document_view = document_service.build_document_view(
        base_drag_snapshot.text,
    )
    base_drag_render_plan = syntax_service.build_render_plan(
        base_drag_document_view,
        syntax_profile,
    )
    return PromptReorderPreviewState(
        preview_snapshot=PromptReorderProjectionSnapshot(
            document_view=preview_document_view,
            render_plan=preview_render_plan,
            chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
        ),
        base_drag_snapshot=PromptReorderProjectionSnapshot(
            document_view=base_drag_document_view,
            render_plan=base_drag_render_plan,
            chip_rendered_ranges_by_index=base_drag_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=base_drag_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=base_drag_snapshot.gap_ranges_by_index,
        ),
        ordered_chip_indices=tuple(
            document_service.reorder_layout_chip_indices(preview_layout_view),
        ),
        dragged_chip_index=dragged_chip_index,
    )


def test_reorder_pointer_release_does_not_mutate_source_or_undo(
    widgets: list[QWidget],
) -> None:
    """Drag start should build bounded setup state and release should not mutate."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha,beta,")
    cursor = box.textCursor()
    cursor.setPosition(7)
    box.setTextCursor(cursor)
    can_undo_before = box.canUndo()

    overlay = _open_reorder_overlay(box)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    _process_events(app)

    before_drag_start = _performance_counters(overlay)

    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)

    after_drag_start = _performance_counters(overlay)
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "drag_proxy_render_state_rebuild_count",
        )
        == 1
    )
    assert after_drag_start["drag_proxy_render_state_invalidation_count"] == 0
    assert _counter_delta(before_drag_start, after_drag_start, "drag_move_count") == 1
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "pointer_unexpected_work_count",
        )
        == 0
    )
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "projection_snapshot_rebuild_count",
        )
        <= 3
    )
    _assert_timing_observed(after_drag_start, "max_drag_move_ms")
    before_release = after_drag_start

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    assert box.toPlainText() == "alpha,beta,"
    assert box.canUndo() is can_undo_before
    after_release = _performance_counters(overlay)
    assert (
        after_release["drag_proxy_render_state_rebuild_count"]
        == before_release["drag_proxy_render_state_rebuild_count"]
    )
    assert (
        after_release["drag_proxy_render_state_invalidation_count"]
        == before_release["drag_proxy_render_state_invalidation_count"]
    )
    assert (
        _counter_delta(
            before_release,
            after_release,
            "projection_snapshot_rebuild_count",
        )
        <= 1
    )


def test_plain_alt_rebuilds_text_rasters_after_theme_or_font_invalidation(
    widgets: list[QWidget],
) -> None:
    """Plain Alt chips should keep text rasters after Qt theme/font churn."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")

    overlay = _open_reorder_overlay(box)
    QApplication.sendEvent(overlay, QEvent(QEvent.Type.FontChange))
    _process_events(app)

    _assert_plain_alt_live_rasters(overlay)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
    assert getattr(box, "_segment_overlay") is None

    reopened_overlay = _open_reorder_overlay(box)
    _assert_plain_alt_live_rasters(reopened_overlay)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_preview_does_not_mutate_source_until_alt_release(
    widgets: list[QWidget],
) -> None:
    """Keyboard reorder preview should stay display-only before Alt release."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)
    can_undo_before = box.canUndo()

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert box.toPlainText() == "alpha, beta, gamma"
    assert box.canUndo() is can_undo_before

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)

    assert box.toPlainText() == "beta, alpha, gamma"


def test_reorder_keyboard_end_of_line_separator_uses_preceding_chip(
    widgets: list[QWidget],
) -> None:
    """Alt+Arrow at a trailing comma/newline should move the preceding chip."""

    app = _ensure_qapp()
    text = (
        "1girl, (mature female:1.10), floating, black bident, parted lips, "
        "holding double helix spear, see-through silhouette, contrapposto, \n"
    )
    box = _create_prompt_editor(widgets, text=text, width=760, height=260)
    cursor = box.textCursor()
    cursor.setPosition(len(text))
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))

    assert overlay.active_segment_index() == 7
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert overlay.ordered_chip_indices() == [0, 1, 2, 3, 4, 5, 7, 6]
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1
    assert _editor_reorder_preview_text(box) == (
        "1girl, (mature female:1.10), floating, black bident, parted lips, "
        "holding double helix spear, contrapposto, see-through silhouette, "
    )
    assert box.toPlainText() == text

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


@pytest.mark.parametrize(
    "movement_key",
    [Qt.Key.Key_Down, Qt.Key.Key_Right],
)
def test_reorder_keyboard_targets_blank_line_before_next_populated_row(
    widgets: list[QWidget],
    movement_key: Qt.Key,
) -> None:
    """Alt+Arrow should target a prepared blank-line lane before the next chip row."""

    app = _ensure_qapp()
    text = (
        "empty eyes, sharp teeth, halo behind head, too many rabbits,\n\nbacklighting,"
    )
    box = _create_prompt_editor(widgets, text=text, width=520, height=260)
    cursor = box.textCursor()
    cursor.setPosition(text.index("too many rabbits") + 2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    before = _performance_counters(overlay)

    QTest.keyClick(box, movement_key)
    _process_events(app)
    after = _performance_counters(overlay)

    assert overlay.drop_target() == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=0,
    )
    assert _editor_reorder_preview_text(box) == (
        "empty eyes, sharp teeth, halo behind head, \ntoo many rabbits,\nbacklighting, "
    )
    assert box.toPlainText() == text
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_alt_left_builds_keyboard_animation_plan(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Left should animate changed chips from settled keyboard preview geometry."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    presenter = cast(Any, overlay)._animation_presenter
    original_apply_plan = presenter.apply_plan
    recorded_plans: list[Any] = []
    before = _performance_counters(overlay)

    def record_apply_plan(plan: Any, chip_widgets: object) -> None:
        """Record keyboard animation plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, chip_widgets)

    monkeypatch.setattr(presenter, "apply_plan", record_apply_plan)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert box.toPlainText() == "alpha, beta, gamma"
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1
    assert recorded_plans
    assert recorded_plans[-1].reason == "keyboard_target_changed"
    assert recorded_plans[-1].dragged_segment_index == 1
    assert overlay.drop_target() is not None
    assert all(
        target.segment_index != recorded_plans[-1].dragged_segment_index
        for target in recorded_plans[-1].changed_targets
    )
    assert recorded_plans[-1].changed_targets
    assert presenter.is_animating() is True
    assert presenter.paint_rect_overrides()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_animation_first_frame_is_coherent(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Arrow should not publish a frame before the held-chip override exists."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    original_sync = cast(Any, overlay)._sync_reorder_view_state
    animation_frames: list[tuple[dict[int, QRectF], dict[int, QRectF]]] = []

    def record_animation_frame(*, reason: str) -> None:
        """Record frame override ownership while preserving real rendering."""

        if reason == "animation_frame":
            animation_frames.append(
                (
                    cast(Any, overlay)._animation_presenter.paint_rect_overrides(),
                    cast(Any, overlay)._held_chip_presenter.paint_rect_overrides(),
                )
            )
        original_sync(reason=reason)

    monkeypatch.setattr(
        overlay,
        "_sync_reorder_view_state",
        record_animation_frame,
    )

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    assert animation_frames
    first_frame = animation_frames[0]
    assert first_frame[0]
    assert set(first_frame[1]) == {1}

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_suppression_clips_settled_projection(
    widgets: list[QWidget],
) -> None:
    """Alt+Arrow overlay ownership should hide settled projection chip paint."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    surface = surface_for(box)
    visible_region = cast(Any, surface)._preview_visible_region()

    assert cast(Any, surface)._reorder_overlay_suppressed_chip_indices >= frozenset(
        {0, 1, 2}
    )
    assert visible_region is not None
    hidden_region = QRegion(surface.viewport().rect()).subtracted(visible_region)
    assert not hidden_region.isEmpty()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_blank_line_animation_survives_overlay_resize(
    widgets: list[QWidget],
) -> None:
    """Preview-owned overlay resizes should not settle blank-line animations."""

    app = _ensure_qapp()
    text = (
        "empty eyes, sharp teeth, halo behind head, too many rabbits,\n\nbacklighting,"
    )
    box = _create_prompt_editor(widgets, text=text, width=520, height=260)
    cursor = box.textCursor()
    cursor.setPosition(text.index("too many rabbits") + 2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    cast(Any, overlay)._animation_presenter._duration_ms = 1000
    cast(Any, overlay)._held_chip_presenter._duration_ms = 1000

    QTest.keyClick(box, Qt.Key.Key_Down)
    _process_events(app)

    assert overlay.drop_target() == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=0,
    )
    assert (
        cast(Any, overlay)._animation_presenter.paint_rect_overrides()
        or cast(Any, overlay)._held_chip_presenter.paint_rect_overrides()
    )
    before = _performance_counters(overlay)

    overlay.resize(overlay.width() + 1, overlay.height() + 1)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _counter_delta(before, after, "animation_settled_count") == 0
    assert _counter_delta(before, after, "held_animation_settled_count") == 0
    assert (
        cast(Any, overlay)._animation_presenter.paint_rect_overrides()
        or cast(Any, overlay)._held_chip_presenter.paint_rect_overrides()
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_return_from_blank_line_still_animates(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returning to original order should still animate the active preview target."""

    app = _ensure_qapp()
    text = (
        "empty eyes, sharp teeth, halo behind head, too many rabbits,\n\nbacklighting,"
    )
    box = _create_prompt_editor(widgets, text=text, width=520, height=260)
    cursor = box.textCursor()
    cursor.setPosition(text.index("too many rabbits") + 2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    cast(Any, overlay)._animation_presenter._duration_ms = 1000
    cast(Any, overlay)._held_chip_presenter._duration_ms = 1000

    QTest.keyClick(box, Qt.Key.Key_Down)
    _process_events(app)

    assert overlay.has_reordered() is True
    assert overlay.drop_target() == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=0,
    )
    monkeypatch.setattr(overlay, "has_reordered", lambda: False)
    before_return = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Up)
    _process_events(app)
    after_return = _performance_counters(overlay)

    assert overlay.has_reordered() is False
    assert (
        _counter_delta(before_return, after_return, "animation_plan_build_count") == 1
    )
    assert (
        _counter_delta(before_return, after_return, "animation_plan_applied_count") == 1
    )
    assert (
        cast(Any, overlay)._animation_presenter.paint_rect_overrides()
        or cast(Any, overlay)._held_chip_presenter.paint_rect_overrides()
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_alt_right_captures_commit_snapshot_before_animation(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Right should publish commit state before presenter animation runs."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    presenter = cast(Any, overlay)._animation_presenter
    original_apply_plan = presenter.apply_plan
    observed_orders: list[tuple[int, ...] | None] = []

    def record_snapshot_before_animation(plan: Any, chip_widgets: object) -> None:
        """Record controller commit state when the display animation is applied."""

        _ = plan
        reorder_controller = cast(Any, box)._interaction_controller._reorder
        latest_snapshot = reorder_controller.latest_commit_snapshot
        observed_orders.append(
            None if latest_snapshot is None else latest_snapshot.ordered_chip_indices
        )
        original_apply_plan(plan, chip_widgets)

    monkeypatch.setattr(presenter, "apply_plan", record_snapshot_before_animation)

    QTest.keyClick(box, Qt.Key.Key_Right)
    _process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert observed_orders == [(1, 0, 2)]
    assert box.toPlainText() == "alpha, beta, gamma"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_vertical_keyboard_move_animates_to_lane_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Up should animate visible chips to projection-owned target lane rects."""

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        width=380,
        height=240,
        text="alpha,\n\n\ngamma, beta",
    )
    cursor = box.textCursor()
    cursor.setPosition(len("alpha,\n\n\ngamma, beta"))
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    presenter = cast(Any, overlay)._animation_presenter
    original_apply_plan = presenter.apply_plan
    recorded_plans: list[Any] = []

    def record_apply_plan(plan: Any, chip_widgets: object) -> None:
        """Record vertical keyboard plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, chip_widgets)

    monkeypatch.setattr(presenter, "apply_plan", record_apply_plan)
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Up)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "alpha,\n\nbeta,\ngamma"
    assert recorded_plans
    assert recorded_plans[-1].dragged_segment_index == 2
    assert recorded_plans[-1].changed_targets == ()
    assert _counter_delta(before, after, "held_animation_started_count") == 1
    held_overrides = cast(Any, overlay)._held_chip_presenter.paint_rect_overrides()
    assert set(held_overrides) == {2}
    target_geometry = cast(Any, overlay)._preview_chip_geometry_for_segment(2)
    assert target_geometry is not None
    assert held_overrides[2] != QRectF(target_geometry.hotspot_rect)
    for target in recorded_plans[-1].changed_targets:
        preview_geometry = cast(Any, overlay)._preview_chip_geometry_for_segment(
            target.segment_index
        )
        assert preview_geometry is not None
        preview_rect = QRectF(preview_geometry.hotspot_rect)
        assert target.target_rect.left() == preview_rect.left()
        assert target.target_rect.top() == preview_rect.top()
        assert target.target_rect.width() == preview_rect.width()
        assert target.target_rect.height() == preview_rect.height()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_boundary_noop_builds_no_animation_plan(
    widgets: list[QWidget],
) -> None:
    """Boundary Alt+Arrow no-ops should not advance animation planning."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "alpha, beta, gamma"
    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert _counter_delta(before, after, "animation_plan_build_count") == 0
    assert _counter_delta(before, after, "animation_plan_applied_count") == 0

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_animation_frame_syncs_suppression_without_raster_churn(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Animation frames should own suppression without rebuilding prepared rasters."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    suppression_publications: list[frozenset[int]] = []
    original_suppression = box.set_reorder_overlay_suppressed_chip_indices

    def count_suppression(indices: frozenset[int]) -> None:
        """Count suppression publications while preserving real behavior."""

        suppression_publications.append(indices)
        original_suppression(indices)

    monkeypatch.setattr(
        box,
        "set_reorder_overlay_suppressed_chip_indices",
        count_suppression,
    )

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    cast(Any, overlay)._last_suppressed_chip_indices = frozenset()
    original_suppression(frozenset())
    before = _performance_counters(overlay)
    before_suppression_call_count = len(suppression_publications)
    cast(Any, overlay)._sync_reorder_animation_frame()
    after = _performance_counters(overlay)
    after_suppression_call_count = len(suppression_publications)
    cast(Any, overlay)._sync_reorder_animation_frame()

    assert after["raster_build_count"] == before["raster_build_count"]
    assert after_suppression_call_count == before_suppression_call_count + 1
    assert suppression_publications[-1] >= frozenset({0, 1, 2})
    assert len(suppression_publications) == after_suppression_call_count

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_animation_frame_suppresses_vector_fallback_preview_chips(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlay-painted vector fallback chips should hide settled projection paint."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    suppression_publications: list[frozenset[int]] = []
    original_suppression = box.set_reorder_overlay_suppressed_chip_indices

    def count_suppression(indices: frozenset[int]) -> None:
        """Count suppression publications while preserving real behavior."""

        suppression_publications.append(indices)
        original_suppression(indices)

    monkeypatch.setattr(
        box,
        "set_reorder_overlay_suppressed_chip_indices",
        count_suppression,
    )

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    monkeypatch.setattr(
        cast(Any, overlay)._raster_cache,
        "entries_for_snapshots",
        lambda **_kwargs: {},
    )

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    cast(Any, overlay)._last_suppressed_chip_indices = frozenset()
    original_suppression(frozenset())
    cast(Any, overlay)._sync_reorder_animation_frame()

    assert suppression_publications[-1] >= frozenset({0, 1, 2})
    assert surface_for(box)._reorder_overlay_suppressed_chip_indices >= frozenset(  # noqa: SLF001
        {0, 1, 2}
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_unchanged_target_pointer_move_preserves_hot_path_counters(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged-target pointer moves prove the cheap path with counters.

    GUI timing budgets are intentionally observed through `max_drag_move_ms`;
    deterministic CI assertions use owner counters because Qt/offscreen timing
    varies by host load.
    """

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,",
    )
    overlay = _open_reorder_overlay(box)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)

    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)
    before_pointer_state = overlay.pointer_reorder_state()
    before_animation_state = overlay.animation_generation_state()
    telemetry_type = type(cast(Any, overlay)._telemetry)
    tracker = cast(Any, overlay)._drop_target_tracker
    original_resolve = tracker.resolve
    tracker_resolve_count = 0

    with monkeypatch.context() as telemetry_patch:
        assert not hasattr(
            cast(Any, overlay)._geometry,
            "resolve_drop_target_for_drag_rect",
        )

        def reject_heavy_context(
            *_args: object,
            **_kwargs: object,
        ) -> dict[str, object]:
            """Fail if unchanged-target movement builds structural diagnostics."""

            raise AssertionError("unchanged target built heavy telemetry context")

        def record_tracker_resolve(
            resolver_input: Any,
            *,
            gesture_id: int | None = None,
            event_id: int | None = None,
        ) -> Any:
            """Record that pointer movement used the projection drop-target tracker."""

            nonlocal tracker_resolve_count
            tracker_resolve_count += 1
            return original_resolve(
                resolver_input,
                gesture_id=gesture_id,
                event_id=event_id,
            )

        telemetry_patch.setattr(tracker, "resolve", record_tracker_resolve)
        for helper_name in (
            "style_context",
            "visual_context",
            "held_shadow_context",
            "target_visual_context",
            "visual_delta_context",
        ):
            telemetry_patch.setattr(
                telemetry_type,
                helper_name,
                reject_heavy_context,
            )

        QTest.mouseMove(
            second_chip,
            second_chip.mapFromGlobal(target_global + QPoint(1, 0)),
            10,
        )
        _process_events(app)

        after = _performance_counters(overlay)
        after_pointer_state = overlay.pointer_reorder_state()
        after_animation_state = overlay.animation_generation_state()

        assert _counter_delta(before, after, "drag_move_count") == 1
        _assert_timing_observed(after, "max_drag_move_ms")
        assert tracker_resolve_count == 1
        assert _counter_delta(before, after, "drop_target_no_change_count") == 1
        assert (
            after_pointer_state.active_drop_target
            == before_pointer_state.active_drop_target
        )
        assert (
            after_animation_state.generation_id == before_animation_state.generation_id
        )
        for counter_name in (
            "projection_snapshot_rebuild_count",
            "preview_scheduler_request_count",
            "preview_scheduler_run_count",
            "preview_geometry_full_count",
            "drag_proxy_render_state_rebuild_count",
            "drag_proxy_render_state_invalidation_count",
            "autoscroll_invalidation_count",
            "animation_plan_build_count",
            "animation_plan_applied_count",
            "pointer_preview_rebuild_count",
            "pointer_full_refresh_count",
            "pointer_base_cache_miss_count",
            "pointer_paint_request_count",
            "pointer_unexpected_work_count",
        ):
            assert after[counter_name] == before[counter_name]

        def sample_target_changes_only(
            _self: object,
            *,
            move_count: int,
            target_changed: bool,
        ) -> bool:
            """Force the unchanged-target path to behave like an unsampled move."""

            _ = move_count
            return target_changed

        def reject_unsampled_timing(
            _self: object,
            event: str,
            *,
            started_at: float,
            **_context: object,
        ) -> float:
            """Fail if unchanged-target movement emits sampled timing telemetry."""

            _ = started_at
            raise AssertionError(f"unchanged target emitted timing telemetry: {event}")

        telemetry_patch.setattr(
            telemetry_type,
            "should_log_pointer_event",
            sample_target_changes_only,
        )
        telemetry_patch.setattr(telemetry_type, "log_timing", reject_unsampled_timing)

        QTest.mouseMove(
            second_chip,
            second_chip.mapFromGlobal(target_global + QPoint(2, 0)),
            10,
        )
        _process_events(app)

        unsampled_after = _performance_counters(overlay)
        assert _counter_delta(after, unsampled_after, "drag_move_count") == 1
        assert (
            _counter_delta(after, unsampled_after, "drop_target_no_change_count") == 1
        )

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)


def test_reorder_target_change_pointer_move_records_rebuild_path_counters(
    widgets: list[QWidget],
) -> None:
    """Changed-target moves should schedule preview work without mutating source."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,gamma,",
    )
    overlay = _open_reorder_overlay(editor)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    third_chip = _overlay_chip_by_segment_index(overlay, 2)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )
    next_target_global = third_chip.mapToGlobal(
        QPoint(third_chip.width() - 4, max(4, third_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)
    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)

    QTest.mouseMove(
        second_chip,
        second_chip.mapFromGlobal(next_target_global),
        10,
    )
    _process_events(app)

    after = _performance_counters(overlay)
    pointer_state = overlay.pointer_reorder_state()
    preview_state = overlay.preview_target_state()
    geometry_state = overlay.geometry_generation_state()

    assert editor.toPlainText() == "alpha,beta,gamma,"
    assert _counter_delta(before, after, "drag_move_count") == 1
    assert _counter_delta(before, after, "drop_target_changed_count") == 1
    assert _counter_delta(before, after, "preview_scheduler_request_count") == 1
    assert _counter_delta(before, after, "preview_scheduler_run_count") == 0
    assert _counter_delta(before, after, "preview_geometry_full_count") == 0
    assert _counter_delta(before, after, "projection_snapshot_rebuild_count") == 0
    assert _counter_delta(before, after, "animation_plan_build_count") == 0
    assert _counter_delta(before, after, "pointer_unexpected_work_count") == 0
    _assert_timing_observed(after, "max_drag_move_ms")
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_rebuild_count",
        )
        == 0
    )
    assert pointer_state.active_drop_target == preview_state.active_target
    assert geometry_state.prepared_geometry_identity.active_target == (
        pointer_state.active_drop_target
    )

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)


def test_reorder_target_change_paints_displaced_neighbors_after_preview_sync(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointer target changes should visibly displace neighbors in the paint state."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("prompt reorder preview sync can abort under Windows xdist")

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,gamma,",
    )
    overlay = _open_reorder_overlay(editor)
    presenter = cast(Any, overlay)._animation_presenter
    presenter._duration_ms = 1000
    recorded_plans: list[Any] = []
    original_apply_plan = presenter.apply_plan

    def record_apply_plan(plan: Any, chip_widgets: object) -> None:
        """Record pointer displacement plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, chip_widgets)

    monkeypatch.setattr(presenter, "apply_plan", record_apply_plan)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    first_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    _process_events(app)

    before = _performance_counters(overlay)
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(first_target), 10)
    immediate_after = _performance_counters(overlay)

    assert editor.toPlainText() == "alpha,beta,gamma,"
    assert _counter_delta(before, immediate_after, "drag_move_count") == 1
    assert _counter_delta(before, immediate_after, "drop_target_changed_count") == 1

    _wait_for_preview_sync(app)
    after_sync = _performance_counters(overlay)

    assert _counter_delta(before, after_sync, "animation_plan_build_count") >= 1
    assert _counter_delta(before, after_sync, "animation_plan_applied_count") >= 1
    assert overlay.preview_rect_for_segment(1) is not None
    assert recorded_plans
    displaced_target = cast(
        PromptReorderAnimationTarget,
        recorded_plans[-1].changed_targets[0],
    )
    painted_rect = _painted_preview_rect(overlay, displaced_target.segment_index)
    assert painted_rect != displaced_target.target_rect
    start_left = displaced_target.start_rect.left()
    painted_left = painted_rect.left()
    target_left = displaced_target.target_rect.left()
    assert start_left <= painted_left
    assert painted_left < target_left
    assert overlay.preview_rect_for_segment(displaced_target.segment_index) == (
        displaced_target.target_rect.toAlignedRect()
    )

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(first_target),
        delay=10,
    )
    _process_events(app)


def test_reorder_rapid_target_changes_coalesce_one_preview_sync(
    widgets: list[QWidget],
) -> None:
    """Changed-target work should coalesce to one plan per event-loop turn."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=460,
        height=220,
        text="alpha,beta,gamma,delta,",
    )
    overlay = _open_reorder_overlay(editor)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    third_chip = _overlay_chip_by_segment_index(overlay, 2)
    first_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )
    third_target = third_chip.mapToGlobal(
        QPoint(third_chip.width() - 4, max(4, third_chip.rect().center().y()))
    )
    second_target = second_chip.mapToGlobal(
        QPoint(second_chip.width() - 4, max(4, second_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(first_target), 10)
    _process_events(app)

    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(second_target), 10)
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(third_target), 10)
    immediate_after = _performance_counters(overlay)

    assert _counter_delta(before, immediate_after, "drop_target_changed_count") == 2
    assert (
        _counter_delta(before, immediate_after, "preview_scheduler_request_count") == 2
    )
    assert _counter_delta(before, immediate_after, "preview_scheduler_run_count") == 0
    assert _counter_delta(before, immediate_after, "preview_geometry_full_count") == 0
    assert (
        _counter_delta(before, immediate_after, "projection_snapshot_rebuild_count")
        == 0
    )
    assert _counter_delta(before, immediate_after, "animation_plan_build_count") == 0
    assert _counter_delta(before, immediate_after, "pointer_unexpected_work_count") == 0

    _wait_for_preview_sync(app)
    after_sync = _performance_counters(overlay)

    assert _counter_delta(before, after_sync, "preview_scheduler_run_count") == 1
    assert _counter_delta(before, after_sync, "preview_geometry_full_count") == 1
    assert _counter_delta(before, after_sync, "animation_plan_build_count") == 1
    assert _counter_delta(before, after_sync, "animation_plan_applied_count") == 1
    _assert_timing_observed(after_sync, "max_drag_move_ms")
    _assert_timing_observed(after_sync, "max_preview_sync_ms")
    assert editor.toPlainText() == "alpha,beta,gamma,delta,"
    assert overlay.preview_rect_for_segment(1) is not None

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(third_target),
        delay=10,
    )
    _process_events(app)


def test_reorder_wrapped_drag_preview_builds_wrapped_animation_plan(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped target changes should animate toward settled wrapped rects."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=170,
        height=180,
        text="alpha, beta, gamma, delta",
    )
    overlay = _open_reorder_overlay(editor)
    dragged_chip = _overlay_chip_by_segment_index(overlay, 3)
    target_chip = _overlay_chip_by_segment_index(overlay, 1)
    recorded_plans: list[Any] = []
    presenter = cast(Any, overlay)._animation_presenter
    original_apply_plan = presenter.apply_plan

    def record_apply_plan(plan: Any, chip_widgets: object) -> None:
        """Record integration plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, chip_widgets)

    monkeypatch.setattr(presenter, "apply_plan", record_apply_plan)
    target_global = target_chip.mapToGlobal(
        QPoint(4, max(4, target_chip.rect().center().y()))
    )

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(target_global), 10)
    immediate_after = _performance_counters(overlay)

    assert immediate_after["animation_plan_build_count"] == 0

    _wait_for_preview_sync(app)
    after_sync = _performance_counters(overlay)

    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert _editor_reorder_preview_text(editor) == "alpha, delta, beta, gamma"
    assert after_sync["animation_plan_build_count"] == 1
    assert recorded_plans
    wrapped_targets = [
        target
        for target in recorded_plans[-1].changed_targets
        if target.target_rect.top() > target.start_rect.top()
    ]
    assert wrapped_targets
    for target in wrapped_targets:
        preview_geometry = cast(Any, overlay)._preview_chip_geometry_for_segment(
            target.segment_index
        )
        assert preview_geometry is not None
        preview_rect = QRectF(preview_geometry.hotspot_rect)
        assert target.target_rect.left() == preview_rect.left()
        assert target.target_rect.top() == preview_rect.top()
        assert target.target_rect.width() == preview_rect.width()

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    _process_events(app)

    assert editor.toPlainText() == "alpha, delta, beta, gamma"


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
    presenter = cast(Any, overlay)._animation_presenter
    applied_generations: list[int] = []

    def no_op_apply_plan(plan: Any, _chip_widgets: object) -> None:
        """Simulate an animation presenter that cannot run animations."""

        applied_generations.append(plan.generation)

    monkeypatch.setattr(presenter, "apply_plan", no_op_apply_plan)
    target_global = target_chip.mapToGlobal(
        QPoint(4, max(4, target_chip.rect().center().y()))
    )

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(target_global), 10)
    _wait_for_preview_sync(app)

    assert applied_generations
    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert _editor_reorder_preview_text(editor) == "alpha, delta, beta, gamma"
    assert overlay.preview_rect_for_segment(1) is not None

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    _process_events(app)

    assert editor.toPlainText() == "alpha, delta, beta, gamma"


def test_reorder_drag_proxy_font_invalidation_rebuilds_before_visible_use(
    widgets: list[QWidget],
) -> None:
    """Explicit proxy invalidation should rebuild once, then reuse while moving."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,gamma,",
    )
    overlay = _open_reorder_overlay(editor)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)
    before = _performance_counters(overlay)

    changed_font = QFont(editor.viewport().font())
    changed_font.setPointSize(changed_font.pointSize() + 2)
    editor.viewport().setFont(changed_font)
    app.sendEvent(overlay, QEvent(QEvent.Type.FontChange))
    _process_events(app)

    after = _performance_counters(overlay)
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_invalidation_count",
        )
        == 1
    )
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_rebuild_count",
        )
        == 1
    )

    QTest.mouseMove(
        second_chip,
        second_chip.mapFromGlobal(target_global + QPoint(3, 0)),
        10,
    )
    _process_events(app)
    after_move = _performance_counters(overlay)
    assert (
        _counter_delta(
            after,
            after_move,
            "drag_proxy_render_state_rebuild_count",
        )
        == 0
    )
    assert _counter_delta(after, after_move, "projection_snapshot_rebuild_count") == 0
    assert _counter_delta(after, after_move, "animation_plan_build_count") == 0
    _assert_timing_observed(after_move, "max_drag_move_ms")

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)


def test_reorder_autoscroll_steps_do_not_rebuild_surface_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Autoscroll ticks should coalesce geometry/projection work behind counters."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=240,
        height=120,
        text=", ".join(
            f"segment {index} with a longer description" for index in range(20)
        ),
    )
    overlay = _open_reorder_overlay(editor)
    scrollbar = editor.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(0)
    _process_events(app)

    dragged_chip = _overlay_chip_by_segment_index(overlay, 0)
    edge_global = overlay.mapToGlobal(
        QPoint(overlay.width() // 2, overlay.height() - 2)
    )
    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(edge_global), 10)
    _process_events(app)

    before = _performance_counters(overlay)

    before_geometry_generation = overlay.geometry_generation_state().generation_id
    tracker = cast(Any, overlay)._drop_target_tracker
    original_resolve = tracker.resolve
    resolved_geometry_generations: list[int] = []

    def record_resolve_generation(
        resolver_input: Any,
        *,
        gesture_id: int | None = None,
        event_id: int | None = None,
    ) -> Any:
        """Record the geometry generation used for post-scroll target resolution."""

        resolved_geometry_generations.append(resolver_input.geometry_generation_id)
        return original_resolve(
            resolver_input,
            gesture_id=gesture_id,
            event_id=event_id,
        )

    monkeypatch.setattr(tracker, "resolve", record_resolve_generation)
    cast(Any, overlay)._autoscroll.apply_step_for_tests()
    cast(Any, overlay)._autoscroll.apply_step_for_tests()

    after_ticks_before_flush = _performance_counters(overlay)

    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "autoscroll_invalidation_count",
        )
        >= 2
    )
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "autoscroll_coalesced_count",
        )
        >= 1
    )
    assert after_ticks_before_flush["autoscroll_pending_invalidation_count"] == 1
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "projection_snapshot_rebuild_count",
        )
        == 0
    )

    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "animation_plan_build_count",
        )
        == 0
    )
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "preview_scheduler_request_count",
        )
        >= 1
    )

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(edge_global),
        delay=10,
    )
    _process_events(app)

    after_release = _performance_counters(overlay)

    invalidation_delta = _counter_delta(
        before,
        after_release,
        "autoscroll_invalidation_count",
    )
    flush_delta = _counter_delta(before, after_release, "autoscroll_flush_count")
    projection_rebuild_delta = _counter_delta(
        before,
        after_release,
        "projection_snapshot_rebuild_count",
    )
    assert invalidation_delta >= 2
    assert flush_delta == 1
    assert projection_rebuild_delta < invalidation_delta
    _assert_timing_observed(after_release, "max_drag_move_ms")
    assert after_release["autoscroll_pending_invalidation_count"] == 0
    assert (
        overlay.geometry_generation_state().generation_id > before_geometry_generation
    )
    assert resolved_geometry_generations
    assert resolved_geometry_generations[-1] > before_geometry_generation


def test_reorder_surface_projection_rebuild_counter_tracks_cache_misses(
    widgets: list[QWidget],
) -> None:
    """Projection counters should increment when preview snapshots are rebuilt."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.reset_reorder_geometry_cache_counters()
    before = surface.reorder_geometry_cache_counters()

    surface.set_reorder_preview_state(preview_state)
    _process_events(app)

    after = surface.reorder_geometry_cache_counters()

    assert _counter_delta(before, after, "preview_projection_cache_miss_count") == 1
    assert _counter_delta(before, after, "projection_snapshot_rebuild_count") == 2


def test_reorder_surface_preview_projection_cache_hit_avoids_rebuild(
    widgets: list[QWidget],
) -> None:
    """Preview projection cache hits should not rebuild projection snapshots."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    _process_events(app)

    before_hit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    _process_events(app)
    after_hit = surface.reorder_geometry_cache_counters()

    assert (
        _counter_delta(
            before_hit, after_hit, "preview_projection_active_cache_hit_count"
        )
        == 1
    )
    assert (
        _counter_delta(before_hit, after_hit, "projection_snapshot_rebuild_count") == 0
    )
    assert (
        _counter_delta(before_hit, after_hit, "preview_projection_cache_miss_count")
        == 0
    )
