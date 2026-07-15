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

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.node_behavior import TitleControl
from tests.node_card_builder_test_helpers import build_node_card_builder
from tests.node_behavior_test_helpers import build_behavior_snapshot


class DummyGateway:
    def get_node_definition(self, _node_class: str) -> dict[str, object]:
        """Return no optional live metadata for node-card tests."""

        return self.get_required_node_definition(_node_class)

    def get_required_node_definition(self, _node_class: str) -> dict[str, object]:
        """Return no required live metadata for node-card tests."""

        return {}


class DummyCubeState:
    def __init__(self, nodes=None, overrides=None):
        self.buffer = {"nodes": nodes or {}, "definitions": {}}
        self.ui = {"overrides": overrides} if overrides is not None else {}
        self.dirty = False


class DummyPanel(QWidget):
    def __init__(self, stack_order, cube_states):
        super().__init__()
        self._stack_order = stack_order
        self._cube_states = cube_states
        self.row_widgets = {}

    def is_connection(self, val) -> bool:
        return False


def ensure_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_checkpoint_loader_switch_policy_and_default_enabled() -> None:
    ensure_qapp()

    node_name = "ckpt"
    node_type = "CheckpointLoaderSimple"

    nodes_a = {node_name: {"class_type": node_type, "inputs": {}}}
    nodes_b = {node_name: {"class_type": node_type, "inputs": {}, "mode": 4}}

    cs_a = DummyCubeState(nodes=nodes_a)
    cs_b = DummyCubeState(nodes=nodes_b)
    cube_states = {"A": cs_a, "B": cs_b}

    panel = DummyPanel(stack_order=["A", "B"], cube_states=cube_states)
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )
    snapshot = build_behavior_snapshot(
        cube_states=cube_states,
        stack_order=["A", "B"],
    )
    resolved_a = snapshot.resolved_nodes_by_alias["A"][node_name]
    resolved_b = snapshot.resolved_nodes_by_alias["B"][node_name]
    decision_a = snapshot.card_decisions_by_alias["A"][node_name]
    decision_b = snapshot.card_decisions_by_alias["B"][node_name]

    wrapper_a = builder.build_node_card(
        node_name=node_name,
        inputs={},
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cs_a,
        resolved_behavior=resolved_a,
        display_decision=decision_a,
        alias="A",
    )
    assert wrapper_a is None
    assert TitleControl.ENABLED_SWITCH not in resolved_a.card.title_controls
    assert decision_a.enabled is True
    assert decision_a.show_enabled_switch is False

    wrapper_b = builder.build_node_card(
        node_name=node_name,
        inputs={},
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["B"][node_name],
        cube_state=cs_b,
        resolved_behavior=resolved_b,
        display_decision=decision_b,
        alias="B",
    )
    assert isinstance(wrapper_b, QWidget)
    assert TitleControl.ENABLED_SWITCH not in resolved_b.card.title_controls
    assert decision_b.show_enabled_switch is True
    assert decision_b.enabled is False
