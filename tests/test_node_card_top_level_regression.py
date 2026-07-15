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

"""Regression tests for editor node-card widgets escaping as top-level windows."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionContentClip,
)
from substitute.presentation.editor.panel.widgets.node_card import NodeCardWidget
from tests.presentation.editor.widget_lifecycle_assertions import (
    assert_no_editor_widgets_are_top_level,
    editor_top_level_widget_ids,
)


def _ensure_qapp() -> QApplication:
    """Return the active Qt application for focused widget lifecycle tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_widget_lifecycle_helper_detects_node_card_content_top_level() -> None:
    """The regression helper should fail on a parentless node-card content clip."""

    app = _ensure_qapp()
    escaped = QWidget()
    escaped.setObjectName("NodeCardContentClip")
    escaped.show()
    app.processEvents()
    try:
        with pytest.raises(AssertionError, match="NodeCardContentClip"):
            assert_no_editor_widgets_are_top_level()
    finally:
        escaped.setObjectName("")
        escaped.close()
        escaped.deleteLater()
        app.processEvents()


def test_parent_first_node_card_surfaces_do_not_become_top_level() -> None:
    """Parent-first node card construction should keep card surfaces below the host."""

    app = _ensure_qapp()
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
    app.processEvents()
    try:
        assert_no_editor_widgets_are_top_level(
            ignored_widget_ids=existing_editor_top_levels,
        )
    finally:
        host.close()
        host.deleteLater()
        app.processEvents()
