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

"""Verify authored separator editing and rich-mode projection behavior."""

from __future__ import annotations

from PySide6.QtCore import Qt

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_adjacent_separator_region_accepts_text_without_collapsing(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep both partitions when typing into their empty shared region."""

    source = "global\n[SEP]\n[SEP]\nregional"
    insertion_position = source.rindex("[SEP]")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, insertion_position)

    real_shell_scenario.input.type_text(field, "middle")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="adjacent-region-populated",
    )

    assert after.source_text == "global\n[SEP]\nmiddle\n[SEP]\nregional"
    assert after.cursor_position == len("global\n[SEP]\nmiddle")
    assert after.projection_region_separator_count == 2
    assert after.region_chrome_divider_count == 2
    assert after.region_chrome_rail_count == 2
    assert not snapshot_invariant_violations(after)


def test_real_shell_typing_after_separator_completion_starts_regional_line(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Continue typing in the newly created regional section after `[SEP]`."""

    source = "global\n[SEP]\n"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, len(source))

    real_shell_scenario.input.type_text(field, "[SEP]jfklasfjal")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="separator-followed-by-regional-text",
    )

    assert after.source_text == "global\n[SEP]\n[SEP]\njfklasfjal"
    assert after.cursor_position == len(after.source_text)
    assert after.document_view_region_separator_count == 2
    assert after.projection_region_separator_count == 2
    assert after.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in after.projection_text
    assert after.region_chrome_divider_count == 2
    assert after.region_chrome_rail_count == 2
    assert not snapshot_invariant_violations(after)


def test_real_shell_terminal_separator_immediately_renders_empty_region_rail(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Render a terminal separator's empty regional row immediately."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="global\n[SEP"
    )
    real_shell_scenario.input.set_source_cursor_position(field, len("global\n[SEP"))

    immediate = real_shell_scenario.input.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_BracketRight,
        label="terminal-separator-empty-region-immediate",
    )
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="terminal-separator-empty-region-settled",
    )

    for snapshot in (immediate, settled):
        assert snapshot.source_text == "global\n[SEP]\n"
        assert snapshot.cursor_position == len(snapshot.source_text)
        assert snapshot.document_view_region_separator_count == 1
        assert snapshot.projection_region_separator_count == 1
        assert snapshot.region_chrome_divider_count == 1
        assert snapshot.region_chrome_rail_count == 1
    assert not snapshot_invariant_violations(settled)


def test_real_shell_raw_mode_has_literal_separator_and_no_regional_chrome(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose literal source without structural chrome in raw mode."""

    source = "global\n[SEP]\nregional"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    rich = real_shell_scenario.snapshots.capture(field, label="separator-rich-mode")

    real_shell_scenario.input.set_rich_rendering(field, enabled=False)
    raw = real_shell_scenario.snapshots.capture(field, label="separator-raw-mode")

    assert raw.display_mode == "raw"
    assert raw.source_text == source
    assert raw.projection_text == source
    assert raw.projection_token_count == 0
    assert not any(row.is_structural for row in raw.visible_layout_rows), (
        raw.active_projection_text,
        raw.layout_projection_text,
        raw.layout_uses_projection_document,
        raw.layout_uses_active_projection_document,
        raw.visible_layout_rows,
    )
    assert raw.region_chrome_divider_count == 0
    assert raw.region_chrome_rail_count == 0
    assert raw.region_chrome_visited_line_count == 0
    assert raw.region_chrome_prepare_count == rich.region_chrome_prepare_count
    assert not snapshot_invariant_violations(raw)


def test_real_shell_raw_caret_inside_marker_resolves_when_rich_mode_returns(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Resolve a raw caret inside `[SEP]` to one visible rich-mode edge."""

    source = "global\n[SEP]\nregional"
    separator_start = source.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_rich_rendering(field, enabled=False)
    real_shell_scenario.input.set_source_cursor_position(field, separator_start + 2)
    raw = real_shell_scenario.snapshots.capture(
        field,
        label="raw-caret-inside-separator",
    )

    real_shell_scenario.input.set_rich_rendering(field, enabled=True)
    rich = real_shell_scenario.snapshots.capture(
        field,
        label="rich-caret-after-raw-separator",
    )

    assert raw.cursor_position == separator_start + 2
    assert raw.caret_state_placement == "plain_text"
    assert rich.cursor_position in {separator_start, separator_end}
    assert not rich.caret_inside_region_separator
    assert rich.region_chrome_divider_count == 1
    assert not snapshot_invariant_violations(rich)
