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

"""Verify ownership of node-card title widgets."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    CardBehavior,
    NodeDisplayDecision,
    TitleControl,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    ensure_qapp,
    has_ancestor,
    node_card_for,
    title_row_for,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_title_widgets_are_born_inside_card_subtree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parent every card-owned title control below the card wrapper."""

    ensure_qapp()
    node_name = "ksampler"
    nodes = {
        node_name: {
            "class_type": "KSampler",
            "inputs": {"steps": 20},
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {"input": {"required": {"steps": ["INT", {}]}}}
        },
    )
    resolved_behavior = replace(
        snapshot.resolved_nodes_by_alias["A"][node_name],
        card=CardBehavior(
            icon_name="edit",
            title_controls=(TitleControl.ENABLED_SWITCH,),
        ),
    )
    display_decision = NodeDisplayDecision(
        visible=True,
        enabled=True,
        reason="test",
        show_enabled_switch=True,
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
            inputs={"steps": 20},
            node_type="KSampler",
            field_specs=snapshot.field_specs_by_alias["A"][node_name],
            cube_state=cube_state,
            resolved_behavior=resolved_behavior,
            display_decision=display_decision,
            alias="A",
        ),
    )
    try:
        assert wrapper is not None
        node_card = node_card_for(wrapper)
        title_row = title_row_for(wrapper)
        title_icon_slot = title_row.findChild(QWidget, "NodeCardTitleIconSlot")
        chevrons = title_row.findChildren(AccordionChevronWidget)
        enabled_switch_wrapper = getattr(title_row, "_enabled_switch_wrapper", None)

        assert title_row.parentWidget() is node_card
        assert title_icon_slot is not None
        assert title_icon_slot.parentWidget() is title_row
        assert chevrons
        assert chevrons[0].parentWidget() is title_row
        assert isinstance(enabled_switch_wrapper, QWidget)
        assert enabled_switch_wrapper.parentWidget() is title_row
        for card_owned_widget in (
            title_row,
            title_icon_slot,
            chevrons[0],
            enabled_switch_wrapper,
        ):
            assert card_owned_widget.parentWidget() is not panel
            assert has_ancestor(card_owned_widget, wrapper)
    finally:
        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)
