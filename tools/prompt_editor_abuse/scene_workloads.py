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

"""Define immediate scene-title editing and deletion workloads."""

from __future__ import annotations

from dataclasses import replace

from .models import PromptAbuseScenario
from .scenario_builder import PromptAbuseScenarioBuilder


def scene_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return exact scene topology mutation workloads."""

    return (
        _scene_spaced_title_typing_scenario(),
        _scene_edit_delete_scenario(),
        _scene_enter_backspace_relocation_torture_scenario(),
    )


def _scene_spaced_title_typing_scenario() -> PromptAbuseScenario:
    """Type and revise a long scene title while every space remains visible."""

    builder = PromptAbuseScenarioBuilder("", cursor_position=0)
    builder.type_text("**scene ")
    builder.passive_action("request_paint")
    builder.actions[-1] = replace(
        builder.actions[-1],
        expected_scene_titles=("scene",),
    )
    builder.type_text("with a deliberately long title and many spaced words")
    builder.drain_events()
    builder.passive_action("request_paint")
    middle = builder.text.index("deliberately") + len("deliberately")
    builder.move_cursor(middle)
    builder.actions[-1] = replace(
        builder.actions[-1],
        expected_scene_titles=(
            "scene with a deliberately long title and many spaced words",
        ),
    )
    builder.type_text(" very")
    builder.key("backspace")
    builder.type_text("y")
    builder.drain_events()
    return builder.build(
        "scene-spaced-title-typing",
        "",
        initial_cursor_position=0,
        viewport_size=(430, 260),
    )


def _scene_edit_delete_scenario() -> PromptAbuseScenario:
    """Rename one scene and delete another with synchronous owner checkpoints."""

    source = "**Scene One\nbody\n**Scene Two\nend"
    builder = PromptAbuseScenarioBuilder(source, cursor_position=2)
    first_title_end = source.index("\n")
    builder.select(2, first_title_end)
    builder.type_text("Renamed")
    builder.passive_action("request_paint")
    builder.actions[-1] = replace(
        builder.actions[-1],
        expected_scene_titles=("Renamed", "Scene Two"),
    )

    second_scene_start = builder.text.index("**Scene Two")
    second_scene_end = second_scene_start + len("**Scene Two\n")
    builder.select(second_scene_start, second_scene_end)
    builder.key("delete")
    builder.passive_action("request_paint")
    builder.actions[-1] = replace(
        builder.actions[-1],
        expected_scene_titles=("Renamed",),
    )
    builder.drain_events()
    return builder.build(
        "scene-edit-delete-immediate",
        source,
        initial_cursor_position=2,
        viewport_size=(420, 240),
    )


def _scene_enter_backspace_relocation_torture_scenario() -> PromptAbuseScenario:
    """Alternate scene-body newlines and clicks without recursive caret history."""

    source = "**scene\nbody, (sharp eyes:1.25), <lora:detail_booster:1.00>"
    title_end = len("**scene")
    builder = PromptAbuseScenarioBuilder(source, cursor_position=title_end)
    for cycle in range(40):
        builder.move_cursor(title_end)
        builder.key("enter")
        builder.key("backspace")
        if cycle % 5 == 4:
            builder.passive_action("request_paint")
            builder.actions[-1] = replace(
                builder.actions[-1],
                expected_scene_titles=("scene",),
            )
            builder.drain_events()
    return builder.build(
        "scene-enter-backspace-relocation-torture",
        source,
        initial_cursor_position=title_end,
        viewport_size=(460, 260),
    )


__all__ = ["scene_scenarios"]
