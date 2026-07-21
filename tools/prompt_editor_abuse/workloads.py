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

"""Compose and resolve the complete prompt-editor abuse workload matrix."""

from __future__ import annotations

from .autocomplete_workloads import autocomplete_scenarios
from .danbooru_workloads import danbooru_scenarios
from .diagnostic_workloads import diagnostic_scenarios
from .display_workloads import display_scenarios
from .emphasis_workloads import emphasis_scenarios
from .models import PromptAbuseScenario
from .mouse_workloads import mouse_scenarios
from .keyboard_workloads import keyboard_scenarios
from .lora_feature_workloads import lora_feature_scenarios
from .paint_workloads import prompt_paint_scenarios
from .prompt_workloads import prompt_scenarios
from .scene_workloads import scene_scenarios
from .structured_syntax_workloads import structured_syntax_scenarios
from .wildcard_workloads import wildcard_scenarios
from .workload_constants import KEY_SLAM


def hostile_prompt_scenarios(*, seed: int = 7) -> tuple[PromptAbuseScenario, ...]:
    """Return prompt, wildcard, paint, lifecycle, and mixed hostile workloads."""

    return (
        *prompt_scenarios(seed=seed),
        *autocomplete_scenarios(),
        *diagnostic_scenarios(),
        *danbooru_scenarios(),
        *display_scenarios(),
        *emphasis_scenarios(),
        *lora_feature_scenarios(),
        *mouse_scenarios(),
        *scene_scenarios(),
        *structured_syntax_scenarios(),
        *keyboard_scenarios(),
        *wildcard_scenarios(),
        *prompt_paint_scenarios(),
    )


def resolve_scenarios(name: str, *, seed: int = 7) -> tuple[PromptAbuseScenario, ...]:
    """Return the complete matrix or one exact named scenario."""

    scenarios = hostile_prompt_scenarios(seed=seed)
    if name.casefold() == "all":
        return scenarios
    selected = tuple(scenario for scenario in scenarios if scenario.name == name)
    if not selected:
        raise ValueError(f"Unknown prompt abuse scenario {name!r}.")
    return selected


__all__ = ["KEY_SLAM", "hostile_prompt_scenarios", "resolve_scenarios"]
