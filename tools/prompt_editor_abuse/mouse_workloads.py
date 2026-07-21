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

"""Define real-pointer caret and selection workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario


def mouse_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact click and directional drag-selection scenarios."""

    return (_mouse_caret_selection_scenario(),)


def _mouse_caret_selection_scenario() -> PromptAbuseScenario:
    """Click among wrapped lines and drag a cross-line source selection."""

    source = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    click_position = source.index("epsilon") + 3
    selection_start = source.index("beta")
    selection_end = source.index("theta") + len("theta")
    actions = (
        PromptAbuseAction(
            "mouse_caret",
            position=click_position,
            expected_source=source,
            expected_cursor_position=click_position,
            expected_anchor_position=click_position,
        ),
        PromptAbuseAction(
            "mouse_drag_selection",
            position=selection_start,
            selection_end=selection_end,
            expected_source=source,
            expected_cursor_position=selection_end,
            expected_anchor_position=selection_start,
        ),
        PromptAbuseAction(
            "request_paint",
            expected_source=source,
            expected_cursor_position=selection_end,
            expected_anchor_position=selection_start,
        ),
        PromptAbuseAction(
            "event_turn",
            expected_source=source,
            expected_cursor_position=selection_end,
            expected_anchor_position=selection_start,
        ),
    )
    return PromptAbuseScenario(
        name="mouse-caret-drag-selection",
        initial_text=source,
        actions=actions,
        expected_text=source,
        viewport_size=(250, 180),
    )


__all__ = ["mouse_scenarios"]
