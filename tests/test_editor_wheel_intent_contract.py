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

"""Verify deliberate wheel-intent arbitration for editor controls."""

from __future__ import annotations

from PySide6.QtCore import QPoint

from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
    WheelIntentTarget,
    WheelIntentTargetKind,
)


def _target(kind: WheelIntentTargetKind, identity: str) -> WheelIntentTarget:
    """Create a target identity for arbiter contract tests."""

    return WheelIntentTarget(kind=kind, widget=None, identity=identity)


def test_target_does_not_arm_immediately_after_pointer_move() -> None:
    """Pointer movement should start dwell rather than immediately arming."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "seed")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    assert arbiter.armed_target(timestamp_ms=1399) is None


def test_target_arms_after_pointer_dwell() -> None:
    """Stable pointer dwell should arm the target reached by mouse movement."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "seed")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    assert arbiter.armed_target(timestamp_ms=1400) == target


def test_target_does_not_arm_without_pointer_movement() -> None:
    """A target cannot arm only because layout moved under the cursor."""

    arbiter = WheelIntentArbiter(dwell_ms=0)

    assert arbiter.armed_target(timestamp_ms=1000) is None


def test_dwell_resets_when_target_identity_changes() -> None:
    """Moving onto a different meaningful target should restart dwell."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    first = _target(WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT, "token-a")
    second = _target(WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT, "token-b")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=first,
        timestamp_ms=1000,
    )
    arbiter.handle_pointer_move(
        global_position=QPoint(12, 10),
        target=second,
        timestamp_ms=1300,
    )

    assert arbiter.armed_target(timestamp_ms=1699) is None
    assert arbiter.armed_target(timestamp_ms=1700) == second


def test_dwell_resets_when_pointer_moves_beyond_stability_radius() -> None:
    """Large movement inside the same target should require a fresh dwell."""

    arbiter = WheelIntentArbiter(dwell_ms=400, stability_radius_px=6)
    target = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )
    arbiter.handle_pointer_move(
        global_position=QPoint(20, 10),
        target=target,
        timestamp_ms=1300,
    )

    assert arbiter.armed_target(timestamp_ms=1699) is None
    assert arbiter.armed_target(timestamp_ms=1700) == target


def test_armed_target_survives_later_movement_inside_same_target() -> None:
    """Intent should hold after dwell while the pointer remains in the same target."""

    arbiter = WheelIntentArbiter(dwell_ms=400, stability_radius_px=6)
    target = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )
    assert arbiter.armed_target(timestamp_ms=1400) == target

    arbiter.handle_pointer_move(
        global_position=QPoint(100, 100),
        target=target,
        timestamp_ms=1500,
    )

    assert arbiter.armed_target(timestamp_ms=1500) == target


def test_wheel_latches_to_editor_scroll_when_no_child_is_armed() -> None:
    """Unarmed wheel input should belong to editor scrolling by default."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    owner = arbiter.wheel_owner_for_event(target=target, timestamp_ms=1200)

    assert owner == WheelIntentTarget.editor_scroll()


def test_premature_wheel_restarts_dwell_without_blocking_target() -> None:
    """Early wheel input should restart dwell without latching editor scroll."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    owner = arbiter.wheel_owner_for_event(target=target, timestamp_ms=1200)

    assert owner == WheelIntentTarget.editor_scroll()
    assert not arbiter.target_is_armed(target, timestamp_ms=1599)
    assert arbiter.target_is_armed(target, timestamp_ms=1600)
    assert arbiter.wheel_owner_for_event(target=target, timestamp_ms=1600) == target


def test_repeated_premature_wheel_restarts_dwell_each_time() -> None:
    """Each early wheel attempt should require a fresh dwell interval."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    assert arbiter.wheel_owner_for_event(target=target, timestamp_ms=1200) == (
        WheelIntentTarget.editor_scroll()
    )
    assert arbiter.wheel_owner_for_event(target=target, timestamp_ms=1400) == (
        WheelIntentTarget.editor_scroll()
    )

    assert not arbiter.target_is_armed(target, timestamp_ms=1799)
    assert arbiter.target_is_armed(target, timestamp_ms=1800)


def test_wheel_latches_to_armed_numeric_target() -> None:
    """Wheel input over an armed numeric target should latch to that target."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=target,
        timestamp_ms=1000,
    )

    owner = arbiter.wheel_owner_for_event(target=target, timestamp_ms=1400)

    assert owner == target


def test_wheel_latches_to_active_matching_target_without_dwell() -> None:
    """Explicitly active targets should not need hover dwell to own wheel input."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")

    arbiter.set_active_target(target)

    owner = arbiter.wheel_owner_for_event(target=target, timestamp_ms=1000)

    assert owner == target


