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

"""Classify one source edit into an ordered projection strategy plan."""

from __future__ import annotations

from .edit_strategy import (
    PromptEditClassificationInput,
    PromptEditStrategy,
    PromptEditStrategyPlan,
    PromptSourceEditKind,
)


def _strategy_plan(
    *,
    restore_checkpoint: bool,
    direct_deferred_feedback: bool,
    edit_kind: PromptSourceEditKind,
    deferred_plain_edit_extendable: bool,
    allow_trailing_plain_insert: bool,
    wrap_reflow_deferrable: bool,
) -> PromptEditStrategyPlan:
    """Build one immutable module-lifetime strategy plan."""

    candidates: list[PromptEditStrategy] = []
    if restore_checkpoint:
        candidates.append(PromptEditStrategy.RESTORE_CHECKPOINT)
    if direct_deferred_feedback:
        candidates.append(PromptEditStrategy.DEFER_DIRECT_FEEDBACK)
    if deferred_plain_edit_extendable:
        candidates.append(PromptEditStrategy.EXTEND_DEFERRED_WRAP)
    elif edit_kind is PromptSourceEditKind.DELETE:
        candidates.extend(
            (
                PromptEditStrategy.TRAILING_PLAIN_DELETE,
                PromptEditStrategy.TRAILING_NEWLINE_DELETE,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            )
        )
    elif edit_kind is PromptSourceEditKind.NEWLINE_INSERT:
        candidates.extend(
            (
                PromptEditStrategy.TRAILING_NEWLINE_INSERT,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            )
        )
    elif edit_kind is PromptSourceEditKind.PLAIN_REPLACEMENT:
        if allow_trailing_plain_insert:
            candidates.append(PromptEditStrategy.TRAILING_PLAIN_INSERT)
        candidates.append(PromptEditStrategy.INCREMENTAL_PLAIN)
    if wrap_reflow_deferrable:
        candidates.append(PromptEditStrategy.DEFER_INCREMENTAL_WRAP)
    candidates.extend(
        (
            PromptEditStrategy.DEFER_TRANSIENT_FALLBACK,
            PromptEditStrategy.PUBLISH_PREBUILT_REFLOW,
            PromptEditStrategy.BUILD_CANONICAL_REFLOW,
            PromptEditStrategy.FULL_REBUILD,
        )
    )
    return PromptEditStrategyPlan(tuple(candidates))


_FULL_REBUILD_PLAN = PromptEditStrategyPlan((PromptEditStrategy.FULL_REBUILD,))
_PLAN_COUNT = 1 << 7
_STRATEGY_PLANS = tuple(
    _strategy_plan(
        restore_checkpoint=bool(plan_index & (1 << 6)),
        direct_deferred_feedback=bool(plan_index & (1 << 5)),
        edit_kind=PromptSourceEditKind((plan_index >> 3) & 0b11),
        deferred_plain_edit_extendable=bool(plan_index & (1 << 2)),
        allow_trailing_plain_insert=bool(plan_index & (1 << 1)),
        wrap_reflow_deferrable=bool(plan_index & 1),
    )
    for plan_index in range(_PLAN_COUNT)
)


class PromptEditClassifier:
    """Select projection strategy order without accessing mutable editor state."""

    def classify(
        self,
        facts: PromptEditClassificationInput,
    ) -> PromptEditStrategyPlan:
        """Return a prebuilt fallback plan for supplied bounded facts."""

        if (
            facts.region_structure_requires_rebuild
            or facts.projection_topology_requires_rebuild
        ):
            return _FULL_REBUILD_PLAN
        allow_trailing_insert = (
            not facts.typed_character_requires_immediate_projection
            or facts.syntax_sensitive_prefix_deferrable
        )
        plan_index = (
            (int(facts.restore_checkpoint_available) << 6)
            | (int(facts.direct_deferred_feedback_allowed) << 5)
            | (int(facts.edit_kind) << 3)
            | (int(facts.deferred_plain_edit_extendable) << 2)
            | (int(allow_trailing_insert) << 1)
            | int(facts.wrap_reflow_deferrable)
        )
        return _STRATEGY_PLANS[plan_index]


__all__ = ["PromptEditClassifier"]
