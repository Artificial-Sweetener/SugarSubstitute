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

"""Test prompt-editor abuse scenario-minimization contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.models import (
    PromptAbuseAction,
    PromptAbuseScenario,
)
from tools.prompt_editor_abuse.minimization import truncate_scenario_to_sample


def test_minimizer_truncates_one_typed_action_at_the_selected_unit() -> None:
    """A slow character should become the final unit of an exact replay."""

    scenario = PromptAbuseScenario(
        "typing",
        "alpha",
        (
            PromptAbuseAction(
                "type",
                value="abcdef",
                expected_source="alphaabcdef",
                expected_cursor_position=11,
            ),
        ),
        "alphaabcdef",
        cursor_position=5,
    )

    minimized = truncate_scenario_to_sample(
        scenario,
        action_index=0,
        unit_index=2,
    )

    assert minimized.actions[0].value == "abc"
    assert minimized.expected_text == "alphaabc"
    assert minimized.actions[0].expected_cursor_position == 8
