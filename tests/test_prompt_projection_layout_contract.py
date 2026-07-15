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

from collections.abc import Iterator, Mapping
from dataclasses import replace
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from typing import Any, cast

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPalette
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptDocumentService,
    PromptLineDropTarget,
    PromptReorderChipView,
    PromptReorderLayoutView,
    PromptSyntaxProfileService,
    PromptSyntaxService,
)
from substitute.domain.appearance import RgbColor, SemanticPalette
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    token_weight_controls as token_weight_control_lifecycle,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    token_weight_view as token_weight_control_theme,
)
from substitute.presentation.editor.prompt_editor.projection.layout_engine import (
    PromptProjectionLayout,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretPlacement,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionRun,
    PromptProjectionSelection,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintStateBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
    _emphasis_decoration_metrics,
    _emphasis_parenthesis_color,
    _emphasis_weight_color,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)


def _layout_for(
    text: str,
    *,
    active_span_range: tuple[int, int] | None = None,
    decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    scene_error_keys: frozenset[str] = frozenset(),
    semantic_palette: SemanticPalette | None = None,
    text_width: float = 220.0,
) -> tuple[PromptProjectionLayout, PromptProjectionDocument]:
    """Build one projection layout for the supplied prompt text."""

    ensure_qapp()
    document_view, projection = _projection_for(
        text,
        active_span_range=active_span_range,
        decoration_accent_ranges=decoration_accent_ranges,
        display_mode=display_mode,
        scene_error_keys=scene_error_keys,
    )
    layout = PromptProjectionLayout(
        PromptProjectionInlineObjectRendererRegistry(
            (
                PromptEmphasisPrefixRenderer(),
                PromptEmphasisSuffixRenderer(),
                PromptWildcardInlineObjectRenderer(),
            )
        )
    )
    layout.set_base_font(QFont())
    layout.set_palette(QPalette())
    layout.set_semantic_palette(semantic_palette)
    layout.set_projection(projection, prompt_document_view=document_view)
    layout.set_text_width(text_width)
    return layout, projection


