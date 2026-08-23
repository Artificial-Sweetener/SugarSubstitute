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

"""Verify navigation and source-order repair around projected separators."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_horizontal_navigation_crosses_separator_without_stalling(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Cross one hidden separator with one visible left or right move."""

    source = "global\n[SEP]\npink witch hat"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    regional_start = source.index("pink")
    real_shell_scenario.input.set_source_cursor_position(field, global_end)

    before = real_shell_scenario.snapshots.capture(
        field,
        label="separator-right-before",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
    after_right = real_shell_scenario.snapshots.capture(
        field,
        label="separator-right-after",
    )

    assert after_right.cursor_position == regional_start
    assert after_right.caret_state_placement == "plain_text"
    assert after_right.caret_rect != before.caret_rect

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Left)
    after_left = real_shell_scenario.snapshots.capture(
        field,
        label="separator-left-after",
    )

    assert after_left.cursor_position == global_end
    assert after_left.caret_state_placement == "plain_text"
    assert after_left.caret_rect == before.caret_rect
    assert not snapshot_invariant_violations(after_right)
    assert not snapshot_invariant_violations(after_left)


def test_real_shell_horizontal_navigation_visits_adjacent_empty_region_once(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose one visible caret row for the empty region between dividers."""

    source = "global\n[SEP]\n[SEP]\nregional"
    global_end = source.index("\n")
    empty_region = source.rindex("[SEP]")
    regional_start = source.index("regional")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, global_end)
    snapshots = [
        real_shell_scenario.snapshots.capture(
            field,
            label="adjacent-navigation-global",
        )
    ]

    for label in ("empty", "regional"):
        real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
        snapshots.append(
            real_shell_scenario.snapshots.capture(
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
    assert all(not snapshot_invariant_violations(snapshot) for snapshot in snapshots)


def test_real_shell_separator_navigation_never_enters_hidden_source_or_stalls(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Cross atomic separator boundaries without hidden caret or anchor stops."""

    source = "above\n[SEP]\nbelow"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, source.index("\n"))
    snapshots = [
        real_shell_scenario.snapshots.capture(field, label="separator-atomic-origin")
    ]

    for step in range(3):
        real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
        snapshots.append(
            real_shell_scenario.snapshots.capture(
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
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Select across hidden separator source without hidden anchor stops."""

    source = "above\n[SEP]\nbelow"
    global_end = source.index("\n")
    regional_start = source.index("below")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, global_end)

    real_shell_scenario.input.press_key(
        field,
        Qt.Key.Key_Right,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    selected = real_shell_scenario.snapshots.capture(
        field,
        label="separator-shift-right",
    )
    real_shell_scenario.input.press_key(
        field,
        Qt.Key.Key_Left,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    collapsed = real_shell_scenario.snapshots.capture(
        field,
        label="separator-shift-left",
    )

    assert selected.selection_range == (global_end, regional_start)
    assert selected.selected_source_text == "\n[SEP]\n"
    assert selected.cursor_position == regional_start
    assert not selected.caret_inside_region_separator
    assert not selected.anchor_inside_region_separator
    assert collapsed.selection_range == (global_end, global_end)
    assert collapsed.cursor_position == global_end
    assert not snapshot_invariant_violations(selected)
    assert not snapshot_invariant_violations(collapsed)


def test_real_shell_requested_hidden_separator_positions_resolve_to_atomic_edges(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Resolve external caret placement inside `[SEP]` to visible edges."""

    source = "above\n[SEP]\nbelow"
    separator_start = source.index("[SEP]")
    separator_end = separator_start + len("[SEP]")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)

    for position in range(separator_start + 1, separator_end):
        real_shell_scenario.input.set_source_cursor_position(field, position)
        snapshot = real_shell_scenario.snapshots.capture(
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
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Place the caret beside, rather than inside, a clicked separator row."""

    source = "above\n[SEP]\nbelow"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    before = real_shell_scenario.snapshots.capture(
        field,
        label="separator-row-before-click",
    )
    structural_row = next(
        row for row in before.visible_layout_rows if row.is_structural
    )
    point = QPoint(
        before.viewport_rect[2] // 2,
        round(structural_row.viewport_top + structural_row.height / 2.0),
    )

    real_shell_scenario.input.click_editor_viewport_point(field, point)
    clicked = real_shell_scenario.snapshots.capture(
        field,
        label="separator-row-after-click",
    )

    assert clicked.cursor_position in {source.index("\n"), source.index("below")}
    assert clicked.caret_state_placement == "plain_text"
    assert clicked.caret_token_id is None
    assert not clicked.caret_inside_region_separator
    assert not snapshot_invariant_violations(clicked)


def test_real_shell_nearby_inline_sep_text_preserves_visual_source_order(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Edit a nearby visual row while normalizing inserted `[SEP]` syntax."""

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
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)

    real_shell_scenario.input.click_projected_source_position(field, insertion_position)
    clicked = real_shell_scenario.snapshots.capture(
        field,
        label="near-separator-clicked",
    )
    immediate = real_shell_scenario.input.type_text_and_capture_immediate_state(
        field,
        typed_text,
        label="near-separator-typed-immediate",
    )
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="near-separator-typed-settled",
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
    immediate_violations = snapshot_invariant_violations(immediate)
    assert all(
        violation.startswith("shell_height_contract_mismatch:")
        for violation in immediate_violations
    ), immediate_violations
    assert not snapshot_invariant_violations(settled)
