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

"""Mount node cards for focused body-layout assertions."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from collections.abc import Mapping

import pytest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    ensure_qapp,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


@dataclass(frozen=True, slots=True)
class MountedBodyCard:
    """Expose one mounted card and its exact Qt owners."""

    host: QWidget
    panel: WidgetPanel
    wrapper: QWidget
    cube_state: SimpleNamespace

    def destroy(self) -> None:
        """Destroy the card host and panel synchronously."""

        self.host.close()
        destroy_qt_object(self.host)
        destroy_qt_object(self.panel)


def mount_body_card(
    monkeypatch: pytest.MonkeyPatch,
    *,
    node_name: str,
    node_type: str,
    inputs: dict[str, object],
    definitions: Mapping[str, Mapping[str, object]] | None = None,
) -> MountedBodyCard:
    """Build and visibly mount one card with simple field widgets."""

    ensure_qapp()
    active_definitions = dict(definitions or {})
    nodes: dict[str, dict[str, object]] = {
        node_name: {"class_type": node_type, "inputs": inputs}
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": active_definitions},
        ui={},
    )
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=active_definitions,
    )
    builder = build_node_card_builder(panel, Gateway())
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
    if wrapper is None:
        destroy_qt_object(panel)
        raise AssertionError("Body-layout scenario did not produce a node card.")
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    return MountedBodyCard(
        host=host,
        panel=panel,
        wrapper=wrapper,
        cube_state=cube_state,
    )


__all__ = ["MountedBodyCard", "mount_body_card"]