def _projection_for(
    text: str,
    *,
    active_span_range: tuple[int, int] | None = None,
    decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    scene_error_keys: frozenset[str] = frozenset(),
) -> tuple[PromptDocumentView, PromptProjectionDocument]:
    """Build one prompt document view and matching projection."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        PromptSyntaxProfileService().default_profile(),
    )
    projection = PromptProjectionBuilder().build_projection(
        document_view,
        render_plan,
        display_mode=display_mode,
        session=PromptProjectionSession(),
        active_span_range=active_span_range,
        decoration_accent_ranges=decoration_accent_ranges,
        scene_error_keys=scene_error_keys,
    )
    return document_view, projection


def _line_texts(layout: PromptProjectionLayout) -> tuple[str, ...]:
    """Return visible line text, including inline-object display text."""

    line_texts: list[str] = []
    for line in layout._snapshot.lines:  # noqa: SLF001
        line_text = ""
        for fragment in line.fragments:
            if isinstance(fragment, PromptProjectionTextFragment):
                line_text += fragment.text
                continue
            run = layout.projection_document.run_by_id(fragment.run_id)
            line_text += "" if run is None else run.display_text
        line_texts.append(line_text)
    return tuple(line_texts)


def _blank_line_break_ranges(prompt: str) -> tuple[tuple[int, int], ...]:
    """Return newline ranges that own visual blank rows in consecutive breaks."""

    return tuple(
        (index + 1, index + 2)
        for index in range(len(prompt) - 1)
        if prompt[index] == "\n" and prompt[index + 1] == "\n"
    )


def _line_has_selection_rect(
    line: PromptProjectionLineSnapshot,
    selection_rects: tuple[QRectF, ...],
) -> bool:
    """Return whether a selection rect intersects one layout line."""

    line_bottom = line.top + line.height
    for rect in selection_rects:
        rect_center_y = rect.top() + rect.height() / 2.0
        if line.top <= rect_center_y <= line_bottom:
            return True
    return False


def test_consecutive_paragraph_break_rows_own_newline_source_before_tokens() -> None:
    """Blank rows from consecutive newlines should own selectable source spans."""

    prompt = (
        "alpha,\n\n(small:1.20) breasts, flat chest,\n\n(pale skin:1.20), pointy ears"
    )
    layout, _projection = _layout_for(prompt, text_width=760.0)
    selection_rects = layout.selection_rects(PromptProjectionSelection(0, len(prompt)))
    expected_blank_ranges = _blank_line_break_ranges(prompt)
    rows_by_range = {
        (line.source_start, line.source_end): line
        for line in layout._snapshot.lines  # noqa: SLF001
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
        for line in layout._snapshot.lines  # noqa: SLF001
        if not line.fragments
        and line.source_start == line.source_end
        and line.source_start < len(prompt)
    ]


def _layout_geometry_signature(
    layout: PromptProjectionLayout,
) -> tuple[
    tuple[float, float, int, int, tuple[tuple[float, float, float, float], ...]],
    ...,
]:
    """Return stable row and text-fragment geometry for layout comparisons."""

    signature = []
    for line in layout._snapshot.lines:  # noqa: SLF001
        signature.append(
            (
                round(line.top, 3),
                round(line.height, 3),
                line.source_start,
                line.source_end,
                tuple(
                    (
                        round(fragment.rect.x(), 3),
                        round(fragment.rect.y(), 3),
                        round(fragment.rect.width(), 3),
                        round(fragment.rect.height(), 3),
                    )
                    for fragment in line.fragments
                ),
            )
        )
    return tuple(signature)


class _NonIterableCaretRectMapping(Mapping[int, QRectF]):
    """Raise if a trailing edit tries to clone prior caret rects by iteration."""

    def __init__(self, backing: dict[int, QRectF]) -> None:
        """Store caret rects available only through direct key lookup."""

        self._backing = backing

    def __len__(self) -> int:
        """Return the number of available caret rects."""

        return len(self._backing)

    def __iter__(self) -> Iterator[int]:
        """Reject broad iteration of the prior caret-rect map."""

        raise AssertionError("caret rect mapping was iterated")

    def __getitem__(self, key: int) -> QRectF:
        """Return one caret rect by exact projection position."""

        return self._backing[key]


def _install_non_iterable_caret_rect_mapping(
    layout: PromptProjectionLayout,
) -> None:
    """Replace snapshot caret rects with a mapping that forbids full scans."""

    snapshot = layout._snapshot  # noqa: SLF001
    backing = {
        caret_stop.projection_position: QRectF(caret_stop.rect)
        for line in snapshot.lines
        for caret_stop in line.caret_stops
    }
    layout._snapshot = replace(  # noqa: SLF001
        snapshot,
        caret_rects_by_projection_position=_NonIterableCaretRectMapping(backing),
    )


class _CountingEmphasisPrefixRenderer(PromptEmphasisPrefixRenderer):
    """Count prefix measurement calls made by geometry reuse checks."""

    def __init__(self) -> None:
        """Initialize measurement counters."""

        super().__init__()
        self.measure_calls = 0

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Count one prefix measurement and delegate to the real renderer."""

        self.measure_calls += 1
        return super().measure_inline_object(run, token, base_font=base_font)


class _CountingEmphasisSuffixRenderer(PromptEmphasisSuffixRenderer):
    """Count suffix measurement calls made by geometry reuse checks."""

    def __init__(self) -> None:
        """Initialize measurement counters."""

        super().__init__()
        self.measure_calls = 0

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Count one suffix measurement and delegate to the real renderer."""

        self.measure_calls += 1
        return super().measure_inline_object(run, token, base_font=base_font)


def _assert_all_projection_caret_rects_resolve(
    layout: PromptProjectionLayout,
    projection: PromptProjectionDocument,
) -> None:
    """Assert every projection boundary resolves to a caret rect."""

    caret_rects = layout._snapshot.caret_rects_by_projection_position  # noqa: SLF001
    assert len(caret_rects) == projection.mapping.projection_length + 1
    for projection_position in range(projection.mapping.projection_length + 1):
        assert caret_rects[projection_position].height() > 0.0


def test_projection_layout_sets_projection_and_width_before_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-pass projection replacement should avoid rebuilding at default 1px width."""

    layout, projection = _layout_for("alpha beta", text_width=240.0)
    rebuild_widths: list[float] = []

    def record_rebuild() -> None:
        """Record the layout width visible to the rebuild call."""

        rebuild_widths.append(layout._text_width)  # noqa: SLF001

    monkeypatch.setattr(layout, "_rebuild_snapshot", record_rebuild)

    layout.set_projection_and_text_width(projection, 480.0)

    assert rebuild_widths == [480.0]


