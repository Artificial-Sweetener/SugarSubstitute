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

"""Define LoRA and wildcard syntax/autocomplete torture workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def structured_syntax_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return structured-token projection and acceptance scenarios."""

    return (
        _lora_syntax_scenario(),
        _lora_autocomplete_scenario(),
        _wildcard_autocomplete_scenario(),
    )


def _lora_syntax_scenario() -> PromptAbuseScenario:
    """Form and repaint a complete LoRA schedule token one key at a time."""

    builder = PromptAbuseScenarioBuilder("", cursor_position=0)
    builder.type_text("<lora:detail_booster:1.00>")
    builder.drain_events()
    actions = (
        *builder.actions,
        PromptAbuseAction(
            "request_paint",
            expected_source=builder.text,
            expected_token_kinds=("lora",),
        ),
        PromptAbuseAction("event_turn", expected_source=builder.text),
    )
    return PromptAbuseScenario(
        name="lora-syntax-formation",
        initial_text="",
        actions=actions,
        expected_text=builder.text,
        fixture_features=("lora_catalog",),
    )


def _lora_autocomplete_scenario() -> PromptAbuseScenario:
    """Query and accept a catalog LoRA through the real autocomplete session."""

    prefix = "<lora:det"
    accepted = "<lora:detail_booster:1.00>"
    builder = PromptAbuseScenarioBuilder("", cursor_position=0)
    builder.type_text(prefix)
    builder.drain_events()
    return PromptAbuseScenario(
        name="lora-autocomplete-acceptance",
        initial_text="",
        actions=(
            *builder.actions,
            PromptAbuseAction(
                "key",
                value="tab",
                expected_source=accepted,
                expected_cursor_position=len(accepted),
                expected_anchor_position=len(accepted),
            ),
            PromptAbuseAction("drain_events", expected_source=accepted),
        ),
        expected_text=accepted,
        fixture_features=("lora_catalog",),
    )


def _wildcard_autocomplete_scenario() -> PromptAbuseScenario:
    """Query and accept a wildcard placeholder through the catalog gateway."""

    prefix = "{li"
    accepted = "{lighting/day}"
    builder = PromptAbuseScenarioBuilder("", cursor_position=0)
    builder.type_text(prefix)
    builder.drain_events()
    return PromptAbuseScenario(
        name="wildcard-autocomplete-acceptance",
        initial_text="",
        actions=(
            *builder.actions,
            PromptAbuseAction(
                "key",
                value="tab",
                expected_source=accepted,
                expected_cursor_position=len(accepted),
                expected_anchor_position=len(accepted),
            ),
            PromptAbuseAction("drain_events", expected_source=accepted),
        ),
        expected_text=accepted,
        fixture_features=("wildcard_catalog",),
    )


__all__ = ["structured_syntax_scenarios"]
