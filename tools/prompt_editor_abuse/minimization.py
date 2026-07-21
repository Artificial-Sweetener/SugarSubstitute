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

"""Reduce saved prompt-editor traces to the earliest actionable failing unit."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, cast

from .models import PromptAbuseScenario
from .replay import load_report_scenarios, scenario_prefix


def minimized_scenario_from_report(
    path: Path,
    *,
    scenario_name: str,
    threshold_ms: float | None = None,
) -> PromptAbuseScenario:
    """Return a replay ending at the first failure or selected latency spike."""

    scenario = load_report_scenarios(path, scenario_name=scenario_name)[0]
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    result = next(
        result
        for result in cast(list[dict[str, Any]], payload.get("results", []))
        if cast(dict[str, Any], result["scenario"])["name"] == scenario_name
    )
    samples = cast(list[dict[str, Any]], result.get("dispatch_samples", []))
    if not samples:
        raise ValueError("Saved scenario has no dispatch samples to minimize.")
    incorrect_sample = next(
        (
            sample
            for sample in samples
            if not sample.get("source_exact", False)
            or not sample.get("caret_exact", False)
            or sample.get("visible_source_current_after_dispatch") is False
            or sample.get("visible_caret_current_after_dispatch") is False
        ),
        None,
    )
    if incorrect_sample is not None:
        selected_sample = incorrect_sample
    elif threshold_ms is not None:
        selected_sample = next(
            (
                sample
                for sample in samples
                if float(sample.get("dispatch_ms", 0.0)) >= threshold_ms
            ),
            max(samples, key=lambda sample: float(sample.get("dispatch_ms", 0.0))),
        )
    else:
        selected_sample = max(
            samples,
            key=lambda sample: float(sample.get("dispatch_ms", 0.0)),
        )
    return truncate_scenario_to_sample(
        scenario,
        action_index=int(selected_sample["action_index"]),
        unit_index=int(selected_sample["unit_index"]),
    )


def truncate_scenario_to_sample(
    scenario: PromptAbuseScenario,
    *,
    action_index: int,
    unit_index: int,
) -> PromptAbuseScenario:
    """Return an exact scenario prefix ending at one per-unit sample."""

    if action_index < 0 or action_index >= len(scenario.actions):
        raise ValueError("Minimization action index lies outside the scenario.")
    action = scenario.actions[action_index]
    if action.kind != "type" or unit_index >= len(action.value) - 1:
        return scenario_prefix(scenario, action_count=action_index + 1)
    if unit_index < 0:
        raise ValueError("Minimization unit index must not be negative.")
    source_before = (
        scenario.initial_text
        if action_index == 0
        else scenario.actions[action_index - 1].expected_source
    )
    if source_before is None:
        raise ValueError("Typed minimization lacks a preceding source checkpoint.")
    selection_start, selection_end = _selection_before_action(
        scenario,
        action_index=action_index,
    )
    typed_prefix = action.value[: unit_index + 1]
    expected_source = (
        source_before[:selection_start] + typed_prefix + source_before[selection_end:]
    )
    expected_cursor = selection_start + len(typed_prefix)
    truncated_action = replace(
        action,
        value=typed_prefix,
        expected_source=expected_source,
        expected_cursor_position=expected_cursor,
    )
    return replace(
        scenario,
        name=f"{scenario.name}-a{action_index}-u{unit_index}",
        actions=scenario.actions[:action_index] + (truncated_action,),
        expected_text=expected_source,
    )


def _selection_before_action(
    scenario: PromptAbuseScenario,
    *,
    action_index: int,
) -> tuple[int, int]:
    """Return the selected source range immediately before one typed action."""

    if action_index > 0:
        previous_action = scenario.actions[action_index - 1]
        if (
            previous_action.kind == "select"
            and previous_action.position is not None
            and previous_action.selection_end is not None
        ):
            return (
                min(previous_action.position, previous_action.selection_end),
                max(previous_action.position, previous_action.selection_end),
            )
        if previous_action.expected_cursor_position is not None:
            position = previous_action.expected_cursor_position
            return position, position
    return scenario.cursor_position, scenario.cursor_position


__all__ = ["minimized_scenario_from_report", "truncate_scenario_to_sample"]
