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

"""Verify node-card title-row geometry and activation interaction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    ensure_card_body_layout_state,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway as _Gateway,
    WidgetPanel as _WidgetPanel,
    content_body_for as _content_body_for,
    ensure_qapp as _ensure_qapp,
    node_card_for as _node_card_for,
    release_title_row as _release_title_row,
    row_activation_enabled as _row_activation_enabled,
    title_row_for as _title_row_for,
    title_switch as _title_switch,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_collapsible_node_card_title_row_exposes_row_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collapsible title rows should expose feedback and preserve accordion toggling."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    inputs: dict[str, object] = {"steps": 12}
    nodes: dict[str, dict[str, object]] = {
        node_name: {
            "class_type": node_type,
            "inputs": inputs,
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
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
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    try:
        title_row = _title_row_for(wrapper)
        content_body = _content_body_for(wrapper)
        assert _row_activation_enabled(title_row) is True
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert content_body.maximumHeight() > 0
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        wait_for_qt_condition(lambda: not state.animating)

        assert content_body.maximumHeight() == 0
    finally:
        host.close()
        destroy_qt_object(host)
        destroy_qt_object(panel)


def test_title_only_enabled_switch_row_exposes_row_activation() -> None:
    """Title-only activation-switch cards should light up and toggle from row clicks."""

    _ensure_qapp()
    node_name = "vae_override"
    node_type = "VAELoader"
    inputs: dict[str, object] = {}
    nodes: dict[str, dict[str, object]] = {
        node_name: {"class_type": node_type, "inputs": inputs, "mode": 4}
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
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
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    try:
        node_card = _node_card_for(wrapper)
        title_row = _title_row_for(wrapper)
        switch = _title_switch(title_row)

        node_card_layout = node_card.layout()
        assert node_card_layout is not None
        assert node_card_layout.count() == 1
        assert title_row.findChildren(AccordionChevronWidget) == []
        assert _row_activation_enabled(title_row) is True
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor

        _release_title_row(title_row)
        wait_for_qt_condition(lambda: len(panel.node_behavior_service.calls) == 1)

        is_checked = getattr(switch, "isChecked", None)
        assert callable(is_checked)
        assert bool(is_checked()) is True
        assert panel.node_behavior_service.calls == [(cube_state, node_name, True)]
        assert panel.refresh_reasons == ["node_activation_changed"]
    finally:
        host.close()
        destroy_qt_object(host)
        destroy_qt_object(panel)


def test_row_click_prefers_accordion_when_title_row_also_has_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accordion title-row clicks should not toggle a visible switch on the same row."""

    _ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    inputs: dict[str, object] = {"brightness": 0.25, "contrast": 0.0}
    nodes: dict[str, dict[str, object]] = {
        node_name: {
            "class_type": node_type,
            "inputs": inputs,
        }
    }
    cube_a = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    cube_b = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=inputs,
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["B"][node_name],
        cube_state=cube_b,
        resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
        display_decision=snapshot.card_decisions_by_alias["B"][node_name],
        alias="B",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    try:
        title_row = _title_row_for(wrapper)
        content_body = _content_body_for(wrapper)
        switch = _title_switch(title_row)
        is_checked = getattr(switch, "isChecked", None)
        assert callable(is_checked)
        assert bool(is_checked()) is True
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        wait_for_qt_condition(lambda: not state.animating)

        assert content_body.maximumHeight() == 0
        assert bool(is_checked()) is True
        assert panel.node_behavior_service.calls == []

        switch_target = getattr(switch, "indicator", switch)
        assert isinstance(switch_target, QWidget)
        QTest.mouseClick(switch_target, Qt.MouseButton.LeftButton)
        wait_for_qt_condition(lambda: len(panel.node_behavior_service.calls) == 1)

        assert bool(is_checked()) is False
        assert panel.node_behavior_service.calls == [(cube_b, node_name, False)]
    finally:
        host.close()
        destroy_qt_object(host)
        destroy_qt_object(panel)
