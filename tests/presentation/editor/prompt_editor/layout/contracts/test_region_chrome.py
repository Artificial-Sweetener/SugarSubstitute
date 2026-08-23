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


import pytest

from PySide6.QtGui import QColor, QFont, QFontMetricsF

from substitute.domain.appearance import RgbColor, SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.region_chrome import (
    PromptRegionChrome,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


@pytest.mark.parametrize(
    ("source", "separator_count"),
    (
        ("ordinary prompt", 0),
        ("[SEP]\n", 1),
        ("global\n[SEP]\nregional", 1),
        ("global\n[SEP]\n[SEP]\nregional", 2),
        ("[SEP]\nfirst\n[SEP]\n", 2),
        ("global\n\n[SEP]\n\nfirst\n\n[SEP]\n\nsecond", 2),
    ),
    ids=(
        "ordinary",
        "terminal",
        "single",
        "adjacent",
        "leading-and-terminal",
        "multiple-with-blanks",
    ),
)
@pytest.mark.parametrize(
    "display_mode",
    (PromptProjectionDisplayMode.PROJECTED, PromptProjectionDisplayMode.RAW),
)
def test_region_structure_mode_and_topology_matrix(
    source: str,
    separator_count: int,
    display_mode: PromptProjectionDisplayMode,
) -> None:
    """Raw and rich owners must agree for every separator topology shape."""

    layout, projection = _layout_for(source, display_mode=display_mode)
    chrome = PromptRegionChrome()
    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )
    region_tokens = tuple(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    structural_runs = tuple(
        run
        for run in projection.runs
        if run.kind is PromptProjectionRunKind.STRUCTURAL_ROW
    )

    if display_mode is PromptProjectionDisplayMode.RAW:
        assert projection.projection_text == source
        assert region_tokens == ()
        assert structural_runs == ()
        assert snapshot.divider_lines == ()
        assert snapshot.rail_lines == ()
        assert snapshot.visited_line_count == 0
        return

    assert len(region_tokens) == separator_count
    assert len(structural_runs) == separator_count
    assert len(snapshot.divider_lines) == separator_count
    assert len(snapshot.rail_lines) == separator_count
    assert projection.projection_text.count("\ufffc") == separator_count
    assert "[SEP]" not in projection.projection_text


def test_region_chrome_prepares_centered_dividers_and_continuous_rails_once() -> None:
    """Chrome geometry should be centered and derived in one pass over visual lines."""

    layout, _projection = _layout_for(
        "global\n[SEP]\nfirst line that wraps across width\n[SEP]\nsecond"
    )
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert len(snapshot.divider_lines) == 2
    assert len(snapshot.rail_lines) == 2
    assert snapshot.visited_line_count == layout.frame.output.snapshot.line_count()
    expected_center = (
        layout.frame.output.configuration.metrics.content_left
        + layout.frame.output.configuration.metrics.content_width / 2.0
    )
    expected_width = min(
        36.0, layout.frame.output.configuration.metrics.content_width * 0.2
    )
    assert all(
        divider.center().x() == pytest.approx(expected_center)
        and divider.length() == pytest.approx(expected_width)
        for divider in snapshot.divider_lines
    )
    assert all(rail.x1() == rail.x2() for rail in snapshot.rail_lines)
    assert chrome.prepare_count == 1


def test_region_chrome_renders_normal_bold_titles_between_region_rules() -> None:
    """Named separators should use normal text styling and distinct rule colors."""

    layout, _projection = _layout_for(
        "global\n[SEP|Subject]\nfirst\n[SEP|Background]\nsecond"
    )
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert tuple(label.text for label in snapshot.labels) == (
        "Subject",
        "Background",
    )
    assert len(snapshot.strokes) == 2
    assert snapshot.strokes[0].pen.color() != snapshot.strokes[1].pen.color()
    assert all(len(stroke.lines) == 3 for stroke in snapshot.strokes)
    for divider, stroke in zip(snapshot.divider_lines, snapshot.strokes, strict=True):
        assert tuple(line.length() for line in stroke.lines[1:]) == pytest.approx(
            (divider.length(), divider.length())
        )
    assert all(
        QFontMetricsF(label.font).height() <= label.rect.height()
        for label in snapshot.labels
    )
    base_font = layout.frame.output.configuration.base_font
    assert all(label.color == _REGION_TEXT_COLOR for label in snapshot.labels)
    assert all(label.font.weight() == QFont.Weight.Bold for label in snapshot.labels)
    assert all(
        label.font.pointSizeF() == pytest.approx(base_font.pointSizeF())
        and label.font.pixelSize() == base_font.pixelSize()
        for label in snapshot.labels
    )
    assert all(target.color == _REGION_TEXT_COLOR for target in snapshot.edit_targets)


def test_region_chrome_hover_emphasizes_one_region_without_relayout() -> None:
    """Transient linked hover should reuse geometry and only strengthen one stroke."""

    layout, _projection = _layout_for("global\n[SEP]\nfirst\n[SEP]\nsecond")
    chrome = PromptRegionChrome()
    palette = SemanticPalette(
        accent=RgbColor(20, 80, 160),
        error_foreground=RgbColor(180, 20, 20),
        warning_foreground=RgbColor(180, 140, 20),
    )
    chrome.prepare_active(
        layout.frame.output,
        semantic_palette=palette,
        text_color=_REGION_TEXT_COLOR,
    )
    baseline = chrome.active_snapshot
    assert baseline is not None
    baseline_widths = tuple(stroke.pen.widthF() for stroke in baseline.strokes)
    prepare_count = chrome.prepare_count

    assert chrome.set_hovered_region(1) is True

    hovered = chrome.active_snapshot
    assert hovered is not None
    assert hovered.strokes[0].pen.widthF() == baseline_widths[0]
    assert hovered.strokes[1].pen.widthF() > baseline_widths[1]
    assert hovered.strokes[1].lines == baseline.strokes[1].lines
    assert chrome.prepare_count == prepare_count

    assert chrome.set_hovered_region(None) is True
    assert chrome.active_snapshot is baseline


def test_region_chrome_reflows_framing_rules_while_title_draft_changes() -> None:
    """Uncommitted title text should resize its editor and rules without relayout."""

    layout, _projection = _layout_for("global\n[SEP|A]\nregion")
    chrome = PromptRegionChrome()
    palette = SemanticPalette(
        accent=RgbColor(20, 80, 160),
        error_foreground=RgbColor(180, 20, 20),
        warning_foreground=RgbColor(180, 140, 20),
    )
    chrome.prepare_active(
        layout.frame.output,
        semantic_palette=palette,
        text_color=_REGION_TEXT_COLOR,
    )
    prepare_count = chrome.prepare_count

    assert chrome.set_editing_region(0) is True
    assert chrome.set_editing_region_draft(0, "A") is True
    short = chrome.active_snapshot
    assert short is not None
    short_target = short.edit_targets[0]
    short_rules = short.strokes[0].lines[-2:]

    assert chrome.set_editing_region_draft(0, "A much longer region title") is True
    long = chrome.active_snapshot
    assert long is not None
    long_target = long.edit_targets[0]
    long_rules = long.strokes[0].lines[-2:]

    assert long_target.width > short_target.width
    assert long_rules[0].x2() < short_rules[0].x2()
    assert long_rules[1].x1() > short_rules[1].x1()
    assert tuple(line.length() for line in long_rules) == pytest.approx(
        (long_target.rule_length, long_target.rule_length)
    )
    assert chrome.prepare_count == prepare_count
    assert long.labels == ()


def test_region_chrome_renders_rail_for_empty_terminal_partition() -> None:
    """A terminal separator should expose its empty regional input row."""

    layout, _projection = _layout_for("global\n[SEP]\n")
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert len(snapshot.divider_lines) == 1
    assert len(snapshot.rail_lines) == 1
    assert snapshot.rail_lines[0].length() == pytest.approx(
        layout.frame.output.configuration.metrics.initial_row_height()
    )


def test_region_chrome_skips_line_scan_for_ordinary_prompts() -> None:
    """Prompts without regional structure should add no line-walking cost."""

    layout, _projection = _layout_for("ordinary prompt\nwith several lines")
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert snapshot.visited_line_count == 0
    assert snapshot.paint_lines == ()


def test_region_chrome_uses_boundary_lookups_for_long_regional_prompts() -> None:
    """Regional chrome preparation must not scan every visual content line."""

    regional_lines = "\n".join(
        f"regional line {index}, detailed background and lighting"
        for index in range(400)
    )
    layout, _projection = _layout_for(
        f"global\n[SEP]\n{regional_lines}\n[SEP]\nterminal",
        text_width=180.0,
    )
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert len(snapshot.divider_lines) == 2
    assert len(snapshot.rail_lines) == 2
    assert layout.frame.output.snapshot.line_count() > 800
    assert snapshot.visited_line_count < 64
    assert snapshot.visited_line_count * 10 < layout.frame.output.snapshot.line_count()


def test_region_chrome_skips_raw_region_structure_without_preparation() -> None:
    """Raw source mode must not derive or retain any regional paint geometry."""

    layout, _projection = _layout_for(
        "global\n[SEP]\nregional",
        display_mode=PromptProjectionDisplayMode.RAW,
    )
    chrome = PromptRegionChrome()

    snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=SemanticPalette(
            accent=RgbColor(20, 80, 160),
            error_foreground=RgbColor(180, 20, 20),
            warning_foreground=RgbColor(180, 140, 20),
        ),
        text_color=_REGION_TEXT_COLOR,
    )

    assert snapshot.divider_lines == ()
    assert snapshot.rail_lines == ()
    assert snapshot.paint_lines == ()
    assert snapshot.visited_line_count == 0
    assert chrome.prepare_count == 0


def test_region_chrome_reuses_empty_snapshot_for_ordinary_prompt_syncs() -> None:
    """Repeated ordinary layout syncs should add no separator preparation work."""

    layout, _projection = _layout_for("ordinary prompt\nwith several lines")
    chrome = PromptRegionChrome()
    palette = SemanticPalette(
        accent=RgbColor(20, 80, 160),
        error_foreground=RgbColor(180, 20, 20),
        warning_foreground=RgbColor(180, 140, 20),
    )

    first_snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=palette,
        text_color=_REGION_TEXT_COLOR,
    )
    second_snapshot = chrome.prepare(
        layout.frame.output,
        semantic_palette=palette,
        text_color=_REGION_TEXT_COLOR,
    )

    assert second_snapshot is first_snapshot
    assert chrome.prepare_count == 1