def test_projection_layout_paint_state_validation_skips_inline_measurements() -> None:
    """Paint-state validation should not remeasure unchanged inline objects."""

    ensure_qapp()
    prefix_renderer = _CountingEmphasisPrefixRenderer()
    suffix_renderer = _CountingEmphasisSuffixRenderer()
    document_view, projection = _projection_for("(cat:1.05), (dog:1.05)")
    layout = PromptProjectionLayout(
        PromptProjectionInlineObjectRendererRegistry(
            (
                prefix_renderer,
                suffix_renderer,
                PromptWildcardInlineObjectRenderer(),
            )
        )
    )
    layout.set_base_font(QFont())
    layout.set_palette(QPalette())
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

    assert layout.can_apply_paint_state(paint_state)

    assert prefix_renderer.measure_calls + suffix_renderer.measure_calls < 8


def _assert_word_not_split_across_lines(
    line_texts: tuple[str, ...],
    word: str,
) -> None:
    """Assert that no adjacent visual lines divide one normal word."""

    for previous_line, next_line in zip(line_texts, line_texts[1:], strict=False):
        for split_index in range(1, len(word)):
            assert not (
                previous_line.endswith(word[:split_index])
                and next_line.startswith(word[split_index:])
            ), line_texts


def _line_indices_for_source_range(
    layout: PromptProjectionLayout,
    *,
    start: int,
    end: int,
) -> set[int]:
    """Return wrapped line indices touched by a source range."""

    line_indices: set[int] = set()
    for line_index, line in enumerate(layout._snapshot.lines):  # noqa: SLF001
        for fragment in line.fragments:
            if any(
                start <= source_position < end
                for source_position in fragment.source_positions
            ):
                line_indices.add(line_index)
                break
    return line_indices


