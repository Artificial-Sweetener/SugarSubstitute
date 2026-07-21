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

"""Load and slice exact prompt-editor abuse scenarios for deterministic replay."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, cast

from .models import PromptAbuseAction, PromptAbuseScenario


def load_report_scenarios(
    path: Path,
    *,
    scenario_name: str = "all",
) -> tuple[PromptAbuseScenario, ...]:
    """Return unique scenarios reconstructed from one campaign report."""

    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    unique_scenarios: dict[str, PromptAbuseScenario] = {}
    for result_payload in cast(list[dict[str, Any]], payload.get("results", [])):
        scenario_payload = cast(dict[str, Any], result_payload["scenario"])
        scenario = _scenario_from_payload(scenario_payload)
        unique_scenarios.setdefault(scenario.name, scenario)
    scenarios = tuple(unique_scenarios.values())
    if scenario_name.casefold() == "all":
        return scenarios
    selected = tuple(
        scenario for scenario in scenarios if scenario.name == scenario_name
    )
    if not selected:
        raise ValueError(f"Report {path} does not contain scenario {scenario_name!r}.")
    return selected


def scenario_prefix(
    scenario: PromptAbuseScenario,
    *,
    action_count: int,
) -> PromptAbuseScenario:
    """Return an exact replay ending after the requested action count."""

    if action_count < 1 or action_count > len(scenario.actions):
        raise ValueError("Replay action count lies outside the scenario.")
    actions = scenario.actions[:action_count]
    expected_text = actions[-1].expected_source
    if expected_text is None:
        raise ValueError("Replay prefix ends at an action without a source checkpoint.")
    return replace(
        scenario,
        name=f"{scenario.name}-actions-{action_count}",
        actions=actions,
        expected_text=expected_text,
    )


def _scenario_from_payload(payload: dict[str, Any]) -> PromptAbuseScenario:
    """Reconstruct one typed scenario from its JSON object."""

    actions = tuple(
        PromptAbuseAction(
            kind=cast(Any, action_payload["kind"]),
            value=str(action_payload.get("value", "")),
            position=cast(int | None, action_payload.get("position")),
            selection_end=cast(int | None, action_payload.get("selection_end")),
            viewport_size=_optional_size(action_payload.get("viewport_size")),
            source_ranges=_source_ranges(action_payload.get("source_ranges", ())),
            active_index=cast(int | None, action_payload.get("active_index")),
            expected_source=cast(str | None, action_payload.get("expected_source")),
            expected_cursor_position=cast(
                int | None,
                action_payload.get("expected_cursor_position"),
            ),
            expected_anchor_position=cast(
                int | None,
                action_payload.get("expected_anchor_position"),
            ),
            expected_scene_titles=_optional_string_tuple(
                action_payload.get("expected_scene_titles")
            ),
            expected_diagnostics=_optional_diagnostics(
                action_payload.get("expected_diagnostics")
            ),
            expected_context_labels=_optional_string_tuple(
                action_payload.get("expected_context_labels")
            ),
            expected_token_kinds=_optional_string_tuple(
                action_payload.get("expected_token_kinds")
            ),
        )
        for action_payload in cast(list[dict[str, Any]], payload["actions"])
    )
    return PromptAbuseScenario(
        name=str(payload["name"]),
        initial_text=str(payload["initial_text"]),
        actions=actions,
        expected_text=str(payload["expected_text"]),
        cursor_position=int(payload.get("cursor_position", 0)),
        viewport_size=_size(payload.get("viewport_size", (720, 240))),
        editor_kind=cast(Any, payload.get("editor_kind", "prompt")),
        seed=cast(int | None, payload.get("seed")),
    )


def _optional_size(value: object) -> tuple[int, int] | None:
    """Return an optional JSON size pair as a tuple."""

    if value is None:
        return None
    return _size(value)


def _size(value: object) -> tuple[int, int]:
    """Validate and return one JSON size pair."""

    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Invalid prompt abuse viewport size {value!r}.")
    return int(value[0]), int(value[1])


def _source_ranges(value: object) -> tuple[tuple[int, int], ...]:
    """Validate and return serialized source-range pairs."""

    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Invalid prompt abuse source ranges {value!r}.")
    return tuple(_size(item) for item in value)


def _optional_string_tuple(value: object) -> tuple[str, ...] | None:
    """Return one optional serialized tuple of strings."""

    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Invalid prompt abuse string tuple {value!r}.")
    return tuple(str(item) for item in value)


def _optional_diagnostics(
    value: object,
) -> tuple[tuple[str, int, int], ...] | None:
    """Return optional serialized diagnostic identity triples."""

    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Invalid prompt abuse diagnostics {value!r}.")
    diagnostics: list[tuple[str, int, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise ValueError(f"Invalid prompt abuse diagnostic {item!r}.")
        diagnostics.append((str(item[0]), int(item[1]), int(item[2])))
    return tuple(diagnostics)


__all__ = ["load_report_scenarios", "scenario_prefix"]
