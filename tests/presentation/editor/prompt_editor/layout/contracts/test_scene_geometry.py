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


from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF

from substitute.domain.appearance import RgbColor, SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.painter import (
    PromptProjectionPainter,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry import (
    PromptProjectionReorderGeometry,
    reorder_geometry_state,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_reports_full_width_scene_region_rows() -> None:
    """Scene zebra geometry should cover rows without relying on title chrome."""

    text = "**portrait\none\n**cafe\ntwo"
    layout, _ = _layout_for(text, text_width=320.0)
    viewport_rect = QRectF(0.0, 0.0, 320.0, 160.0)

    rects = PromptProjectionReorderGeometry().source_range_row_rects(
        reorder_geometry_state(layout.frame.geometry),
        text.index("cafe"),
        len(text),
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )

    assert len(rects) == 2
    assert all(rect.left() == viewport_rect.left() for rect in rects)
    assert all(rect.width() == viewport_rect.width() for rect in rects)


def test_projection_layout_paints_invalid_scene_titles_with_semantic_error_color() -> (
    None
):
    """Only invalid scene title text should consume the semantic error foreground."""

    error_color = RgbColor(10, 120, 230)
    semantic_palette = SemanticPalette(
        accent=RgbColor(1, 2, 3),
        error_foreground=error_color,
        warning_foreground=RgbColor(90, 120, 10),
    )
    layout, projection = _layout_for(
        "**hands\ndetail",
        scene_error_keys=frozenset({"hands"}),
        semantic_palette=semantic_palette,
    )
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    fragment = next(
        fragment
        for fragment in layout.frame.output.snapshot.text_fragments
        if fragment.token_id == token.token_id
    )

    assert (
        PromptProjectionPainter()
        .font_for_fragment(
            fragment,
            paint_input=layout.frame.paint_input,
        )
        .weight()
        > QFont().weight()
    )
    assert PromptProjectionPainter().text_color_for_fragment(
        fragment,
        paint_input=layout.frame.paint_input,
    ) == QColor(
        error_color.red,
        error_color.green,
        error_color.blue,
    )


def test_projection_layout_measures_scene_title_caret_with_bold_metrics() -> None:
    """Scene title caret geometry should match the bold font used for painting."""

    title = "wide scene title"
    layout, projection = _layout_for(f"**{title}\nbody", text_width=420.0)
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    fragment = next(
        fragment
        for fragment in layout.frame.output.snapshot.text_fragments
        if fragment.token_id == token.token_id
    )
    assert token.content_end is not None

    bold_font = PromptProjectionPainter().font_for_fragment(
        fragment,
        paint_input=layout.frame.paint_input,
    )
    regular_font = QFont()
    bold_advance = QFontMetricsF(bold_font).horizontalAdvance(title)
    regular_advance = QFontMetricsF(regular_font).horizontalAdvance(title)
    title_end_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_end),
        scroll_offset=0.0,
    )

    assert bold_font.weight() > regular_font.weight()
    assert abs(fragment.rect.width() - bold_advance) < 1.0
    assert abs(title_end_rect.left() - (fragment.rect.left() + bold_advance)) < 1.0
    if abs(bold_advance - regular_advance) > 1.0:
        assert (
            abs(title_end_rect.left() - (fragment.rect.left() + regular_advance)) > 1.0
        )
