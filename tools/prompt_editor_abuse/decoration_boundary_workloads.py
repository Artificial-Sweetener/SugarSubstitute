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

"""Define exact-checkpoint abuse for projected decoration edit boundaries."""

from __future__ import annotations

from .models import PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def prompt_decoration_boundary_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return hostile edits that settle projection before boundary continuation."""

    continuation_text = "(1girl, blue hair:1.2)"
    content_end = continuation_text.index(":1.2)")
    continuation = PromptAbuseScenarioBuilder(
        continuation_text,
        cursor_position=content_end,
    )
    continuation.type_text(",")
    continuation.drain_events()
    continuation.type_text(" red eyes")
    continuation.drain_events()

    adjacent_comma_text = "ornaments,(red:1.10) heart"
    token_start = adjacent_comma_text.index("(")
    adjacent_comma = PromptAbuseScenarioBuilder(
        adjacent_comma_text,
        cursor_position=token_start,
    )
    adjacent_comma.key("left")
    adjacent_comma.key("right")
    return (
        continuation.build(
            "decoration-content-end-continuation",
            continuation_text,
            initial_cursor_position=content_end,
        ),
        adjacent_comma.build(
            "decorated-comma-boundary-navigation",
            adjacent_comma_text,
            initial_cursor_position=token_start,
        ),
    )


__all__ = ["prompt_decoration_boundary_scenarios"]
