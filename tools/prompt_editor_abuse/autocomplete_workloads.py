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

"""Define deterministic autocomplete lifecycle torture workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def autocomplete_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact query, ghost, navigation, acceptance, and dismissal abuse."""

    return (_autocomplete_navigation_acceptance_scenario(),)


def _autocomplete_navigation_acceptance_scenario() -> PromptAbuseScenario:
    """Select and accept a non-default suggestion before dismissing a new query."""

    query = PromptAbuseScenarioBuilder("", cursor_position=0)
    query.type_text("re")
    query.drain_events()
    query.key("down")
    accepted = "re:stage!, "
    acceptance = PromptAbuseAction(
        "key",
        value="tab",
        expected_source=accepted,
        expected_cursor_position=len(accepted),
        expected_anchor_position=len(accepted),
    )
    continuation = PromptAbuseScenarioBuilder(
        accepted,
        cursor_position=len(accepted),
    )
    continuation.type_text("backpack")
    continuation.drain_events()
    continuation.key("escape")
    continuation.drain_events()
    return PromptAbuseScenario(
        "autocomplete-navigation-acceptance",
        initial_text="",
        actions=(*query.actions, acceptance, *continuation.actions),
        expected_text=continuation.text,
    )


__all__ = ["autocomplete_scenarios"]
