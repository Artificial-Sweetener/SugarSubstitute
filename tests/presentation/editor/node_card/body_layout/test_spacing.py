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

"""Verify node-card body spacing through a mounted production card."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLayout

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
    EDITOR_ROW_HEIGHT,
)
from tests.presentation.editor.node_card.body_layout.support import mount_body_card
from tests.presentation.editor.node_card.support import (
    content_body_for,
    content_layout_for,
    node_card_for,
)


def test_grouped_rows_use_shared_body_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep grouped rows aligned to the authoritative body rhythm."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
        inputs={"steps": 12, "cfg": 6.5},
    )
    try:
        node_card = node_card_for(mounted.wrapper)
        card_layout = node_card.layout()
        assert card_layout is not None
        assert card_layout.spacing() == 0

        content_body = content_body_for(mounted.wrapper)
        assert content_body.objectName() == "NodeCardContentClip"
        assert content_body.content_widget().objectName() == "NodeCardContentSurface"
        content_layout = content_layout_for(content_body)

        grouped_item = content_layout.itemAt(1)
        assert grouped_item is not None
        grouped_row = grouped_item.widget()
        assert grouped_row is not None
        grouped_layout = grouped_row.layout()
        assert isinstance(grouped_layout, QLayout)
        divider_item = grouped_layout.itemAt(1)
        assert divider_item is not None
        divider = divider_item.widget()
        assert divider is not None

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
        assert grouped_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert grouped_row.height() == EDITOR_FIELD_ROW_HEIGHT
        assert divider.height() == EDITOR_ROW_HEIGHT
        assert divider.minimumHeight() == EDITOR_ROW_HEIGHT
        assert divider.maximumHeight() == EDITOR_ROW_HEIGHT
    finally:
        mounted.destroy()
