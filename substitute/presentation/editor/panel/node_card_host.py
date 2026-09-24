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

"""Realize node cards through the mounted editor panel host API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
)

from .node_card_builder import NodeCardBuilder
from .prompt.field_inputs import build_node_card_prompt_field_inputs


class EditorPanelNodeCardHost:
    """Provide node-card realization through the canonical panel identity."""

    def is_connection(self, value: object) -> bool:
        """Return whether one raw input payload represents a node connection."""

        if isinstance(value, list) and len(value) == 2:
            return isinstance(value[0], str) and isinstance(value[1], int)
        return isinstance(value, list) and not value

    def build_node_card(
        self,
        node_name: str,
        inputs: dict[str, Any],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: object,
        resolved_behavior: ResolvedNodeBehavior,
        display_decision: NodeDisplayDecision | None = None,
        alias: str | None = None,
        parent: QWidget | None = None,
    ) -> QWidget | None:
        """Build one node card with focused cold-projection timing."""

        panel: Any = self
        builder = getattr(panel, "_node_card_builder", None)
        if builder is None:
            builder = NodeCardBuilder(
                panel=panel,
                services=panel._services,
                model_choice_snapshot_controller=(
                    panel.model_choice_snapshot_controller
                ),
                dimension_preset_source=panel.dimension_preset_source,
                node_input_preset_source=panel.node_input_preset_source,
                prompt_segment_preset_source=panel.prompt_segment_preset_source,
                body_contributors=panel._node_card_body_contributors,
            )
            panel._node_card_builder = builder
        return builder.build_node_card(
            node_name=node_name,
            inputs=inputs,
            node_type=node_type,
            field_specs=field_specs,
            cube_state=cube_state,
            resolved_behavior=resolved_behavior,
            display_decision=display_decision,
            alias=alias,
            parent=parent,
            prompt_field_inputs=build_node_card_prompt_field_inputs(
                panel,
                node_name=node_name,
                field_specs=field_specs,
                alias=alias,
            ),
        )


__all__ = ["EditorPanelNodeCardHost"]
