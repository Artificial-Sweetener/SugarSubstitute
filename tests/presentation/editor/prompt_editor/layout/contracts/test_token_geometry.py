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


from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.layout.token_measurement import (
    PromptProjectionTokenMeasurer,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_measures_projected_emphasis_from_visible_content_not_raw_syntax() -> (
    None
):
    """Collapsed emphasis width should match the visible token measurement, not raw syntax."""

    layout, projection = _layout_for("(cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    token_rect = layout.frame.geometry.tokens.token_rect(token, scroll_offset=0.0)

    assert token_rect is not None
    measured_size = PromptProjectionTokenMeasurer().measure(
        token,
        projection_document=layout.frame.output.projection_document,
        inline_object_renderers=(
            layout.frame.output.configuration.inline_object_renderers
        ),
        base_font=layout.frame.output.configuration.base_font,
        metrics=layout.frame.output.configuration.metrics,
    )
    assert token_rect.width() == measured_size.width()


def test_projection_token_geometry_resolves_token_at_viewport_position() -> None:
    """Keep pointer token lookup with the immutable geometry owner."""

    layout, projection = _layout_for("prefix, (cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    geometry = layout.frame.geometry.tokens
    token_rect = geometry.token_rect(token, scroll_offset=0.0)

    assert token_rect is not None
    assert (
        geometry.token_at_viewport_position(
            token_rect.center(),
            scroll_offset=0.0,
        )
        is token
    )


def test_projection_layout_hit_testing_resolves_emphasis_edges_and_internal_content_boundaries() -> (
    None
):
    """Hit testing should map decorative emphasis markers onto token-edge states."""

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
    suffix_fragment = layout.frame.output.snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[2].run_id
    )[0]

    assert token.content_start is not None
    assert token.content_end is not None

    leading_state = layout.frame.geometry.hit_testing.hit_test(
        prefix_fragment.rect.center(),
        scroll_offset=0.0,
    )
    content_start_state = layout.frame.geometry.hit_testing.hit_test(
        QPointF(content_fragment.rect.left() + 1.0, content_fragment.rect.center().y()),
        scroll_offset=0.0,
    )
    after_c_state = layout.frame.geometry.hit_testing.hit_test(
        layout.frame.geometry.caret.cursor_rect(
            projection.caret_map.state_for_source_position(token.content_start + 1),
            scroll_offset=0.0,
        ).center(),
        scroll_offset=0.0,
    )
    after_a_state = layout.frame.geometry.hit_testing.hit_test(
        layout.frame.geometry.caret.cursor_rect(
            projection.caret_map.state_for_source_position(token.content_start + 2),
            scroll_offset=0.0,
        ).center(),
        scroll_offset=0.0,
    )
    content_end_state = layout.frame.geometry.hit_testing.hit_test(
        QPointF(suffix_fragment.rect.left() + 1.0, suffix_fragment.rect.center().y()),
        scroll_offset=0.0,
    )
    trailing_state = layout.frame.geometry.hit_testing.hit_test(
        QPointF(suffix_fragment.rect.right() - 1.0, suffix_fragment.rect.center().y()),
        scroll_offset=0.0,
    )

    assert leading_state.placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
    assert leading_state.source_position == token.source_start
    assert content_start_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
    assert content_start_state.source_position == token.content_start
    assert after_c_state.source_position == token.content_start + 1
    assert after_a_state.source_position == token.content_start + 2
    assert content_end_state.source_position == token.content_end
    assert (
        trailing_state.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
    )
    assert trailing_state.source_position == token.source_end


def test_projection_layout_cursor_rect_supports_distinct_logical_emphasis_caret_states() -> (
    None
):
    """Caret geometry should expose token-edge and content-boundary states separately."""

    layout, projection = _layout_for("(cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    assert token.content_start is not None
    assert token.content_end is not None

    leading_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.source_start),
        scroll_offset=0.0,
    )
    content_start_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_start),
        scroll_offset=0.0,
    )
    after_c_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_start + 1),
        scroll_offset=0.0,
    )
    content_end_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_end),
        scroll_offset=0.0,
    )
    trailing_rect = layout.frame.geometry.caret.cursor_rect(
        projection.caret_map.state_for_source_position(token.source_end),
        scroll_offset=0.0,
    )

    assert leading_rect.left() == content_start_rect.left()
    assert after_c_rect.left() > content_start_rect.left()
    assert content_end_rect.left() > after_c_rect.left()
    assert trailing_rect.left() > content_end_rect.left()


def test_projection_layout_selection_rects_support_partial_collapsed_emphasis_content() -> (
    None
):
    """Collapsed emphasis should paint partial content selection without full-token fill."""

    layout, projection = _layout_for("(cat:1.05), suffix")
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    token_rect = layout.frame.geometry.tokens.token_rect(token, scroll_offset=0.0)
    assert token_rect is not None
    assert token.content_start is not None
    assert token.content_end is not None

    partial_selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(
            anchor_position=token.content_start,
            cursor_position=token.content_end - 1,
        )
    )
    whole_token_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(
            anchor_position=token.source_start,
            cursor_position=token.source_end,
        )
    )

    assert len(partial_selection_rects) == 1
    assert partial_selection_rects[0].width() < token_rect.width()
    assert whole_token_rects[0].left() < partial_selection_rects[0].left()
    assert whole_token_rects[0].right() > partial_selection_rects[0].right()
    assert whole_token_rects == (token_rect,)
