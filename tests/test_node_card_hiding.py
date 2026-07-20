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

from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from tests.node_card_builder_test_helpers import build_node_card_builder
from tests.node_behavior_test_helpers import build_behavior_snapshot
from tests.localization_testing import technical_node_presentation


class DummyGateway:
    def __init__(self, definitions=None):
        """Store optional node definitions for node-card hiding tests."""

        self._definitions = definitions or {}

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured optional definition payload."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured required definition payload."""

        definition = self._definitions.get(node_class)
        return {node_class: definition} if isinstance(definition, dict) else {}


class DummyCubeState:
    def __init__(self, nodes=None, definitions=None, overrides=None):
        self.buffer = {"nodes": nodes or {}, "definitions": definitions or {}}
        self.ui = {"overrides": overrides} if overrides is not None else {}
        self.dirty = False


class DummyPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._stack_order = []
        self._cube_states = {}
        self.row_widgets = {}

    def is_connection(self, val) -> bool:
        # Treat only [str, int] style as a real connection
        return isinstance(val, list) and len(val) == 2 and isinstance(val[0], str)


def ensure_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_node_card_hidden_when_no_rows_and_no_title_controls(monkeypatch):
    ensure_qapp()

    panel = DummyPanel()
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )

    # Avoid creating styled labels/switches in title row during tests
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, *args, **kwargs: (QWidget(panel), None),
    )

    node_name = "empty_node"
    node_type = "SomeUnknownClass"
    inputs = {}
    cube_state = DummyCubeState(
        nodes={node_name: {"inputs": {}, "class_type": node_type}}
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )

    # With no fields and no enabled-switch rule, the card should be hidden (None)
    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=inputs,
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        alias="A",
    )
    assert wrapper is None


def test_node_card_shown_when_no_rows_but_activation_switch_is_requested(
    monkeypatch,
):
    ensure_qapp()

    panel = DummyPanel()
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )

    # Avoid creating styled labels/switches in title row during tests
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, *args, **kwargs: (QWidget(panel), None),
    )

    node_name = "vae_override"
    node_type = "VAELoader"  # presentation.class_rules enables switch
    inputs = {}
    # Provide minimal node structure in buffer so wiring can read/write cleanly
    cube_state = DummyCubeState(
        nodes={node_name: {"inputs": {}, "class_type": node_type}}
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=inputs,
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    assert isinstance(wrapper, QWidget)
    assert wrapper.property("has_title_controls") is True
    assert wrapper.property("base_card_visible") is True


def test_hard_hidden_node_card_is_not_constructed(monkeypatch) -> None:
    """Hard-hidden infrastructure nodes should not build card widgets."""

    ensure_qapp()

    panel = DummyPanel()
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )
    node_name = "schedule"
    node_type = "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
    inputs = {
        "positive_prompt": "quality",
        "negative_prompt": "blurry",
        "encode_style": "style",
    }
    cube_state = DummyCubeState(
        nodes={node_name: {"inputs": inputs, "class_type": node_type}}
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class={
            node_type: {
                "input": {
                    "required": {
                        "positive_prompt": ["STRING", {}],
                        "negative_prompt": ["STRING", {}],
                        "encode_style": ["STRING", {}],
                    }
                }
            }
        },
    )
    decision = snapshot.card_decisions_by_alias["A"][node_name]
    assert decision.enabled is True
    assert decision.visible is False

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=inputs,
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is None
    assert panel.row_widgets == {}


def test_linked_node_card_still_builds_local_rows(monkeypatch) -> None:
    """Linked whole-node cards should keep local rows available for unlink refresh."""

    ensure_qapp()

    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"brightness": 0.75, "contrast": 0.5},
            "node_link": {"from_cube": "A", "from_node": node_name},
        }
    }
    cube_state = DummyCubeState(nodes=nodes)
    panel = DummyPanel()
    panel._stack_order = ["B"]
    panel._cube_states = {"B": cube_state}
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )
    snapshot = build_behavior_snapshot(
        cube_states={"B": cube_state},
        stack_order=["B"],
    )
    title_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    def create_title_row(self, *args, **kwargs):
        title_calls.append(dict(kwargs))
        return QWidget(panel), None

    monkeypatch.setattr(NodeCardBuilder, "_create_title_row", create_title_row)

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["B"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
        display_decision=snapshot.card_decisions_by_alias["B"][node_name],
        alias="B",
    )

    assert wrapper is not None
    assert wrapper.property("has_title_controls") is True
    assert title_calls[0]["no_chevron"] is False
    assert ("B", "vectorscopecc", "brightness") in panel.row_widgets
    assert ("B", "vectorscopecc", "contrast") in panel.row_widgets


def test_node_link_selector_renders_before_enabled_switch(monkeypatch) -> None:
    """Node title controls should order link status before the on/off toggle."""

    ensure_qapp()

    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    cube_a = DummyCubeState(
        nodes={
            node_name: {
                "class_type": node_type,
                "inputs": {"brightness": 0.25, "contrast": 0.0},
            }
        }
    )
    cube_b = DummyCubeState(
        nodes={
            node_name: {
                "class_type": node_type,
                "inputs": {"brightness": 0.75, "contrast": 0.5},
            }
        }
    )
    panel = DummyPanel()
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    panel.node_link_widgets = {}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )
    panel.current_behavior_snapshot = lambda: snapshot
    builder = build_node_card_builder(
        panel,
        DummyGateway(),
    )

    class _MetaRegistry:
        def __init__(self) -> None:
            self.title_layout = None

        def register_node_link_title_surface(self, **kwargs) -> None:
            self.title_layout = kwargs["title_layout"]

        def update_node_link_widgets_for_cube(self, _cube_alias: str) -> None:
            if self.title_layout is None:
                return
            widget = QWidget(panel)
            widget.setObjectName("node_link")
            self.title_layout.addWidget(widget)

    panel.meta_registry = _MetaRegistry()

    def build_switch(*args, **kwargs):
        widget = QWidget(panel)
        widget.setObjectName("enabled_switch")
        return widget

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_enabled_switch",
        build_switch,
    )

    title_row, chevron = builder._create_title_row(
        node_name=node_name,
        resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
        display_decision=snapshot.card_decisions_by_alias["B"][node_name],
        snapshot=builder._snapshot_panel(cube_b, "B"),
        no_chevron=False,
        cube_state=cube_b,
        node_presentation=technical_node_presentation(
            node_name=node_name,
            class_type=node_type,
        ),
    )

    assert chevron is not None
    layout = title_row.layout()
    ordered_names = [
        layout.itemAt(index).widget().objectName()
        for index in range(layout.count())
        if layout.itemAt(index).widget() is not None
    ]
    assert ordered_names.index("node_link") < ordered_names.index("enabled_switch")


def test_node_card_shown_for_combo_only_node() -> None:
    """A node with only a COMBO field should render a dropdown row instead of disappearing."""

    ensure_qapp()

    node_name = "load_upscale_model"
    node_type = "UpscaleModelLoader"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "model_name": [
                        "COMBO",
                        {
                            "options": [
                                "ESRGAN_4x.pth",
                                "R-ESRGAN 4x+ Anime6B.pth",
                            ]
                        },
                    ]
                }
            }
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
        }
    }
    cube_state = DummyCubeState(nodes=nodes, definitions=definitions)
    panel = DummyPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    builder = build_node_card_builder(
        panel,
        DummyGateway(definitions),
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    assert isinstance(wrapper, QWidget)
    assert wrapper.property("has_title_controls") is False
    assert wrapper.property("base_card_visible") is True
