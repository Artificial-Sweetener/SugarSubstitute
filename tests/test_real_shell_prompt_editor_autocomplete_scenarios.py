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

"""Known prompt editor interaction scenarios driven through the real shell."""

from __future__ import annotations

from collections.abc import Iterator
import os
from typing import Any, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from tests.real_shell_prompt_editor_harness import (
    RealShellPromptEditorHarness,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt editor shell harness requires non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def harness() -> Iterator[RealShellPromptEditorHarness]:
    """Create and close a real-shell prompt editor harness."""

    shell_harness = RealShellPromptEditorHarness()
    try:
        yield shell_harness
    finally:
        shell_harness.close()


def test_real_shell_autocomplete_tab_does_not_insert_literal_tab(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Accept active autocomplete on Tab without writing a literal tab."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-tab")
    route = harness.press_key(field, Qt.Key.Key_Tab, text="\t")
    after = harness.capture_state_snapshot(field, label="after-tab")
    violations = harness.transition_invariant_violations(
        action_name="tab",
        before=before,
        after=after,
    )

    if violations or route.inserted_text == "\t":
        artifact = harness.save_artifacts(
            "tab-inserted-literal-tab",
            before=before,
            after=after,
            invariant="Tab with active autocomplete must not insert a literal tab.",
            observed=f"violations={violations}; source after Tab was {after.source_text!r}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert "\t" not in after.source_text
    assert after.source_text.startswith("re:zero kara hajimeru isekai seikatsu")


def test_real_shell_plain_tab_does_not_insert_literal_tab(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Consume plain Tab without mutating prompt source text."""

    field = harness.add_prompt_workflow(initial_text="")
    before = harness.capture_state_snapshot(field, label="before-plain-tab")
    harness.press_key(field, Qt.Key.Key_Tab, text="\t")
    after = harness.capture_state_snapshot(field, label="after-plain-tab")
    violations = harness.transition_invariant_violations(
        action_name="tab",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "plain-tab-inserted-literal-tab",
            before=before,
            after=after,
            invariant="Plain Tab must not insert a literal tab into prompt source.",
            observed=f"violations={violations}; source after Tab was {after.source_text!r}",
        )
        pytest.fail(f"plain Tab inserted a literal tab; artifacts: {artifact}")

    assert after.source_text == before.source_text


def test_real_shell_plain_escape_does_not_insert_control_character(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Consume plain Escape without mutating prompt source text."""

    field = harness.add_prompt_workflow(initial_text="")
    before = harness.capture_state_snapshot(field, label="before-plain-escape")
    harness.press_key(field, Qt.Key.Key_Escape)
    after = harness.capture_state_snapshot(field, label="after-plain-escape")
    violations = harness.transition_invariant_violations(
        action_name="escape",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "plain-escape-inserted-control-character",
            before=before,
            after=after,
            invariant="Plain Escape must not insert a control character.",
            observed=f"violations={violations}; source after Escape was {after.source_text!r}",
        )
        pytest.fail(f"plain Escape inserted a control character; artifacts: {artifact}")

    assert after.source_text == before.source_text


def test_real_shell_newline_before_separator_preserves_regional_structure(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A newline in the global prompt must not destabilize the following separator."""

    source = (
        "blue decorative staff bow ribbon,  \n\n[SEP]\n"
        "grass, flower field, cloudy sky, pink petals, blue petals, "
        "mountainous horizon,    "
    )
    field = harness.add_prompt_workflow(initial_text=source)
    cursor_position = source.index("ribbon,") + len("ribbon,")
    harness.set_source_cursor_position(field, cursor_position)
    before = harness.capture_state_snapshot(field, label="before-global-newline")

    harness.press_key(field, Qt.Key.Key_Return)
    after = harness.capture_state_snapshot(field, label="after-global-newline")

    assert (
        after.source_text == source[:cursor_position] + "\n" + source[cursor_position:]
    )
    assert before.projection_text.count("\ufffc") == 1
    assert after.projection_text.count("\ufffc") == 1
    assert "[SEP]" not in after.projection_text
    assert not harness.transition_invariant_violations(
        action_name="newline",
        before=before,
        after=after,
    )


def test_real_shell_separator_completion_normalizes_in_one_undo_transaction(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Completing `[SEP]` should add both line breaks in the authored edit transaction."""

    field = harness.add_prompt_workflow(initial_text="global[SEP")
    harness.set_source_cursor_position(field, len("global[SEP"))

    harness.type_text(field, "]")
    normalized = harness.capture_state_snapshot(field, label="normalized-separator")
    harness.undo(field)
    undone = harness.capture_state_snapshot(field, label="undone-separator")

    assert normalized.source_text == "global\n[SEP]\n"
    assert normalized.projection_text.count("\ufffc") == 1
    assert undone.source_text == "global[SEP"
    assert not harness.invariant_violations(normalized)
    assert not harness.invariant_violations(undone)


@pytest.mark.parametrize(
    ("source", "cursor_position", "expected_source"),
    (
        (
            "global\n[SEP]\nregional",
            len("global\n[SEP]\n"),
            "global\n[SEP]\n[SEP]\nregional",
        ),
        (
            "global\n[SEP]\nregional alpha",
            len("global\n[SEP]\nregional"),
            "global\n[SEP]\nregional\n[SEP]\n alpha",
        ),
    ),
)
def test_real_shell_typing_second_separator_creates_new_region(
    harness: RealShellPromptEditorHarness,
    source: str,
    cursor_position: int,
    expected_source: str,
) -> None:
    """Typing `[SEP]` within a regional partition must create another partition."""

    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, cursor_position)

    harness.type_text(field, "[SEP]")
    after = harness.capture_state_snapshot(field, label="authored-second-separator")

    assert after.source_text == expected_source
    assert after.document_view_region_separator_count == 2
    assert after.projection_region_separator_count == 2
    assert after.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in after.projection_text
    assert sum(row.is_structural for row in after.visible_layout_rows) == 2
    assert not harness.invariant_violations(after)


def test_real_shell_second_separator_completion_publishes_adjacent_region_immediately(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Completing a nearby second marker must publish both partitions immediately."""

    source = "global\n[SEP]\n[SEPregional"
    completion_position = source.index("regional")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, completion_position)

    immediate = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_BracketRight,
        label="adjacent-second-separator-immediate",
    )
    settled = harness.capture_state_snapshot(
        field,
        label="adjacent-second-separator-settled",
    )

    for snapshot in (immediate, settled):
        assert snapshot.source_text == "global\n[SEP]\n[SEP]\nregional"
        assert snapshot.document_view_region_separator_count == 2
        assert snapshot.projection_region_separator_count == 2
        assert snapshot.projection_text.count("\ufffc") == 2
        assert "[SEP]" not in snapshot.projection_text
        assert sum(row.is_structural for row in snapshot.visible_layout_rows) == 2
    assert not harness.invariant_violations(settled)


def test_real_shell_adjacent_separator_region_accepts_text_without_collapsing(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Typing into the empty region between dividers must preserve both sections."""

    source = "global\n[SEP]\n[SEP]\nregional"
    insertion_position = source.rindex("[SEP]")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, insertion_position)

    harness.type_text(field, "middle")
    after = harness.capture_state_snapshot(field, label="adjacent-region-populated")

    assert after.source_text == "global\n[SEP]\nmiddle\n[SEP]\nregional"
    assert after.cursor_position == len("global\n[SEP]\nmiddle")
    assert after.projection_region_separator_count == 2
    assert after.region_chrome_divider_count == 2
    assert after.region_chrome_rail_count == 2
    assert not harness.invariant_violations(after)


def test_real_shell_typing_after_separator_completion_starts_regional_line(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Continued typing after `[SEP]` must enter its new regional section."""

    source = "global\n[SEP]\n"
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, len(source))

    harness.type_text(field, "[SEP]jfklasfjal")
    after = harness.capture_state_snapshot(
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
    assert not harness.invariant_violations(after)


def test_real_shell_terminal_separator_immediately_renders_empty_region_rail(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Completing a terminal marker must render its empty regional row immediately."""

    field = harness.add_prompt_workflow(initial_text="global\n[SEP")
    harness.set_source_cursor_position(field, len("global\n[SEP"))

    immediate = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_BracketRight,
        label="terminal-separator-empty-region-immediate",
    )
    settled = harness.capture_state_snapshot(
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
    assert not harness.invariant_violations(settled)


def test_real_shell_raw_mode_has_literal_separator_and_no_regional_chrome(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Raw mode must expose exact source without preparing structural chrome."""

    source = "global\n[SEP]\nregional"
    field = harness.add_prompt_workflow(initial_text=source)
    rich = harness.capture_state_snapshot(field, label="separator-rich-mode")

    harness.set_rich_rendering(field, enabled=False)
    raw = harness.capture_state_snapshot(field, label="separator-raw-mode")

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
    assert not harness.invariant_violations(raw)


def test_real_shell_raw_caret_inside_marker_resolves_when_rich_mode_returns(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A raw source caret inside `[SEP]` must become one visible rich boundary."""

    source = "global\n[SEP]\nregional"
    separator_start = source.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_rich_rendering(field, enabled=False)
    harness.set_source_cursor_position(field, separator_start + 2)
    raw = harness.capture_state_snapshot(field, label="raw-caret-inside-separator")

    harness.set_rich_rendering(field, enabled=True)
    rich = harness.capture_state_snapshot(field, label="rich-caret-after-raw-separator")

    assert raw.cursor_position == separator_start + 2
    assert raw.caret_state_placement == "plain_text"
    assert rich.cursor_position in {separator_start, separator_end}
    assert not rich.caret_inside_region_separator
    assert rich.region_chrome_divider_count == 1
    assert not harness.invariant_violations(rich)


def test_real_shell_backspace_at_region_start_deletes_separator_closing_bracket(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Backspace from regional text should expose a partial SEP marker."""

    source = "global\n[SEP]\npink witch hat"
    field = harness.add_prompt_workflow(initial_text=source)
    regional_start = source.index("pink")
    harness.set_source_cursor_position(field, regional_start)
    before = harness.capture_state_snapshot(field, label="before-region-backspace")

    harness.press_key(field, Qt.Key.Key_Backspace)
    after = harness.capture_state_snapshot(field, label="after-region-backspace")

    assert before.cursor_position == regional_start
    assert before.caret_state_placement == "plain_text"
    assert after.source_text == "global\n[SEP\npink witch hat"
    assert after.cursor_position == source.index("[SEP]") + len("[SEP")
    assert "[SEP" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not harness.invariant_violations(after)


def test_real_shell_backspace_below_separator_decoration_rebuilds_immediately(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Backspace beside a separator must delete its closing bracket atomically."""

    source = "global\n[SEP]\nregional"
    field = harness.add_prompt_workflow(initial_text=source)
    regional_start = source.index("regional")
    harness.click_projected_source_position(field, regional_start)
    clicked = harness.capture_state_snapshot(
        field,
        label="separator-below-backspace-clicked",
    )

    immediate = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Backspace,
        label="separator-below-backspace-immediate",
    )
    settled = harness.capture_state_snapshot(
        field,
        label="separator-below-backspace-settled",
    )

    for snapshot in (immediate, settled):
        assert snapshot.source_text == "global\n[SEP\nregional"
        assert snapshot.document_view_region_separator_count == 0
        assert snapshot.projection_region_separator_count == 0
        assert not any(row.is_structural for row in snapshot.visible_layout_rows)
    assert clicked.cursor_position == regional_start
    assert clicked.caret_state_placement == "plain_text"
    assert not harness.invariant_violations(settled)


def test_real_shell_backspace_removes_extra_line_below_separator_decoration(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Backspace at regional text removes its visible blank line without demoting SEP."""

    source = "global\n[SEP]\n\nregional"
    field = harness.add_prompt_workflow(initial_text=source)
    regional_start = source.index("regional")

    harness.click_projected_source_position(field, regional_start)
    clicked = harness.capture_state_snapshot(
        field,
        label="separator-extra-line-backspace-clicked",
    )
    harness.press_key(field, Qt.Key.Key_Backspace)
    settled = harness.capture_state_snapshot(
        field,
        label="separator-extra-line-backspace-settled",
    )

    assert clicked.cursor_position == regional_start
    assert clicked.caret_state_placement == "plain_text"
    assert settled.source_text == "global\n[SEP]\nregional"
    assert settled.cursor_position == regional_start - 1
    assert settled.document_view_region_separator_count == 1
    assert settled.projection_region_separator_count == 1
    assert sum(row.is_structural for row in settled.visible_layout_rows) == 1
    assert not harness.invariant_violations(settled)


def test_real_shell_backspace_on_separator_closing_bracket_reveals_partial_marker(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Deleting `]` should reveal editable partial marker text rather than full SEP."""

    source = "global\n[SEP]\nregional"
    separator_end = source.index("[SEP]") + len("[SEP]")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, separator_end)
    before = harness.capture_state_snapshot(field, label="separator-closing-before")

    harness.press_key(field, Qt.Key.Key_Backspace)
    after = harness.capture_state_snapshot(field, label="separator-closing-after")

    assert before.caret_state_placement == "token_trailing_edge"
    assert after.source_text == "global\n[SEP\nregional"
    assert "[SEP" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert after.projection_region_separator_count == 0
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not harness.invariant_violations(after)


def test_real_shell_delete_before_separator_deletes_opening_bracket(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Delete before a separator should expose its partial marker text."""

    source = "global\n[SEP]\npink witch hat"
    field = harness.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    harness.set_source_cursor_position(field, global_end)

    harness.press_key(field, Qt.Key.Key_Delete)
    after = harness.capture_state_snapshot(
        field, label="after-separator-leading-delete"
    )

    assert after.source_text == "global\nSEP]\npink witch hat"
    assert after.cursor_position == global_end + 1
    assert "SEP]" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not harness.invariant_violations(after)


def test_real_shell_repeated_delete_exposes_partial_separator_text(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Repeated Delete may remove blank lines before exposing one partial marker."""

    source = "global\n\n[SEP]\npink witch hat"
    field = harness.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    harness.set_source_cursor_position(field, global_end)

    immediate_structural = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Delete,
        label="separator-delete-preserves-structure",
    )
    still_structural = harness.capture_state_snapshot(
        field,
        label="separator-delete-preserves-structure-settled",
    )
    immediate_partial = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Delete,
        label="separator-delete-exposes-partial-marker",
    )
    now_partial = harness.capture_state_snapshot(
        field,
        label="separator-delete-exposes-partial-marker-settled",
    )

    for snapshot in (immediate_structural, still_structural):
        assert snapshot.source_text == "global\n[SEP]\npink witch hat"
        assert snapshot.projection_text.count("\ufffc") == 1
        assert "[SEP]" not in snapshot.projection_text
        assert sum(row.is_structural for row in snapshot.visible_layout_rows) == 1
        assert not snapshot.transient_deletion_overlay_present
    for snapshot in (immediate_partial, now_partial):
        assert snapshot.source_text == "global\nSEP]\npink witch hat"
        assert "SEP]" in snapshot.projection_text
        assert "[SEP]" not in snapshot.projection_text
        assert not any(row.is_structural for row in snapshot.visible_layout_rows)
        assert not snapshot.transient_deletion_overlay_present
    assert not harness.invariant_violations(still_structural)
    assert not harness.invariant_violations(now_partial)


def test_real_shell_horizontal_navigation_crosses_separator_without_stalling(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Left and Right should cross one hidden separator in one visible move."""

    source = "global\n[SEP]\npink witch hat"
    field = harness.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    regional_start = source.index("pink")
    harness.set_source_cursor_position(field, global_end)

    before = harness.capture_state_snapshot(field, label="separator-right-before")
    harness.press_key(field, Qt.Key.Key_Right)
    after_right = harness.capture_state_snapshot(field, label="separator-right-after")

    assert after_right.cursor_position == regional_start
    assert after_right.caret_state_placement == "plain_text"
    assert after_right.caret_rect != before.caret_rect

    harness.press_key(field, Qt.Key.Key_Left)
    after_left = harness.capture_state_snapshot(field, label="separator-left-after")

    assert after_left.cursor_position == global_end
    assert after_left.caret_state_placement == "plain_text"
    assert after_left.caret_rect == before.caret_rect
    assert not harness.invariant_violations(after_right)
    assert not harness.invariant_violations(after_left)


def test_real_shell_horizontal_navigation_visits_adjacent_empty_region_once(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Adjacent dividers must expose one visible caret row for their empty region."""

    source = "global\n[SEP]\n[SEP]\nregional"
    global_end = source.index("\n")
    empty_region = source.rindex("[SEP]")
    regional_start = source.index("regional")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, global_end)
    snapshots = [
        harness.capture_state_snapshot(field, label="adjacent-navigation-global")
    ]

    for label in ("empty", "regional"):
        harness.press_key(field, Qt.Key.Key_Right)
        snapshots.append(
            harness.capture_state_snapshot(
                field,
                label=f"adjacent-navigation-{label}",
            )
        )

    assert tuple(snapshot.cursor_position for snapshot in snapshots) == (
        global_end,
        empty_region,
        regional_start,
    )
    assert all(snapshot.caret_state_placement == "plain_text" for snapshot in snapshots)
    assert all(snapshot.caret_token_id is None for snapshot in snapshots)
    assert all(
        before.caret_rect != after.caret_rect
        for before, after in zip(snapshots, snapshots[1:])
    )
    assert all(not harness.invariant_violations(snapshot) for snapshot in snapshots)


def test_real_shell_separator_navigation_never_enters_hidden_source_or_stalls(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Horizontal movement must cross atomic separator boundaries visibly."""

    source = "above\n[SEP]\nbelow"
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, source.index("\n"))
    snapshots = [harness.capture_state_snapshot(field, label="separator-atomic-origin")]

    for step in range(3):
        harness.press_key(field, Qt.Key.Key_Right)
        snapshots.append(
            harness.capture_state_snapshot(
                field,
                label=f"separator-atomic-right-{step}",
            )
        )

    assert tuple(snapshot.cursor_position for snapshot in snapshots) == (
        source.index("\n"),
        source.index("below"),
        source.index("below") + 1,
        source.index("below") + 2,
    )
    assert not any(snapshot.caret_inside_region_separator for snapshot in snapshots)
    assert not any(snapshot.anchor_inside_region_separator for snapshot in snapshots)
    assert all(
        before.caret_rect != after.caret_rect
        for before, after in zip(snapshots, snapshots[1:])
    ), tuple(
        (
            snapshot.cursor_position,
            snapshot.caret_state_placement,
            snapshot.caret_rect,
        )
        for snapshot in snapshots
    )


def test_real_shell_shift_navigation_selects_across_separator_atomically(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Shift+arrow must cross hidden marker source without hidden anchor stops."""

    source = "above\n[SEP]\nbelow"
    global_end = source.index("\n")
    regional_start = source.index("below")
    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, global_end)

    harness.press_key(
        field,
        Qt.Key.Key_Right,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    selected = harness.capture_state_snapshot(field, label="separator-shift-right")
    harness.press_key(
        field,
        Qt.Key.Key_Left,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    collapsed = harness.capture_state_snapshot(field, label="separator-shift-left")

    assert selected.selection_range == (global_end, regional_start)
    assert selected.selected_source_text == "\n[SEP]\n"
    assert selected.cursor_position == regional_start
    assert not selected.caret_inside_region_separator
    assert not selected.anchor_inside_region_separator
    assert collapsed.selection_range == (global_end, global_end)
    assert collapsed.cursor_position == global_end
    assert not harness.invariant_violations(selected)
    assert not harness.invariant_violations(collapsed)


def test_real_shell_requested_hidden_separator_positions_resolve_to_atomic_edges(
    harness: RealShellPromptEditorHarness,
) -> None:
    """External caret placement inside `[SEP]` must resolve to a visible edge."""

    source = "above\n[SEP]\nbelow"
    separator_start = source.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    field = harness.add_prompt_workflow(initial_text=source)

    for position in range(separator_start + 1, separator_end):
        harness.set_source_cursor_position(field, position)
        snapshot = harness.capture_state_snapshot(
            field,
            label=f"separator-hidden-position-{position}",
        )

        assert snapshot.cursor_position in {separator_start, separator_end}
        assert not snapshot.caret_inside_region_separator
        assert snapshot.caret_state_placement in {
            "token_leading_edge",
            "token_trailing_edge",
        }


def test_real_shell_clicking_separator_row_resolves_to_visible_caret(
    harness: RealShellPromptEditorHarness,
) -> None:
    """A divider-row click must not leave the caret owned by hidden marker text."""

    source = "above\n[SEP]\nbelow"
    field = harness.add_prompt_workflow(initial_text=source)
    before = harness.capture_state_snapshot(field, label="separator-row-before-click")
    structural_row = next(
        row for row in before.visible_layout_rows if row.is_structural
    )
    point = QPoint(
        before.viewport_rect[2] // 2,
        round(structural_row.viewport_top + structural_row.height / 2.0),
    )

    harness.click_editor_viewport_point(field, point)
    clicked = harness.capture_state_snapshot(field, label="separator-row-after-click")

    assert clicked.cursor_position in {source.index("\n"), source.index("below")}
    assert clicked.caret_state_placement == "plain_text"
    assert clicked.caret_token_id is None
    assert not clicked.caret_inside_region_separator
    assert not harness.invariant_violations(clicked)


def test_real_shell_nearby_inline_sep_text_preserves_visual_source_order(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Typing arbitrary `[SEP]`-suffixed text near a divider edits that visual row."""

    source = (
        "best quality, score_7, masterpiece, very aesthetic\n"
        "\n"
        "2girls, standing, full body, looking at viewer, outdoors, cherry "
        "blossoms, school uniform \n"
        "\n"
        "[SEP]\n"
        "1girl, red hair, long hair, green eyes, smile, blazer, pleated skirt, "
        "black thighhighs \n"
        "\n"
        "\n"
        "faksflas\n"
        "jfak;lsfa\n"
        "\n"
        "fsjma;f \n"
        "[SEP]\n"
        "\n"
        " \n"
        "\n"
        "1girl, blue hair, short hair, blue eyes, serious, cardigan, pleated "
        "skirt, kneehighs\n"
    )
    typed_text = "fasdfsa[SEP]"
    second_separator = source.index("[SEP]", source.index("[SEP]") + 1)
    insertion_position = second_separator + len("[SEP]\n")
    normalized_insert = "fasdfsa\n[SEP]"
    expected_source = (
        source[:insertion_position] + normalized_insert + source[insertion_position:]
    )
    field = harness.add_prompt_workflow(initial_text=source)

    harness.click_projected_source_position(field, insertion_position)
    clicked = harness.capture_state_snapshot(field, label="near-separator-clicked")
    immediate = harness.type_text_and_capture_immediate_state(
        field,
        typed_text,
        label="near-separator-typed-immediate",
    )
    settled = harness.capture_state_snapshot(
        field, label="near-separator-typed-settled"
    )

    assert clicked.cursor_position == insertion_position
    for snapshot in (immediate, settled):
        assert snapshot.source_text == expected_source
        assert (
            snapshot.cursor_position == insertion_position + len(normalized_insert) + 1
        )
        assert snapshot.document_view_region_separator_count == 3
        assert snapshot.projection_region_separator_count == 3
        assert snapshot.region_chrome_divider_count == 3
        assert "fasdfsa" in snapshot.projection_text
        assert typed_text not in snapshot.source_text
        assert not snapshot.caret_inside_region_separator
    immediate_violations = harness.invariant_violations(immediate)
    assert all(
        violation.startswith("shell_height_contract_mismatch:")
        for violation in immediate_violations
    ), immediate_violations
    assert not harness.invariant_violations(settled)


def test_real_shell_vertical_navigation_crosses_separator_as_line_break(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Up and Down should skip separator chrome and preserve text-column affinity."""

    source = "alpha\n[SEP]\nbravo"
    field = harness.add_prompt_workflow(initial_text=source)
    global_position = source.index("alpha") + 3
    regional_position = source.index("bravo") + 3
    harness.set_source_cursor_position(field, regional_position)

    harness.press_key(field, Qt.Key.Key_Up)
    after_up = harness.capture_state_snapshot(field, label="separator-up-crossing")
    harness.press_key(field, Qt.Key.Key_Down)
    after_down = harness.capture_state_snapshot(field, label="separator-down-crossing")

    assert after_up.cursor_position == global_position
    assert after_up.caret_state_placement == "plain_text"
    assert after_down.cursor_position == regional_position
    assert after_down.caret_state_placement == "plain_text"
    assert not harness.invariant_violations(after_up)
    assert not harness.invariant_violations(after_down)


@pytest.mark.parametrize(
    ("separator_occurrence", "boundary"),
    (
        (0, "before"),
        (0, "after"),
        (1, "before"),
        (1, "after"),
    ),
)
def test_real_shell_line_breaks_adjacent_to_multiple_separators_preserve_chrome(
    harness: RealShellPromptEditorHarness,
    separator_occurrence: int,
    boundary: str,
) -> None:
    """Line breaks beside either separator must preserve both structural rows."""

    source = (
        "testbest quality, score_7, masterpiece, very aesthetic\n\n"
        "2girls, standing, full body, looking at viewer, outdoors, cherry blossoms, "
        "school uniform \n"
        "[SEP]\n"
        "1girl, red hair, long hair, green eyes, smile, blazer, pleated skirt, "
        "black thighhighs \n\n\n"
        "[SEP]\n"
        "1girl, blue hair, short hair, blue eyes, serious, cardigan, pleated skirt, "
        "kneehighs\n"
    )
    separator_positions = (source.index("[SEP]"), source.rindex("[SEP]"))
    insertion_position = separator_positions[separator_occurrence]
    if boundary == "after":
        insertion_position += len("[SEP]\n")

    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, insertion_position)
    harness.press_key(field, Qt.Key.Key_Return)
    after = harness.capture_state_snapshot(
        field,
        label=f"separator-{separator_occurrence}-{boundary}-newline",
    )

    assert after.projection_region_separator_count == 2
    assert after.document_view_region_separator_count == 2
    assert after.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in after.projection_text
    assert not harness.invariant_violations(after)


@pytest.mark.parametrize(
    ("source", "insertion_position"),
    (
        ("school uniform [SEP]\nregional", len("school uniform ")),
        ("global\n[SEP] regional", len("global\n[SEP]")),
    ),
)
def test_real_shell_line_break_promotes_inline_separator_to_decoration(
    harness: RealShellPromptEditorHarness,
    source: str,
    insertion_position: int,
) -> None:
    """A line break that isolates `[SEP]` must publish structural chrome immediately."""

    field = harness.add_prompt_workflow(initial_text=source)
    harness.set_source_cursor_position(field, insertion_position)

    immediate = harness.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Return,
        label="separator-promotion-immediate",
    )
    settled = harness.capture_state_snapshot(field, label="separator-promotion-settled")

    for snapshot in (immediate, settled):
        assert snapshot.projection_region_separator_count == 1
        assert snapshot.document_view_region_separator_count == 1
        assert snapshot.projection_text.count("\ufffc") == 1
        assert "[SEP]" not in snapshot.projection_text
    assert not harness.invariant_violations(settled)


def test_real_shell_paste_canonicalizes_implicit_parenthesis_weights(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Canonicalize pasted implicit emphasis through the full editor-panel route."""

    field = harness.add_prompt_workflow(initial_text="")
    before = harness.capture_state_snapshot(field, label="before-parenthesis-paste")
    harness.paste_text(field, "(blue laces), ((deep focus)), (wide shot:6)")
    after = harness.capture_state_snapshot(field, label="after-parenthesis-paste")

    assert after.source_text == (
        "(blue laces:1.10), (deep focus:1.21), (wide shot:6.00)"
    )
    assert not harness.transition_invariant_violations(
        action_name="paste",
        before=before,
        after=after,
    )


def test_real_shell_typing_nested_parentheses_canonicalizes_once_closed(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Canonicalize authored nested emphasis through the full editor-panel route."""

    field = harness.add_prompt_workflow(initial_text="")
    before = harness.capture_state_snapshot(
        field, label="before-nested-parenthesis-typing"
    )
    harness.type_text(field, "((test))")
    after = harness.capture_state_snapshot(
        field, label="after-nested-parenthesis-typing"
    )

    assert after.source_text == "(test:1.21)"
    assert not harness.transition_invariant_violations(
        action_name="typing",
        before=before,
        after=after,
    )


def test_real_shell_wrapping_generated_emphasis_re_evaluates_nesting(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Re-evaluate generated emphasis when parentheses are added around it later."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "(test)")
    generated = harness.capture_state_snapshot(field, label="generated-single-emphasis")
    assert generated.source_text == "(test:1.10)"

    harness.set_source_cursor_position(field, 0)
    harness.type_text(field, "(")
    harness.set_source_cursor_position(field, len(field.editor.toPlainText()))
    harness.type_text(field, ")")
    wrapped = harness.capture_state_snapshot(field, label="wrapped-generated-emphasis")

    assert wrapped.source_text == "(test:1.21)"
    assert not harness.invariant_violations(wrapped)


def test_real_shell_generated_emphasis_re_evaluates_after_undo_redo(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Restore generated-weight provenance with real editor history."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "(test)")
    generated = harness.capture_state_snapshot(field, label="generated-before-history")
    assert generated.source_text == "(test:1.10)"

    harness.undo(field)
    harness.redo(field)
    restored = harness.capture_state_snapshot(field, label="generated-after-history")
    assert restored.source_text == generated.source_text

    harness.set_source_cursor_position(field, 0)
    harness.type_text(field, "(")
    harness.set_source_cursor_position(field, len(field.editor.toPlainText()))
    harness.type_text(field, ")")
    wrapped = harness.capture_state_snapshot(
        field,
        label="wrapped-generated-after-history",
    )

    assert wrapped.source_text == "(test:1.21)"
    assert not harness.invariant_violations(wrapped)


def test_real_shell_parenthesis_conversion_round_trips_through_undo_redo(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Restore canonicalized source, mappings, and projection through history."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.paste_text(field, "((blue laces))")
    canonical = harness.capture_state_snapshot(field, label="canonical-parentheses")
    harness.undo(field)
    undone = harness.capture_state_snapshot(field, label="undone-parentheses")
    harness.redo(field)
    redone = harness.capture_state_snapshot(field, label="redone-parentheses")

    assert canonical.source_text == "(blue laces:1.21)"
    assert undone.source_text == ""
    assert redone.source_text == canonical.source_text
    assert not harness.invariant_violations(redone)


def test_real_shell_manual_unescape_persists_until_segment_replacement(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Respect direct user escapement edits until the segment is reconstructed."""

    field = harness.add_prompt_workflow(initial_text=r"\(blue laces\)")
    harness.set_rich_rendering(field, enabled=False)
    harness.set_source_cursor_position(field, 0)
    harness.press_key(field, Qt.Key.Key_Delete)
    closing_slash = field.editor.toPlainText().index(r"\)")
    harness.set_source_cursor_position(field, closing_slash)
    harness.press_key(field, Qt.Key.Key_Delete)
    harness.set_source_cursor_position(field, len(field.editor.toPlainText()) - 1)
    harness.type_text(field, "!")
    harness.set_rich_rendering(field, enabled=True)
    overridden = harness.capture_state_snapshot(field, label="manual-unescape")

    assert overridden.source_text == "(blue laces!)"
    assert not harness.invariant_violations(overridden)

    harness.replace_text_with_keys(field, "(fresh)")
    replaced = harness.capture_state_snapshot(field, label="replaced-segment")

    assert replaced.source_text == "(fresh:1.10)"
    assert not harness.invariant_violations(replaced)


def test_real_shell_autocomplete_selection_navigation_stays_coherent(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Arrow navigation through suggestions keeps session and popup state coherent."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-autocomplete-down")
    harness.press_key(field, Qt.Key.Key_Down)
    after_down = harness.capture_state_snapshot(field, label="after-autocomplete-down")
    harness.press_key(field, Qt.Key.Key_Up)
    after_up = harness.capture_state_snapshot(field, label="after-autocomplete-up")

    down_violations = harness.transition_invariant_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after_down,
    )
    up_violations = harness.transition_invariant_violations(
        action_name="autocomplete_navigation",
        before=after_down,
        after=after_up,
    )
    violations = down_violations + up_violations
    if violations:
        artifact = harness.save_artifacts(
            "autocomplete-selection-navigation-left-bad-state",
            before=before,
            after=after_up,
            invariant="Autocomplete selection movement must keep session and popup coherent.",
            observed=f"down={down_violations}; up={up_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_session_selected_index == 0
    assert after_down.autocomplete_session_selected_index == 1
    assert after_up.autocomplete_session_selected_index == 0
    assert after_up.popup_state_visible
    assert after_up.autocomplete_preview_active
    assert not violations


def test_real_shell_space_does_not_displace_ghost_text(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect Space committing whitespace while ghost text remains visible."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-space")
    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(field, label="after-space")
    violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "space-displaced-ghost-text",
            before=before,
            after=after,
            invariant=(
                "Space with active autocomplete must not leave ghost text visually "
                "separated from the committed prefix."
            ),
            observed=f"source after Space was {after.source_text!r}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations
    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible


def test_real_shell_space_keeps_whitespace_tag_completion_active(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Treat Space as part of tag autocomplete for whitespace-containing tags."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "backpack")
    before = harness.capture_state_snapshot(field, label="before-backpack-space")
    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(field, label="after-backpack-space")

    violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=after,
    )
    if violations or not after.autocomplete_preview_active:
        artifact = harness.save_artifacts(
            "space-dismissed-whitespace-tag-completion",
            before=before,
            after=after,
            invariant=(
                "Space is part of tag autocomplete; `backpack ` should keep "
                "`backpack basket` active with `basket` as ghost text."
            ),
            observed=f"violations={violations}; after={_autocomplete_stale_observed(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.autocomplete_session_prefix == "backpack "
    assert after.autocomplete_preview_suffix == "basket"
    assert after.autocomplete_preview_source_position == len("backpack ")
    assert after.autocomplete_presenter_panel_visible


def test_real_shell_space_clears_stale_whitespace_leading_preview(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Retarget leaked whitespace-leading ghost state after Space commits."""

    field = harness.add_prompt_workflow(initial_text="backpack")
    harness.move_cursor_to_end(field)
    field.editor.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("backpack"),
            suffix_text=" basket",
        )
    )
    before = harness.capture_state_snapshot(
        field,
        label="before-stale-backpack-space",
    )

    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(
        field,
        label="after-stale-backpack-space",
    )

    violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=after,
    )
    if violations or after.cursor_position != len("backpack "):
        artifact = harness.save_artifacts(
            "space-retargeted-stale-backpack-preview",
            before=before,
            after=after,
            invariant=(
                "Space must retarget stale whitespace-leading autocomplete preview "
                "instead of moving the caret through ghost text."
            ),
            observed=_autocomplete_stale_observed(after),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.cursor_position == len("backpack ")
    assert after.autocomplete_preview_active
    assert after.autocomplete_preview_suffix == "basket"
    assert after.autocomplete_preview_source_position == len("backpack ")


def test_real_shell_space_after_autocomplete_dismissal_rebuilds_projection(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep Space after dismissed autocomplete from leaving stale ghost projection."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "backpack")
    active = harness.capture_state_snapshot(
        field,
        label="before-backpack-escape",
    )
    harness.press_key(field, Qt.Key.Key_Escape)
    dismissed = harness.capture_state_snapshot(
        field,
        label="after-backpack-escape",
    )
    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(
        field,
        label="after-backpack-space-after-escape",
    )

    violations = harness.transition_invariant_violations(
        action_name="space",
        before=dismissed,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "space-after-backpack-dismissal-left-stale-projection",
            before=active,
            after=after,
            invariant=(
                "Space after autocomplete dismissal must immediately rebuild "
                "projection so stale ghost text cannot remain painted."
            ),
            observed=f"violations={violations}; dismissed={_autocomplete_stale_observed(dismissed)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.projection_document_source_text == "backpack "
    assert after.active_projection_source_text == "backpack "
    assert not after.projection_has_pending_update
    assert not after.projection_has_stale_geometry


def test_real_shell_ghost_requires_visually_present_dropdown(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect ghost text visible without a visually present suggestions dropdown."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-escape")
    harness.press_key(field, Qt.Key.Key_Escape)
    after = harness.capture_state_snapshot(field, label="after-escape")

    violations = harness.transition_invariant_violations(
        action_name="escape",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "ghost-without-visible-dropdown",
            before=before,
            after=after,
            invariant="Visible ghost text requires a visually present dropdown.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_click_away_clears_ghost_and_dropdown(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect autocomplete ghost state surviving a click outside the editor."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-click-away")
    harness.click_away_from_editor()
    after = harness.capture_state_snapshot(field, label="after-click-away")

    violations = harness.transition_invariant_violations(
        action_name="click_away",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "click-away-left-ghost-without-dropdown",
            before=before,
            after=after,
            invariant=(
                "Clicking outside active autocomplete clears projection ghost "
                "state and the visible dropdown."
            ),
            observed=_autocomplete_stale_observed(after),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_backpack_click_away_clears_basket_ghost(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Clear whitespace-tag ghost text when focus leaves autocomplete."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "backpack")
    before = harness.capture_state_snapshot(
        field,
        label="before-backpack-click-away",
    )
    harness.click_away_from_editor()
    after = harness.capture_state_snapshot(
        field,
        label="after-backpack-click-away",
    )

    violations = harness.transition_invariant_violations(
        action_name="click_away",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "backpack-click-away-left-basket-ghost",
            before=before,
            after=after,
            invariant="Click-away must clear `backpack basket` ghost projection.",
            observed=f"violations={violations}; after={_autocomplete_stale_observed(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible
    assert after.active_projection_text == after.projection_text == "backpack"


def test_real_shell_backpack_up_arrow_selects_previous_suggestion(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Use Up to wrap from the first suggestion to the previous suggestion."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "backpack")
    before = harness.capture_state_snapshot(field, label="before-backpack-up")
    harness.press_key(field, Qt.Key.Key_Up)
    after = harness.capture_state_snapshot(field, label="after-backpack-up")

    violations = harness.transition_invariant_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "backpack-up-navigation-left-bad-state",
            before=before,
            after=after,
            invariant="Up-arrow must retarget autocomplete preview coherently.",
            observed=f"violations={violations}; after={_autocomplete_stale_observed(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_session_selected_index == 0
    assert before.autocomplete_preview_suffix == " basket"
    assert after.autocomplete_session_selected_index == 1
    assert after.autocomplete_preview_suffix == " strap"
    assert after.autocomplete_presenter_panel_visible
    assert after.projection_text == "backpack"
    assert after.active_projection_text == "backpack strap"
    assert not violations


def test_real_shell_multiline_backpack_up_arrow_selects_previous_suggestion(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep Up navigation inside autocomplete for a multiline prompt."""

    prefix_line = "empty eyes, pointy ears, sharp teeth"
    field = harness.add_prompt_workflow(initial_text=f"{prefix_line}\n")
    harness.move_cursor_to_end(field)
    harness.type_text(field, "backpack")
    before = harness.capture_state_snapshot(
        field,
        label="before-multiline-backpack-up",
    )

    harness.press_key(field, Qt.Key.Key_Up)
    after = harness.capture_state_snapshot(
        field,
        label="after-multiline-backpack-up",
    )

    violations = harness.transition_invariant_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "multiline-backpack-up-navigation-left-bad-state",
            before=before,
            after=after,
            invariant="Up-arrow must retarget multiline autocomplete coherently.",
            observed=f"violations={violations}; after={_autocomplete_stale_observed(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_preview_active
    assert before.autocomplete_preview_suffix == " basket"
    assert before.autocomplete_session_selected_index == 0
    assert after.autocomplete_preview_active
    assert after.autocomplete_preview_suffix == " strap"
    assert after.autocomplete_session_selected_index == 1
    assert after.autocomplete_presenter_panel_visible
    assert after.source_text == f"{prefix_line}\nbackpack"
    assert after.projection_text == after.source_text
    assert after.active_projection_text == f"{after.source_text} strap"
    assert not violations


def test_real_shell_canvas_navigation_clears_ghost_and_dropdown(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect autocomplete ghost state surviving canvas route navigation."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-canvas-nav")
    harness.switch_canvas("Output")
    harness.switch_canvas("Input")
    after = harness.capture_state_snapshot(field, label="after-canvas-nav")

    violations = harness.transition_invariant_violations(
        action_name="canvas",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "canvas-navigation-left-ghost-without-dropdown",
            before=before,
            after=after,
            invariant=(
                "Canvas navigation clears autocomplete projection ghost state "
                "and the visible dropdown."
            ),
            observed=_autocomplete_stale_observed(after),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_workflow_navigation_clears_ghost_and_dropdown(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect autocomplete ghost state surviving workflow route navigation."""

    field = harness.add_prompt_workflow(alias="alpha", initial_text="")
    harness.add_prompt_workflow(alias="beta", initial_text="", activate=False)
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-workflow-nav")
    harness.activate_workflow("beta", force_refresh=False)
    harness.activate_workflow("alpha", force_refresh=False)
    field = harness.prompt_field("alpha")
    after = harness.capture_state_snapshot(field, label="after-workflow-nav")

    violations = harness.transition_invariant_violations(
        action_name="workflow",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "workflow-navigation-left-ghost-without-dropdown",
            before=before,
            after=after,
            invariant=(
                "Workflow navigation clears autocomplete projection ghost state "
                "and the visible dropdown."
            ),
            observed=_autocomplete_stale_observed(after),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_backspace_keeps_projection_state_current(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect stale projection owner state after Backspace."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "masterpiece, best quality")
    before = harness.capture_state_snapshot(field, label="before-backspace")
    harness.press_key(field, Qt.Key.Key_Backspace)
    after = harness.capture_state_snapshot(field, label="after-backspace")
    violations = harness.transition_invariant_violations(
        action_name="backspace",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "backspace-live-paint-mismatch",
            before=before,
            after=after,
            invariant="Backspace must leave projection owner state current.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_transient_edit_dirty_regions_stay_bounded(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Typing and erasure over wrapped text keep dirty-region owner state bounded."""

    prompt = (
        "(small:1.20) breasts, flat chest, see-through silhouette, "
        "sparkling blue sash, sparkling blue bralette,\n\n"
        "backpack basket\n\n"
        "empty eyes, pointy ears, sharp teeth, too many rabbits, backlighting"
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.shell.resize(500, 620)
    harness.process_events(cycles=10)
    harness.move_cursor_to_end(field)
    before_insert = harness.capture_state_snapshot(
        field,
        label="before-dirty-region-insert",
    )
    harness.type_text(field, ", red eyes")
    after_insert = harness.capture_state_snapshot(
        field,
        label="after-dirty-region-insert",
    )
    harness.press_key(field, Qt.Key.Key_Backspace)
    after_backspace = harness.capture_state_snapshot(
        field,
        label="after-dirty-region-backspace",
    )
    harness.press_key(field, Qt.Key.Key_Delete)
    after_delete = harness.capture_state_snapshot(
        field,
        label="after-dirty-region-delete",
    )

    insert_violations = harness.transition_invariant_violations(
        action_name="typing",
        before=before_insert,
        after=after_insert,
    )
    backspace_violations = harness.transition_invariant_violations(
        action_name="backspace",
        before=after_insert,
        after=after_backspace,
    )
    delete_violations = harness.transition_invariant_violations(
        action_name="delete",
        before=after_backspace,
        after=after_delete,
    )
    violations = insert_violations + backspace_violations + delete_violations
    if violations:
        artifact = harness.save_artifacts(
            "transient-edit-dirty-regions-left-bad-state",
            before=before_insert,
            after=after_delete,
            invariant="Transient edit dirty regions must remain bounded and coherent.",
            observed=(
                f"insert={insert_violations}; "
                f"backspace={backspace_violations}; delete={delete_violations}"
            ),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after_insert.source_text.endswith("backlighting, red eyes")
    assert not violations


def test_real_shell_deferred_typing_keeps_transient_overlay_state_valid(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Validate deferred safe typing through the same transient owner path as paint."""

    field = harness.add_prompt_workflow(
        initial_text="alpha, (small:1.20), <lora:missing:1.00>, omega",
    )
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(
        field,
        label="before-deferred-overlay-typing",
    )
    harness.type_text(field, "re")
    after = harness.capture_state_snapshot(
        field,
        label="after-deferred-overlay-typing",
    )
    violations = harness.transition_invariant_violations(
        action_name="typing",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "deferred-typing-left-invalid-transient-overlay",
            before=before,
            after=after,
            invariant="Deferred typing must expose valid transient overlay owner state.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text.endswith("omegare")
    assert after.transient_caret_geometry_present
    assert after.transient_caret_geometry_valid
    assert after.transient_insertion_overlay_present
    assert after.transient_insertion_overlay_valid
    assert not violations


def test_real_shell_trailing_typing_keeps_caret_aligned_without_erasing_background(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep accumulated end typing aligned without painting a foreign backing fill."""

    field = harness.add_prompt_workflow(initial_text="alpha")
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="trailing-typing-before")
    after = harness.type_text_and_capture_immediate_state(
        field,
        "xyz",
        label="trailing-typing-immediate",
    )
    surface = field.editor._surface
    command = surface._render_frame_owner.frame.transient_layer.insertion

    assert command is not None
    assert command.text == "xyz"
    assert before.caret_rect is not None
    assert after.transient_insertion_overlay_viewport_rect is not None
    assert after.caret_rect is not None
    assert command.rect[0] == pytest.approx(before.caret_rect[0])
    assert after.caret_rect[0] == pytest.approx(command.rect[0] + command.rect[2])
    assert not command.erase_underlying_content


def test_real_shell_space_after_deferred_typing_updates_projection_or_bridge(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep a typed space from dropping the only visible bridge to pending text."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "alpha")
    before = harness.capture_state_snapshot(
        field,
        label="before-deferred-space",
    )
    harness.press_key(field, Qt.Key.Key_Space, text=" ")
    after = harness.capture_state_snapshot(
        field,
        label="after-deferred-space",
    )
    violations = harness.transition_invariant_violations(
        action_name="space",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "space-after-deferred-typing-left-stale-projection",
            before=before,
            after=after,
            invariant=(
                "Space after deferred typing must either rebuild projection "
                "or keep a valid transient bridge."
            ),
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "alpha "
    assert not violations


def test_real_shell_delete_at_end_after_canvas_navigation_is_noop(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep Delete at source end from building an invalid projection range."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    harness.switch_canvas("Output")
    harness.switch_canvas("Input")
    before = harness.capture_state_snapshot(field, label="before-delete-at-end")
    harness.press_key(field, Qt.Key.Key_Delete)
    after = harness.capture_state_snapshot(field, label="after-delete-at-end")

    assert after.source_text == before.source_text
    assert after.cursor_position == before.cursor_position


def test_real_shell_multiline_paste_keeps_projection_and_selection_sane(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Keep projection, caret, scroll, and overlay owners sane after multiline paste."""

    field = harness.add_prompt_workflow(initial_text="alpha")
    harness.focus_editor(field)
    QApplication.clipboard().setText("backpack basket\nempty eyes")
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Paste)
    harness.process_events(cycles=8)
    after = harness.capture_state_snapshot(field, label="after-multiline-paste")

    violations = harness.invariant_violations(after)
    if violations:
        artifact = harness.save_artifacts(
            "multiline-paste-left-bad-editor-state",
            before=after,
            after=after,
            invariant="Multiline paste must leave editor owners coherent.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert "backpack basket\nempty eyes" in after.source_text
    assert not violations


def test_real_shell_shift_selection_keeps_selection_and_caret_sane(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Extend and collapse a keyboard selection without corrupting editor owners."""

    field = harness.add_prompt_workflow(initial_text="alpha beta gamma")
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="before-shift-selection")
    for _ in range(5):
        harness.press_key(
            field,
            Qt.Key.Key_Left,
            modifiers=Qt.KeyboardModifier.ShiftModifier,
        )
    selected = harness.capture_state_snapshot(field, label="after-shift-left")
    harness.press_key(field, Qt.Key.Key_Right)
    collapsed = harness.capture_state_snapshot(field, label="after-collapse-right")

    selection_violations = harness.transition_invariant_violations(
        action_name="selection",
        before=before,
        after=selected,
    )
    collapse_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=selected,
        after=collapsed,
    )
    if selection_violations or collapse_violations:
        artifact = harness.save_artifacts(
            "shift-selection-left-bad-editor-state",
            before=before,
            after=collapsed,
            invariant="Shift selection and collapse must keep editor owners coherent.",
            observed=f"selection={selection_violations}; collapse={collapse_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert selected.selected_source_text == "gamma"
    assert collapsed.selection_range[0] == collapsed.selection_range[1]
    assert not selection_violations
    assert not collapse_violations


def test_real_shell_wrapped_multiline_selection_geometry_clears_on_collapse(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Wrapped multiline selections expose bounded rects and clear on collapse."""

    prompt = (
        "masterpiece, best quality, official art, backpack basket,\n"
        "empty eyes, pointy ears, sharp teeth, too many rabbits,\n"
        "glowing red eyes, long white hair, swept bangs"
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.shell.resize(520, 620)
    harness.process_events(cycles=10)
    cursor = cast(Any, field.editor).textCursor()
    start = prompt.index("backpack")
    end = prompt.index("glowing")
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    selected = harness.capture_state_snapshot(field, label="after-wrapped-selection")
    harness.press_key(field, Qt.Key.Key_Right)
    collapsed = harness.capture_state_snapshot(field, label="after-selection-collapse")

    selection_violations = harness.transition_invariant_violations(
        action_name="selection",
        before=selected,
        after=selected,
    )
    collapse_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=selected,
        after=collapsed,
    )
    violations = selection_violations + collapse_violations
    if violations:
        artifact = harness.save_artifacts(
            "wrapped-selection-geometry-left-bad-state",
            before=selected,
            after=collapsed,
            invariant="Wrapped multiline selection rects must be bounded and clear on collapse.",
            observed=f"selection={selection_violations}; collapse={collapse_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert selected.selection_range == (start, end)
    assert selected.selection_rects
    assert collapsed.selection_range[0] == collapsed.selection_range[1]
    assert not collapsed.selection_rects
    assert not violations


def test_real_shell_selection_replacement_collapses_selection_and_updates_projection(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Replacing a selected source range should collapse selection at inserted text."""

    field = harness.add_prompt_workflow(initial_text="alpha beta gamma")
    cursor = cast(Any, field.editor).textCursor()
    start = len("alpha ")
    end = start + len("beta")
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    before = harness.capture_state_snapshot(field, label="before-selection-replace")
    harness.type_text(field, "omega")
    after = harness.capture_state_snapshot(field, label="after-selection-replace")

    violations = harness.transition_invariant_violations(
        action_name="selection",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "selection-replacement-left-bad-editor-state",
            before=before,
            after=after,
            invariant="Selection replacement must collapse and update projection.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "alpha omega gamma"
    assert after.selection_range[0] == after.selection_range[1]
    assert after.cursor_position == len("alpha omega")
    assert after.projection_document_source_text == after.source_text
    assert not violations


def test_real_shell_selection_clears_active_autocomplete_surfaces(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Starting a selection while autocomplete is active clears ghost and dropdown."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(
        field, label="before-autocomplete-selection"
    )
    harness.press_key(
        field,
        Qt.Key.Key_Left,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    after = harness.capture_state_snapshot(field, label="after-autocomplete-selection")

    violations = harness.transition_invariant_violations(
        action_name="selection",
        before=before,
        after=after,
    )
    if violations:
        artifact = harness.save_artifacts(
            "selection-left-autocomplete-active",
            before=before,
            after=after,
            invariant="Selection must clear autocomplete ghost and dropdown.",
            observed=f"violations={violations}; after={_autocomplete_stale_observed(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_preview_active
    assert after.selection_range[0] != after.selection_range[1]
    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible
    assert not violations


def test_real_shell_undo_redo_roundtrip_keeps_projection_and_history_sane(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Exercise undo/redo owner state through real key sequences."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "alpha")
    edited = harness.capture_state_snapshot(field, label="after-typing-alpha")
    harness.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    harness.process_events(cycles=8)
    undone = harness.capture_state_snapshot(field, label="after-undo-alpha")
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Redo)
    harness.process_events(cycles=8)
    redone = harness.capture_state_snapshot(field, label="after-redo-alpha")

    undo_violations = harness.transition_invariant_violations(
        action_name="undo_redo",
        before=edited,
        after=undone,
    )
    redo_violations = harness.transition_invariant_violations(
        action_name="undo_redo",
        before=undone,
        after=redone,
    )
    if undo_violations or redo_violations:
        artifact = harness.save_artifacts(
            "undo-redo-left-bad-editor-state",
            before=undone,
            after=redone,
            invariant="Undo/redo must leave editor owners coherent.",
            observed=f"undo={undo_violations}; redo={redo_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert redone.source_text == edited.source_text
    assert not undo_violations
    assert not redo_violations


def test_real_shell_contiguous_typing_undoes_as_one_group(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Contiguous word typing should undo as one owner-coalesced edit group."""

    field = harness.add_prompt_workflow(initial_text="")
    before = harness.capture_state_snapshot(field, label="before-typing-group-alpha")
    harness.type_text(field, "alpha")
    typed = harness.capture_state_snapshot(field, label="after-typing-group-alpha")
    harness.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    harness.process_events(cycles=8)
    undone = harness.capture_state_snapshot(field, label="after-typing-group-undo")

    violations = harness.transition_invariant_violations(
        action_name="undo_redo",
        before=typed,
        after=undone,
    )
    if violations:
        artifact = harness.save_artifacts(
            "typing-group-undo-left-bad-editor-state",
            before=typed,
            after=undone,
            invariant="Contiguous word typing must undo as one edit group.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert typed.source_text == "alpha"
    if typed.undo_typing_group_active:
        assert typed.undo_typing_group_last_cursor_position == len("alpha")
        assert typed.undo_depth == before.undo_depth
    else:
        # A loaded runner may cross the real 900 ms idle boundary while the
        # diagnostic snapshot pumps events; the committed word remains one step.
        assert typed.undo_typing_group_last_cursor_position is None
        assert typed.undo_depth == before.undo_depth + 1
    assert undone.source_text == ""
    assert not undone.undo_typing_group_active
    assert undone.redo_available
    assert not violations


def test_real_shell_repeated_backspace_undoes_as_one_delete_group(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Repeated Backspace before idle should undo as one delete group."""

    field = harness.add_prompt_workflow(initial_text="abcdef")
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="before-delete-group")
    for _ in range(3):
        harness.press_key(field, Qt.Key.Key_Backspace)
    deleted = harness.capture_state_snapshot(field, label="after-delete-group")
    harness.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    harness.process_events(cycles=8)
    undone = harness.capture_state_snapshot(field, label="after-delete-group-undo")

    delete_violations = harness.transition_invariant_violations(
        action_name="backspace",
        before=before,
        after=deleted,
    )
    undo_violations = harness.transition_invariant_violations(
        action_name="undo_redo",
        before=deleted,
        after=undone,
    )
    violations = delete_violations + undo_violations
    if violations:
        artifact = harness.save_artifacts(
            "delete-group-undo-left-bad-editor-state",
            before=before,
            after=undone,
            invariant="Repeated Backspace must undo as one delete edit group.",
            observed=f"delete={delete_violations}; undo={undo_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert deleted.source_text == "abc"
    if deleted.undo_delete_group_active:
        assert deleted.undo_delete_group_key is not None
        assert deleted.undo_depth == before.undo_depth
    else:
        # A loaded runner may cross the real 750 ms idle boundary while the
        # diagnostic snapshot pumps events; the committed group remains one step.
        assert deleted.undo_delete_group_key is None
        assert deleted.undo_depth == before.undo_depth + 1
    assert undone.source_text == "abcdef"
    assert not undone.undo_delete_group_active
    assert undone.redo_available
    assert not violations


def test_real_shell_projected_token_navigation_keeps_caret_map_sane(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Move through projected tokens and keep caret/token state coherent."""

    prompt = "alpha, (small:1.20), <lora:missing:1.00>, omega"
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="before-token-navigation")
    for _ in range(18):
        harness.press_key(field, Qt.Key.Key_Left)
    after_left = harness.capture_state_snapshot(field, label="after-token-left")
    for _ in range(18):
        harness.press_key(field, Qt.Key.Key_Right)
    after_right = harness.capture_state_snapshot(field, label="after-token-right")

    left_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=before,
        after=after_left,
    )
    right_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=after_left,
        after=after_right,
    )
    if left_violations or right_violations:
        artifact = harness.save_artifacts(
            "projected-token-navigation-left-bad-editor-state",
            before=before,
            after=after_right,
            invariant="Projected token navigation must keep caret-map state coherent.",
            observed=f"left={left_violations}; right={right_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after_left.source_text == prompt
    assert after_right.source_text == prompt
    assert not left_violations
    assert not right_violations


def test_real_shell_vertical_navigation_preferred_x_is_owned_and_reset(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Vertical movement owns preferred x, and horizontal movement clears it."""

    prompt = (
        "masterpiece, best quality, official art\n"
        "backpack basket, empty eyes, pointy ears, sharp teeth\n"
        "glowing red eyes, long white hair, swept bangs"
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.shell.resize(560, 640)
    harness.process_events(cycles=10)
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="before-vertical-nav")
    harness.press_key(field, Qt.Key.Key_Up)
    after_up = harness.capture_state_snapshot(field, label="after-up-nav")
    harness.press_key(field, Qt.Key.Key_Down)
    after_down = harness.capture_state_snapshot(field, label="after-down-nav")
    harness.press_key(field, Qt.Key.Key_Left)
    after_left = harness.capture_state_snapshot(field, label="after-left-reset")

    up_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=before,
        after=after_up,
    )
    down_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=after_up,
        after=after_down,
    )
    left_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=after_down,
        after=after_left,
    )
    violations = up_violations + down_violations + left_violations
    if violations:
        artifact = harness.save_artifacts(
            "vertical-navigation-left-bad-caret-owner-state",
            before=before,
            after=after_left,
            invariant="Vertical caret navigation must own and reset preferred x.",
            observed=(
                f"up={up_violations}; down={down_violations}; left={left_violations}"
            ),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after_up.caret_preferred_x is not None
    assert after_down.caret_preferred_x is not None
    assert after_left.caret_preferred_x is None
    assert not after_left.skip_next_same_source_soft_wrap_move
    assert not violations


def test_real_shell_long_document_home_end_keep_caret_visible(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Document-boundary navigation must scroll same-position carets into view."""

    prompt = "\n".join(
        f"line {index:02d} backpack basket empty eyes pointy ears"
        for index in range(60)
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.shell.resize(520, 420)
    harness.process_events(cycles=10)
    before = harness.capture_state_snapshot(field, label="before-long-end")
    harness.press_key(field, Qt.Key.Key_End)
    after_end = harness.capture_state_snapshot(field, label="after-long-end")
    harness.press_key(field, Qt.Key.Key_Home)
    after_home = harness.capture_state_snapshot(field, label="after-long-home")

    end_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=before,
        after=after_end,
    )
    home_violations = harness.transition_invariant_violations(
        action_name="caret",
        before=after_end,
        after=after_home,
    )
    violations = end_violations + home_violations
    if violations:
        artifact = harness.save_artifacts(
            "long-document-boundary-navigation-left-caret-hidden",
            before=before,
            after=after_home,
            invariant="Home/End navigation must keep long-document carets visible.",
            observed=f"end={end_violations}; home={home_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.vertical_scroll_maximum > 0
    assert after_end.cursor_position == len(prompt)
    assert after_end.caret_rect_intersects_viewport
    assert (
        after_end.scroll_values["editor_vertical"]
        > before.scroll_values["editor_vertical"]
    )
    assert after_home.cursor_position == 0
    assert after_home.caret_rect_intersects_viewport
    assert (
        after_home.scroll_values["editor_vertical"]
        <= after_end.scroll_values["editor_vertical"]
    )
    assert not violations


def test_real_shell_resize_wrap_keeps_layout_and_caret_sane(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Repeated width changes should preserve coherent layout and caret state."""

    prompt = (
        "masterpiece, best quality, very aesthetic, official art, "
        "(small:1.20), backpack basket, empty eyes, pointy ears, sharp teeth, "
        "<lora:missing:1.00>, glowing red eyes, long white hair"
    )
    field = harness.add_prompt_workflow(initial_text=prompt)
    harness.move_cursor_to_end(field)
    before = harness.capture_state_snapshot(field, label="before-resize-wrap")
    snapshots = []
    for index, width in enumerate((460, 920, 560, 1180, 520)):
        harness.shell.resize(width, 640)
        harness.process_events(cycles=10)
        snapshots.append(
            harness.capture_state_snapshot(field, label=f"after-resize-{index}")
        )

    violations: list[str] = []
    previous = before
    for snapshot in snapshots:
        violations.extend(
            harness.transition_invariant_violations(
                action_name="resize",
                before=previous,
                after=snapshot,
            )
        )
        previous = snapshot
    if violations:
        artifact = harness.save_artifacts(
            "resize-wrap-left-bad-editor-state",
            before=before,
            after=snapshots[-1],
            invariant="Resize/wrap changes must keep layout and caret state coherent.",
            observed=f"violations={tuple(dict.fromkeys(violations))}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert all(snapshot.source_text == prompt for snapshot in snapshots)
    assert not violations


def test_real_shell_escape_clears_ghost_and_dropdown(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Verify Escape clears visible autocomplete surfaces."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-escape-clear")
    harness.press_key(field, Qt.Key.Key_Escape)
    after = harness.capture_state_snapshot(field, label="after-escape-clear")
    violations = harness.transition_invariant_violations(
        action_name="escape",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "escape-did-not-clear-autocomplete",
            before=before,
            after=after,
            invariant="Escape with active autocomplete clears ghost and dropdown.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def test_real_shell_cursor_navigation_clears_or_retargets_ghost(
    harness: RealShellPromptEditorHarness,
) -> None:
    """Detect stale ghost text after cursor navigation changes the active prefix."""

    field = harness.add_prompt_workflow(initial_text="")
    harness.type_text(field, "re")
    before = harness.capture_state_snapshot(field, label="before-left")
    harness.press_key(field, Qt.Key.Key_Left)
    after = harness.capture_state_snapshot(field, label="after-left")
    violations = harness.transition_invariant_violations(
        action_name="cursor",
        before=before,
        after=after,
    )

    if violations:
        artifact = harness.save_artifacts(
            "cursor-navigation-stale-ghost",
            before=before,
            after=after,
            invariant="Cursor movement clears or retargets autocomplete ghost text.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations


def _autocomplete_stale_observed(snapshot: object) -> str:
    """Return a compact observation string for autocomplete stale artifacts."""

    return (
        f"preview_active={getattr(snapshot, 'autocomplete_preview_active')}, "
        f"preview_suffix={getattr(snapshot, 'autocomplete_preview_suffix')!r}, "
        f"active_session={getattr(snapshot, 'autocomplete_has_active_session')}, "
        f"presenter_panel_visible="
        f"{getattr(snapshot, 'autocomplete_presenter_panel_visible')}, "
        f"source={getattr(snapshot, 'source_text')!r}, "
        f"projection={getattr(snapshot, 'projection_text', '<missing>')!r}, "
        f"active_projection={getattr(snapshot, 'active_projection_text', '<missing>')!r}, "
        f"layout_projection={getattr(snapshot, 'layout_projection_text', '<missing>')!r}, "
        "layout_uses_projection_document="
        f"{getattr(snapshot, 'layout_uses_projection_document', '<missing>')}, "
        f"paint_cache_key_present={getattr(snapshot, 'paint_cache_key_present', '<missing>')}, "
        "paint_cache_ghosted_run_ids="
        f"{getattr(snapshot, 'paint_cache_ghosted_run_ids', '<missing>')}"
    )
