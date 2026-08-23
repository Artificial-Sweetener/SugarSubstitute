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

"""Verify node-card title and body-row geometry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, IconWidget  # type: ignore[import-untyped]

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
    EDITOR_ROW_BODY_SPACING,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway as _Gateway,
    WidgetPanel as _WidgetPanel,
    accordion_content_attached as _accordion_content_attached,
    content_body_for as _content_body_for,
    content_layout_for as _content_layout_for,
    ensure_qapp as _ensure_qapp,
    title_body_divider_for as _title_body_divider_for,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_node_card_title_row_uses_shared_editor_row_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node-card titles should share fixed editor-row sizing with scalar rows."""

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
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    try:
        wrapper_layout = wrapper.layout()
        assert wrapper_layout is not None
        node_card_item = wrapper_layout.itemAt(0)
        assert node_card_item is not None
        node_card = node_card_item.widget()
        assert node_card is not None
        card_layout = node_card.layout()
        assert card_layout is not None
        assert card_layout.spacing() == 0
        title_row_item = card_layout.itemAt(0)
        assert title_row_item is not None
        title_row = title_row_item.widget()
        assert title_row is not None
        assert title_row.objectName() == "NodeCardHeaderSurface"
        title_layout = title_row.layout()
        assert title_layout is not None
        title_body_divider = _title_body_divider_for(wrapper)
        content_body = _content_body_for(wrapper)
        assert content_body.objectName() == "NodeCardContentClip"
        assert content_body.content_widget().objectName() == "NodeCardContentSurface"
        content_layout = _content_layout_for(content_body)
        scalar_row_item = content_layout.itemAt(1)
        assert scalar_row_item is not None
        scalar_row = scalar_row_item.widget()
        assert scalar_row is not None

        title_icon_slot_item = title_layout.itemAt(0)
        assert title_icon_slot_item is not None
        title_icon_slot = title_icon_slot_item.widget()
        assert title_icon_slot is not None
        title_icon = title_icon_slot.findChild(IconWidget, "NodeCardTitleIcon")
        assert title_icon is not None
        title_labels = title_row.findChildren(CaptionLabel)
        chevrons = title_row.findChildren(AccordionChevronWidget)

        assert title_row.minimumHeight() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_row.maximumHeight() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_row.height() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_layout.contentsMargins().top() == EDITOR_ROW_BODY_SPACING
        assert title_layout.contentsMargins().bottom() == EDITOR_ROW_BODY_SPACING
        assert title_icon_slot.width() == node_card_view.NODE_CARD_TITLE_ICON_SLOT_SIZE
        assert title_icon_slot.height() == node_card_view.NODE_CARD_TITLE_ICON_SLOT_SIZE
        assert title_icon.width() == node_card_view.NODE_CARD_TITLE_ICON_SIZE
        assert title_icon.height() == node_card_view.NODE_CARD_TITLE_ICON_SIZE
        assert len(title_labels) == 1
        assert title_labels[0].font().pixelSize() == 14
        assert len(chevrons) == 1
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert _accordion_content_attached(title_row) is True
        assert _accordion_content_attached(content_body.content_widget()) is True
        assert title_body_divider.objectName() == "NodeCardTitleBodyDivider"
        assert title_body_divider.property("title_body_divider") is True
        assert title_body_divider.height() == 1
        assert content_body.content_overlap_y() == 0
        assert node_card_view.NODE_CARD_BODY_TOP_PADDING == 0
        assert (
            content_layout.contentsMargins().top()
            == node_card_view.NODE_CARD_BODY_TOP_PADDING
        )
        assert (
            content_layout.contentsMargins().bottom()
            == node_card_view.NODE_CARD_BODY_BOTTOM_PADDING
        )
        assert content_layout.spacing() == node_card_view.NODE_CARD_BODY_ROW_SPACING
        assert scalar_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert scalar_row.height() == EDITOR_FIELD_ROW_HEIGHT
    finally:
        host.close()
        destroy_qt_object(host)
        destroy_qt_object(panel)
