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

    source_text = "(1girl, blue hair:1.2)"
    content_end = source_text.index(":1.2)")
    builder = PromptAbuseScenarioBuilder(
        source_text,
        cursor_position=content_end,
    )
    builder.type_text(",")
    builder.drain_events()
    builder.type_text(" red eyes")
    builder.drain_events()
    return (
        builder.build(
            "decoration-content-end-continuation",
            source_text,
            initial_cursor_position=content_end,
        ),
    )


__all__ = ["prompt_decoration_boundary_scenarios"]
