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

"""Qualify continuous emphasis-wheel gestures in the mounted editor shell."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from substitute.presentation.editor.prompt_editor.interactions.wheel_controller import (
    PromptTokenWeightWheelIntentController,
)
from tests.presentation.editor.prompt_editor.interactions.weight.mounting import (
    anchor_rect_for,
    emphasis_token_for,
    reveal_emphasis_controls,
    send_viewport_mouse_move,
    token_rect_for,
    wheel_widget_at_point,
)
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.projection_engine_support import (
    surface_for,
    token_weight_controls_for,
)


def test_continuous_wheel_crosses_neutral_at_one_stationary_pointer(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep neutral visually available until the next wheel tick goes below one."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="(1girl:1.05), portrait"
    )
    real_shell_scenario.input.focus_editor(field)
    real_shell_scenario.input.set_source_cursor_position(field, 0)
    editor = field.editor
    token = emphasis_token_for(editor)
    reveal_emphasis_controls(editor, token)
    controls = token_weight_controls_for(editor)
    wheel_owner = cast(
        PromptTokenWeightWheelIntentController,
        controls._wheel_intent._owner,  # noqa: SLF001
    )
    real_shell_scenario.wait_until(
        lambda: wheel_owner._ready_token is not None,  # noqa: SLF001
        description="emphasis wheel hover dwell",
    )
    pointer = anchor_rect_for(editor, token).center().toPoint()
    viewport = surface_for(editor).viewport()

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=-120)
    neutral = real_shell_scenario.snapshots.capture(field, label="wheel-neutral")
    assert neutral.source_text == "1girl, portrait"
    assert emphasis_token_for(editor).value_text == "1.00"
    assert not snapshot_invariant_violations(neutral)

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=-120)
    sub_one = real_shell_scenario.snapshots.capture(field, label="wheel-sub-one")
    assert sub_one.source_text == "(1girl:0.95), portrait"
    assert not snapshot_invariant_violations(sub_one)


def test_neutral_wheel_decoration_disappears_after_pointer_leaves(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep the 1.00 shell visible during wheel input, then remove it on leave."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="(1girl:1.05), portrait"
    )
    real_shell_scenario.input.focus_editor(field)
    real_shell_scenario.input.set_source_cursor_position(field, 0)
    editor = field.editor
    token = emphasis_token_for(editor)
    controls = reveal_emphasis_controls(editor, token)
    wheel_owner = cast(
        PromptTokenWeightWheelIntentController,
        controls._wheel_intent._owner,  # noqa: SLF001
    )
    real_shell_scenario.wait_until(
        lambda: wheel_owner._ready_token is not None,  # noqa: SLF001
        description="emphasis wheel hover dwell",
    )
    viewport = surface_for(editor).viewport()
    pointer = anchor_rect_for(editor, token).center().toPoint()

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=-120)
    assert editor.toPlainText() == "1girl, portrait"
    assert emphasis_token_for(editor).value_text == "1.00"

    send_viewport_mouse_move(
        viewport, QPoint(viewport.width() - 5, viewport.height() - 5)
    )
    real_shell_scenario.wait_until(
        lambda: (
            not any(
                item.kind.value == "emphasis"
                for item in surface_for(editor).projection_document().tokens
            )
        ),
        description="neutral wheel decoration clears after pointer leave",
    )
    settled = real_shell_scenario.snapshots.capture(field, label="wheel-settled")
    assert settled.source_text == "1girl, portrait"
    assert settled.projection_token_count == 0
    assert not snapshot_invariant_violations(settled)


def test_wheel_over_text_crosses_neutral_after_controls_hide(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep a viewport-owned wheel gesture active when its control chrome hides."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="(1girl:1.05), portrait"
    )
    real_shell_scenario.input.focus_editor(field)
    editor = field.editor
    token = emphasis_token_for(editor)
    controls = reveal_emphasis_controls(editor, token)
    viewport = surface_for(editor).viewport()
    pointer = token_rect_for(editor, token).center().toPoint()
    QTest.mouseMove(viewport, pointer)
    wheel_owner = cast(
        PromptTokenWeightWheelIntentController,
        controls._wheel_intent._owner,  # noqa: SLF001
    )
    real_shell_scenario.wait_until(
        lambda: wheel_owner._ready_token is not None,  # noqa: SLF001
        description="emphasis text wheel hover dwell",
    )

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=-120)
    real_shell_scenario.wait_until(
        lambda: controls.visible_token is None,
        description="controls hide while wheel remains over token text",
    )
    neutral = real_shell_scenario.snapshots.capture(field, label="wheel-text-neutral")
    assert neutral.source_text == "1girl, portrait"
    assert emphasis_token_for(editor).value_text == "1.00"
    assert not snapshot_invariant_violations(neutral)

    assert wheel_widget_at_point(viewport, local_point=pointer, angle_delta_y=-120)
    sub_one = real_shell_scenario.snapshots.capture(field, label="wheel-text-sub-one")
    assert sub_one.source_text == "(1girl:0.95), portrait"
    assert not snapshot_invariant_violations(sub_one)
