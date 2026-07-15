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

"""Tests for shell layout capture and restore arithmetic."""

from __future__ import annotations

from substitute.domain.workspace_snapshot import ShellLayoutSnapshot
from substitute.presentation.shell.shell_layout_state import (
    MIN_CANVAS_PANEL_WIDTH,
    MIN_EDITOR_PANEL_WIDTH,
    MIN_SIDE_PANEL_WIDTH,
    LiveShellLayoutMeasurements,
    build_shell_layout_restore_plan,
    canonical_layout_from_measurements,
)


def test_canonical_layout_from_measurements_keeps_positive_dimensions() -> None:
    """Live shell measurements should become durable canonical layout values."""

    layout = canonical_layout_from_measurements(
        LiveShellLayoutMeasurements(
            main_splitter_sizes=(1038, 500, 0),
            editor_output_splitter_sizes=(700, 300),
            cube_stack_width=206,
            editor_panel_width=832,
            canvas_panel_width=500,
            side_panel_visible=True,
            side_panel_width=360,
            output_panel_height=240,
        )
    )

    assert layout.cube_stack_width == 206
    assert layout.editor_panel_width == 832
    assert layout.canvas_panel_width == 500
    assert layout.side_panel_visible is True
    assert layout.side_panel_width == 360
    assert layout.output_panel_height == 240


def test_restore_plan_prefers_canonical_widths_over_raw_splitter_sizes() -> None:
    """Canonical layout fields should reconstruct the splitter over raw Qt sizes."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            main_splitter_sizes=(640, 1000, 0),
            cube_stack_width=206,
            editor_panel_width=832,
            canvas_panel_width=500,
            side_panel_visible=True,
            side_panel_width=360,
        ),
        available_width=1900,
        target_pane_count=3,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.used_legacy_splitter is False
    assert plan.cube_stack_width == 206
    assert plan.main_splitter_sizes == (1038, 502, 360)
    assert plan.side_panel_visible is True
    assert plan.side_panel_width == 360


def test_restore_plan_clamps_canvas_in_legacy_splitter_payloads() -> None:
    """Legacy raw splitter restore should avoid preserving a collapsed canvas."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(main_splitter_sizes=(1535, 94, 0)),
        available_width=1628,
        target_pane_count=3,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.used_legacy_splitter is True
    assert plan.main_splitter_sizes[1] == MIN_CANVAS_PANEL_WIDTH
    assert "main_splitter_sizes" in plan.clamped_fields


def test_restore_plan_hidden_side_panel_remains_zero_width() -> None:
    """Hidden side panels should not reserve splitter width."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            cube_stack_width=206,
            editor_panel_width=832,
            side_panel_visible=False,
            side_panel_width=420,
        ),
        available_width=1600,
        target_pane_count=3,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.side_panel_visible is False
    assert plan.side_panel_width is None
    assert plan.main_splitter_sizes[2] == 0


def test_restore_plan_derives_compact_width_from_mode() -> None:
    """Compact snapshots should repair mismatched serialized stack width."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            cube_stack_compact=True,
            cube_stack_width=206,
            editor_panel_width=832,
        ),
        available_width=1400,
        target_pane_count=2,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.cube_stack_compact is True
    assert plan.cube_stack_width == 58
    assert plan.main_splitter_sizes[0] == 890
    assert "cube_stack_width" in plan.clamped_fields


def test_restore_plan_derives_expanded_width_from_mode() -> None:
    """Expanded snapshots should repair mismatched serialized stack width."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            cube_stack_compact=False,
            cube_stack_width=58,
            editor_panel_width=832,
        ),
        available_width=1400,
        target_pane_count=2,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.cube_stack_compact is False
    assert plan.cube_stack_width == 206
    assert plan.main_splitter_sizes[0] == 1038
    assert "cube_stack_width" in plan.clamped_fields


def test_restore_plan_keeps_editor_width_when_window_width_changes() -> None:
    """A wider restored window should grow canvas instead of editor intent."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            cube_stack_width=206,
            editor_panel_width=832,
            canvas_panel_width=400,
        ),
        available_width=1800,
        target_pane_count=2,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.main_splitter_sizes[0] == 1038
    assert plan.main_splitter_sizes[1] == 762


def test_restore_plan_clamps_editor_when_window_is_too_narrow() -> None:
    """A narrow window should clamp editor/canvas widths to usable minimums."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(cube_stack_width=206, editor_panel_width=1200),
        available_width=700,
        target_pane_count=2,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.main_splitter_sizes[0] == 580
    assert plan.main_splitter_sizes[1] == MIN_CANVAS_PANEL_WIDTH
    assert plan.main_splitter_sizes[0] >= MIN_EDITOR_PANEL_WIDTH
    assert "editor_panel_width" in plan.clamped_fields


def test_restore_plan_clamps_visible_side_panel_width() -> None:
    """Visible side panels should restore at a usable width."""

    plan = build_shell_layout_restore_plan(
        ShellLayoutSnapshot(
            cube_stack_width=206,
            editor_panel_width=832,
            side_panel_visible=True,
            side_panel_width=10,
        ),
        available_width=1600,
        target_pane_count=3,
        compact_cube_stack_width=58,
        expanded_cube_stack_width=206,
    )

    assert plan.side_panel_width == MIN_SIDE_PANEL_WIDTH
    assert plan.main_splitter_sizes[2] == MIN_SIDE_PANEL_WIDTH
    assert "side_panel_width" in plan.clamped_fields
