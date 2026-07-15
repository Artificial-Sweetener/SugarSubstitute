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

"""Exercise cube close behavior across restored compact shell lifecycles."""

from __future__ import annotations

import os

import pytest

from substitute.presentation.workflows.cube_stack_view import CUBE_ITEM_EXPANDED_WIDTH

from tests.real_shell_cube_stack_harness import (
    RealShellCubeStackHarness,
    assert_compact_close_invariant,
    assert_expanded_close_invariant,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real-shell cube-stack scenarios require non-xdist Qt execution",
        allow_module_level=True,
    )


def test_restored_retracted_stack_exposes_selected_close_after_expansion() -> None:
    """A stack materialized retracted should fully restore close behavior on expand."""

    harness = RealShellCubeStackHarness(start_compact=True)
    harness.add_workflow("workflow-a", ("First", "Selected"))

    assert_compact_close_invariant(harness.probe("workflow-a", "Selected"))
    harness.set_compact(False)
    harness.wait_for_transition()

    expanded = harness.probe("workflow-a", "Selected")
    assert_expanded_close_invariant(expanded)
    assert harness.click_close("workflow-a", "Selected") == [1]


def test_workflow_switch_does_not_repair_expanded_close_state() -> None:
    """Workflow routing should not be required to repair expanded card affordances."""

    harness = RealShellCubeStackHarness(start_compact=True)
    harness.add_workflow("workflow-a", ("A",))
    harness.add_workflow("workflow-b", ("B",))
    harness.switch_workflow("workflow-a")
    harness.set_compact(False)
    harness.wait_for_transition()

    before_switch = harness.probe("workflow-a", "A")
    harness.switch_workflow("workflow-b")
    harness.switch_workflow("workflow-a")
    after_switch = harness.probe("workflow-a", "A")

    assert_expanded_close_invariant(before_switch)
    assert_expanded_close_invariant(after_switch)
    assert before_switch.close_available == after_switch.close_available


def test_restore_retracts_materialized_stack_then_hover_close_recovers_on_expand() -> (
    None
):
    """Restoring compact after materialization should not strand hover affordances."""

    harness = RealShellCubeStackHarness(start_compact=False)
    harness.add_workflow("workflow-a", ("First", "Selected"))
    harness.apply_restored_compact(True)
    harness.hover_card("workflow-a", "First")

    hovered_compact = harness.probe("workflow-a", "First")
    assert hovered_compact.hovered is True
    assert hovered_compact.close_hidden is True
    harness.set_compact(False)
    harness.wait_for_transition()

    hovered_expanded = harness.probe("workflow-a", "First")
    assert hovered_expanded.card_progress == 0.0
    assert hovered_expanded.hovered is True
    assert hovered_expanded.close_available is True
    assert harness.click_close("workflow-a", "First") == [0]


def test_unselected_card_close_remains_available_under_cursor() -> None:
    """Showing the close child under the cursor should not trigger hover flicker."""

    harness = RealShellCubeStackHarness(start_compact=True)
    harness.add_workflow("workflow-a", ("Hover target", "Selected"))
    harness.set_compact(False)
    harness.wait_for_transition()
    harness.hover_close_location("workflow-a", "Hover target")

    hovered = harness.probe("workflow-a", "Hover target")
    assert hovered.selected is False
    assert hovered.close_available is True
    assert harness.click_close("workflow-a", "Hover target") == [0]


def test_rendered_expansion_endpoint_does_not_wait_for_lifecycle_commit() -> None:
    """The X should follow rendered expansion even if committed compact state lags."""

    harness = RealShellCubeStackHarness(start_compact=True)
    harness.add_workflow("workflow-a", ("Selected",))
    harness.render_expanded_endpoint_without_commit("workflow-a")

    endpoint = harness.probe("workflow-a", "Selected")
    assert endpoint.stack_compact is True
    assert endpoint.card_compact is True
    assert endpoint.stack_transition_active is True
    assert endpoint.card_transition_active is True
    assert endpoint.card_progress == 0.0
    assert endpoint.card_width == CUBE_ITEM_EXPANDED_WIDTH
    assert endpoint.close_available is True
    assert endpoint.close_visible_region_empty is False
    assert endpoint.close_center_inside_viewport is True
    assert harness.click_close("workflow-a", "Selected") == [0]


def test_repeated_retracted_start_transitions_preserve_close_invariant() -> None:
    """Rapidly reversed real animations should settle every card coherently."""

    harness = RealShellCubeStackHarness(start_compact=True)
    harness.add_workflow("workflow-a", ("A",))
    harness.add_workflow("workflow-b", ("B",))

    harness.set_compact(False)
    harness.set_compact(True)
    harness.set_compact(False)
    harness.wait_for_transition()

    assert_expanded_close_invariant(harness.probe("workflow-a", "A"))
    expanded_hidden_stack = harness.probe("workflow-b", "B")
    assert expanded_hidden_stack.stack_compact is False
    assert expanded_hidden_stack.card_compact is False
    assert expanded_hidden_stack.card_progress == 0.0
    assert expanded_hidden_stack.close_hidden is False
    assert expanded_hidden_stack.close_enabled is True

    harness.set_compact(True)
    harness.wait_for_transition()
    assert_compact_close_invariant(harness.probe("workflow-a", "A"))
    assert_compact_close_invariant(harness.probe("workflow-b", "B"))


def test_materialization_during_expansion_settles_close_state() -> None:
    """Stacks and cards created during expansion should join the final mode coherently."""

    harness = RealShellCubeStackHarness(start_compact=True)
    first_stack = harness.add_workflow("workflow-a", ("Existing",))
    harness.set_compact(False)
    from PySide6.QtTest import QTest

    QTest.qWait(20)
    first_stack.addTab("Late card", "Late card")
    first_stack.select_cube("Late card", animated=False)
    harness.add_workflow("workflow-b", ("Late workflow",))
    harness.wait_for_transition()

    assert_expanded_close_invariant(harness.probe("workflow-a", "Late card"))
    late_workflow = harness.probe("workflow-b", "Late workflow")
    assert late_workflow.stack_compact is False
    assert late_workflow.card_compact is False
    assert late_workflow.card_progress == 0.0
    assert late_workflow.close_hidden is False
    assert late_workflow.close_enabled is True


def test_rebuild_during_retract_expand_reversal_settles_close_state() -> None:
    """Replacing cards between reversed transitions should not retain compact state."""

    harness = RealShellCubeStackHarness(start_compact=True)
    stack = harness.add_workflow("workflow-a", ("Initial",))
    harness.set_compact(False)
    from PySide6.QtTest import QTest

    QTest.qWait(20)
    stack.clear()
    stack.addTab("Rebuilt", "Rebuilt")
    stack.select_cube("Rebuilt", animated=False)
    harness.set_compact(True)
    QTest.qWait(20)
    harness.set_compact(False)
    harness.wait_for_transition()

    assert_expanded_close_invariant(harness.probe("workflow-a", "Rebuilt"))
