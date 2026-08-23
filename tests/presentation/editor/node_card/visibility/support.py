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

"""Build cards for focused construction-visibility assertions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior.models import EditorBehaviorSnapshot
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    DefinitionGateway,
    WidgetPanel,
    ensure_qapp,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


@dataclass(slots=True)
class VisibilityScenario:
    """Own a panel, card builder, and one node behavior snapshot."""

    panel: WidgetPanel
    builder: NodeCardBuilder
    cube_state: SimpleNamespace
    node_name: str
    node_type: str
    inputs: dict[str, object]
    snapshot: EditorBehaviorSnapshot

    def build(self) -> QWidget | None:
        """Build the configured card through its public boundary."""

        return cast(
            QWidget | None,
            self.builder.build_node_card(
                node_name=self.node_name,
                inputs=self.inputs,
                node_type=self.node_type,
                field_specs=self.snapshot.field_specs_by_alias["A"][self.node_name],
                cube_state=self.cube_state,
                resolved_behavior=self.snapshot.resolved_nodes_by_alias["A"][
                    self.node_name
                ],
                display_decision=self.snapshot.card_decisions_by_alias["A"][
                    self.node_name
                ],
                alias="A",
            ),
        )

    def destroy(self, wrapper: QWidget | None) -> None:
        """Destroy the optional wrapper and panel synchronously."""

        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(self.panel)


def create_visibility_scenario(
    monkeypatch: pytest.MonkeyPatch,
    *,
    node_name: str,
    node_type: str,
    inputs: dict[str, object],
    definitions: Mapping[str, Mapping[str, object]] | None = None,
    node_metadata: Mapping[str, object] | None = None,
    use_minimal_field_widget: bool = True,
) -> VisibilityScenario:
    """Create one deterministic card-construction scenario."""

    ensure_qapp()
    active_definitions = dict(definitions or {})
    node = dict(node_metadata or {})
    node.update({"class_type": node_type, "inputs": inputs})
    nodes = {node_name: node}
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": active_definitions},
        ui={},
        dirty=False,
    )
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=active_definitions,
    )
    builder = build_node_card_builder(panel, DefinitionGateway(active_definitions))
    if use_minimal_field_widget:
        monkeypatch.setattr(
            "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
            lambda **_kwargs: QWidget(panel),
        )
    return VisibilityScenario(
        panel=panel,
        builder=builder,
        cube_state=cube_state,
        node_name=node_name,
        node_type=node_type,
        inputs=inputs,
        snapshot=snapshot,
    )


__all__ = ["VisibilityScenario", "create_visibility_scenario"]
