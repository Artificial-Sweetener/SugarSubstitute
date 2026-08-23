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

"""Test prompt-local wheel boundary spill suppression."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.widgets.wheel_intent import (
    DEFAULT_WHEEL_GESTURE_IDLE_MS,
    WheelIntentArbiter,
    WheelIntentTarget,
    WheelIntentTargetKind,
)
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission
from tests.support.prompt_editor.projection_engine_support import (
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.widgets.wheel_intent.support import (
    WheelIntentOwner,
    wheel_event,
)


def test_boundary_wheel_after_idle_is_not_spill(
    wheel_owner: WheelIntentOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow a fresh boundary gesture to bubble after controlled idle time."""

    app = wheel_owner.application
    box = show_prompt_editor(
        wheel_owner.widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    spill_clock_ms = [0]
    monkeypatch.setattr(
        surface_for(box)._wheel_handler,  # noqa: SLF001
        "_spill_now_ms",
        lambda: spill_clock_ms[0],
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.maximum() - 1)
    to_bottom_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), to_bottom_event)
    process_events(app)
    assert to_bottom_event.isAccepted()

    timestamp_ms += 10
    spill_clock_ms[0] += 10
    spill_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), spill_event)
    process_events(app)
    assert spill_event.isAccepted()

    idle_advance = DEFAULT_WHEEL_GESTURE_IDLE_MS + 50
    timestamp_ms += idle_advance
    spill_clock_ms[0] += idle_advance
    after_idle_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), after_idle_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert not after_idle_event.isAccepted()


def _install_prompt_scroll_permission(
    box: PromptEditor,
    arbiter: WheelIntentArbiter,
    timestamp: Callable[[], int],
) -> None:
    """Install prompt-scroll permission backed by one controlled arbiter."""

    target = _prompt_scroll_target(box)

    def allow_wheel(_widget: QWidget, _event: QWheelEvent) -> bool:
        """Allow wheel input only while prompt scrolling owns the gesture."""

        return (
            arbiter.wheel_owner_for_event(
                target=target,
                timestamp_ms=timestamp(),
            )
            == target
        )

    set_wheel_intent_permission(box, allow_wheel)


def _arm_prompt_scroll(
    box: PromptEditor,
    arbiter: WheelIntentArbiter,
    timestamp_ms: int,
) -> int:
    """Arm prompt scrolling and return a timestamp beyond its dwell."""

    target = _prompt_scroll_target(box)
    arbiter.clear_gesture()
    arbiter.handle_pointer_move(
        global_position=box.mapToGlobal(box.rect().center()),
        target=target,
        timestamp_ms=timestamp_ms,
    )
    return timestamp_ms + 400


def _prompt_scroll_target(box: PromptEditor) -> WheelIntentTarget:
    """Build the prompt-scroll target identity for one editor."""

    return WheelIntentTarget(
        kind=WheelIntentTargetKind.PROMPT_SCROLL,
        widget=box,
        identity=("prompt-scroll", id(box)),
    )
