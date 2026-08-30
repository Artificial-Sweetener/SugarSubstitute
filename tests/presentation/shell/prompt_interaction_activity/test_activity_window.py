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

"""Test prompt interaction activity-window policy."""

from __future__ import annotations

from substitute.presentation.shell.prompt_interaction_activity import (
    PromptInteractionActivityTracker,
)

import pytest


def test_prompt_interaction_activity_is_active_inside_configured_window() -> None:
    """Prompt interaction activity should stay active only inside its window."""

    now = 10.0
    tracker = PromptInteractionActivityTracker(
        active_window_ms=250,
        clock=lambda: now,
    )

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() is None

    tracker.record_prompt_interaction()

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == 0.0

    now = 10.2

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(200.0)

    now = 10.251

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(251.0)


def test_repeated_prompt_interactions_extend_activity_window() -> None:
    """Repeated interactions should anchor the active window to the latest event."""

    now = 20.0
    tracker = PromptInteractionActivityTracker(
        active_window_ms=100,
        clock=lambda: now,
    )

    tracker.record_prompt_interaction()
    now = 20.08
    tracker.record_prompt_interaction()
    now = 20.15

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(70.0)

    now = 20.181

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(101.0)
