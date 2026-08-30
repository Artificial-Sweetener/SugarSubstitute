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

"""Construct typed node-card mode-controller scenarios."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from substitute.application.node_behavior import NodeDisplayDecision
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
    AccordionMotionController,
)
from substitute.presentation.editor.panel.node_card.mode_controller import (
    NodeCardModeBinding,
    NodeCardModeController,
)
from tests.presentation.editor.node_card.support import ensure_qapp
from tests.support.qt.lifecycle import destroy_qt_object


class RecordingAccordionController:
    """Record title-row accordion toggle requests."""

    def __init__(self) -> None:
        """Initialize an empty toggle log."""

        self.toggle_calls = 0

    def toggle(self) -> None:
        """Record one accordion toggle request."""

        self.toggle_calls += 1


class InteractiveTitleRow(QWidget):
    """Provide the production row-activation surface without styling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize without an active row callback."""

        super().__init__(parent)
        self._row_activation: Callable[[], None] | None = None

    def set_row_activation(self, callback: Callable[[], None] | None) -> None:
        """Store one callback and mirror the production cursor state."""

        self._row_activation = callback
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if callback is not None
            else Qt.CursorShape.ArrowCursor
        )

    def clear_row_activation(self) -> None:
        """Clear row activation and its cursor feedback."""

        self.set_row_activation(None)

    def row_activation_enabled(self) -> bool:
        """Return whether row-level activation is installed."""

        return self._row_activation is not None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Invoke row activation from a release event."""

        if self._row_activation is not None:
            self._row_activation()
            event.accept()
            return
        super().mouseReleaseEvent(event)


@dataclass(slots=True)
class ModeHarness:
    """Own one registered mode-controller binding and its Qt objects."""

    wrapper: QWidget
    title_row: QWidget
    content_body: QWidget | None
    content_layout: QVBoxLayout | None
    chevron: AccordionChevronWidget | None
    switch_wrapper: QWidget | None
    enabled_switch: QCheckBox | None
    controller: NodeCardModeController

    def apply(self, decision: NodeDisplayDecision) -> None:
        """Apply one decision to the registered test card."""

        self.controller.apply_decisions({"B": {"node": decision}})

    def destroy(self) -> None:
        """Destroy the complete card tree synchronously."""

        destroy_qt_object(self.wrapper)


def create_body_harness() -> ModeHarness:
    """Create a visible card with body, chevron, and enabled switch."""

    ensure_qapp()
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
    return _register_harness(
        wrapper=wrapper,
        title_row=title_row,
        content_body=content_body,
        content_layout=content_layout,
        chevron=chevron,
        switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=None,
        collapsible=True,
        has_rows=True,
    )


def create_title_harness(
    *,
    collapsible: bool,
    has_rows: bool,
    accordion_controller: RecordingAccordionController | None = None,
) -> ModeHarness:
    """Create a card whose title row exposes activation behavior."""

    ensure_qapp()
    wrapper = QWidget()
    title_row = InteractiveTitleRow(wrapper)
    switch_wrapper = QWidget(wrapper)
    enabled_switch = QCheckBox(switch_wrapper)
    return _register_harness(
        wrapper=wrapper,
        title_row=title_row,
        content_body=None,
        content_layout=None,
        chevron=AccordionChevronWidget(wrapper) if collapsible else None,
        switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=accordion_controller,
        collapsible=collapsible,
        has_rows=has_rows,
    )


def linked_decision() -> NodeDisplayDecision:
    """Return the inherited linked-mode decision."""

    return NodeDisplayDecision(
        visible=True,
        enabled=False,
        reason="node-link:inherited-enabled",
        show_enabled_switch=True,
        node_link_active=True,
    )


def independent_decision(*, enabled: bool) -> NodeDisplayDecision:
    """Return an independent-mode decision with explicit activation state."""

    return NodeDisplayDecision(
        visible=True,
        enabled=enabled,
        reason="explicit:enabled",
        show_enabled_switch=True,
        node_link_active=False,
    )


def expected_visible_item_height(layout: QVBoxLayout, *widgets: QWidget) -> int:
    """Return layout height from visible items, margins, and spacing."""

    margins = layout.contentsMargins()
    visible_widgets = [widget for widget in widgets if not widget.isHidden()]
    spacing = layout.spacing() * max(0, len(visible_widgets) - 1)
    return (
        margins.top()
        + sum(_expected_widget_height(widget) for widget in visible_widgets)
        + spacing
        + margins.bottom()
    )


def _register_harness(
    *,
    wrapper: QWidget,
    title_row: QWidget,
    content_body: QWidget | None,
    content_layout: QVBoxLayout | None,
    chevron: AccordionChevronWidget | None,
    switch_wrapper: QWidget | None,
    enabled_switch: QCheckBox | None,
    accordion_controller: RecordingAccordionController | None,
    collapsible: bool,
    has_rows: bool,
) -> ModeHarness:
    """Register one exact binding with a fresh controller."""

    binding = NodeCardModeBinding(
        wrapper=wrapper,
        title_row=title_row,
        content_body=content_body,
        content_layout=content_layout,
        chevron=chevron,
        enabled_switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        accordion_controller=(
            None
            if accordion_controller is None
            else cast(AccordionMotionController, accordion_controller)
        ),
        collapsible=collapsible,
        has_rows=has_rows,
        allow_unbounded_content_height=False,
    )
    controller = NodeCardModeController()
    controller.register("B", "node", binding)
    return ModeHarness(
        wrapper=wrapper,
        title_row=title_row,
        content_body=content_body,
        content_layout=content_layout,
        chevron=chevron,
        switch_wrapper=switch_wrapper,
        enabled_switch=enabled_switch,
        controller=controller,
    )


def _expected_widget_height(widget: QWidget) -> int:
    """Return the height contributed by one visible widget."""

    return max(widget.sizeHint().height(), widget.minimumHeight(), widget.height())


__all__ = [
    "InteractiveTitleRow",
    "ModeHarness",
    "RecordingAccordionController",
    "create_body_harness",
    "create_title_harness",
    "expected_visible_item_height",
    "independent_decision",
    "linked_decision",
]
