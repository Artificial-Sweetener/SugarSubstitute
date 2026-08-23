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

"""Prompt LoRA inline-renderer geometry contracts."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from substitute.presentation.editor.prompt_editor.projection.metrics import (
    projection_text_line_height,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptLoraInlineObjectRenderer,
)

from tests.presentation.editor.prompt_editor.lora_rendering.support import (
    _run,
    _token,
    ensure_qapp,
)


def test_lora_renderer_measures_content_width_with_long_title_cap() -> None:
    """LoRA bars should stay shorter than the canonical projection row height."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("fizrot (artist style) [Illustrious]")
    token = _token()
    font = QFont()

    size = renderer.measure_inline_object(run, token, base_font=font)

    assert 120 <= size.width() <= 360
    assert size.height() < projection_text_line_height(font)


def test_lora_renderer_keeps_weight_rect_inside_canonical_height() -> None:
    """LoRA weight chrome should not protrude beyond the measured chip height."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    token = _token()
    font = QFont()
    size = renderer.measure_inline_object(run, token, base_font=font)

    weight_rect = renderer.weight_text_rect(
        run,
        token,
        QRectF(0.0, 0.0, size.width(), size.height()),
        base_font=font,
    )

    assert weight_rect is not None
    assert weight_rect.height() <= size.height()
    assert weight_rect.top() >= 0.0
    assert weight_rect.bottom() <= size.height()


def test_lora_renderer_uses_smaller_title_font() -> None:
    """LoRA page and version labels should be slightly smaller than editor text."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    base_font = QFont()
    title_font = renderer._title_font(base_font)  # noqa: SLF001

    assert QFontMetricsF(title_font).height() <= QFontMetricsF(base_font).height()
    assert QFontMetricsF(title_font).horizontalAdvance("Mineru") < QFontMetricsF(
        base_font
    ).horizontalAdvance("Mineru")


def test_lora_renderer_caps_page_and_version_character_counts() -> None:
    """LoRA labels should be character-capped before width-based elision."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    metrics = QFontMetricsF(QFont())

    segments = renderer._title_segments(  # noqa: SLF001
        metrics,
        page_text="Extremely Long CivitAI Collection Page Name With Extra Words",
        version_text="Overly Detailed Version Name With Extra Words",
        available_width=600.0,
    )

    assert segments == (
        "Extremely Long Ci...",
        " - ",
        "Overly Detai...",
    )
    assert len(segments[0]) == 20
    assert len(segments[2]) == 15


def test_lora_renderer_weight_changes_do_not_shift_normal_bar_width() -> None:
    """Common LoRA weight edits should use a stable reserved weight slot."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    font = QFont()

    widths = {
        renderer.measure_inline_object(
            run,
            _token(value_text=value_text),
            base_font=font,
        ).width()
        for value_text in ("0.80", "1.00", "1.25", "-0.25")
    }

    assert len(widths) == 1


def test_lora_renderer_keeps_version_visible_after_page_elision() -> None:
    """Long page names should elide before the LoRA version label disappears."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    metrics = QFontMetricsF(QFont())

    segments = renderer._title_segments(  # noqa: SLF001
        metrics,
        page_text="Extremely Long CivitAI Collection Page Name With Extra Words",
        version_text="Battoujutsu Variant",
        available_width=145.0,
    )

    assert len(segments) == 3
    assert segments[1] == " - "
    assert segments[0] != "Extremely Long CivitAI Collection Page Name With Extra Words"
    assert segments[2]


def test_lora_renderer_exact_edit_uses_existing_pill_width_without_growth() -> None:
    """Exact edit mode should not add LoRA weight padding twice."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    font = QFont()
    normal_token = _token(value_text="0.80")

    normal_size = renderer.measure_inline_object(run, normal_token, base_font=font)
    normal_weight_rect = renderer.weight_text_rect(
        run,
        normal_token,
        QRectF(0.0, 0.0, normal_size.width(), normal_size.height()),
        base_font=font,
    )
    assert normal_weight_rect is not None
    editing_size = renderer.measure_inline_object(
        run,
        _token(
            value_text="0.80",
            editing_value_text="0.80",
            editing_slot_width=normal_weight_rect.width(),
        ),
        base_font=font,
    )

    assert editing_size == normal_size


def test_lora_renderer_chevron_path_has_sharp_angle_ends() -> None:
    """The rendered LoRA bar shape should use sharp angle-bracket tips."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    path = renderer._chevron_path(QRectF(0.0, 0.0, 120.0, 24.0))  # noqa: SLF001

    polygon = path.toFillPolygon()
    first = polygon.at(0)
    second = polygon.at(1)
    fourth = polygon.at(3)

    assert first.x() == 0
    assert first.y() == 12
    assert second.x() > 0
    assert second.y() == 0
    assert fourth.x() == 120
    assert fourth.y() == 12


def test_lora_renderer_keeps_weight_rect_available_for_controls() -> None:
    """Existing weight controls should still have a stable weight slot."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    token = _token()
    rect = QRectF(0.0, 0.0, 180.0, 26.0)

    weight_rect = renderer.weight_text_rect(run, token, rect, base_font=QFont())
    anchor_rect = renderer.anchor_rect(run, token, rect, base_font=QFont())

    assert weight_rect is not None
    assert anchor_rect is not None
    assert weight_rect == anchor_rect
    assert weight_rect.right() < rect.right()
    assert weight_rect.left() > rect.center().x()
