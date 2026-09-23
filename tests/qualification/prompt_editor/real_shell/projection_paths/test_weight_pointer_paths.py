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

"""Qualify rapid arrow input and nested-text wheel targeting in the real shell."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from substitute.presentation.editor.prompt_editor.interactions.wheel_controller import (
    PromptTokenWeightWheelIntentController,
)
from tests.presentation.editor.prompt_editor.interactions.weight.mounting import (
    emphasis_token_for,
    reveal_emphasis_controls,
    send_viewport_mouse_move,
    wheel_widget_at_point,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_rapid_down_click_at_neutral_keeps_the_same_arrow_target(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """A Qt double-click press over the down arrow must perform the next step."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="(cat:1.05), portrait"
    )
    real_shell_scenario.input.focus_editor(field)
    editor = field.editor
    controls = reveal_emphasis_controls(editor, emphasis_token_for(editor))
    assert controls.decrease_rect is not None
    control_parent = controls.parentWidget()
    assert control_parent is not None
    global_point = control_parent.mapToGlobal(controls.decrease_rect.center().toPoint())

    QTest.mouseClick(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    neutral = real_shell_scenario.snapshots.capture(field, label="arrow-neutral")
    assert neutral.source_text == "cat, portrait"
    assert emphasis_token_for(editor).value_text == "1.00"
    assert controls.isVisible()
    assert controls.decrease_rect is not None
    assert (
        control_parent.mapToGlobal(controls.decrease_rect.center().toPoint())
        == global_point
    )
    assert not snapshot_invariant_violations(neutral)

    QTest.mouseDClick(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    QTest.mouseRelease(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    sub_one = real_shell_scenario.snapshots.capture(field, label="arrow-sub-one")
    assert sub_one.source_text == "(cat:0.95), portrait"
    assert not snapshot_invariant_violations(sub_one)


def test_wheel_on_outer_text_of_nested_emphasis_targets_outer_weight(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """The first word of nested emphasis remains an outer wheel target."""

    source = "(ths (and then this:1.20):1.40)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    editor = field.editor
    outer = emphasis_token_for(editor)
    real_shell_scenario.input.set_source_cursor_position(field, source.index("ths") + 1)
    pointer = editor.cursorRect().center()
    real_shell_scenario.input.set_source_cursor_position(field, len(source))
    viewport = surface_for(editor).viewport()
    controls = reveal_emphasis_controls(editor, outer)
    send_viewport_mouse_move(viewport, pointer)
    wheel_owner = cast(
        PromptTokenWeightWheelIntentController,
        controls._wheel_intent._owner,  # noqa: SLF001
    )
    real_shell_scenario.wait_until(
        lambda: (
            (ready := wheel_owner._ready_token) is not None  # noqa: SLF001
            and ready.token_id == outer.token_id
        ),
        description="outer emphasis wheel hover dwell",
        state=lambda: {
            "candidate": None
            if wheel_owner.candidate_token is None
            else wheel_owner.candidate_token.token_id,
            "ready": None
            if wheel_owner._ready_token is None
            else wheel_owner._ready_token.token_id,  # noqa: SLF001
            "owner_hit": controls.weighted_token_at_viewport_position(pointer),
            "fragment": surface_for(editor).enclosing_emphasis_at_viewport_position(
                pointer
            ),
            "pointer": pointer,
            "host_pointer": controls._gestures.pointer_host_position,  # noqa: SLF001
        },
    )

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=120)
    increased = real_shell_scenario.snapshots.capture(field, label="outer-increased")
    assert increased.source_text == "(ths (and then this:1.20):1.45)"
    assert not snapshot_invariant_violations(increased)
