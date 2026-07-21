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

"""Define spellcheck publication, menu, and repair torture workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario


def diagnostic_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return production spellcheck diagnostics and action scenarios."""

    source = "mispelled prompt segment"
    corrected = "misspelled prompt segment"
    spelling_range = ("spelling", 0, len("mispelled"))
    actions = (
        PromptAbuseAction(
            "refresh_diagnostics",
            expected_source=source,
            expected_diagnostics=(spelling_range,),
        ),
        PromptAbuseAction(
            "context_menu",
            position=2,
            expected_source=source,
            expected_diagnostics=(spelling_range,),
            expected_context_labels=("misspelled", "Ignore spelling"),
        ),
        PromptAbuseAction(
            "context_menu_trigger_cached",
            value="misspelled",
            expected_source=corrected,
        ),
        PromptAbuseAction("drain_events", expected_source=corrected),
    )
    return (
        PromptAbuseScenario(
            name="spellcheck-diagnostic-action",
            initial_text=source,
            actions=actions,
            expected_text=corrected,
            cursor_position=len(source),
            fixture_features=("spellcheck",),
        ),
    )


__all__ = ["diagnostic_scenarios"]