def _reorder_geometry_inputs_for_text(
    text: str,
) -> tuple[
    PromptReorderLayoutView,
    tuple[PromptReorderChipView, ...],
    dict[int, tuple[int, int]],
    dict[int, tuple[tuple[int, int], ...]],
]:
    """Return application-owned reorder metadata keyed by semantic chip index."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    chips = document_service.reorder_chips(document_view)
    layout_view = document_service.build_reorder_layout_view(document_view)
    rendered_ranges = {
        chip.index: (chip.selection_start, chip.selection_end) for chip in chips
    }
    owned_ranges: dict[int, tuple[tuple[int, int], ...]] = {
        chip.index: ((chip.selection_start, chip.selection_end),) for chip in chips
    }
    return layout_view, chips, rendered_ranges, owned_ranges


def test_projection_layout_keeps_short_comma_tag_on_one_line_when_it_fits() -> None:
    """Short comma-delimited prompt tags should move as unbroken wrapping units."""

    layout, _ = _layout_for(
        "masterpiece, best quality, detailed eyes",
        text_width=260.0,
    )

    assert "best quality, " in _line_texts(layout)


def test_projection_layout_keeps_three_word_comma_tag_on_one_line_when_it_fits() -> (
    None
):
    """Three-word comma-delimited tags should remain protected keep groups."""

    layout, _ = _layout_for(
        "alpha, greco roman clothes, omega",
        text_width=260.0,
    )

    assert "greco roman clothes, " in _line_texts(layout)


def test_projection_layout_does_not_promote_four_word_comma_tag_to_keep_group() -> None:
    """Four-word comma-delimited tags should keep normal wrapping behavior."""

    prompt_text = "alpha, one two three four, omega"
    layout, _ = _layout_for(prompt_text, text_width=250.0)
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
    layout, _ = _layout_for(prompt_text, text_width=260.0)

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
        for line in layout._snapshot.lines  # noqa: SLF001
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
    row_heights = tuple(line.height for line in layout._snapshot.lines)  # noqa: SLF001
    expected_height = layout.metrics.content_height_for_rows(row_heights)

    assert layout.content_size().height() == expected_height


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

    layout, _ = _layout_for(
        "alpha, (best quality:1.2), tail",
        text_width=280.0,
    )

    assert any(
        line_text.startswith("(best quality1.2, ") for line_text in _line_texts(layout)
    )


def test_projection_layout_attaches_leading_decoration_during_oversized_fallback() -> (
    None
):
    """Oversized decorated tags should not leave leading decoration on the prior line."""

    layout, _ = _layout_for(
        "alpha, (long descriptive tag extra:1.2), tail",
        text_width=150.0,
    )

    assert "alpha, " in _line_texts(layout)
    assert any(line_text.startswith("(long ") for line_text in _line_texts(layout))


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


def test_projection_layout_applies_local_comma_insert_that_creates_keep_groups() -> (
    None
):
    """Comma insertion may stay incremental when the new keep group remains local."""

    previous_text = "test test test test, omega"
    edit_start = len("test")
    next_text = previous_text[:edit_start] + "," + previous_text[edit_start:]
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=",",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert layout.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_rejects_comma_insert_when_new_keep_group_needs_wrap() -> (
    None
):
    """Comma insertion should reflow when the new kept tag no longer fits locally."""

    previous_text = "test test test test, omega"
    edit_start = len("test")
    next_text = previous_text[:edit_start] + "," + previous_text[edit_start:]
    layout, _ = _layout_for(previous_text, text_width=140.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=",",
        first_dirty_projection_position=edit_start,
    )

    assert result is None
    assert layout.last_incremental_reflow_rejection_reason == "tag_keep_group"


def test_projection_layout_rejects_incremental_comma_delete_that_removes_keep_groups() -> (
    None
):
    """Comma deletion should reflow when it merges kept tags into normal wrapping."""

    previous_text = "test, test test test, omega"
    edit_start = previous_text.index(",")
    next_text = previous_text[:edit_start] + previous_text[edit_start + 1 :]
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert result is None
    assert layout.last_incremental_reflow_rejection_reason in {
        "tag_keep_group",
        "fragment_edit_not_supported",
    }


def test_projection_layout_applies_same_length_plain_replacement_incrementally() -> (
    None
):
    """Plain same-line replacement should publish real layout without full relayout."""

    previous_text = "alpha beta gamma"
    edit_start = previous_text.index("b")
    next_text = f"{previous_text[:edit_start]}z{previous_text[edit_start + 1 :]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="z",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert layout.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_incremental_plain_edit_matches_full_rebuild_geometry() -> (
    None
):
    """Incremental same-line text edits should match full rebuild row geometry."""

    previous_text = "alpha beta gamma delta"
    edit_start = previous_text.index("beta")
    next_text = f"{previous_text[:edit_start]}bravo{previous_text[edit_start + 4 :]}"
    incremental_layout, _ = _layout_for(previous_text, text_width=96.0)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=96.0)

    result = incremental_layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 4,
        replacement_text="bravo",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_applies_same_line_plain_selection_delete_incrementally() -> (
    None
):
    """Plain same-line selection delete should update geometry without full relayout."""

    previous_text = "alpha removable beta gamma"
    edit_start = previous_text.index("removable ")
    edit_end = edit_start + len("removable ")
    next_text = f"{previous_text[:edit_start]}{previous_text[edit_end:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert layout.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_trailing_insert_after_shifted_fragment_does_not_crash() -> (
    None
):
    """Trailing insert should handle fragments shifted by prior same-line edits."""

    previous_text = "alpha beta gamma"
    first_next_text = "alpha Xbeta gamma"
    second_next_text = f"{first_next_text}!"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    first_document_view, first_projection = _projection_for(first_next_text)

    first_result = layout.try_apply_same_line_plain_text_edit(
        first_projection,
        prompt_document_view=first_document_view,
        edit_start=len("alpha "),
        edit_end=len("alpha "),
        replacement_text="X",
        first_dirty_projection_position=len("alpha "),
    )

    assert first_result is not None
    second_document_view, second_projection = _projection_for(second_next_text)

    assert layout.try_apply_trailing_plain_insert(
        second_projection,
        prompt_document_view=second_document_view,
    )
    assert layout.projection_document.source_text == second_next_text
    assert _line_texts(layout) == (second_next_text,)


def test_projection_layout_trailing_insert_derives_caret_rects_from_lines() -> None:
    """Trailing insert should not clone the prior caret-rect map on the hot path."""

    previous_text = "alpha beta gamma"
    next_text = f"{previous_text}!"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    _install_non_iterable_caret_rect_mapping(layout)
    next_document_view, next_projection = _projection_for(next_text)

    assert layout.try_apply_trailing_plain_insert(
        next_projection,
        prompt_document_view=next_document_view,
    )
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_rejects_trailing_comma_insert_that_creates_keep_group() -> (
    None
):
    """Trailing comma insertion should reflow when it creates kept-tag semantics."""

    previous_text = "1girl"
    next_text = f"{previous_text},"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    assert (
        layout.try_apply_trailing_plain_insert(
            next_projection,
            prompt_document_view=next_document_view,
        )
        is False
    )
    assert layout.projection_document.source_text == previous_text


def test_projection_layout_trailing_newline_after_shifted_line_does_not_crash() -> None:
    """Trailing newline should handle line snapshots shifted by prior edits."""

    previous_text = "alpha beta gamma"
    first_next_text = "alpha Xbeta gamma"
    second_next_text = f"{first_next_text}\n"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    first_document_view, first_projection = _projection_for(first_next_text)

    first_result = layout.try_apply_same_line_plain_text_edit(
        first_projection,
        prompt_document_view=first_document_view,
        edit_start=len("alpha "),
        edit_end=len("alpha "),
        replacement_text="X",
        first_dirty_projection_position=len("alpha "),
    )

    assert first_result is not None
    second_document_view, second_projection = _projection_for(second_next_text)

    assert layout.try_apply_trailing_newline_insert(
        second_projection,
        prompt_document_view=second_document_view,
    )
    assert layout.projection_document.source_text == second_next_text
    assert _line_texts(layout) == (first_next_text, "")


def test_projection_layout_trailing_newline_derives_caret_rects_from_lines() -> None:
    """Trailing newline should install line-owned caret rects without map cloning."""

    previous_text = "alpha beta gamma"
    next_text = f"{previous_text}\n"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    _install_non_iterable_caret_rect_mapping(layout)
    next_document_view, next_projection = _projection_for(next_text)

    assert layout.try_apply_trailing_newline_insert(
        next_projection,
        prompt_document_view=next_document_view,
    )
    assert _line_texts(layout) == (previous_text, "")
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_middle_newline_insert_uses_incremental_layout() -> None:
    """Middle newline insert should split a plain line without full relayout."""

    previous_text = "alpha beta"
    edit_start = len("alpha")
    next_text = f"{previous_text[:edit_start]}\n{previous_text[edit_start:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="\n",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert result.content_height_changed is True
    assert layout.projection_document.source_text == next_text
    assert _line_texts(layout) == ("alpha", " beta")
    first_line = layout._snapshot.lines[0]  # noqa: SLF001
    second_line = layout._snapshot.lines[1]  # noqa: SLF001
    assert first_line.line_break_start == edit_start
    assert first_line.line_break_end == edit_start + 1
    assert second_line.source_start == edit_start + 1


def test_projection_layout_middle_newline_insert_keeps_downstream_lines_lazy() -> None:
    """Middle newline insert should not materialize every downstream visual line."""

    previous_text = "alpha beta\ngamma delta\nomega"
    edit_start = len("alpha")
    next_text = f"{previous_text[:edit_start]}\n{previous_text[edit_start:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    previous_downstream_line = layout._snapshot.lines[1]  # noqa: SLF001
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="\n",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    shifted_downstream_line = layout._snapshot.lines[2]  # noqa: SLF001
    assert shifted_downstream_line.__class__.__name__ == "_ShiftedLineSnapshot"
    assert shifted_downstream_line.top == previous_downstream_line.top + (
        layout._snapshot.lines[1].height  # noqa: SLF001
    )
    assert (
        shifted_downstream_line.source_start
        == previous_downstream_line.source_start + 1
    )
    assert shifted_downstream_line.fragments[0].source_positions[0] == (
        previous_downstream_line.fragments[0].source_positions[0] + 1
    )


def test_projection_layout_middle_newline_delete_uses_incremental_layout() -> None:
    """Middle newline delete should join adjacent plain lines without full relayout."""

    previous_text = "alpha\nbeta"
    edit_start = len("alpha")
    next_text = "alphabeta"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert result is not None
    assert result.content_height_changed is True
    assert layout.projection_document.source_text == next_text
    assert _line_texts(layout) == ("alphabeta",)
    joined_line = layout._snapshot.lines[0]  # noqa: SLF001
    assert joined_line.line_break_start is None
    assert joined_line.line_break_end is None


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
    token_rect = layout.token_rect(token, scroll_offset=0.0)

    assert token_rect is not None
    assert token_rect.width() == layout.measure_token(token).width()


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
    prefix_fragment = layout._snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[0].run_id
    )[0]
    content_fragment = layout._snapshot.text_fragments_for_run(token_runs[1].run_id)[  # noqa: SLF001
        0
    ]
    suffix_fragment = layout._snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[2].run_id
    )[0]

    assert token.content_start is not None
    assert token.content_end is not None

    leading_state = layout.hit_test(
        prefix_fragment.rect.center(),
        scroll_offset=0.0,
    )
    content_start_state = layout.hit_test(
        QPointF(content_fragment.rect.left() + 1.0, content_fragment.rect.center().y()),
        scroll_offset=0.0,
    )
    after_c_state = layout.hit_test(
        layout.cursor_rect(
            projection.caret_map.state_for_source_position(token.content_start + 1),
            scroll_offset=0.0,
        ).center(),
        scroll_offset=0.0,
    )
    after_a_state = layout.hit_test(
        layout.cursor_rect(
            projection.caret_map.state_for_source_position(token.content_start + 2),
            scroll_offset=0.0,
        ).center(),
        scroll_offset=0.0,
    )
    content_end_state = layout.hit_test(
        QPointF(suffix_fragment.rect.left() + 1.0, suffix_fragment.rect.center().y()),
        scroll_offset=0.0,
    )
    trailing_state = layout.hit_test(
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

    leading_rect = layout.cursor_rect(
        projection.caret_map.state_for_source_position(token.source_start),
        scroll_offset=0.0,
    )
    content_start_rect = layout.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_start),
        scroll_offset=0.0,
    )
    after_c_rect = layout.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_start + 1),
        scroll_offset=0.0,
    )
    content_end_rect = layout.cursor_rect(
        projection.caret_map.state_for_source_position(token.content_end),
        scroll_offset=0.0,
    )
    trailing_rect = layout.cursor_rect(
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
    token_rect = layout.token_rect(token, scroll_offset=0.0)
    assert token_rect is not None
    assert token.content_start is not None
    assert token.content_end is not None

    partial_selection_rects = layout.selection_rects(
        PromptProjectionSelection(
            anchor_position=token.content_start,
            cursor_position=token.content_end - 1,
        )
    )
    whole_token_rects = layout.selection_rects(
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


def test_projection_layout_selection_rects_include_selected_empty_lines() -> None:
    """Selected blank visual rows should expose one synthetic highlight rect."""

    layout, _ = _layout_for("alpha\n\nbeta")
    blank_line = next(line for line in layout._snapshot.lines if not line.fragments)  # noqa: SLF001

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(anchor_position=6, cursor_position=7)
    )

    assert any(abs(rect.top() - blank_line.top) < 1.0 for rect in selection_rects)
    blank_line_rect = next(
        rect for rect in selection_rects if abs(rect.top() - blank_line.top) < 1.0
    )
    assert blank_line_rect.width() >= 8.0


def test_projection_line_snapshots_distinguish_content_from_line_break() -> None:
    """Hard-wrapped lines should expose visible content and newline boundaries."""

    layout, _ = _layout_for("alpha\nbeta")
    first_line = layout._snapshot.lines[0]  # noqa: SLF001
    second_line = layout._snapshot.lines[1]  # noqa: SLF001

    assert first_line.source_content_start == 0
    assert first_line.source_content_end == 5
    assert first_line.line_break_start == 5
    assert first_line.line_break_end == 6
    assert second_line.source_content_start == 6
    assert second_line.source_content_end == 10
    assert second_line.line_break_start is None
    assert second_line.line_break_end is None


def test_projection_layout_selection_rects_show_selected_line_break() -> None:
    """Selected hard line breaks should visibly extend the selected source range."""

    layout, _ = _layout_for("alpha\nbeta")
    first_line = layout._snapshot.lines[0]  # noqa: SLF001
    first_fragment = first_line.fragments[0]

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(anchor_position=0, cursor_position=6)
    )

    first_line_right = max(
        rect.right()
        for rect in selection_rects
        if abs(rect.top() - first_line.top) < 1.0
    )
    assert first_line_right > first_fragment.rect.right() + 4.0


def test_projection_layout_selection_rects_do_not_invent_soft_wrap_breaks() -> None:
    """Soft-wrapped line ends should not receive hard-line-break selection affordances."""

    layout, _ = _layout_for("alpha beta gamma delta epsilon zeta eta theta")
    first_line = layout._snapshot.lines[0]  # noqa: SLF001
    first_line_content_right = max(
        fragment.rect.right() for fragment in first_line.fragments
    )

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(
            anchor_position=first_line.source_start,
            cursor_position=first_line.source_end,
        )
    )

    first_line_right = max(
        rect.right()
        for rect in selection_rects
        if abs(rect.top() - first_line.top) < 1.0
    )
    assert first_line.line_break_start is None
    assert first_line.line_break_end is None
    assert first_line_right <= first_line_content_right + 1.0


def test_projection_layout_selection_rects_include_empty_line_at_active_boundary() -> (
    None
):
    """Landing the selection endpoint on an empty row should still paint that row."""

    layout, _ = _layout_for("alpha\n\nbeta")
    blank_line = next(line for line in layout._snapshot.lines if not line.fragments)  # noqa: SLF001

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(anchor_position=0, cursor_position=6)
    )

    assert any(abs(rect.top() - blank_line.top) < 1.0 for rect in selection_rects)


def test_projection_layout_selection_rects_ignore_empty_line_anchor_boundary() -> None:
    """Starting on an empty row should not paint it when selecting the previous break."""

    layout, _ = _layout_for("\n\n")
    anchored_line = layout._snapshot.lines[1]  # noqa: SLF001

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(anchor_position=1, cursor_position=0)
    )

    assert selection_rects
    assert all(abs(rect.top() - anchored_line.top) >= 1.0 for rect in selection_rects)


def test_projection_layout_selection_rects_exclude_blank_line_before_next_line_start() -> (
    None
):
    """Selecting from the next line's first column should not highlight the blank row above."""

    layout, _ = _layout_for("some, prompt, tags,\n\nblue and pink,\n")
    blank_line = next(
        line
        for line in layout._snapshot.lines  # noqa: SLF001
        if not line.fragments and line.source_end == 21
    )

    selection_rects = layout.selection_rects(
        PromptProjectionSelection(anchor_position=21, cursor_position=34)
    )

    assert all(abs(rect.top() - blank_line.top) >= 1.0 for rect in selection_rects)


