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

from dataclasses import replace

from .models import PromptAbuseAction, PromptAbuseMountSource, PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def emphasis_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact emphasis formation and shortcut scenarios."""

    pointer_scenarios = (
        _emphasis_pointer_step_scenario(),
        _emphasis_exact_edit_scenario(),
        _lora_pointer_step_scenario(),
        _lora_exact_edit_scenario(),
    )
    return (
        _emphasis_syntax_scenario(),
        _emphasis_shortcut_scenario(),
        _emphasis_wheel_scenario(),
        *pointer_scenarios,
        *_restored_pointer_scenarios(pointer_scenarios),
    )


def _restored_pointer_scenarios(
    scenarios: tuple[PromptAbuseScenario, ...],
) -> tuple[PromptAbuseScenario, ...]:
    """Replay weight pointer routes after both reported restore lifecycles."""

    restored: list[PromptAbuseScenario] = []
    restore_routes: tuple[tuple[PromptAbuseMountSource, str], ...] = (
        ("workspace_cache", "cache-restored"),
        ("workspace_cache_0_19_2", "v0-19-2-cache-restored"),
        ("image_sugar_script", "image-sugar-script-restored"),
    )
    for mount_source, name_prefix in restore_routes:
        restored.extend(
            replace(
                scenario,
                name=f"{name_prefix}-{scenario.name}",
                mount_source=mount_source,
            )
            for scenario in scenarios
        )
    return tuple(restored)


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


def _emphasis_pointer_step_scenario() -> PromptAbuseScenario:
    """Exercise pop-out emphasis arrows around real-shell lifecycle churn."""

    source = "prefix (cat:1.05), tail"
    raised = "prefix (cat:1.10), tail"
    actions = (
        PromptAbuseAction("focus_cycle", expected_source=source),
        PromptAbuseAction("resize", viewport_size=(460, 96), expected_source=source),
        PromptAbuseAction("step_weight", value="up", expected_source=raised),
        PromptAbuseAction("event_turn", expected_source=raised),
        PromptAbuseAction("step_weight", value="down", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="emphasis-pointer-step",
        initial_text=source,
        actions=actions,
        expected_text=source,
    )


def _emphasis_exact_edit_scenario() -> PromptAbuseScenario:
    """Exercise emphasis exact editing through a real double-click and commit."""

    source = "prefix (cat:1.05), tail"
    updated = "prefix (cat:1.37), tail"
    actions = (
        PromptAbuseAction("focus_cycle", expected_source=source),
        PromptAbuseAction("edit_weight_exact", value="1.37", expected_source=updated),
        PromptAbuseAction("drain_events", expected_source=updated),
    )
    return PromptAbuseScenario(
        name="emphasis-exact-edit-pointer",
        initial_text=source,
        actions=actions,
        expected_text=updated,
    )


def _lora_pointer_step_scenario() -> PromptAbuseScenario:
    """Exercise pop-out LoRA arrows around real-shell lifecycle churn."""

    source = "prefix <lora:Mineru:0.80>, tail"
    raised = "prefix <lora:Mineru:0.85>, tail"
    actions = (
        PromptAbuseAction("resize", viewport_size=(460, 96), expected_source=source),
        PromptAbuseAction("step_weight", value="up", expected_source=raised),
        PromptAbuseAction("event_turn", expected_source=raised),
        PromptAbuseAction("step_weight", value="down", expected_source=source),
        PromptAbuseAction("drain_events", expected_source=source),
    )
    return PromptAbuseScenario(
        name="lora-pointer-step",
        initial_text=source,
        actions=actions,
        expected_text=source,
    )


def _lora_exact_edit_scenario() -> PromptAbuseScenario:
    """Exercise LoRA exact editing through a real double-click and commit."""

    source = "prefix <lora:Mineru:0.80>, tail"
    updated = "prefix <lora:Mineru:1.25>, tail"
    actions = (
        PromptAbuseAction("focus_cycle", expected_source=source),
        PromptAbuseAction("edit_weight_exact", value="1.25", expected_source=updated),
        PromptAbuseAction("drain_events", expected_source=updated),
    )
    return PromptAbuseScenario(
        name="lora-exact-edit-pointer",
        initial_text=source,
        actions=actions,
        expected_text=updated,
    )


__all__ = ["emphasis_scenarios"]
