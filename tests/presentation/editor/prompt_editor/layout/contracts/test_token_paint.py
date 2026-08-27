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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations

from types import SimpleNamespace


import pytest
from typing import Any, cast

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    token_weight_controls as token_weight_control_lifecycle,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    token_weight_view as token_weight_control_theme,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.painter import (
    PromptProjectionPainter,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    _emphasis_decoration_metrics,
    _emphasis_parenthesis_color,
    _emphasis_weight_color,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_active_emphasis_keeps_default_text_color() -> None:
    """Caret-active emphasis should not tint the visible token text foreground."""

    layout, projection = _layout_for("(cat:1.05), suffix", active_span_range=(0, 10))
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    fragment = next(
        fragment
        for fragment in layout.frame.output.snapshot.text_fragments
        if fragment.token_id == token.token_id
    )

    assert token.active is True
    assert PromptProjectionPainter().text_color_for_fragment(
        fragment,
        paint_input=layout.frame.paint_input,
    ) == QPalette().color(QPalette.ColorRole.Text)


def test_projection_layout_decoration_feedback_accents_only_emphasis_parentheses() -> (
    None
):
    """Decoration feedback should tint only the parens, not the content or weight text."""

    layout, projection = _layout_for(
        "(cat:1.05), suffix",
        decoration_accent_ranges=((0, 10),),
    )
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    fragment = next(
        fragment
        for fragment in layout.frame.output.snapshot.text_fragments
        if fragment.token_id == token.token_id
    )

    assert token.decoration_accented is True
    palette = QPalette()
    assert _emphasis_parenthesis_color(palette, token) != palette.color(
        QPalette.ColorRole.Text
    )
    assert _emphasis_weight_color(palette) == palette.color(QPalette.ColorRole.Text)
    assert PromptProjectionPainter().text_color_for_fragment(
        fragment,
        paint_input=layout.frame.paint_input,
    ) == palette.color(QPalette.ColorRole.Text)


def test_projection_layout_selected_emphasis_decorations_use_highlighted_text() -> None:
    """Selected emphasis decorations should paint with the selection foreground role."""

    layout, projection = _layout_for(
        "(cat:1.05), suffix",
        decoration_accent_ranges=((0, 10),),
    )
    palette = QPalette()
    selected_color = QColor("#102030")
    palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, selected_color)
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    selection = PromptProjectionSelection(token.source_start, token.source_end)
    emphasis_decoration_fragments = [
        fragment
        for fragment in layout.frame.output.snapshot.inline_object_fragments
        if fragment.token_id == token.token_id
    ]

    assert emphasis_decoration_fragments
    assert all(
        PromptProjectionPainter().inline_object_fragment_is_selected(
            layout.frame.output.projection_document,
            fragment,
            selection,
        )
        for fragment in emphasis_decoration_fragments
    )
    assert _emphasis_parenthesis_color(palette, token, selected=True) == selected_color
    assert _emphasis_weight_color(palette, selected=True) == selected_color


def test_projection_weight_controls_derive_preview_and_arrow_colors_from_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floating weights and arrow controls should use QFluent theme primitives."""

    ensure_qapp()
    surface_widget = QWidget()
    palette = QPalette()
    text_color = QColor("#101418")
    palette.setColor(QPalette.ColorRole.Text, text_color)
    surface_widget.setPalette(palette)

    monkeypatch.setattr(token_weight_control_theme, "isDarkTheme", lambda: False)

    assert token_weight_control_theme.surface_text_color(surface_widget) == text_color
    assert token_weight_control_theme._theme_contrast_fill(18) == QColor(0, 0, 0, 18)
    assert token_weight_control_theme._theme_contrast_fill(28) == QColor(0, 0, 0, 28)
    assert token_weight_control_theme.weight_preview_shadow_color() == QColor(
        255,
        255,
        255,
        230,
    )

    monkeypatch.setattr(token_weight_control_theme, "isDarkTheme", lambda: True)

    assert token_weight_control_theme._theme_contrast_fill(18) == QColor(
        255,
        255,
        255,
        18,
    )
    assert token_weight_control_theme._theme_contrast_fill(28) == QColor(
        255,
        255,
        255,
        28,
    )
    assert token_weight_control_theme.weight_preview_shadow_color() == QColor(
        0,
        0,
        0,
        216,
    )


def test_projection_weight_controls_ignore_deleted_qt_mapping_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Teardown-time pointer updates should not touch deleted host or timer objects."""

    class DeletedHost:
        """Stand in for a Qt wrapper whose C++ object has already gone away."""

        def mapFromGlobal(self, _point: object) -> object:  # noqa: N802
            """Match the RuntimeError raised by a deleted QWidget wrapper."""

            raise RuntimeError("Internal C++ object already deleted.")

    host = cast(QWidget, DeletedHost())
    controls = token_weight_control_lifecycle.PromptTokenWeightControls.__new__(
        token_weight_control_lifecycle.PromptTokenWeightControls
    )
    controls._host = host  # noqa: SLF001
    cast(Any, controls)._gestures = SimpleNamespace(
        pointer_host_position=QPointF(1.0, 1.0)
    )

    monkeypatch.setattr(
        token_weight_control_lifecycle,
        "isValid",
        lambda _candidate: False,
    )

    assert token_weight_control_lifecycle._qt_object_is_valid(host) is False
    assert controls._host_point_from_global(QPointF(4.0, 5.0)) is None  # noqa: SLF001

    controls._set_pointer_from_global(QPointF(4.0, 5.0))  # noqa: SLF001

    assert controls._gestures.pointer_host_position is None  # noqa: SLF001