def test_active_target_does_not_steal_wheel_from_other_target() -> None:
    """Active intent should apply only to wheel events over the same target."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    prompt = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")
    numeric = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.set_active_target(prompt)

    owner = arbiter.wheel_owner_for_event(target=numeric, timestamp_ms=1000)

    assert owner == WheelIntentTarget.editor_scroll()


def test_cleared_active_target_no_longer_owns_wheel_without_dwell() -> None:
    """Focus loss should remove active intent without affecting hover dwell."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")

    arbiter.set_active_target(target)
    arbiter.clear_active_target(target)

    owner = arbiter.wheel_owner_for_event(target=target, timestamp_ms=1000)

    assert owner == WheelIntentTarget.editor_scroll()


def test_wheel_gesture_owner_persists_across_same_target_burst() -> None:
    """A wheel burst should keep its owner while the pointer stays on one target."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    numeric = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=numeric,
        timestamp_ms=1000,
    )
    assert arbiter.wheel_owner_for_event(target=numeric, timestamp_ms=1400) == numeric

    arbiter.handle_pointer_move(
        global_position=QPoint(12, 10),
        target=numeric,
        timestamp_ms=1450,
    )

    assert arbiter.wheel_owner_for_event(target=numeric, timestamp_ms=1500) == numeric


def test_new_target_can_arm_after_previous_target_latched() -> None:
    """Moving to another target should allow fresh dwell without editor reset."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    first = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "first")
    second = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "second")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=first,
        timestamp_ms=1000,
    )
    assert arbiter.wheel_owner_for_event(target=first, timestamp_ms=1400) == first

    arbiter.handle_pointer_move(
        global_position=QPoint(40, 10),
        target=second,
        timestamp_ms=1450,
    )

    assert not arbiter.target_is_armed(second, timestamp_ms=1849)
    assert arbiter.target_is_armed(second, timestamp_ms=1850)
    assert arbiter.wheel_owner_for_event(target=second, timestamp_ms=1850) == second


def test_new_target_premature_wheel_restarts_dwell_after_previous_latch() -> None:
    """Early wheel on a new target should restart that target's dwell."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    first = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "first")
    second = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "second")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=first,
        timestamp_ms=1000,
    )
    assert arbiter.wheel_owner_for_event(target=first, timestamp_ms=1400) == first

    arbiter.handle_pointer_move(
        global_position=QPoint(40, 10),
        target=second,
        timestamp_ms=1450,
    )
    assert arbiter.wheel_owner_for_event(target=second, timestamp_ms=1600) == (
        WheelIntentTarget.editor_scroll()
    )

    assert not arbiter.target_is_armed(second, timestamp_ms=1999)
    assert arbiter.target_is_armed(second, timestamp_ms=2000)


def test_wheel_gesture_owner_clears_after_idle_timeout() -> None:
    """Idle wheel gestures should release their latched owner."""

    arbiter = WheelIntentArbiter(dwell_ms=400, gesture_idle_ms=250)
    numeric = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=numeric,
        timestamp_ms=1000,
    )
    assert arbiter.wheel_owner_for_event(target=numeric, timestamp_ms=1400) == numeric

    arbiter.end_gesture_if_idle(timestamp_ms=1650)

    assert arbiter.armed_target(timestamp_ms=1650) == numeric


def test_target_is_armed_releases_idle_latch_before_readiness_check() -> None:
    """Read-only dwell checks should not keep an expired wheel owner latched."""

    arbiter = WheelIntentArbiter(dwell_ms=400, gesture_idle_ms=250)
    numeric = _target(WheelIntentTargetKind.NUMERIC_ADJUSTMENT, "spin")
    prompt_weight = _target(
        WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT,
        "prompt-weight",
    )

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=numeric,
        timestamp_ms=1000,
    )
    assert arbiter.wheel_owner_for_event(target=numeric, timestamp_ms=1400) == numeric

    arbiter.handle_pointer_move(
        global_position=QPoint(40, 10),
        target=prompt_weight,
        timestamp_ms=1700,
    )

    assert arbiter.target_is_armed(prompt_weight, timestamp_ms=2100)


def test_prompt_scroll_target_hands_off_when_it_cannot_scroll_in_direction() -> None:
    """Armed prompt scroll targets should not consume boundary wheel input."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    prompt = _target(WheelIntentTargetKind.PROMPT_SCROLL, "prompt")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=prompt,
        timestamp_ms=1000,
    )

    owner = arbiter.wheel_owner_for_event(
        target=prompt,
        timestamp_ms=1400,
        target_can_accept_wheel=False,
    )

    assert owner == WheelIntentTarget.editor_scroll()


def test_prompt_token_arming_is_token_specific() -> None:
    """Only the hovered weighted-token identity should become armed."""

    arbiter = WheelIntentArbiter(dwell_ms=400)
    first = _target(WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT, "token-a")
    second = _target(WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT, "token-b")

    arbiter.handle_pointer_move(
        global_position=QPoint(10, 10),
        target=first,
        timestamp_ms=1000,
    )

    assert arbiter.target_is_armed(first, timestamp_ms=1400)
    assert not arbiter.target_is_armed(second, timestamp_ms=1400)
