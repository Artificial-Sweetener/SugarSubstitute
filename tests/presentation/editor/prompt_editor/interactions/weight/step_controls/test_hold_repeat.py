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

"""Verify held weight arrows repeat and stop at interaction boundaries."""

from __future__ import annotations

from typing import Literal

import pytest
from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.overlays.token_weight_hold_repeat import (
    PromptTokenWeightHoldRepeater,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    show_prompt_editor,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition
from ..mounting import (
    emphasis_token_for,
    lora_token_for,
    reveal_emphasis_controls,
    show_lora_prompt_editor,
)


def test_held_increase_repeats_and_release_adds_no_step(
    widgets: list[QWidget],
) -> None:
    """Holding an arrow repeats; release ends the gesture without another step."""

    box = show_prompt_editor(widgets, text="(cat:1.05)", width=180)
    controls = reveal_emphasis_controls(box, emphasis_token_for(box))
    assert controls.increase_rect is not None
    control_parent = controls.parentWidget()
    assert control_parent is not None
    global_point = control_parent.mapToGlobal(controls.increase_rect.center().toPoint())
    QTest.mousePress(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    assert box.toPlainText() == "(cat:1.05)"

    wait_for_qt_condition(
        lambda: float(emphasis_token_for(box).value_text or "0") >= 1.15,
        description="two held up-arrow steps",
        state=box.toPlainText,
    )
    before_release = box.toPlainText()
    QTest.mouseRelease(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    assert box.toPlainText() == before_release


def test_held_arrow_repeat_pace_starts_deliberately_and_accelerates_once() -> None:
    """Keep the agreed delay and bounded repeat intervals as an interaction contract."""

    assert PromptTokenWeightHoldRepeater.INITIAL_DELAY_MS == 400
    assert PromptTokenWeightHoldRepeater.interval_for_elapsed_ms(1999) == 120
    assert PromptTokenWeightHoldRepeater.interval_for_elapsed_ms(2000) == 80
    assert PromptTokenWeightHoldRepeater.interval_for_elapsed_ms(10_000) == 80


def test_held_lora_increase_repeats_without_extra_release_step(
    widgets: list[QWidget],
) -> None:
    """A held chip arrow follows the same timing and release contract."""

    box = show_lora_prompt_editor(widgets, text="<lora:Mineru:1.00>", width=300)
    controls = reveal_emphasis_controls(box, lora_token_for(box))
    assert controls.increase_rect is not None
    control_parent = controls.parentWidget()
    assert control_parent is not None
    global_point = control_parent.mapToGlobal(controls.increase_rect.center().toPoint())
    QTest.mousePress(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    wait_for_qt_condition(
        lambda: float(lora_token_for(box).value_text or "0") >= 1.10,
        description="two held LoRA up-arrow steps",
        state=box.toPlainText,
    )
    before_release = box.toPlainText()
    QTest.mouseRelease(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    assert box.toPlainText() == before_release


@pytest.mark.parametrize("cancellation", ("pointer_exit", "window_deactivate"))
def test_held_arrow_cancels_without_delayed_or_release_step(
    widgets: list[QWidget],
    cancellation: Literal["pointer_exit", "window_deactivate"],
) -> None:
    """Leaving the arrow or deactivating the window stops the held gesture."""

    box = show_prompt_editor(widgets, text="(cat:1.05)", width=180)
    controls = reveal_emphasis_controls(box, emphasis_token_for(box))
    assert controls.increase_rect is not None
    control_parent = controls.parentWidget()
    assert control_parent is not None
    global_point = control_parent.mapToGlobal(controls.increase_rect.center().toPoint())
    QTest.mousePress(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    if cancellation == "pointer_exit":
        QTest.mouseMove(controls, QPoint(-12, -12))
    else:
        ensure_qapp().sendEvent(box.window(), QEvent(QEvent.Type.WindowDeactivate))

    deadline_reached = False

    def reach_deadline() -> None:
        """Observe a deadline beyond the initial hold-repeat threshold."""

        nonlocal deadline_reached
        deadline_reached = True

    QTimer.singleShot(550, reach_deadline)
    wait_for_qt_condition(
        lambda: deadline_reached,
        description="canceled hold passes repeat threshold",
    )
    assert box.toPlainText() == "(cat:1.05)"
    QTest.mouseRelease(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    assert box.toPlainText() == "(cat:1.05)"


def test_pointer_exit_stops_an_already_repeating_arrow(
    widgets: list[QWidget],
) -> None:
    """Moving off the pressed arrow stops an active repeat without another step."""

    box = show_prompt_editor(widgets, text="(cat:1.05)", width=180)
    controls = reveal_emphasis_controls(box, emphasis_token_for(box))
    assert controls.increase_rect is not None
    control_parent = controls.parentWidget()
    assert control_parent is not None
    global_point = control_parent.mapToGlobal(controls.increase_rect.center().toPoint())
    QTest.mousePress(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    wait_for_qt_condition(
        lambda: float(emphasis_token_for(box).value_text or "0") >= 1.10,
        description="held arrow begins repeating",
    )
    QTest.mouseMove(controls, QPoint(-12, -12))
    after_exit = box.toPlainText()

    deadline_reached = False

    def reach_deadline() -> None:
        """Observe a deadline beyond the accelerated repeat interval."""

        nonlocal deadline_reached
        deadline_reached = True

    QTimer.singleShot(250, reach_deadline)
    wait_for_qt_condition(
        lambda: deadline_reached,
        description="exited arrow remains stopped",
    )
    assert box.toPlainText() == after_exit
    QTest.mouseRelease(
        controls,
        Qt.MouseButton.LeftButton,
        pos=controls.mapFromGlobal(global_point),
    )
    assert box.toPlainText() == after_exit
