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

"""Verify node-card title seams and row-divider visibility."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QLayout, QWidget

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
)
from tests.presentation.editor.node_card.body_layout.support import mount_body_card
from tests.presentation.editor.node_card.support import (
    content_body_for,
    content_layout_for,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_body_inserts_dividers_only_between_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separate the title seam from dividers owned by later rows."""

    node_name = "vectorscopecc"
    mounted = mount_body_card(
        monkeypatch,
        node_name=node_name,
        node_type="VectorscopeCC",
        inputs={"brightness": 0.05, "contrast": 0.0},
    )
    try:
        content_body = content_body_for(mounted.wrapper)
        content_layout = content_layout_for(content_body)
        title_body_divider = _widget_at(content_layout, 0)
        first_row = _widget_at(content_layout, 1)
        divider = _widget_at(content_layout, 2)
        second_row = _widget_at(content_layout, 3)

        assert content_body.content_widget().y() == 0
        assert title_body_divider.objectName() == "NodeCardTitleBodyDivider"
        assert title_body_divider.property("title_body_divider") is True
        assert title_body_divider.height() == 1
        assert (
            content_layout.contentsMargins().top()
            == node_card_view.NODE_CARD_BODY_TOP_PADDING
        )
        assert first_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert first_row.height() == EDITOR_FIELD_ROW_HEIGHT
        assert first_row.property("divider_for_field") is None
        assert tuple(divider.property("divider_for_field")) == (
            "A",
            node_name,
            "contrast",
        )
        assert divider.height() == 1
        assert second_row.y() == (
            node_card_view.NODE_CARD_BODY_TOP_PADDING
            + 1
            + EDITOR_FIELD_ROW_HEIGHT
            + 1
            + node_card_view.NODE_CARD_BODY_ROW_SPACING
        )
        assert mounted.panel.row_widgets[("A", node_name, "brightness")][0] is None
        assert mounted.panel.row_widgets[("A", node_name, "contrast")][0] is divider
    finally:
        mounted.destroy()


def test_hidden_first_row_does_not_leave_leading_divider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep only the authoritative title/body divider before a visible row."""

    node_name = "vectorscopecc"
    mounted = mount_body_card(
        monkeypatch,
        node_name=node_name,
        node_type="VectorscopeCC",
        inputs={"brightness": 0.05, "contrast": 0.0},
    )
    try:
        field_sync = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, mounted.panel)
        )
        field_sync.apply_hidden_field_keys({("A", node_name, "brightness")})

        content_layout = content_layout_for(content_body_for(mounted.wrapper))
        title_body_divider = _widget_at(content_layout, 0)
        hidden_first_row = _widget_at(content_layout, 1)
        leading_divider = _widget_at(content_layout, 2)
        first_visible_row = _widget_at(content_layout, 3)

        assert not title_body_divider.isHidden()
        assert hidden_first_row.isHidden()
        assert leading_divider.isHidden()
        assert not first_visible_row.isHidden()
        wait_for_qt_condition(lambda: first_visible_row.y() == 1)
        assert first_visible_row.y() == 1
    finally:
        mounted.destroy()


def test_hidden_leading_group_does_not_leave_title_seam_divider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep only the title/body divider when the leading group is hidden."""

    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "scheduler": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    mounted = mount_body_card(
        monkeypatch,
        node_name=node_name,
        node_type=node_type,
        definitions=definitions,
        inputs={
            "sampler_name": "euler",
            "scheduler": "normal",
            "steps": 28,
            "cfg": 5.5,
        },
    )
    try:
        field_sync = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, mounted.panel)
        )
        field_sync.apply_hidden_field_keys(
            {
                ("A", node_name, "sampler_name"),
                ("A", node_name, "scheduler"),
            }
        )

        content_layout = content_layout_for(content_body_for(mounted.wrapper))
        title_body_divider = _widget_at(content_layout, 0)
        first_group = _widget_at(content_layout, 1)
        divider_before_steps = _widget_at(content_layout, 2)
        steps_group = _widget_at(content_layout, 3)

        assert not title_body_divider.isHidden()
        assert first_group.isHidden()
        assert divider_before_steps.isHidden()
        assert not steps_group.isHidden()
        assert tuple(divider_before_steps.property("divider_for_field")) == (
            "A",
            node_name,
            "steps",
        )
        wait_for_qt_condition(lambda: steps_group.y() == 1)
        assert steps_group.y() == 1
    finally:
        mounted.destroy()


def _widget_at(layout: QLayout, index: int) -> QWidget:
    """Return one required widget from a Qt layout-like owner."""

    item = layout.itemAt(index)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget
