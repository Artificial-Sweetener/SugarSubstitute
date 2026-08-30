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

"""Test real-editor pointer reorder commits and preview behavior."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway as _StaticPromptAutocompleteGateway,
    create_prompt_editor,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.reorder_pointer_support import (
    PromptReorderPointerTarget,
    drag_prompt_reorder_target_to_global,
    prompt_reorder_pointer_target,
    prompt_reorder_pointer_targets,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
)


def _overlay_pointer_regions(overlay: QWidget) -> list[PromptReorderPointerTarget]:
    """Return visible logical reorder targets in rendered order."""

    return prompt_reorder_pointer_targets(overlay)


def _overlay_preview_segment_indices(overlay: QWidget) -> list[int]:
    """Return visible reorder preview indices in render order."""

    return cast(SegmentReorderOverlay, overlay).preview_chip_indices()


def _overlay_blank_line_target_visuals(overlay: QWidget) -> tuple[object, ...]:
    """Return the current virtual blank-line target visuals for the reorder overlay."""

    visuals = cast(Any, overlay)._geometry.state.drop_target_visuals
    return tuple(
        visual
        for visual in cast(tuple[object, ...], visuals)
        if isinstance(cast(Any, visual).target, PromptGapBlankLineDropTarget)
    )


def _editor_reorder_preview_document(
    box: PromptEditor,
) -> PromptProjectionDocument | None:
    """Return the surface-owned preview document active during reorder mode."""

    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(box), "_reorder_preview_projection").preview_document,
    )


def _editor_reorder_preview_text(box: PromptEditor) -> str:
    """Return the surface-owned preview text active during reorder mode."""

    preview_document = _editor_reorder_preview_document(box)
    if preview_document is None:
        return ""
    return preview_document.source_text


def _flush_reorder_preview(box: PromptEditor) -> None:
    """Synchronize the owner-published reorder preview for a direct assertion."""

    interaction = cast(Any, getattr(box, "_interaction_controller"))
    publication = interaction._reorder._overlay_session._preview_publication
    publication.flush(reason="test_reorder_preview", forced=True)
    box.flush_pending_projection_update(reason="test_reorder_preview")


def _overlay_chip_by_segment_index(
    overlay: QWidget, segment_index: int
) -> PromptReorderPointerTarget:
    """Return one logical reorder target by its stable segment index."""

    return prompt_reorder_pointer_target(overlay, segment_index)


def _overlay_drag_proxy(overlay: QWidget) -> QWidget:
    """Return the floating drag proxy widget used during segment dragging."""

    return cast(SegmentReorderOverlay, overlay).drag_proxy_widget()


def _drag_reorder_chip_to_global(
    chip: PromptReorderPointerTarget,
    *,
    global_target: QPoint,
) -> None:
    """Drag one reorder hotspot to the supplied global position."""

    drag_prompt_reorder_target_to_global(chip, global_target=global_target)


def test_prompt_editor_real_widget_retains_focus_during_alt_reorder_drag(
    widgets: list[QWidget],
) -> None:
    """Alt reorder gestures should keep the host prompt editor focused throughout."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    assert box.hasFocus() is True

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None
    assert box.hasFocus() is True

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    drag_target = first_chip.leading_global_point()
    second_chip_target = second_chip.mapFromGlobal(drag_target)

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    process_events(app)

    assert box.hasFocus() is True

    QTest.mouseMove(second_chip.overlay, second_chip_target, 10)
    process_events(app)

    assert box.hasFocus() is True

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip_target,
        delay=10,
    )
    process_events(app)

    assert box.hasFocus() is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.hasFocus() is True


