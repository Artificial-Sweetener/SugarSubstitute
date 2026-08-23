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

"""Verify caret invariants across soft-wrap edits and stress sequences."""

from __future__ import annotations

import random

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _CaretPlacementHarness,
    _projection_lines,
)


def test_projection_surface_caret_placement_harness_preserves_soft_wrap_edges(
    widgets: list[QWidget],
) -> None:
    """Right-arrow movement should cross a soft-wrap edge before advancing text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz",
        width=142,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    assert wrap_position > 0

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(right_line_index, "right across soft-wrap edge")

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position + 1
    caret_rect = harness.assert_caret_valid("right after soft-wrap edge")
    right_line = _projection_lines(surface)[right_line_index]
    assert caret_rect.top() == pytest.approx(right_line.top, abs=1.0)
    assert caret_rect.left() > harness.content_left
    assert left_line_index + 1 == right_line_index


def test_projection_surface_caret_placement_harness_backspace_at_soft_wrap_start(
    widgets: list[QWidget],
) -> None:
    """Backspace at a wrapped row start should leave one unambiguous caret position."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz",
        width=142,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(
        right_line_index,
        "initial visual start of wrapped row",
    )

    harness.key(Qt.Key.Key_Backspace)

    assert surface.cursor_position == wrap_position - 1
    caret_rect = harness.assert_caret_has_no_stale_visual_override(
        "after Backspace at soft-wrap row start",
    )
    lines = _projection_lines(surface)
    caret_line_index = harness._line_index_for_rect(caret_rect)
    assert caret_line_index is not None
    assert caret_line_index in {left_line_index, right_line_index}

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    right_rect = harness.assert_caret_valid("right after soft-wrap Backspace")
    right_line_after_index = harness._line_index_for_rect(right_rect)
    assert surface.cursor_position == wrap_position
    assert right_line_after_index is not None
    assert lines


def test_projection_surface_caret_placement_harness_right_arrow_visits_soft_wrap_start(
    widgets: list[QWidget],
) -> None:
    """Right arrow should visit a wrapped row start before the next character."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=150,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface
    _left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)

    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(
        right_line_index,
        "right arrow should visit wrapped row start",
    )


def test_projection_surface_caret_placement_harness_repeated_soft_wrap_start_backspace(
    widgets: list[QWidget],
) -> None:
    """Repeated Backspace at wrapped row starts should not retain stale affinity."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=150,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface

    for iteration in range(12):
        _left_line_index, right_line_index, wrap_position = (
            harness.soft_wrap_transition_pair()
        )
        harness.set_visual_line_start_from_layout_hit(right_line_index)
        assert surface.cursor_position == wrap_position
        harness.assert_caret_at_line_start(
            right_line_index,
            f"iteration {iteration} wrapped row start",
        )

        harness.key(Qt.Key.Key_Backspace)

        assert surface.cursor_position == wrap_position - 1
        harness.assert_caret_has_no_stale_visual_override(
            f"iteration {iteration} after soft-wrap start Backspace",
        )


def test_projection_surface_caret_placement_harness_left_after_soft_wrap_start_backspace(
    widgets: list[QWidget],
) -> None:
    """Left after a soft-wrap-start Backspace should leave the wrap boundary."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alphabetagamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=110,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface
    _left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    harness.set_visual_line_start_from_layout_hit(right_line_index)

    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Backspace)
    after_backspace_position = surface.cursor_position

    harness.key(Qt.Key.Key_Left)

    assert surface.cursor_position == after_backspace_position - 1
    harness.assert_caret_has_no_stale_visual_override(
        "left after soft-wrap-start Backspace",
    )


def test_projection_surface_caret_placement_harness_survives_mixed_edit_navigation(
    widgets: list[QWidget],
) -> None:
    """Caret placement should survive interleaved edits, clicks, and navigation."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon\n"
            "zeta eta theta iota kappa lambda\n"
            "mu nu xi omicron pi rho sigma"
        ),
        width=180,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)

    harness.set_cursor(len("alpha beta gamma"))
    harness.key(Qt.Key.Key_Return)
    harness.type_text("x")
    harness.key(Qt.Key.Key_Left)
    harness.key(Qt.Key.Key_Right)
    harness.key(Qt.Key.Key_Backspace)
    harness.key(Qt.Key.Key_Backspace)

    first_newline = box.toPlainText().index("\n")
    harness.set_cursor(first_newline + 1)
    harness.click_visual_line_start(1)
    harness.key(Qt.Key.Key_Down)
    harness.key(Qt.Key.Key_Up)

    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    harness.set_cursor(max(0, wrap_position - 1))
    harness.key(Qt.Key.Key_Right)
    harness.key(Qt.Key.Key_Right)
    harness.assert_caret_at_line_start(
        right_line_index,
        "mixed sequence soft-wrap transition",
    )
    assert left_line_index + 1 == right_line_index


@pytest.mark.parametrize("seed", [7, 19, 41])
def test_projection_surface_caret_placement_harness_random_edit_navigation_stress(
    widgets: list[QWidget],
    seed: int,
) -> None:
    """Random edit/navigation stress should never place caret in the left margin."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=("alpha beta gamma\ndelta epsilon zeta eta theta\niota kappa lambda mu"),
        width=170,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    rng = random.Random(seed)
    operations: list[str] = []

    for step_index in range(120):
        operations.append(
            harness.random_stress_step(rng=rng, step_index=step_index),
        )

    assert operations


@pytest.mark.parametrize("seed", [11, 23, 37])
def test_projection_surface_caret_placement_harness_random_edit_down_navigation_stress(
    widgets: list[QWidget],
    seed: int,
) -> None:
    """Random edits should not strand Down navigation above lower visual lines."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=("alpha beta gamma\nfajsklfajfkla\n "),
        width=170,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    rng = random.Random(seed)

    for step_index in range(80):
        harness.random_stress_step(rng=rng, step_index=step_index)
        if step_index % 5 == 0:
            harness.assert_down_moves_when_lower_visual_line_exists(
                f"random_down_stress({seed}, {step_index})",
            )