def test_projection_layout_source_range_fragments_do_not_include_empty_line_selection_affordances() -> (
    None
):
    """Source-range fragments should exclude synthetic blank-line selection geometry."""

    layout, _ = _layout_for("alpha\n\nbeta, gamma")
    blank_line = next(line for line in layout._snapshot.lines if not line.fragments)  # noqa: SLF001

    fragments = layout.source_range_fragments(
        7,
        11,
        viewport_rect=QRectF(0.0, 0.0, 360.0, 220.0),
        scroll_offset=0.0,
    )

    assert fragments
    assert all(abs(rect.top() - blank_line.top) >= 1.0 for rect in fragments)
    assert len(fragments) == 1


def test_projection_layout_builds_one_reorder_chip_geometry_for_escaped_weight_text() -> (
    None
):
    """Escaped numeric-looking chip text should not split semantic chip identity."""

    prompt_text = (
        r"see-through white dress, lace trim, center opening, sparkling dress, "
        r"black underbust \(ribbon:1.20\), see-through silhouette, short dress, "
        r"bare legs, sleeveless, bare arms, pink eyes,"
    )
    layout, _projection = _layout_for(prompt_text, text_width=170.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )

    snapshot = layout.reorder_chip_geometry_snapshot(
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )
    target_geometry = snapshot.geometries_by_chip_index[target_chip.index]

    assert target_geometry.chip_index == target_chip.index
    assert target_geometry.rendered_start == target_chip.selection_start
    assert target_geometry.rendered_end == target_chip.selection_end
    assert not target_geometry.chrome_path.isEmpty()
    assert tuple(
        chip_index
        for chip_index in snapshot.ordered_chip_indices
        if chip_index == target_chip.index
    ) == (target_chip.index,)