def test_prompt_editor_real_widget_commits_actual_reorder_on_alt_release(
    widgets: list[QWidget],
) -> None:
    """Dragging chips in reorder mode should commit the new order through the editor path."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    cursor = box.textCursor()
    cursor.setPosition(7, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None
    assert _editor_reorder_preview_document(box) is None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    assert first_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert second_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.leading_global_point(),
    )
    process_events(app)
    _flush_reorder_preview(box)

    assert second_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert _editor_reorder_preview_document(box) is not None
    assert _editor_reorder_preview_text(box) == "beta, alpha,"
    ordered_segment_indices = cast(Any, overlay).ordered_chip_indices()
    preview_segment_indices = _overlay_preview_segment_indices(overlay)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert ordered_segment_indices == [1, 0]
    assert preview_segment_indices == [1, 0]
    assert box.toPlainText() == "beta, alpha,"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 1
    assert _editor_reorder_preview_document(box) is None
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_accumulates_multiple_reorder_drags_before_alt_release(
    widgets: list[QWidget],
) -> None:
    """Multiple drags in one Alt session should build on the current session order."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(len(box.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    alpha_chip = _overlay_chip_by_segment_index(overlay, 0)
    beta_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        beta_chip,
        global_target=alpha_chip.leading_global_point(),
    )
    process_events(app)
    _flush_reorder_preview(box)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"

    beta_chip = _overlay_chip_by_segment_index(overlay, 1)
    gamma_chip = _overlay_chip_by_segment_index(overlay, 2)
    _drag_reorder_chip_to_global(
        gamma_chip,
        global_target=beta_chip.leading_global_point(),
    )
    process_events(app)
    _flush_reorder_preview(box)

    assert _editor_reorder_preview_text(box) == "gamma, beta, alpha"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "gamma, beta, alpha"
    assert _editor_reorder_preview_document(box) is None
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_keeps_emphasis_rendering_during_reorder_drag(
    widgets: list[QWidget],
) -> None:
    """Dragging an emphasized segment should keep rich emphasis formatting in the preview."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("(1girl:0.05), solo")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    emphasized_chip = _overlay_chip_by_segment_index(overlay, 0)
    solo_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        emphasized_chip,
        global_target=overlay.mapToGlobal(
            QPoint(overlay.width() - 8, solo_chip.rect().center().y())
        ),
    )
    process_events(app)
    _flush_reorder_preview(box)

    preview_text = _editor_reorder_preview_text(box)
    preview_projection_document = _editor_reorder_preview_document(box)
    drag_proxy_projection_document = cast(
        Any, _overlay_drag_proxy(overlay)
    ).projection_document()

    assert preview_text == "solo, (1girl:0.05)"
    assert preview_projection_document is not None
    assert drag_proxy_projection_document is not None
    assert preview_projection_document.projection_text.count("\ufffc") == 2
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in preview_projection_document.tokens
    )
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in drag_proxy_projection_document.tokens
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)


def test_prompt_editor_real_widget_reorder_commit_round_trips_through_editor_undo_stack(
    widgets: list[QWidget],
) -> None:
    """Committed segment reorders should behave like one undoable text edit."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.leading_global_point(),
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha,"

    box.undo()
    process_events(app)

    assert box.toPlainText() == "alpha,beta,"

    box.redo()
    process_events(app)

    assert box.toPlainText() == "beta, alpha,"


def test_prompt_editor_real_widget_reorder_commit_preserves_line_break_slot_formatting(
    widgets: list[QWidget],
) -> None:
    """Dragging through reorder mode should preserve newline separators on commit."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,\nbeta, gamma")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.leading_global_point(),
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha,\ngamma"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_can_drop_tag_onto_specific_blank_line(
    widgets: list[QWidget],
) -> None:
    """Dragging into a multiline gap should commit the segment onto the chosen blank line."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 320)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText(
        "1girl, detailed eyes, solo, portrait, looking at viewer,\n\n\n\n\n"
        "soft lighting, pastel colors, clean lineart, highres"
    )
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    soft_lighting_chip = _overlay_chip_by_segment_index(overlay, 5)
    solo_chip = _overlay_chip_by_segment_index(overlay, 2)

    QTest.mousePress(
        solo_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.rect().center(),
    )
    QTest.mouseMove(
        solo_chip.overlay,
        solo_chip.mapFromGlobal(soft_lighting_chip.leading_global_point()),
        10,
    )
    process_events(app)

    blank_line_visuals = _overlay_blank_line_target_visuals(overlay)
    assert len(blank_line_visuals) == 4

    third_blank_line = cast(Any, blank_line_visuals[2])
    third_blank_line_global = overlay.mapToGlobal(
        third_blank_line.hit_rect.center().toPoint()
    )
    QTest.mouseMove(
        solo_chip.overlay,
        solo_chip.mapFromGlobal(third_blank_line_global),
        10,
    )
    process_events(app)

    QTest.mouseRelease(
        solo_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.mapFromGlobal(third_blank_line_global),
        delay=10,
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert (
        box.toPlainText()
        == "1girl, detailed eyes, portrait, looking at viewer,\n\n\nsolo,\n\n"
        "soft lighting, pastel colors, clean lineart, highres"
    )
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_reorder_preview_still_wraps_in_narrow_card_width(
    widgets: list[QWidget],
) -> None:
    """Reorder preview should stay usable in narrow card widths without a second panel."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(260, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText(
        "alpha long segment, beta long segment, gamma long segment, delta long segment"
    )
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = getattr(box, "_segment_overlay")
    assert overlay is not None

    chips = _overlay_pointer_regions(overlay)

    assert overlay.parentWidget() is box.viewport()
    assert overlay.findChild(QWidget, "segmentReorderScrollArea") is None
    assert overlay.findChild(QWidget, "segmentReorderFrame") is None
    assert len({chip.geometry().top() for chip in chips}) > 1
    assert all(chip.cursor().shape() == Qt.CursorShape.OpenHandCursor for chip in chips)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert getattr(box, "_segment_overlay") is None
