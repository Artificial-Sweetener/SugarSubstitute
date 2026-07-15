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

"""Tests for linked-mode presentation updates on existing node cards."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QCheckBox, QVBoxLayout, QWidget

from substitute.domain.node_behavior import NodeDisplayDecision
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
    AccordionMotionController,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    ensure_card_body_layout_state,
)
from substitute.presentation.editor.panel.node_card.mode_controller import (
    NodeCardModeBinding,
    NodeCardModeController,
)


def ensure_qapp() -> QApplication:
    """Return an active QApplication for widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush pending layout updates after linked-mode state changes."""

    for _ in range(cycles):
        app.processEvents()


def expected_visible_item_height(layout: QVBoxLayout, *widgets: QWidget) -> int:
    """Return layout height from visible widgets, margins, and inter-item spacing."""

    margins = layout.contentsMargins()
    visible_widgets = [widget for widget in widgets if not widget.isHidden()]
    spacing = layout.spacing() * max(0, len(visible_widgets) - 1)
    return (
        margins.top()
        + sum(expected_widget_height(widget) for widget in visible_widgets)
        + spacing
        + margins.bottom()
    )


def expected_widget_height(widget: QWidget) -> int:
    """Return the height Qt layout constraints contribute for one visible widget."""

    return max(widget.sizeHint().height(), widget.minimumHeight(), widget.height())


class _AccordionController:
    """Record title-row accordion toggle requests from mode-controller tests."""

    def __init__(self) -> None:
        """Initialize an empty toggle log."""

        self.toggle_calls = 0

    def toggle(self) -> None:
        """Record one accordion toggle request."""

        self.toggle_calls += 1


class _InteractiveTitleRow(QWidget):
    """Provide the row-owned title activation API used by the mode controller."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the title-row test double without an active callback."""

        super().__init__(parent)
        self._row_activation: Callable[[], None] | None = None

    def set_row_activation(self, callback: Callable[[], None] | None) -> None:
        """Store one row activation callback and mirror the production cursor."""

        self._row_activation = callback
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if callback is not None
            else Qt.CursorShape.ArrowCursor
        )

    def clear_row_activation(self) -> None:
        """Clear row activation and mirror the production cursor."""

        self.set_row_activation(None)

    def row_activation_enabled(self) -> bool:
        """Return whether the title row currently has row-level behavior."""

        return self._row_activation is not None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Invoke row activation from a release event like the production title row."""

        if self._row_activation is not None:
            self._row_activation()
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _row_activation_enabled(title_row: QWidget) -> bool:
    """Return whether a title row exposes row-level activation."""

    enabled = getattr(title_row, "row_activation_enabled", None)
    assert callable(enabled)
    return bool(enabled())


def _release_title_row(title_row: _InteractiveTitleRow) -> None:
    """Deliver a deterministic row-release event to the title-row test double."""

    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 4),
        QPointF(4, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    title_row.mouseReleaseEvent(event)


def test_node_card_mode_controller_hides_and_restores_existing_controls() -> None:
    """Linked mode should hide card controls and independent mode should restore them."""

    app = ensure_qapp()
    wrapper = QWidget()
    wrapper_layout = QVBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(0, 10, 0, 10)
    wrapper_layout.setSpacing(12)
    title_row = QWidget(wrapper)
    title_row.setFixedHeight(22)
    content_body = QWidget(wrapper)
    content_layout = QVBoxLayout(content_body)
    row = QWidget(content_body)
    row.setFixedHeight(24)
    content_layout.addWidget(row)
    wrapper_layout.addWidget(title_row)
    wrapper_layout.addWidget(content_body)
    chevron = AccordionChevronWidget(wrapper)
    switch_wrapper = QWidget(wrapper)
    enabled_switch = QCheckBox(switch_wrapper)
    binding = NodeCardModeBinding(
        wrapper=wrapper,
        title_row=title_row,
        content_body=content_body,
        content_layout=content_layout,
        chevron=chevron,
        enabled_switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=None,
        collapsible=True,
        has_rows=True,
        allow_unbounded_content_height=False,
    )
    controller = NodeCardModeController()
    controller.register("B", "vectorscopecc", binding)
    wrapper.show()
    process_events(app)

    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="node-link:inherited-enabled",
                    show_enabled_switch=True,
                    node_link_active=True,
                )
            }
        }
    )
    process_events(app)

    assert content_body.maximumHeight() == 0
    assert content_body.isHidden()
    body_item = wrapper_layout.itemAt(1)
    assert body_item is not None
    assert body_item.isEmpty() is True
    assert wrapper.sizeHint().height() == expected_visible_item_height(
        wrapper_layout,
        title_row,
        content_body,
    )
    assert chevron.isHidden()
    assert switch_wrapper.isHidden()
    assert enabled_switch.isChecked() is False

    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                    show_enabled_switch=True,
                    node_link_active=False,
                )
            }
        }
    )
    process_events(app)

    assert content_body.isHidden() is False
    assert content_body.maximumHeight() > 0
    assert body_item.isEmpty() is False
    assert chevron.isHidden() is False
    assert switch_wrapper.isHidden() is False
    assert enabled_switch.isChecked() is True
    wrapper.close()
    wrapper.deleteLater()
    process_events(app)


def test_node_card_mode_controller_preserves_manual_collapse_across_link_mode() -> None:
    """Linked collapse should not overwrite the user's accordion collapse state."""

    app = ensure_qapp()
    wrapper = QWidget()
    title_row = QWidget(wrapper)
    content_body = QWidget(wrapper)
    content_layout = QVBoxLayout(content_body)
    row = QWidget(content_body)
    row.setFixedHeight(24)
    content_layout.addWidget(row)
    binding = NodeCardModeBinding(
        wrapper=wrapper,
        title_row=title_row,
        content_body=content_body,
        content_layout=content_layout,
        chevron=None,
        enabled_switch_wrapper=None,
        enabled_switch=None,
        accordion_controller=None,
        collapsible=True,
        has_rows=True,
        allow_unbounded_content_height=False,
    )
    state = ensure_card_body_layout_state(
        content_body=content_body,
        expanded_height=content_layout.sizeHint().height(),
    )
    state.collapsed = True
    controller = NodeCardModeController()
    controller.register("B", "vectorscopecc", binding)

    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="node-link:inherited-enabled",
                    show_enabled_switch=True,
                    node_link_active=True,
                )
            }
        }
    )
    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                    show_enabled_switch=True,
                    node_link_active=False,
                )
            }
        }
    )

    assert state.collapsed is True
    assert state.forced_collapsed is False
    assert content_body.maximumHeight() == 0
    assert content_body.isHidden()
    wrapper.deleteLater()
    process_events(app)


