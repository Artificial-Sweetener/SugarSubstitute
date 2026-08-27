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


from PySide6.QtCore import QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPalette

from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintStateBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp

from .support import (
    _line_texts,
    _blank_line_break_ranges,
    _line_has_selection_rect,
    _CountingEmphasisPrefixRenderer,
    _CountingEmphasisSuffixRenderer,
    _assert_word_not_split_across_lines,
    _line_indices_for_source_range,
    _plain_text_wrap_width,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_consecutive_paragraph_break_rows_own_newline_source_before_tokens() -> None:
    """Blank rows from consecutive newlines should own selectable source spans."""

    prompt = (
        "alpha,\n\n(small:1.20) breasts, flat chest,\n\n(pale skin:1.20), pointy ears"
    )
    layout, _projection = _layout_for(prompt, text_width=760.0)
    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(0, len(prompt))
    )
    expected_blank_ranges = _blank_line_break_ranges(prompt)
    rows_by_range = {
        (line.source_start, line.source_end): line
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        if (line.source_start, line.source_end) in expected_blank_ranges
    }

    assert set(rows_by_range) == set(expected_blank_ranges)
    for row_range, line in rows_by_range.items():
        assert not line.fragments
        assert (line.line_break_start, line.line_break_end) == row_range
        assert prompt[line.source_start : line.source_end] == "\n"
        assert _line_has_selection_rect(line, selection_rects)

    assert not [
        line
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        if not line.fragments
        and line.source_start == line.source_end
        and line.source_start < len(prompt)
    ]


def test_projection_layout_sets_projection_and_width_atomically() -> None:
    """Projection replacement should publish its final width with the document."""

    layout, projection = _layout_for("alpha beta", text_width=240.0)

    layout.set_projection_and_text_width(projection, 480.0)

    assert layout.frame.output.projection_document is projection
    assert layout.frame.output.configuration.text_width == 480.0


