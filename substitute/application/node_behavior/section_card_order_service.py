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

"""Coordinate post-resolution card ordering across editor graph sections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.node_behavior import (
    NodeDisplayDecision,
    PromptGraphContext,
)

from .models import ResolvedFieldSpec
from .node_card_order_planner import (
    NodeCardOrderPlanner,
    NodeCardOrderRequest,
    NodeCardOrderingMode,
)


class SectionCardOrderService:
    """Plan every section through one prompt-aware card-order authority."""

    def __init__(self) -> None:
        """Initialize the pure card-order planner."""

        self._planner = NodeCardOrderPlanner()

    def plan(
        self,
        *,
        section_states: Mapping[str, object],
        section_order: Sequence[str],
        baseline_order_by_alias: Mapping[str, tuple[str, ...]],
        field_specs_by_alias: Mapping[
            str,
            Mapping[str, Mapping[str, ResolvedFieldSpec]],
        ],
        card_decisions_by_alias: Mapping[
            str,
            Mapping[str, NodeDisplayDecision],
        ],
        prompt_contexts_by_alias: Mapping[str, tuple[PromptGraphContext, ...]],
    ) -> dict[str, tuple[str, ...]]:
        """Return deterministic card order for every available editor section."""

        planned: dict[str, tuple[str, ...]] = {}
        for alias in section_order:
            state = section_states.get(alias)
            if state is None:
                continue
            buffer = getattr(state, "buffer", {})
            raw_nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
            nodes = raw_nodes if isinstance(raw_nodes, Mapping) else {}
            planned[alias] = self._planner.plan(
                NodeCardOrderRequest(
                    mode=(
                        NodeCardOrderingMode.DIRECT_WORKFLOW
                        if isinstance(state, DirectWorkflowState)
                        else NodeCardOrderingMode.CUBE
                    ),
                    baseline_order=baseline_order_by_alias.get(alias, ()),
                    nodes=nodes,
                    field_specs_by_node=field_specs_by_alias.get(alias, {}),
                    card_decisions=card_decisions_by_alias.get(alias, {}),
                    prompt_contexts=prompt_contexts_by_alias.get(alias, ()),
                )
            )
        return planned


__all__ = ["SectionCardOrderService"]