def test_projection_layout_reports_wrapped_fragments_and_anchor_geometry_for_tokens() -> (
    None
):
    """Wrapped layouts should still expose source fragments and token anchor rects."""

    layout, projection = _layout_for("(alpha beta gamma delta epsilon zeta:1.10)")
    token = projection.tokens[0]
    viewport_rect = QRectF(0.0, 0.0, 140.0, 320.0)
    layout.set_text_width(viewport_rect.width())

    fragments = layout.frame.geometry.selection.source_range_fragments(
        token.source_start,
        token.source_end,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    anchor_rect = layout.frame.geometry.tokens.token_anchor_rect(
        token, scroll_offset=0.0
    )

    assert len(fragments) >= 1
    assert anchor_rect is not None
    assert anchor_rect.isValid() is True


def test_projection_layout_emphasis_weight_anchor_stays_compact_and_close_to_suffix() -> (
    None
):
    """Weight anchor geometry should remain compact and hug the closing marker."""

    layout, projection = _layout_for("(cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    token_runs = projection.runs_for_token(token.token_id)
    suffix_fragment = layout.frame.output.snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[2].run_id
    )[0]
    anchor_rect = layout.frame.geometry.tokens.token_anchor_rect(
        token, scroll_offset=0.0
    )

    assert anchor_rect is not None
    assert anchor_rect.left() - suffix_fragment.rect.left() < (
        suffix_fragment.rect.width() * 0.35
    )
    assert anchor_rect.width() < suffix_fragment.rect.width()
    assert anchor_rect.height() < suffix_fragment.rect.height()


def test_projection_layout_uses_shared_gap_for_emphasis_parentheses() -> None:
    """Opening and closing emphasis parens should sit off the content by the same gap."""

    layout, projection = _layout_for("(cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    token_runs = projection.runs_for_token(token.token_id)
    prefix_fragment = layout.frame.output.snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[0].run_id
    )[0]
    content_fragment = layout.frame.output.snapshot.text_fragments_for_run(
        token_runs[1].run_id
    )[  # noqa: SLF001
        0
    ]
    anchor_rect = layout.frame.geometry.tokens.token_anchor_rect(
        token, scroll_offset=0.0
    )
    assert anchor_rect is not None

    decoration_metrics = _emphasis_decoration_metrics(
        layout.frame.output.configuration.base_font
    )
    left_gap = (
        content_fragment.rect.left()
        - prefix_fragment.rect.left()
        - decoration_metrics.parenthesis_width("(")
    )
    right_gap = (
        anchor_rect.left()
        - content_fragment.rect.right()
        - decoration_metrics.parenthesis_width(")")
        - decoration_metrics.weight_gap
    )

    assert abs(left_gap - decoration_metrics.content_gap) < 0.01
    assert abs(right_gap - decoration_metrics.content_gap) < 0.01
    assert abs(left_gap - right_gap) < 0.01


def test_projection_layout_keeps_inline_emphasis_inside_one_tag_fragment() -> None:
    """One comma-delimited tag should stay one source fragment across inline emphasis."""

    text = "alpha, blue (green:1.10) hair, gamma"
    layout, projection = _layout_for(text)
    layout.set_text_width(480.0)
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    segment_start = text.index("blue")
    segment_end = text.index(", gamma")

    fragments = layout.frame.geometry.selection.source_range_fragments(
        segment_start,
        segment_end,
        viewport_rect=QRectF(0.0, 0.0, 480.0, 80.0),
        scroll_offset=0.0,
    )
    token_rect = layout.frame.geometry.tokens.token_rect(token, scroll_offset=0.0)

    assert len(fragments) == 1
    assert token_rect is not None
    assert fragments[0].left() < token_rect.left()
    assert fragments[0].right() > token_rect.right()


def test_projection_layout_uses_qfluent_document_margin_for_plain_text_geometry() -> (
    None
):
    """Plain-text caret geometry should include the QFluent document left inset."""

    layout, _projection = _layout_for("alpha")
    fragments = layout.frame.geometry.selection.source_range_fragments(
        0,
        1,
        viewport_rect=QRectF(0.0, 0.0, 220.0, 80.0),
        scroll_offset=0.0,
    )

    assert layout.frame.output.configuration.document_margin == 4.0
    assert fragments[0].left() >= 4.0


def test_projection_layout_uses_half_height_separator_rows_without_row_carets() -> None:
    """Separator rows should be compact while their edge carets stay on adjacent lines."""

    layout, projection = _layout_for("global\n[SEP]\nregional")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    structural_line = next(
        line
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        if line.source_start == token.source_start and not line.fragments
    )
    content_lines = [
        line
        for line in layout.frame.output.snapshot.lines
        if line.fragments  # noqa: SLF001
    ]

    assert structural_line.height == pytest.approx(content_lines[0].height)
    assert structural_line.caret_stops == ()
    leading_state = projection.caret_map.state_for_source_position(token.source_start)
    trailing_state = projection.caret_map.state_for_source_position(
        token.source_end,
        prefer_after=True,
    )
    leading_rect = layout.frame.geometry.caret.cursor_rect(
        leading_state, scroll_offset=0.0
    )
    trailing_rect = layout.frame.geometry.caret.cursor_rect(
        trailing_state, scroll_offset=0.0
    )
    assert leading_rect.center().y() < structural_line.top
    assert trailing_rect.center().y() > structural_line.top + structural_line.height
