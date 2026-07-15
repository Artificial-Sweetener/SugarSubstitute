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

"""Tests for presentation load activity tracking."""

from __future__ import annotations

from substitute.presentation.ui_load_activity import PromptProjectionUiLoadActivity


def test_ui_load_activity_reports_recent_output_activity() -> None:
    """Marked output work should become visible through elapsed and recent checks."""

    now = 10.0
    activity = PromptProjectionUiLoadActivity(clock=lambda: now)

    assert activity.output_activity_elapsed_ms() is None
    assert activity.is_output_activity_recent(within_ms=150) is False

    activity.mark_output_activity(reason="test")
    now = 10.025

    elapsed_ms = activity.output_activity_elapsed_ms()
    assert elapsed_ms is not None
    assert round(elapsed_ms, 3) == 25.0
    assert activity.is_output_activity_recent(within_ms=150) is True
    assert activity.is_output_activity_recent(within_ms=10) is False
