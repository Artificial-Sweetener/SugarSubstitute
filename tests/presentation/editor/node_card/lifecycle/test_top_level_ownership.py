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

"""Verify node-card widgets never escape as top-level windows."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QVBoxLayout, QWidget

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionContentClip,
)
from substitute.presentation.editor.panel.widgets.node_card import NodeCardWidget
from tests.presentation.editor.node_card.support import ensure_qapp
from tests.presentation.editor.widget_lifecycle_assertions import (
    assert_no_editor_widgets_are_top_level,
    editor_top_level_widget_ids,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_lifecycle_guard_detects_parentless_node_card_content() -> None:
    """Reject a content clip that escapes its card as a top-level widget."""

    ensure_qapp()
    escaped = QWidget()
    escaped.setObjectName("NodeCardContentClip")
    escaped.show()
    wait_for_qt_condition(lambda: id(escaped) in editor_top_level_widget_ids())
    try:
        with pytest.raises(AssertionError, match="NodeCardContentClip"):
            assert_no_editor_widgets_are_top_level()
    finally:
        escaped.setObjectName("")
        destroy_qt_object(escaped)


def test_parent_first_surfaces_remain_below_card_host() -> None:
    """Keep every parent-first node-card surface below its mounted host."""

    ensure_qapp()
    existing_editor_top_levels = editor_top_level_widget_ids()
    host = QWidget()
    root = NodeCardWidget(host)
    root_layout = QVBoxLayout(root)
    node_card_surface_type = cast(
        type[QWidget], getattr(node_card_view, "_NodeCardSurface")
    )
    node_card_content_surface_type = cast(
        type[QWidget],
        getattr(node_card_view, "_NodeCardContentSurface"),
    )
    node_card = node_card_surface_type(root)
    content_body = AccordionContentClip(
        parent=node_card,
        content_surface_factory=node_card_content_surface_type,
    )
    content_body.setObjectName("NodeCardContentClip")
    root_layout.addWidget(node_card)
    QVBoxLayout(node_card).addWidget(content_body)
    host.show()
    wait_for_qt_condition(host.isVisible)
    try:
        assert_no_editor_widgets_are_top_level(
            ignored_widget_ids=existing_editor_top_levels,
        )
    finally:
        destroy_qt_object(host)
