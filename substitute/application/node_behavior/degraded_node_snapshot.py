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

"""Collect truthful degraded-node behavior during one snapshot build."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from substitute.domain.node_behavior import NodeDisplayDecision

from .models import DegradedNodeBehavior
from .section_node_source import SectionNodeSource


@dataclass(slots=True)
class DegradedNodeSnapshot:
    """Own degraded-node collection and its exceptional card visibility rule."""

    nodes_by_alias: dict[str, dict[str, DegradedNodeBehavior]] = field(
        default_factory=dict
    )

    def record(self, *, alias: str, source: SectionNodeSource) -> bool:
        """Record one unavailable node source and report whether it degraded."""

        error = source.definition_error
        if error is None:
            return False
        self.nodes_by_alias.setdefault(alias, {})[source.node_name] = (
            DegradedNodeBehavior(
                node_name=source.node_name,
                class_type=source.class_type,
                title=source.node_title or source.node_name or source.class_type,
                missing_definition_classes=tuple(
                    sorted({item.class_type for item in error.missing_definitions})
                ),
                missing_fields=tuple(
                    sorted(
                        f"{item.class_type}.{item.field_key}"
                        for item in error.missing_fields
                    )
                ),
            )
        )
        return True

    def ensure_card_visibility(
        self,
        decisions: dict[str, dict[str, NodeDisplayDecision]],
    ) -> dict[str, dict[str, NodeDisplayDecision]]:
        """Keep degraded cards visible unless an active node search excludes them."""

        for alias, degraded_nodes in self.nodes_by_alias.items():
            per_node = decisions.get(alias, {})
            for node_name in degraded_nodes:
                decision = per_node.get(node_name)
                if decision is None or decision.reason == "search:node-filter":
                    continue
                per_node[node_name] = replace(
                    decision,
                    visible=True,
                    reason="missing-live-definition",
                    reveal_checked=True,
                )
        return decisions


__all__ = ["DegradedNodeSnapshot"]
