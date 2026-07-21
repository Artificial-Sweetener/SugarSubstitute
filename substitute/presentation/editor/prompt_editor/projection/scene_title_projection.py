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

"""Build source-faithful visible runs for semantic scene titles."""

from __future__ import annotations

from dataclasses import replace

from .model import PromptProjectionRun, PromptProjectionRunKind, PromptProjectionToken


def build_scene_title_projection_run(
    token: PromptProjectionToken,
    *,
    source_text: str,
    projection_position: int,
) -> PromptProjectionRun:
    """Return a scene run that preserves editable trailing title whitespace."""

    assert token.content_start is not None
    assert token.content_end is not None
    visible_end = max(token.content_end, token.source_end)
    visible_text = source_text[token.content_start : visible_end]
    return PromptProjectionRun(
        run_id=f"scene-title:{token.token_id}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=token.content_start,
        source_end=visible_end,
        display_text=visible_text,
        source_positions=range(token.content_start, visible_end + 1),
        projection_start=projection_position,
        projection_end=projection_position + len(visible_text),
        token_id=token.token_id,
        active=token.active,
        text_style_variant=token.style_variant,
    )


def reconcile_scene_title_projection_run(
    run: PromptProjectionRun,
    *,
    token: PromptProjectionToken,
    source_text: str,
) -> PromptProjectionRun:
    """Align an existing scene run with current semantic and source geometry."""

    canonical_run = build_scene_title_projection_run(
        token,
        source_text=source_text,
        projection_position=run.projection_start,
    )
    return replace(canonical_run, run_id=run.run_id)


__all__ = [
    "build_scene_title_projection_run",
    "reconcile_scene_title_projection_run",
]
