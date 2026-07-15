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

"""Render the dedicated Windows-like Settings navigation pane."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import (
    Property,
    QObject,
    QEvent,
    QRect,
    QRectF,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, IconWidget  # type: ignore[import-untyped]
from qfluentwidgets.common.icon import FluentIconBase  # type: ignore[import-untyped]

from substitute.presentation.motion import (
    SETTINGS_NAV_INDICATOR_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    restart_property_animation,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_NAVIGATION_ICON_SIZE,
    SETTINGS_NAVIGATION_ICON_TEXT_GAP,
    SETTINGS_NAVIGATION_ITEM_HEIGHT,
    SETTINGS_NAVIGATION_ITEM_SPACING,
    SETTINGS_NAVIGATION_ITEM_WIDTH,
    SETTINGS_NAVIGATION_RADIUS,
    SETTINGS_NAVIGATION_RAIL_HEIGHT,
    SETTINGS_NAVIGATION_RAIL_WIDTH,
    SETTINGS_NAVIGATION_TOP_MARGIN,
    SETTINGS_NAVIGATION_WIDTH,
    settings_accent_color,
    settings_navigation_overlay_color,
    settings_navigation_selected_fill_color,
)
from substitute.presentation.widgets.row_interaction_feedback import (
    RowInteractionFeedback,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.settings.settings_navigation")


@dataclass(frozen=True)
class SettingsNavigationDescriptor:
    """Describe one visible Settings navigation page."""

    page_id: str
    title: str
    subtitle: str
    icon: FluentIconBase | str | None = None


class SettingsNavigationItem(QFrame):
    """Render one selectable Settings navigation row."""

    activated = Signal(str)

    def __init__(
        self,
        descriptor: SettingsNavigationDescriptor,
        parent: QWidget | None = None,
    ) -> None:
        """Create a navigation row from one descriptor."""

        super().__init__(parent)
        self.page_id = descriptor.page_id
        self._selected = False
        self._hovered = False
        self._pressed = False
        self.setObjectName(f"SettingsNavigationItem-{descriptor.page_id}")
        self.setFixedSize(
            SETTINGS_NAVIGATION_ITEM_WIDTH, SETTINGS_NAVIGATION_ITEM_HEIGHT
        )
        self.setToolTip(descriptor.subtitle or descriptor.title)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icon_slot = self._build_icon_slot(descriptor.icon)
        self.title_label = self._build_title_label(descriptor.title)
        self._build_layout()
        self._interaction = RowInteractionFeedback(
            self,
            overlay_path=_navigation_item_overlay_path,
            activation=lambda: self.activated.emit(self.page_id),
            consume_target_press=False,
        )
        self._interaction.set_interactive_targets((self.icon_slot, self.title_label))

    def set_selected(self, selected: bool) -> None:
        """Apply selected state to the row."""

        self._selected = selected
        font = self.title_label.font()
        font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        self.title_label.setFont(font)
        self.update()

    def is_selected(self) -> bool:
        """Return whether this row is currently selected."""

        return self._selected

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route label and icon clicks through the row interaction state."""

        if self._interaction.eventFilter(watched, event):
            return True
        return bool(super().eventFilter(watched, event))

    def enterEvent(self, event: QEnterEvent) -> None:
        """Apply hover feedback when the pointer enters the row."""

        self._hovered = True
        self._interaction.set_hovered(True)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear transient feedback when the pointer leaves the row."""

        self._hovered = False
        self._pressed = False
        self._interaction.clear_transient_state()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track pressed state for body clicks."""

        self._pressed = event.button() == Qt.MouseButton.LeftButton
        self._interaction.handle_mouse_press(event)
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit activation for a released row click."""

        self._pressed = False
        self._interaction.handle_mouse_release(event)
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint selection and hover feedback behind row contents."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = _navigation_item_overlay_path(self.rect())
        if self._selected:
            painter.fillPath(path, settings_navigation_selected_fill_color())
        overlay = settings_navigation_overlay_color(
            pressed=self._pressed,
            hovered=self._hovered,
        )
        if overlay.alpha() > 0:
            painter.fillPath(path, overlay)
        self._interaction.paint_overlay(painter)

    def _build_icon_slot(self, icon: FluentIconBase | str | None) -> QWidget:
        """Create the fixed icon slot for one navigation row."""

        slot = QWidget(self)
        slot.setFixedSize(SETTINGS_NAVIGATION_ICON_SIZE, SETTINGS_NAVIGATION_ICON_SIZE)
        layout = QHBoxLayout(slot)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if icon is not None:
            icon_widget = IconWidget(icon, slot)
            icon_widget.setFixedSize(
                SETTINGS_NAVIGATION_ICON_SIZE,
                SETTINGS_NAVIGATION_ICON_SIZE,
            )
            layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignCenter)
        return slot

    def _build_title_label(self, title: str) -> BodyLabel:
        """Create the one-line navigation title label."""

        label = BodyLabel(title, self)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        return label

    def _build_layout(self) -> None:
        """Compose the navigation row."""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 14, 0)
        layout.setSpacing(SETTINGS_NAVIGATION_ICON_TEXT_GAP)
        layout.addWidget(self.icon_slot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignVCenter)


class SettingsNavigationPane(QWidget):
    """Own the Settings page navigation list and animated accent rail."""

    pageSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty Settings navigation pane."""

        super().__init__(parent)
        self._items_by_page_id: dict[str, SettingsNavigationItem] = {}
        self._page_order: list[str] = []
        self._selected_page_id: str | None = None
        self._indicator_y = 0
        self._indicator_animation = QPropertyAnimation(self, b"indicatorY", self)
        self._indicator_realign_pending = False
        self.setFixedWidth(SETTINGS_NAVIGATION_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self._build_layout()

    def set_pages(self, pages: Sequence[SettingsNavigationDescriptor]) -> None:
        """Replace visible navigation rows in stable page order."""

        self._clear_items()
        self._page_order = [page.page_id for page in pages]
        for index, page in enumerate(pages):
            item = SettingsNavigationItem(page, self)
            item.activated.connect(self._on_item_activated)
            self._layout.insertWidget(index, item, 0, Qt.AlignmentFlag.AlignHCenter)
            self._items_by_page_id[page.page_id] = item
        if self._page_order:
            self.select_page(self._page_order[0], animated=False)

    def page_ids(self) -> tuple[str, ...]:
        """Return page ids in navigation order."""

        return tuple(self._page_order)

    def selected_page_id(self) -> str | None:
        """Return the selected page id."""

        return self._selected_page_id

    def select_page(self, page_id: str, *, animated: bool = True) -> None:
        """Select one page row without emitting a user action."""

        if page_id not in self._items_by_page_id:
            return
        if page_id == self._selected_page_id and self._indicator_y:
            return
        self._selected_page_id = page_id
        for current_page_id, item in self._items_by_page_id.items():
            item.set_selected(current_page_id == page_id)
        self._sync_indicator_to_selected(animated=animated)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the accent rail for the selected row."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self._items_by_page_id.get(self._selected_page_id or "")
        if selected is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(settings_accent_color())
            painter.drawRoundedRect(
                selected.x() + 2,
                self._indicator_y,
                SETTINGS_NAVIGATION_RAIL_WIDTH,
                SETTINGS_NAVIGATION_RAIL_HEIGHT,
                1.5,
                1.5,
            )

    def showEvent(self, event: QShowEvent) -> None:
        """Realign the indicator when the navigation pane becomes visible."""

        super().showEvent(event)
        self._schedule_indicator_realign()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Realign the indicator after navigation geometry changes."""

        super().resizeEvent(event)
        self._schedule_indicator_realign()

    def _build_layout(self) -> None:
        """Create the vertical navigation row stack."""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, SETTINGS_NAVIGATION_TOP_MARGIN, 0, 0)
        self._layout.setSpacing(SETTINGS_NAVIGATION_ITEM_SPACING)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self._layout.addStretch(1)

    def _on_item_activated(self, page_id: str) -> None:
        """Select and emit a user-requested page."""

        if page_id == self._selected_page_id:
            return
        self.select_page(page_id)
        self.pageSelected.emit(page_id)

    def _clear_items(self) -> None:
        """Remove existing navigation rows."""

        for item in self._items_by_page_id.values():
            self._layout.removeWidget(item)
            item.setParent(None)
            item.deleteLater()
        self._items_by_page_id.clear()
        self._page_order.clear()
        self._selected_page_id = None
        self._indicator_animation.stop()
        self.setIndicatorY(0)

    def _sync_indicator_to_selected(self, *, animated: bool) -> None:
        """Move the selected accent rail to the selected row."""

        item = self._items_by_page_id.get(self._selected_page_id or "")
        if item is None:
            return
        target_y = item.y() + item.height() // 2 - SETTINGS_NAVIGATION_RAIL_HEIGHT // 2
        if animated:
            restart_property_animation(
                self._indicator_animation,
                start_value=self._indicator_y,
                end_value=target_y,
                duration_ms=SETTINGS_NAV_INDICATOR_DURATION_MS,
                easing_curve=TRANSFORM_EASING_CURVE,
            )
            return
        self._indicator_animation.stop()
        self.setIndicatorY(target_y)

    def _schedule_indicator_realign(self) -> None:
        """Schedule indicator alignment after pending layout work settles."""

        if self._indicator_realign_pending:
            return
        self._indicator_realign_pending = True
        QTimer.singleShot(0, self._complete_indicator_realign)

    def _complete_indicator_realign(self) -> None:
        """Complete pending indicator alignment."""

        self._indicator_realign_pending = False
        self._layout.activate()
        self._sync_indicator_to_selected(animated=False)

    def _getIndicatorY(self) -> int:
        """Return the current accent rail y coordinate."""

        return self._indicator_y

    def setIndicatorY(self, y: int) -> None:
        """Set the accent rail y coordinate and repaint."""

        self._indicator_y = y
        self.update()

    indicatorY = Property(int, _getIndicatorY, setIndicatorY)


def _navigation_item_overlay_path(rect: QRect) -> QPainterPath:
    """Return the rounded path used for navigation row feedback."""

    path = QPainterPath()
    path.addRoundedRect(
        QRectF(rect.adjusted(1, 1, -1, -1)),
        SETTINGS_NAVIGATION_RADIUS,
        SETTINGS_NAVIGATION_RADIUS,
    )
    return path


__all__ = [
    "SETTINGS_NAVIGATION_WIDTH",
    "SettingsNavigationDescriptor",
    "SettingsNavigationItem",
    "SettingsNavigationPane",
]
