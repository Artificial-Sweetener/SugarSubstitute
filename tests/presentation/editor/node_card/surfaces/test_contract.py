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

"""Verify node-card palette, seam painting, and surface attachment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
import substitute.presentation.shell.chrome_style as chrome_style
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
    set_accordion_surface_attachment,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    accordion_content_attached,
    content_body_for,
    ensure_qapp,
    row_activation_enabled,
    title_row_for,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_background_uses_requested_light_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the WinUI light card-fill token."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)

    assert node_card_view._node_card_background_color() == QColor(255, 255, 255, 179)


def test_background_uses_stronger_acrylic_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise card-fill opacity over an acrylic window."""

    ensure_qapp()
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    parent = QWidget()
    setattr(parent.window(), "_backdrop_mode", "acrylic")
    try:
        assert node_card_view._node_card_background_color(parent) == QColor(
            255,
            255,
            255,
            224,
        )
    finally:
        destroy_qt_object(parent)


def test_border_uses_requested_light_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the WinUI light card-stroke token."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)

    assert node_card_view._node_card_border_color() == QColor(0, 0, 0, 15)


def test_attached_content_does_not_repaint_shared_top_stroke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave the attached title/body edge to its single paint owner."""

    ensure_qapp()
    fill = QColor(10, 20, 30, 255)
    stroke = QColor(240, 230, 220, 255)
    monkeypatch.setattr(
        node_card_view,
        "_node_card_background_color",
        lambda _widget=None: fill,
    )
    monkeypatch.setattr(node_card_view, "_node_card_border_color", lambda: stroke)

    surface = node_card_view._NodeCardContentSurface()
    set_accordion_surface_attachment(
        card_title=surface,
        content_body=surface,
        attached=True,
    )
    surface.resize(24, 24)
    image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        surface.render(painter, QPoint(0, 0))
    finally:
        painter.end()
        destroy_qt_object(surface)

    assert image.pixelColor(12, 0) == fill
    assert image.pixelColor(23, 12) != fill


def test_attached_header_does_not_paint_body_seam_stroke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave the header/body seam to the divider widget."""

    ensure_qapp()
    fill = QColor(10, 20, 30, 255)
    stroke = QColor(240, 230, 220, 255)
    monkeypatch.setattr(
        node_card_view,
        "_node_card_background_color",
        lambda _widget=None: fill,
    )
    monkeypatch.setattr(node_card_view, "_node_card_border_color", lambda: stroke)

    surface = node_card_view._NodeCardHeaderSurface()
    set_accordion_surface_attachment(
        card_title=surface,
        content_body=surface,
        attached=True,
    )
    surface.resize(24, 24)
    image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        surface.render(painter, QPoint(0, 0))
    finally:
        painter.end()
        destroy_qt_object(surface)

    assert image.pixelColor(12, 23) == fill
    assert image.pixelColor(12, 0) != fill


def test_non_collapsible_card_keeps_header_and_body_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep expanded non-accordion surfaces joined at their shared edge."""

    ensure_qapp()
    node_name = "positive_prompt"
    node_type = "CLIPTextEncode"
    inputs: dict[str, object] = {"prompt_template": "cinematic portrait"}
    nodes: dict[str, dict[str, object]] = {
        node_name: {"class_type": node_type, "inputs": inputs}
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
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
    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    wait_for_qt_condition(lambda: host.isVisible() and wrapper.height() > 0)
    try:
        title_row = title_row_for(wrapper)
        content_body = content_body_for(wrapper)

        assert title_row.findChildren(AccordionChevronWidget) == []
        assert title_row.cursor().shape() == Qt.CursorShape.ArrowCursor
        assert row_activation_enabled(title_row) is False
        assert accordion_content_attached(title_row) is True
        assert accordion_content_attached(content_body.content_widget()) is True
    finally:
        host.close()
        destroy_qt_object(host)
        destroy_qt_object(panel)
