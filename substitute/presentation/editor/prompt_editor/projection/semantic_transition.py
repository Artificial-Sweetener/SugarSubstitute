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

"""Locate source ranges whose prepared semantics change projection geometry."""

from __future__ import annotations

from collections import Counter

from substitute.application.prompt_editor import PromptSyntaxRenderPlan

from .incremental_editor import projection_affecting_render_plan_ranges


def semantic_projection_change_range(
    previous_render_plan: PromptSyntaxRenderPlan,
    render_plan: PromptSyntaxRenderPlan,
) -> tuple[int, int] | None:
    """Return the bounded union of added and removed projection ranges.

    Equal range collections are deliberately rejected. A range-stable renderer
    metadata change can still alter geometry, so its owner must use the canonical
    fallback until a richer geometry signature proves local equivalence.
    """

    previous_ranges = projection_affecting_render_plan_ranges(previous_render_plan)
    next_ranges = projection_affecting_render_plan_ranges(render_plan)
    if previous_ranges == next_ranges:
        return None

    previous_counts = Counter(previous_ranges)
    next_counts = Counter(next_ranges)
    changed_ranges = tuple((previous_counts - next_counts).elements()) + tuple(
        (next_counts - previous_counts).elements()
    )
    if not changed_ranges:
        return None
    return (
        min(source_range[0] for source_range in changed_ranges),
        max(source_range[1] for source_range in changed_ranges),
    )


__all__ = ["semantic_projection_change_range"]
