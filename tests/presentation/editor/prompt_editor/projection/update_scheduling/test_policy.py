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

"""Verify pure projection scheduling delay policy."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PromptProjectionScheduleContext,
    PromptProjectionSchedulingPolicy,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_scheduling_policy_delays_recent_prompt_activity() -> None:
    """Safe typing should land after one active typing frame by default."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=None,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.active_typing_delay_ms
    assert decision.prompt_activity_recent is True
    assert decision.output_activity_recent is False
    assert decision.force_due_to_max_stale is False


def test_projection_scheduling_policy_uses_output_busy_delay() -> None:
    """Recent output activity should give safe typing projection a wider slot."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=20.0,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.output_busy_delay_ms
    assert decision.prompt_activity_recent is True
    assert decision.output_activity_recent is True


def test_projection_scheduling_policy_uses_idle_delay_without_activity() -> None:
    """Idle safe projection work should land on the normal next turn."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="prompt_state",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=None,
            output_activity_elapsed_ms=None,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.reason == "idle"


def test_projection_scheduling_policy_enforces_max_stale_cap() -> None:
    """Old pending safe projection work should land immediately."""

    policy = PromptProjectionSchedulingPolicy(max_stale_ms=75)

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=75.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=5.0,
            pending_superseded_count=4,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.force_due_to_max_stale is True
    assert decision.reason == "max_stale"


def test_projection_scheduling_policy_uses_idle_delay_when_not_stale_safe() -> None:
    """Exact or non-safe updates should not be delayed by interaction activity."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="prompt_state",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=5.0,
            pending_superseded_count=0,
            stale_safe=False,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.force_due_to_max_stale is False
    assert decision.reason == "not_stale_safe"
