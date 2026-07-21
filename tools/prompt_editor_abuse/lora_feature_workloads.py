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

"""Define LoRA picker and trigger-word interaction torture workloads."""

from __future__ import annotations

from .models import PromptAbuseAction, PromptAbuseScenario


def lora_feature_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return picker opening/activation and trigger-word menu scenarios."""

    return (_lora_picker_scenario(), _lora_trigger_word_scenario())


def _lora_picker_scenario() -> PromptAbuseScenario:
    """Open a populated picker and activate its first production row."""

    inserted = "<lora:detail_booster:1.00>"
    return PromptAbuseScenario(
        name="lora-picker-open-activate",
        initial_text="",
        actions=(
            PromptAbuseAction("drain_events", expected_source=""),
            PromptAbuseAction("lora_picker_open", expected_source=""),
            PromptAbuseAction(
                "lora_picker_activate",
                expected_source=inserted,
            ),
            PromptAbuseAction("drain_events", expected_source=inserted),
        ),
        expected_text=inserted,
        fixture_features=("lora_catalog",),
    )


def _lora_trigger_word_scenario() -> PromptAbuseScenario:
    """Insert trained words from a scheduled inline LoRA menu action."""

    source = "<lora:detail_booster:1.00>, portrait"
    inserted = f"{source}, detail, texture"
    return PromptAbuseScenario(
        name="lora-trigger-word-menu-action",
        initial_text=source,
        actions=(
            PromptAbuseAction("drain_events", expected_source=source),
            PromptAbuseAction(
                "context_menu",
                position=source.index("portrait") + 2,
                expected_source=source,
                expected_context_labels=("Detail Booster…",),
            ),
            PromptAbuseAction(
                "context_menu_trigger_cached",
                value="Trigger words: Detail Booster - local",
                expected_source=inserted,
            ),
            PromptAbuseAction("drain_events", expected_source=inserted),
        ),
        expected_text=inserted,
        cursor_position=len(source),
        fixture_features=("lora_catalog", "scheduled_lora"),
    )


__all__ = ["lora_feature_scenarios"]
