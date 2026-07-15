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

"""Prompt-safe observability fields for performance benchmark results."""

from __future__ import annotations

from dataclasses import fields

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
    ScenarioResult,
)
from substitute.devtools.prompt_editor_performance.scenarios import Scenario


PROMPT_PERFORMANCE_METRIC_NAME = "prompt_editor_performance_scenario"


def scenario_log_fields(
    scenario: Scenario,
    result: ScenarioResult,
) -> dict[str, int | float | str]:
    """Return structured prompt-safe fields for one completed scenario."""

    log_fields: dict[str, int | float | str] = {
        "metric_name": PROMPT_PERFORMANCE_METRIC_NAME,
        "scenario_name": result.name,
        "scenario_operation": scenario.operation,
        "scenario_operation_count": result.operations,
        "scenario_character_count": result.characters,
        "feature_profile_name": feature_profile_name_for_scenario(scenario),
        "average_ms": result.average_ms,
        "p95_ms": result.p95_ms,
        "max_ms": result.max_ms,
    }
    log_fields.update(instrumentation_log_fields(result.instrumentation))
    log_fields.update(extra_count_log_fields(result.extra_counts))
    return log_fields


def feature_profile_name_for_scenario(scenario: Scenario) -> str:
    """Return the named feature-profile class used by one scenario."""

    if (
        scenario.spellcheck_enabled
        or scenario.wildcard_gateway == "static"
        or scenario.danbooru_wiki_enabled
        or scenario.segment_presets_enabled
        or scenario.scheduled_lora_context_enabled
    ):
        return "all_features"
    return "default"


def instrumentation_log_fields(
    instrumentation: Instrumentation,
) -> dict[str, int | float]:
    """Return prefixed count and elapsed values for all instrumentation counters."""

    log_fields: dict[str, int | float] = {}
    for instrumentation_field in fields(instrumentation):
        counter = getattr(instrumentation, instrumentation_field.name)
        if isinstance(counter, OperationCounter):
            prefix = f"instrumentation_{instrumentation_field.name}"
            log_fields[f"{prefix}_count"] = counter.count
            log_fields[f"{prefix}_elapsed_ms"] = counter.elapsed_ms
    return log_fields


def extra_count_log_fields(
    extra_counts: dict[str, int | float],
) -> dict[str, int | float]:
    """Return prefixed safe numeric extra-count values."""

    return {
        f"extra_{key}": value
        for key, value in extra_counts.items()
        if isinstance(key, str) and isinstance(value, int | float)
    }


__all__ = [
    "PROMPT_PERFORMANCE_METRIC_NAME",
    "extra_count_log_fields",
    "feature_profile_name_for_scenario",
    "instrumentation_log_fields",
    "scenario_log_fields",
]