def test_node_card_mode_controller_suppresses_and_restores_title_row_activation() -> (
    None
):
    """Linked mode should clear row feedback and restore accordion precedence later."""

    app = ensure_qapp()
    wrapper = QWidget()
    title_row = _InteractiveTitleRow(wrapper)
    switch_wrapper = QWidget(wrapper)
    enabled_switch = QCheckBox(switch_wrapper)
    accordion_controller = _AccordionController()
    binding = NodeCardModeBinding(
        wrapper=wrapper,
        title_row=title_row,
        content_body=None,
        content_layout=None,
        chevron=AccordionChevronWidget(wrapper),
        enabled_switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=cast(AccordionMotionController, accordion_controller),
        collapsible=True,
        has_rows=True,
        allow_unbounded_content_height=False,
    )
    controller = NodeCardModeController()
    controller.register("B", "vectorscopecc", binding)
    wrapper.show()
    process_events(app)

    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="node-link:inherited-enabled",
                    show_enabled_switch=True,
                    node_link_active=True,
                )
            }
        }
    )
    process_events(app)

    assert _row_activation_enabled(title_row) is False
    assert title_row.cursor().shape() == Qt.CursorShape.ArrowCursor

    controller.apply_decisions(
        {
            "B": {
                "vectorscopecc": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:enabled",
                    show_enabled_switch=True,
                    node_link_active=False,
                )
            }
        }
    )
    process_events(app)

    assert _row_activation_enabled(title_row) is True
    assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor

    _release_title_row(title_row)
    process_events(app)

    assert accordion_controller.toggle_calls == 1
    assert enabled_switch.isChecked() is False
    wrapper.deleteLater()
    process_events(app)


def test_node_card_mode_controller_restores_switch_only_title_row_activation() -> None:
    """Independent switch-only rows should become clickable after linked mode clears."""

    app = ensure_qapp()
    wrapper = QWidget()
    title_row = _InteractiveTitleRow(wrapper)
    switch_wrapper = QWidget(wrapper)
    enabled_switch = QCheckBox(switch_wrapper)
    binding = NodeCardModeBinding(
        wrapper=wrapper,
        title_row=title_row,
        content_body=None,
        content_layout=None,
        chevron=None,
        enabled_switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=None,
        collapsible=False,
        has_rows=False,
        allow_unbounded_content_height=False,
    )
    controller = NodeCardModeController()
    controller.register("B", "vae_override", binding)
    wrapper.show()
    process_events(app)

    controller.apply_decisions(
        {
            "B": {
                "vae_override": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="node-link:inherited-enabled",
                    show_enabled_switch=True,
                    node_link_active=True,
                )
            }
        }
    )
    process_events(app)

    assert _row_activation_enabled(title_row) is False

    controller.apply_decisions(
        {
            "B": {
                "vae_override": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:enabled",
                    show_enabled_switch=True,
                    node_link_active=False,
                )
            }
        }
    )
    process_events(app)

    assert _row_activation_enabled(title_row) is True
    _release_title_row(title_row)
    process_events(app)

    assert enabled_switch.isChecked() is True
    wrapper.deleteLater()
    process_events(app)