def test_projection_layout_builds_one_reorder_chip_geometry_for_emphasis_weight() -> (
    None
):
    """Projected emphasis suffix renderers should not create extra chip identities."""

    prompt_text = "alpha, black underbust (ribbon:1.20), gamma"
    layout, _projection = _layout_for(prompt_text, text_width=150.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )
    range_start, range_end = rendered_ranges[target_chip.index]
    fragments = layout.source_range_fragments(
        range_start,
        range_end,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )

    snapshot = layout.reorder_chip_geometry_snapshot(
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )

    assert len(fragments) > 1
    assert target_chip.index in snapshot.geometries_by_chip_index
    assert snapshot.geometries_by_chip_index[target_chip.index].chip_index == (
        target_chip.index
    )


def test_projection_layout_reorder_placement_uses_chip_geometry_visual_lines() -> None:
    """Placement lanes should be derived from the same chip geometry as paint."""

    prompt_text = r"alpha, black underbust \(ribbon:1.20\), gamma"
    layout, _projection = _layout_for(prompt_text, text_width=115.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )
    viewport_rect = QRectF(0.0, 0.0, 180.0, 240.0)
    chip_snapshot = layout.reorder_chip_geometry_snapshot(
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    target_geometry = chip_snapshot.geometries_by_chip_index[target_chip.index]

    placement_snapshot = layout.reorder_placement_snapshot(
        layout_view=layout_view,
        chip_geometry_snapshot=chip_snapshot,
        gap_ranges_by_index={},
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    adjacent_line_indices = {
        placement.placement_id.visual_line_index
        for placement in placement_snapshot.placements
        if isinstance(placement.target, PromptLineDropTarget)
        and target_chip.index in placement.adjacent_chip_indices
    }

    assert len(target_geometry.visual_lines) > 1
    assert {
        line.visual_line_index for line in target_geometry.visual_lines
    } <= adjacent_line_indices


def test_projection_layout_reports_full_width_scene_region_rows() -> None:
    """Scene zebra geometry should cover rows without relying on title chrome."""

    text = "**portrait\none\n**cafe\ntwo"
    layout, _ = _layout_for(text, text_width=320.0)
    viewport_rect = QRectF(0.0, 0.0, 320.0, 160.0)

    rects = layout.source_range_row_rects(
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
    layout, projection = _layout_for(
        "**hands\ndetail",
        scene_error_keys=frozenset({"hands"}),
        semantic_palette=SemanticPalette(
            accent=RgbColor(1, 2, 3),
            error_foreground=error_color,
            warning_foreground=RgbColor(90, 120, 10),
        ),
    )
    token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    fragment = next(
        fragment
        for fragment in layout._snapshot.text_fragments  # noqa: SLF001
        if fragment.token_id == token.token_id
    )

    assert layout._painter.font_for_fragment(fragment).weight() > QFont().weight()  # noqa: SLF001
    assert layout._painter.text_color_for_fragment(fragment) == QColor(  # noqa: SLF001
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
        for fragment in layout._snapshot.text_fragments  # noqa: SLF001
        if fragment.token_id == token.token_id
    )
    assert token.content_end is not None

    bold_font = layout._painter.font_for_fragment(fragment)  # noqa: SLF001
    regular_font = QFont()
    bold_advance = QFontMetricsF(bold_font).horizontalAdvance(title)
    regular_advance = QFontMetricsF(regular_font).horizontalAdvance(title)
    title_end_rect = layout.cursor_rect(
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
        for fragment in layout._snapshot.text_fragments  # noqa: SLF001
        if fragment.token_id == token.token_id
    )

    assert token.active is True
    assert layout._painter.text_color_for_fragment(fragment) == layout._palette.color(  # noqa: SLF001
        QPalette.ColorRole.Text
    )


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
        for fragment in layout._snapshot.text_fragments  # noqa: SLF001
        if fragment.token_id == token.token_id
    )

    assert token.decoration_accented is True
    assert _emphasis_parenthesis_color(layout._palette, token) != layout._palette.color(  # noqa: SLF001
        QPalette.ColorRole.Text
    )
    assert _emphasis_weight_color(layout._palette) == layout._palette.color(  # noqa: SLF001
        QPalette.ColorRole.Text
    )
    assert layout._painter.text_color_for_fragment(fragment) == layout._palette.color(  # noqa: SLF001
        QPalette.ColorRole.Text
    )


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
        for fragment in layout._snapshot.inline_object_fragments  # noqa: SLF001
        if fragment.token_id == token.token_id
    ]

    assert emphasis_decoration_fragments
    assert all(
        layout._inline_object_fragment_is_selected(  # noqa: SLF001
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

    fragments = layout.source_range_fragments(
        token.source_start,
        token.source_end,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    anchor_rect = layout.token_anchor_rect(token, scroll_offset=0.0)

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
    suffix_fragment = layout._snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[2].run_id
    )[0]
    anchor_rect = layout.token_anchor_rect(token, scroll_offset=0.0)

    assert anchor_rect is not None
    assert anchor_rect.left() - suffix_fragment.rect.left() < (
        suffix_fragment.rect.width() * 0.35
    )
    assert anchor_rect.width() < (suffix_fragment.rect.width() * 0.75)
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
    prefix_fragment = layout._snapshot.inline_object_fragments_for_run(  # noqa: SLF001
        token_runs[0].run_id
    )[0]
    content_fragment = layout._snapshot.text_fragments_for_run(token_runs[1].run_id)[  # noqa: SLF001
        0
    ]
    anchor_rect = layout.token_anchor_rect(token, scroll_offset=0.0)
    assert anchor_rect is not None

    decoration_metrics = _emphasis_decoration_metrics(layout._base_font)  # noqa: SLF001
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

    fragments = layout.source_range_fragments(
        segment_start,
        segment_end,
        viewport_rect=QRectF(0.0, 0.0, 480.0, 80.0),
        scroll_offset=0.0,
    )
    token_rect = layout.token_rect(token, scroll_offset=0.0)

    assert len(fragments) == 1
    assert token_rect is not None
    assert fragments[0].left() < token_rect.left()
    assert fragments[0].right() > token_rect.right()


def test_projection_layout_uses_qfluent_document_margin_for_plain_text_geometry() -> (
    None
):
    """Plain-text caret geometry should include the QFluent document left inset."""

    layout, _projection = _layout_for("alpha")
    fragments = layout.source_range_fragments(
        0,
        1,
        viewport_rect=QRectF(0.0, 0.0, 220.0, 80.0),
        scroll_offset=0.0,
    )

    assert layout.document_margin == 4.0
    assert fragments[0].left() >= 4.0
