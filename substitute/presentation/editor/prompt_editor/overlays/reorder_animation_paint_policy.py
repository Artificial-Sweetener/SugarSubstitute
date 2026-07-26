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

"""Constrain reorder animation plans to chips with complete paint ownership."""

from __future__ import annotations

from dataclasses import replace

from ..projection.reorder_animation import (
    PromptReorderAnimationFallback,
    PromptReorderAnimationPlan,
)


def animation_plan_with_complete_paint_ownership(
    plan: PromptReorderAnimationPlan,
    *,
    snapshot_indices: frozenset[int],
) -> PromptReorderAnimationPlan:
    """Animate only chips whose translated chrome also owns complete text paint."""

    animated_targets = tuple(
        target
        for target in plan.changed_targets
        if target.segment_index in snapshot_indices
    )
    immediate_fallbacks = tuple(
        target
        for target in plan.changed_targets
        if target.segment_index not in snapshot_indices
    )
    if not immediate_fallbacks:
        return plan
    fallback_indices = frozenset(target.segment_index for target in immediate_fallbacks)
    return replace(
        plan,
        changed_targets=animated_targets,
        immediate_targets=plan.immediate_targets + immediate_fallbacks,
        immediate_segment_indices=plan.immediate_segment_indices | fallback_indices,
        fallbacks=plan.fallbacks
        + tuple(
            PromptReorderAnimationFallback(
                segment_index=target.segment_index,
                disposition="immediate",
                reason="projection_paint_snapshot_missing",
                generation=plan.generation,
                has_current_rect=True,
                has_target_rect=True,
                target_visible=target.target_visible,
            )
            for target in immediate_fallbacks
        ),
    )


__all__ = ["animation_plan_with_complete_paint_ownership"]
