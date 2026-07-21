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

"""Define prompt viewport repaint and stale-pixel abuse workloads."""

from __future__ import annotations

from .models import (
    PromptAbuseAction,
    PromptAbuseEditorKind,
    PromptAbuseScenario,
)


def prompt_paint_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return explicit viewport repaint workloads for prompt and wildcard shells."""

    prompt_source = (
        "masterpiece, (detailed face:1.20), {lighting/day}, "
        "<lora:detail_booster:0.80>, cinematic background"
    )
    long_prompt_source = (prompt_source + ", ") * 90
    wildcard_source = "1girl, blonde hair, blue eyes\nsmile, red dress\nhat, outdoors"
    return (
        _repaint_scenario(
            name="prompt-viewport-repaint",
            source=prompt_source,
            editor_kind="prompt",
        ),
        _repaint_scenario(
            name="prompt-long-decorated-repaint",
            source=long_prompt_source,
            editor_kind="prompt",
            prelude=(
                PromptAbuseAction(
                    "scroll", value="middle", expected_source=long_prompt_source
                ),
                PromptAbuseAction("drain_events", expected_source=long_prompt_source),
            ),
            viewport_size=(420, 300),
        ),
        _repaint_scenario(
            name="wildcard-viewport-repaint",
            source=wildcard_source,
            editor_kind="wildcard_txt",
        ),
    )


def _repaint_scenario(
    *,
    name: str,
    source: str,
    editor_kind: PromptAbuseEditorKind,
    prelude: tuple[PromptAbuseAction, ...] = (),
    viewport_size: tuple[int, int] = (720, 240),
) -> PromptAbuseScenario:
    """Return repeated paint requests separated into measured event-loop turns."""

    actions = list(prelude)
    for _repetition in range(24):
        actions.extend(
            (
                PromptAbuseAction("request_paint", expected_source=source),
                PromptAbuseAction("drain_events", expected_source=source),
            )
        )
    return PromptAbuseScenario(
        name=name,
        initial_text=source,
        actions=tuple(actions),
        expected_text=source,
        editor_kind=editor_kind,
        cursor_position=len(source) // 2,
        viewport_size=viewport_size,
    )


__all__ = ["prompt_paint_scenarios"]
