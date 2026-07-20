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

"""Render the pending restart indicator for the workflow toolbar row."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    app_text,
    set_localized_accessible_description,
    set_localized_accessible_name,
    set_localized_tooltip,
)

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPaintEvent, QPainter
from PySide6.QtWidgets import QAbstractButton, QBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, Theme  # type: ignore[import-untyped]

from substitute.presentation.semantic_colors import (
    legible_text_color_for_background,
    semantic_warning_color,
)
from substitute.presentation.shell.chrome_style import (
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    connect_theme_refresh,
)

_BUTTON_WIDTH = WORKFLOW_TOOLBAR_CONTROL_HEIGHT
_ICON_SIZE = 16.0
_ICON_HALF_SIZE = _ICON_SIZE / 2.0


class PendingRestartToolbarButton(QAbstractButton):
    """Show pending restart requirements in the main workflow toolbar."""

    activated = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the toolbar restart indicator in its empty hidden state."""

        super().__init__(parent)
        self._count = 0
        self._collapsed = False
        self._balance_spacer: QWidget | None = None
        self._balance_spacer_width = 0
        self._balance_center_widget: QWidget | None = None
        self._balance_toolbar: QWidget | None = None
        self._centering_spacer: QWidget | None = None
        self._centering_toolbar: QWidget | None = None
        self._alignment_spacer: QWidget | None = None
        self._alignment_toolbar: QWidget | None = None
        self._alignment_minimum_width = WORKFLOW_TOOLBAR_CONTROL_HEIGHT
        self.setObjectName("PendingRestartToolbarButton")
        set_localized_accessible_name(self, "Pending restart requirements")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(WORKFLOW_TOOLBAR_CONTROL_HEIGHT)
        self.setFixedWidth(_BUTTON_WIDTH)
        self.clicked.connect(self.activated.emit)
        connect_theme_refresh(self, self.update)
        self.set_count(0)
        self.set_collapsed(True)

    def set_centering_spacer(self, spacer: QWidget, *, toolbar: QWidget) -> None:
        """Bind the Settings-search leading spacer owned by this toolbar control."""

        self._centering_spacer = spacer
        self._centering_toolbar = toolbar
        toolbar.installEventFilter(self)
        self._sync_centering_spacer()

    def set_balance_spacer(
        self,
        spacer: QWidget,
        *,
        expanded_width: int,
        center_widget: QWidget | None = None,
        toolbar: QWidget | None = None,
    ) -> None:
        """Bind the adaptive toolbar balance spacer to this restart control."""

        self._balance_spacer = spacer
        self._balance_spacer_width = max(0, expanded_width)
        self._balance_center_widget = center_widget
        self._balance_toolbar = toolbar
        if center_widget is not None:
            center_widget.installEventFilter(self)
        if toolbar is not None:
            toolbar.installEventFilter(self)
        self._sync_balance_spacer()

    def set_alignment_spacer(
        self,
        spacer: QWidget,
        *,
        toolbar: QWidget,
        minimum_width: int = WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    ) -> None:
        """Bind the right-alignment spacer used only when real room exists."""

        self._alignment_spacer = spacer
        self._alignment_toolbar = toolbar
        self._alignment_minimum_width = max(1, minimum_width)
        toolbar.installEventFilter(self)
        self._sync_alignment_spacer()

    def refresh_toolbar_spacing(self) -> None:
        """Reconcile owned toolbar spacers after sibling toolbar widgets change."""

        self._sync_centering_spacer()
        self._sync_balance_spacer()
        self._sync_alignment_spacer()
        parent = self.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is not None:
            layout.invalidate()

    def set_count(self, count: int) -> None:
        """Update the pending restart count and tooltip."""

        self._count = max(0, count)
        tooltip = _tooltip(self._count)
        set_localized_tooltip(self, tooltip.source_text, *tooltip.arguments)
        set_localized_accessible_description(
            self, tooltip.source_text, *tooltip.arguments
        )
        self.update()

    def count(self) -> int:
        """Return the current pending restart item count."""

        return self._count

    def set_collapsed(self, collapsed: bool, *, animated: bool = True) -> None:
        """Show or hide the toolbar button without shifting unrelated controls."""

        _ = animated
        self._collapsed = collapsed
        self.setEnabled(not collapsed)
        self.setVisible(not collapsed)
        self.setFixedWidth(0 if collapsed else _BUTTON_WIDTH)
        self._sync_centering_spacer()
        self._sync_balance_spacer()
        self._sync_alignment_spacer()
        self.updateGeometry()

    def is_collapsed(self) -> bool:
        """Return whether the toolbar indicator is hidden."""

        return self._collapsed

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refresh the balance spacer when toolbar pressure changes."""

        if (
            watched is self._balance_center_widget
            or watched is self._balance_toolbar
            or watched is self._centering_toolbar
            or watched is self._alignment_toolbar
        ) and (
            event.type()
            in {
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.Resize,
                QEvent.Type.LayoutRequest,
            }
        ):
            self._sync_centering_spacer()
            self._sync_balance_spacer()
            self._sync_alignment_spacer()
        return super().eventFilter(watched, event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Paint the restart icon and count badge."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        background = self._background_color()
        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(self.rect()), 6.0, 6.0)
        self._paint_restart_icon(painter)
        self._paint_badge(painter)

    def _paint_restart_icon(self, painter: QPainter) -> None:
        """Paint the app-standard restart icon."""

        color = self._icon_color()
        rect = QRectF(
            (self.width() - _ICON_SIZE) / 2.0,
            (self.height() - _ICON_SIZE) / 2.0,
            _ICON_SIZE,
            _ICON_SIZE,
        )
        _render_fluent_icon(FIF.SYNC, painter, rect, color=color, theme=self._theme())

    def _paint_badge(self, painter: QPainter) -> None:
        """Paint the pending restart count badge."""

        if self._count <= 0:
            return
        text = str(min(self._count, 99))
        badge_width = 12.0 if self._count < 10 else 16.0
        badge_height = 12.0
        badge_x = (self.width() / 2.0) + _ICON_HALF_SIZE - (badge_width / 2.0)
        badge_y = (self.height() / 2.0) + _ICON_HALF_SIZE - (badge_height / 2.0)
        badge_rect = QRectF(
            min(max(0.0, badge_x), max(0.0, self.width() - badge_width)),
            min(max(0.0, badge_y), max(0.0, self.height() - badge_height)),
            badge_width,
            badge_height,
        )
        badge_color = semantic_warning_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_color)
        painter.drawRoundedRect(badge_rect, badge_height / 2.0, badge_height / 2.0)
        painter.setPen(legible_text_color_for_background(badge_color))
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _background_color(self) -> QColor:
        """Return the hover/press background for the toolbar button."""

        channel = 255 if self._is_dark_theme() else 0
        if not self.isEnabled():
            return QColor(channel, channel, channel, 0)
        if self.isDown():
            return QColor(
                channel, channel, channel, 32 if self._is_dark_theme() else 24
            )
        if self.underMouse():
            return QColor(
                channel, channel, channel, 22 if self._is_dark_theme() else 14
            )
        return QColor(channel, channel, channel, 0)

    def _icon_color(self) -> QColor:
        """Return the theme-aware restart icon color."""

        color = QColor("#ffffff") if self._is_dark_theme() else QColor("#000000")
        color.setAlpha(225 if self.isEnabled() else 92)
        return color

    def _theme(self) -> Theme:
        """Return the QFluent icon theme matching the active shell theme."""

        return Theme.DARK if self._is_dark_theme() else Theme.LIGHT

    def _is_dark_theme(self) -> bool:
        """Return whether the active QFluent theme is dark."""

        try:
            from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover - lightweight test stubs
            return True
        return bool(isDarkTheme())

    def _sync_centering_spacer(self) -> None:
        """Show Settings-search leading stretch only while search is centered."""

        if self._centering_spacer is not None:
            self._set_spacer_participation(
                self._centering_spacer,
                visible=self._should_show_settings_search_spacers(),
                before_widget=self._balance_center_widget or self,
            )

    def _sync_balance_spacer(self) -> None:
        """Collapse toolbar balance except when centering search is affordable."""

        if self._balance_spacer is not None:
            width = self._resolved_balance_spacer_width()
            self._balance_spacer.setFixedWidth(width)
            self._set_spacer_participation(
                self._balance_spacer,
                visible=width > 0,
                before_widget=self,
            )

    def _sync_alignment_spacer(self) -> None:
        """Show right-alignment spacing only when it can absorb meaningful room."""

        if self._alignment_spacer is not None:
            self._set_spacer_participation(
                self._alignment_spacer,
                visible=self._should_show_alignment_spacer(),
                before_widget=self,
            )

    def _set_spacer_participation(
        self,
        spacer: QWidget,
        *,
        visible: bool,
        before_widget: QWidget,
    ) -> None:
        """Insert or remove a spacer so collapsed spacers add no layout spacing."""

        parent = spacer.parentWidget()
        layout = parent.layout() if parent is not None else None
        if not isinstance(layout, QBoxLayout):
            spacer.setVisible(visible)
            return
        spacer_index = layout.indexOf(spacer)
        if not visible:
            if spacer_index >= 0:
                layout.removeWidget(spacer)
            spacer.setVisible(False)
            return
        before_index = layout.indexOf(before_widget)
        if before_index < 0:
            spacer.setVisible(False)
            return
        if spacer_index < 0:
            layout.insertWidget(before_index, spacer)
        elif spacer_index != max(0, before_index - 1):
            layout.removeWidget(spacer)
            updated_before_index = layout.indexOf(before_widget)
            if updated_before_index >= 0:
                layout.insertWidget(updated_before_index, spacer)
            else:
                spacer.setVisible(False)
                return
        spacer.setVisible(True)

    def _should_show_alignment_spacer(self) -> bool:
        """Return whether right alignment has enough surplus to avoid dead gaps."""

        if self._alignment_spacer is None or self._alignment_toolbar is None:
            return False
        if self._should_show_settings_search_spacers():
            return True
        surplus_width = self._available_alignment_spacer_width()
        return surplus_width >= self._alignment_minimum_width

    def _available_alignment_spacer_width(self) -> int:
        """Return width the alignment spacer would receive if it were visible."""

        if self._alignment_spacer is None or self._alignment_toolbar is None:
            return 0
        layout = self._alignment_toolbar.layout()
        if layout is None:
            return 0
        toolbar_width = int(self._alignment_toolbar.width())
        if toolbar_width <= 0:
            return 0
        margins = layout.contentsMargins()
        spacing = max(0, int(layout.spacing()))
        visible_width = int(margins.left()) + int(margins.right())
        visible_count = 0
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None or widget is self._alignment_spacer or widget.isHidden():
                continue
            visible_width += self._toolbar_widget_preferred_width(widget)
            visible_count += 1
        visible_width += spacing * max(0, visible_count)
        return max(0, toolbar_width - visible_width)

    @staticmethod
    def _toolbar_widget_preferred_width(widget: QWidget) -> int:
        """Return one toolbar widget width demand without using stretched geometry."""

        minimum_width = max(0, int(widget.minimumWidth()))
        preferred_width = max(minimum_width, int(widget.sizeHint().width()))
        maximum_width = int(widget.maximumWidth())
        if maximum_width >= minimum_width:
            return min(preferred_width, maximum_width)
        return preferred_width

    def _resolved_balance_spacer_width(self) -> int:
        """Return the current balance spacer width allowed by toolbar state."""

        if not self._collapsed:
            if self._should_show_settings_search_spacers():
                return max(
                    0,
                    self._balance_spacer_width
                    - _BUTTON_WIDTH
                    - self._toolbar_layout_spacing(),
                )
            return 0
        if (
            self._balance_center_widget is not None
            and self._balance_center_widget.isHidden()
        ):
            return 0
        if self._toolbar_width_is_starved():
            return 0
        return self._balance_spacer_width

    def _should_show_settings_search_spacers(self) -> bool:
        """Return whether Settings search owns the toolbar center slot."""

        if (
            self._balance_center_widget is None
            or self._balance_center_widget.isHidden()
            or self._centering_spacer is None
        ):
            return False
        return not self._toolbar_width_is_starved()

    def _toolbar_layout_spacing(self) -> int:
        """Return toolbar layout spacing for fixed centering compensation."""

        toolbar = self._balance_toolbar or self._alignment_toolbar
        layout = toolbar.layout() if toolbar is not None else None
        if layout is None:
            return 0
        return max(0, int(layout.spacing()))

    def _toolbar_width_is_starved(self) -> bool:
        """Return whether the toolbar cannot afford decorative balance width."""

        if self._balance_toolbar is None or self._balance_center_widget is None:
            return False
        toolbar_width = int(self._balance_toolbar.width())
        if toolbar_width <= 0:
            return False
        center_width = max(
            int(self._balance_center_widget.width()),
            int(self._balance_center_widget.sizeHint().width()),
        )
        minimum_balanced_width = (
            self._toolbar_horizontal_chrome_width()
            + (self._balance_spacer_width * 2)
            + center_width
        )
        return toolbar_width < minimum_balanced_width + self._balance_spacer_width

    def _toolbar_horizontal_chrome_width(self) -> int:
        """Return non-search toolbar width needed before flexible spacers."""

        if self._balance_toolbar is None:
            return 0
        layout = self._balance_toolbar.layout()
        if layout is None:
            return 0
        margins = layout.contentsMargins()
        spacing = max(0, int(layout.spacing()))
        item_count = max(0, int(layout.count()))
        return (
            int(margins.left())
            + int(margins.right())
            + (spacing * max(0, item_count - 1))
        )


def _tooltip(count: int) -> ApplicationMessage:
    """Return the toolbar tooltip for the pending restart count."""

    if count == 1:
        return app_text("1 change requires restart")
    return app_text("%1 changes require restart", count)


def _render_fluent_icon(
    icon: object,
    painter: QPainter,
    rect: QRectF,
    *,
    color: QColor,
    theme: Theme,
) -> None:
    """Render a QFluent icon using the app's standard themed icon path."""

    render = getattr(icon, "render", None)
    if callable(render):
        painter.save()
        painter.setOpacity(color.alphaF())
        render(painter, rect, theme=theme, fill=color.name(QColor.NameFormat.HexRgb))
        painter.restore()
        return
    qicon = icon if isinstance(icon, QIcon) else QIcon()
    qicon.paint(painter, rect.toRect(), Qt.AlignmentFlag.AlignCenter)


__all__ = ["PendingRestartToolbarButton"]