def test_projection_layout_paint_state_validation_skips_inline_measurements() -> None:
    """Paint-state validation should not remeasure unchanged inline objects."""

    ensure_qapp()
    prefix_renderer = _CountingEmphasisPrefixRenderer()
    suffix_renderer = _CountingEmphasisSuffixRenderer()
    document_view, projection = _projection_for("(cat:1.05), (dog:1.05)")
    layout = PromptLayoutEditToFrameCoordinator(
        PromptProjectionInlineObjectRendererRegistry(
            (
                prefix_renderer,
                suffix_renderer,
                PromptWildcardInlineObjectRenderer(),
            )
        )
    )
    layout.set_base_font(QFont())
    layout.frame.set_palette(QPalette())
    layout.set_projection(projection, prompt_document_view=document_view)
    layout.set_text_width(260.0)
    prefix_renderer.measure_calls = 0
    suffix_renderer.measure_calls = 0
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    paint_state = PromptProjectionPaintStateBuilder().build(
        projection,
        session=PromptProjectionSession(),
        active_span_range=(token.source_start, token.source_end),
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert layout.frame.try_set_paint_state(paint_state)

    assert prefix_renderer.measure_calls + suffix_renderer.measure_calls < 8


def test_projection_layout_keeps_short_comma_tag_on_one_line_when_it_fits() -> None:
    """Short comma-delimited prompt tags should move as unbroken wrapping units."""

    prompt_text = "masterpiece, best quality, detailed eyes"
    layout, _ = _layout_for(
        prompt_text,
        text_width=_plain_text_wrap_width("masterpiece, ", "best quality, "),
    )

    line_texts = _line_texts(layout)
    assert len(line_texts) > 1
    assert "best quality, " in line_texts


def test_projection_layout_keeps_three_word_comma_tag_on_one_line_when_it_fits() -> (
    None
):
    """Three-word comma-delimited tags should remain protected keep groups."""

    prompt_text = "alpha, greco roman clothes, omega"
    layout, _ = _layout_for(
        prompt_text,
        text_width=_plain_text_wrap_width("alpha, ", "greco roman clothes, "),
    )

    line_texts = _line_texts(layout)
    assert len(line_texts) > 1
    assert "greco roman clothes, " in line_texts


def test_projection_layout_does_not_promote_four_word_comma_tag_to_keep_group() -> None:
    """Four-word comma-delimited tags should keep normal wrapping behavior."""

    prompt_text = "alpha, one two three four, omega"
    layout, _ = _layout_for(
        prompt_text,
        text_width=_plain_text_wrap_width("one two three "),
    )
    segment_start = prompt_text.index("one")
    segment_end = prompt_text.index(", omega")

    assert (
        len(
            _line_indices_for_source_range(
                layout,
                start=segment_start,
                end=segment_end,
            )
        )
        > 1
    )


def test_projection_layout_wraps_long_comma_section_normally() -> None:
    """Long comma sections should keep normal prose-style wrapping behavior."""

    prompt_text = "a woman walking through a rainy city at night, soft window light"
    layout, _ = _layout_for(
        prompt_text,
        text_width=_plain_text_wrap_width("a woman walking through a rainy "),
    )

    first_segment_end = prompt_text.index(",")
    assert (
        len(_line_indices_for_source_range(layout, start=0, end=first_segment_end)) > 1
    )


def test_projection_layout_uses_stable_text_line_spacing() -> None:
    """Text-only rows should not inherit variable QTextLine height."""

    layout, _ = _layout_for("A😀B C😀D", text_width=44.0)
    font = QFont("Arial")
    font.setPixelSize(14)
    layout.set_base_font(font)
    expected_line_height = float(QFontMetricsF(font).lineSpacing())
    text_only_lines = tuple(
        line
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        if all(
            isinstance(fragment, PromptProjectionTextFragment)
            for fragment in line.fragments
        )
    )

    assert text_only_lines
    assert {line.height for line in text_only_lines} == {expected_line_height}


def test_projection_metrics_owns_text_row_geometry() -> None:
    """Projection metrics should define text row height, rects, and baselines."""

    ensure_qapp()
    font = QFont("Arial")
    font.setPixelSize(14)
    metrics = PromptProjectionMetricsFactory().create(
        base_font=font,
        document_margin=4.0,
        wrap_width=220.0,
        content_left_inset=12.0,
    )

    assert metrics.base_font_key == font.toString()
    assert metrics.content_left == 16.0
    assert metrics.content_width == 200.0
    assert metrics.initial_line_top() == 4.0
    assert metrics.initial_row_height() == metrics.text_line_height

    row_height = metrics.row_height_with_inline_object(
        metrics.initial_row_height(),
        QSizeF(32.0, metrics.text_line_height + 6.0),
    )
    text_rect = metrics.text_fragment_rect(
        x_left=metrics.content_left,
        row_top=metrics.initial_line_top(),
        row_height=row_height,
        width=42.0,
    )

    assert row_height == metrics.text_line_height + 6.0
    assert text_rect.height() == metrics.text_line_height
    assert text_rect.top() > metrics.initial_line_top()
    assert (
        metrics.text_baseline_for_row(
            row_top=metrics.initial_line_top(),
            row_height=row_height,
        )
        == text_rect.top() + metrics.text_ascent
    )


def test_projection_layout_metrics_content_height_matches_rows() -> None:
    """Layout content height should be derivable from metrics and row heights."""

    layout, _ = _layout_for("alpha\nbeta gamma delta", text_width=70.0)
    row_heights = tuple(line.height for line in layout.frame.output.snapshot.lines)  # noqa: SLF001
    expected_height = layout.frame.output.configuration.metrics.content_height_for_rows(
        row_heights
    )

    assert layout.frame.output.snapshot.content_size.height() == expected_height


def test_projection_layout_does_not_split_fitting_plain_word() -> None:
    """Plain text should move a fitting word instead of splitting it mid-word."""

    layout, _ = _layout_for("open mouth", text_width=70.0)

    _assert_word_not_split_across_lines(_line_texts(layout), "mouth")


def test_projection_layout_does_not_split_fitting_emphasized_word() -> None:
    """Rich emphasized text should preserve word integrity while wrapping."""

    layout, _ = _layout_for("(open mouth, parted lips:1.10)", text_width=100.0)
    line_texts = _line_texts(layout)

    _assert_word_not_split_across_lines(line_texts, "mouth")
    assert not any(line_text == "1.10" for line_text in line_texts)


def test_projection_layout_allows_oversized_word_split() -> None:
    """Words wider than the prompt content width should still split to make progress."""

    oversized_word = "supercalifragilisticexpialidocious"
    layout, _ = _layout_for(oversized_word, text_width=80.0)
    line_texts = _line_texts(layout)

    assert len(line_texts) > 1
    assert "".join(line_texts) == oversized_word


def test_projection_layout_keeps_decorated_short_tag_together_when_it_fits() -> None:
    """Decorated short tags should include decoration and separator in one keep group."""

    prompt_text = "alpha, (best quality:1.2), tail"
    layout, _ = _layout_for(
        prompt_text,
        text_width=(_plain_text_wrap_width("alpha, ", "(best quality1.2, ") + 30.0),
    )

    line_texts = _line_texts(layout)
    assert len(line_texts) > 1
    assert any(line.startswith("(best quality1.2, ") for line in line_texts)


def test_projection_layout_attaches_leading_decoration_during_oversized_fallback() -> (
    None
):
    """Oversized decorated tags should not leave leading decoration on the prior line."""

    layout, _ = _layout_for(
        "alpha, (long descriptive tag extra:1.2), tail",
        text_width=_plain_text_wrap_width("alpha, ", "(long "),
    )

    line_texts = _line_texts(layout)
    assert any(line_text.startswith("(long") for line_text in line_texts)
    assert all(not line_text.endswith("(") for line_text in line_texts)


def test_projection_layout_attaches_trailing_decoration_and_separator_during_fallback() -> (
    None
):
    """Oversized decorated tags should keep trailing decoration near final content."""

    layout, _ = _layout_for(
        "(long descriptive tag extra:1.2), tail",
        text_width=140.0,
    )

    line_texts = _line_texts(layout)
    assert all(line_text != "1.2, tail" for line_text in line_texts)
    assert any(line_text.startswith("extra1.2,") for line_text in line_texts)


def test_projection_layout_does_not_apply_tag_keep_groups_in_raw_mode() -> None:
    """Raw display mode should retain normal source-text wrapping."""

    layout, _ = _layout_for(
        "masterpiece, best quality, detailed eyes",
        display_mode=PromptProjectionDisplayMode.RAW,
        text_width=260.0,
    )

    assert "best quality, " not in _line_texts(layout)
