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

"""Verify mounted prompt reorder projection content."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
)

from .mount_support import (
    ensure_qapp,
    process_events,
    _create_overlay,
    _pointer_regions,
    _chip_by_segment_index,
    _chip_text,
    _drag_proxy,
    _drag_proxy_projection_document,
    _drag_proxy_text_paint_payload,
    _preview_projection_document,
    _preview_text,
    _preview_rect,
)


def test_segment_reorder_overlay_uses_projection_engine_for_preview_and_drag_proxy(
    widgets: list[QWidget],
) -> None:
    """Dragging emphasized text should keep projection tokens in preview and proxy."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=340,
        height=180,
        text="(1girl:0.05), solo",
    )
    emphasized_chip = _chip_by_segment_index(overlay, 0)
    solo_chip = _chip_by_segment_index(overlay, 1)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, solo_chip.rect().center().y())
    )

    QTest.mousePress(
        emphasized_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=emphasized_chip.rect().center(),
    )
    QTest.mouseMove(
        emphasized_chip.overlay,
        emphasized_chip.mapFromGlobal(drag_target),
        10,
    )
    process_events(app)

    preview_projection_document = _preview_projection_document(overlay)
    drag_proxy_projection_document = _drag_proxy_projection_document(overlay)

    assert _preview_text(overlay) == "solo, (1girl:0.05)"
    assert preview_projection_document is not None
    assert drag_proxy_projection_document is not None
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in cast(Any, preview_projection_document).tokens
    )
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in cast(Any, drag_proxy_projection_document).tokens
    )

    QTest.mouseRelease(
        emphasized_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=emphasized_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_drag_proxy_projects_lora_without_banners(
    widgets: list[QWidget],
) -> None:
    """Dragging a LoRA chip should keep the proxy projected while suppressing banners."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="<lora:Mineru:0.80>, solo",
    )
    lora_chip = _chip_by_segment_index(overlay, 0)
    solo_chip = _chip_by_segment_index(overlay, 1)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, solo_chip.rect().center().y())
    )

    QTest.mousePress(
        lora_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=lora_chip.rect().center(),
    )
    QTest.mouseMove(lora_chip.overlay, lora_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    drag_proxy_projection_document = _drag_proxy_projection_document(overlay)
    text_paint_payload = _drag_proxy_text_paint_payload(overlay)
    assert text_paint_payload is not None
    lora_renderer = cast(
        Any, text_paint_payload
    ).paint_input.inline_object_renderers.renderer_for("lora_chip")

    assert drag_proxy_projection_document is not None
    assert any(
        token.kind is PromptProjectionTokenKind.LORA
        and token.display_text == "Mineru"
        and token.value_text == "0.80"
        for token in cast(Any, drag_proxy_projection_document).tokens
    )
    assert cast(bool, getattr(lora_renderer, "_suppress_banners")) is True

    QTest.mouseRelease(
        lora_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=lora_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_splits_multi_tag_emphasis_shell_into_multiple_chips(
    widgets: list[QWidget],
) -> None:
    """Alt chip visuals should expose one chip per prompt tag inside an exact shell."""

    _editor, overlay = _create_overlay(
        widgets,
        width=520,
        height=180,
        text="(1girl, solo:1.10), blush",
    )

    chips = _pointer_regions(overlay)

    assert [_chip_text(chip) for chip in chips] == ["1girl,", "solo,", "blush"]


def test_segment_reorder_overlay_expands_preview_and_drag_proxy_for_split_emphasis_chip(
    widgets: list[QWidget],
) -> None:
    """Separated emphasis chips should size preview and proxy bubbles to the standalone shell."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=520,
        height=180,
        text="(1girl, solo:1.10), blush",
    )
    solo_chip = _chip_by_segment_index(overlay, 1)
    blush_chip = _chip_by_segment_index(overlay, 2)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, blush_chip.rect().center().y())
    )
    original_chip_width = solo_chip.width()

    QTest.mousePress(
        solo_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.rect().center(),
    )
    QTest.mouseMove(solo_chip.overlay, solo_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    preview_rect = _preview_rect(overlay, 1)
    proxy = _drag_proxy(overlay)

    assert _preview_text(overlay) == "(1girl:1.10), blush, (solo:1.10)"
    assert preview_rect is not None
    assert preview_rect.width() > original_chip_width
    assert proxy.width() > original_chip_width

    QTest.mouseRelease(
        solo_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_landing_preview_uses_outline_without_redrawing_text(
    widgets: list[QWidget],
) -> None:
    """Landing previews should reuse bubble geometry without repainting dragged text."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=320,
        height=180,
        text="alpha, beta, gamma",
    )
    first_chip = _chip_by_segment_index(overlay, 0)
    second_chip = _chip_by_segment_index(overlay, 1)
    drag_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    painted_text_calls: list[bool] = []
    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    original_paint_projection_text = cast(
        Any, view
    )._projection_chip_painter.paint_projection_text

    def recording_paint_projection_text(*args: object, **kwargs: object) -> object:
        """Record any accidental overlay-owned text painting during landing preview."""

        painted_text_calls.append(True)
        return original_paint_projection_text(*args, **kwargs)

    cast(
        Any, view
    )._projection_chip_painter.paint_projection_text = recording_paint_projection_text

    overlay.repaint()
    process_events(app)

    assert _preview_rect(overlay, 1) is not None
    assert painted_text_calls == []

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)
