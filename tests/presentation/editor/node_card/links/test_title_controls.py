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

"""Verify linked-card rows and title-control ordering."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QHBoxLayout, QWidget

from substitute.application.node_behavior.models import EditorBehaviorSnapshot
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    ensure_qapp,
    title_row_for,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_linked_card_still_builds_local_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep local rows available so unlinking can refresh the card in place."""

    ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    inputs: dict[str, object] = {"brightness": 0.75, "contrast": 0.5}
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": inputs,
            "node_link": {"from_cube": "A", "from_node": node_name},
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = WidgetPanel()
    panel._stack_order = ["B"]
    panel._cube_states = {"B": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"B": cube_state},
        stack_order=["B"],
    )
    builder = build_node_card_builder(panel, Gateway())
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )
    wrapper = cast(
        QWidget | None,
        builder.build_node_card(
            node_name=node_name,
            inputs=inputs,
            node_type=node_type,
            field_specs=snapshot.field_specs_by_alias["B"][node_name],
            cube_state=cube_state,
            resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
            display_decision=snapshot.card_decisions_by_alias["B"][node_name],
            alias="B",
        ),
    )
    try:
        assert wrapper is not None
        assert wrapper.property("has_title_controls") is True
        assert title_row_for(wrapper).findChildren(AccordionChevronWidget)
        assert ("B", node_name, "brightness") in panel.row_widgets
        assert ("B", node_name, "contrast") in panel.row_widgets
    finally:
        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)


def test_node_link_selector_precedes_enabled_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Place node-link status before the activation toggle in the title row."""

    ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    cube_a = _cube_state(
        node_name,
        node_type,
        brightness=0.25,
        contrast=0.0,
    )
    cube_b = _cube_state(
        node_name,
        node_type,
        brightness=0.75,
        contrast=0.5,
    )
    panel = _LinkPanel()
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )
    panel.behavior_snapshot = snapshot
    builder = build_node_card_builder(panel, Gateway())
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    def build_switch(*_args: object, **_kwargs: object) -> QWidget:
        """Return a named activation-control boundary widget."""

        widget = QWidget(panel)
        widget.setObjectName("enabled_switch")
        return widget

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_enabled_switch",
        build_switch,
    )
    inputs = cast(dict[str, object], cube_b.buffer["nodes"][node_name]["inputs"])
    wrapper = cast(
        QWidget | None,
        builder.build_node_card(
            node_name=node_name,
            inputs=inputs,
            node_type=node_type,
            field_specs=snapshot.field_specs_by_alias["B"][node_name],
            cube_state=cube_b,
            resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
            display_decision=snapshot.card_decisions_by_alias["B"][node_name],
            alias="B",
        ),
    )
    try:
        assert wrapper is not None
        title_layout = title_row_for(wrapper).layout()
        assert title_layout is not None
        ordered_names: list[str] = []
        for index in range(title_layout.count()):
            item = title_layout.itemAt(index)
            assert item is not None
            widget = item.widget()
            if widget is not None:
                ordered_names.append(widget.objectName())
        assert ordered_names.index("node_link") < ordered_names.index("enabled_switch")
    finally:
        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)


class _TitleMetaRegistry:
    """Mount a deterministic node-link control into registered title layouts."""

    def __init__(self, panel: QWidget) -> None:
        """Retain the panel owner and no registered layout."""

        self._panel = panel
        self._title_layout: QHBoxLayout | None = None

    def register_node_link_title_surface(self, **kwargs: object) -> None:
        """Retain the title layout supplied by the production builder."""

        self._title_layout = cast(QHBoxLayout, kwargs["title_layout"])

    def update_node_link_widgets_for_cube(self, _cube_alias: str) -> None:
        """Insert one named link-control widget into the title layout."""

        if self._title_layout is None:
            return
        widget = QWidget(self._panel)
        widget.setObjectName("node_link")
        self._title_layout.addWidget(widget)


class _LinkPanel(WidgetPanel):
    """Provide current link behavior and title meta-registration services."""

    def __init__(self) -> None:
        """Initialize link state consumed by title construction."""

        super().__init__()
        self.node_link_widgets: dict[object, object] = {}
        self.behavior_snapshot: EditorBehaviorSnapshot | None = None
        self.meta_registry = _TitleMetaRegistry(self)

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the prepared cross-cube node-link snapshot."""

        return self.behavior_snapshot


def _cube_state(
    node_name: str,
    node_type: str,
    *,
    brightness: float,
    contrast: float,
) -> SimpleNamespace:
    """Return one cube containing the shared linked node identity."""

    return SimpleNamespace(
        buffer={
            "nodes": {
                node_name: {
                    "class_type": node_type,
                    "inputs": {
                        "brightness": brightness,
                        "contrast": contrast,
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
