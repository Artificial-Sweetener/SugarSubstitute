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

"""Define prompt emphasis syntax and keyboard-adjustment workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def emphasis_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact emphasis formation and shortcut scenarios."""

    return (
        _emphasis_syntax_scenario(),
        _emphasis_shortcut_scenario(),
        _emphasis_wheel_scenario(),
    )


def _emphasis_syntax_scenario() -> PromptAbuseScenario:
    """Form explicit weighted emphasis one key at a time and paint it."""

    builder = PromptAbuseScenarioBuilder("", cursor_position=0)
    builder.type_text("(portrait lighting:1.20)")
    builder.passive_action("request_paint")
    builder.drain_events()
    return builder.build(
        "emphasis-syntax-formation",
        "",
        initial_cursor_position=0,
    )


def _emphasis_shortcut_scenario() -> PromptAbuseScenario:
    """Raise and lower an existing weight through the real Ctrl-arrow route."""

    source = "alpha, (portrait:1.20), omega"
    cursor = source.index("portrait")
    raised = "alpha, (portrait:1.25), omega"
    actions = (
        PromptAbuseAction(
            "key",
            value="control_up",
            expected_source=raised,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
        ),
        PromptAbuseAction(
            "request_paint",
            expected_source=raised,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
        ),
        PromptAbuseAction(
            "key",
            value="control_down",
            expected_source=source,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
        ),
        PromptAbuseAction(
            "request_paint",
            expected_source=source,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
        ),
        PromptAbuseAction(
            "drain_events",
            expected_source=source,
            expected_cursor_position=cursor,
            expected_anchor_position=cursor,
        ),
    )
    return PromptAbuseScenario(
        name="emphasis-keyboard-shortcut",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=cursor,
    )


def _emphasis_wheel_scenario() -> PromptAbuseScenario:
    """Adjust a weighted token by pointer wheel while the caret stays elsewhere."""

    source = "prefix (cat:1.05), tail"
    raised = "prefix (cat:1.10), tail"
    actions = (
        PromptAbuseAction(
            "wheel_weight",
            value="up",
            expected_source=raised,
        ),
        PromptAbuseAction("event_turn", expected_source=raised),
        PromptAbuseAction(
            "wheel_weight",
            value="down",
            expected_source=source,
        ),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="emphasis-pointer-wheel",
        initial_text=source,
        actions=actions,
        expected_text=source,
        cursor_position=0,
        wheel_mode="focus_required",
    )


__all__ = ["emphasis_scenarios"]
