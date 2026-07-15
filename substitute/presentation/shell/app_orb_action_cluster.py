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

"""Provide the under-orb shell action cluster."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QIcon,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QAbstractButton, QWidget
from qfluentwidgets import FluentIcon as FIF, Theme  # type: ignore[import-untyped]

from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.chrome_style import (
    APP_ORB_DIAMETER,
    APP_ORB_TOP,
    APP_ORB_RESERVED_WIDTH,
    APP_ORB_TAB_CUTOUT_RADIUS,
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    WORKFLOW_TOOLBAR_VERTICAL_PADDING,
    WORKFLOW_TITLEBAR_HEIGHT,
    connect_theme_refresh,
    toolbar_separator_rgba,
)
from substitute.presentation.shell.menu_button_controller import (
    ShellMenuButtonController,
)

APP_ORB_ACTION_CLUSTER_OBJECT_NAME = "AppOrbActionCluster"
APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME = "AppOrbActionLayoutAnchor"
APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME = "AppOrbCubeStackButton"
APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME = "AppOrbOverrideButton"
APP_ORB_ACTION_SEPARATOR_OBJECT_NAME = "AppOrbActionSeparator"
_BUTTON_WIDTH = 23
_SEPARATOR_WIDTH = 1
_ACTION_REGION_WIDTH = (_BUTTON_WIDTH * 2) + _SEPARATOR_WIDTH
APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH = _ACTION_REGION_WIDTH
_BUTTON_HEIGHT = WORKFLOW_TOOLBAR_CONTROL_HEIGHT
_BUTTON_TOP_CUTOUT_RADIUS = APP_ORB_TAB_CUTOUT_RADIUS
_ORB_BOTTOM_IN_CLUSTER_Y = (
    APP_ORB_TOP
    + APP_ORB_DIAMETER
    - WORKFLOW_TITLEBAR_HEIGHT
    - WORKFLOW_TOOLBAR_VERTICAL_PADDING
)
_BUTTON_TOP_CUTOUT_CENTER_Y = (
    APP_ORB_TOP
    + APP_ORB_DIAMETER / 2
    - WORKFLOW_TITLEBAR_HEIGHT
    - WORKFLOW_TOOLBAR_VERTICAL_PADDING
)
_SEPARATOR_EDGE_INSET = 6
_SEPARATOR_Y = int(_ORB_BOTTOM_IN_CLUSTER_Y) + _SEPARATOR_EDGE_INSET
_SEPARATOR_HEIGHT = (
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT - _SEPARATOR_Y - _SEPARATOR_EDGE_INSET
)
_LOWER_BUTTON_ICON_Y_SHIFT = 2.0
_CUBE_ICON_SIZE = 13.0
_CUBE_ICON_Y_OFFSET = 5.0 + _LOWER_BUTTON_ICON_Y_SHIFT
_PIN_ICON_SIZE = 11.0
_PIN_ICON_Y = 15.0 + _LOWER_BUTTON_ICON_Y_SHIFT
_CHEVRON_WIDTH = 5.0
_CHEVRON_HEIGHT = 3.0
_CHEVRON_STROKE = 1.1
_CHEVRON_Y = 29.0 + _LOWER_BUTTON_ICON_Y_SHIFT


class AppOrbActionCluster(QWidget):
    """Group the orb-adjacent cube-stack and override actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the fixed under-orb action cluster."""

        super().__init__(parent)
        self.setObjectName(APP_ORB_ACTION_CLUSTER_OBJECT_NAME)
        self.setFixedSize(APP_ORB_RESERVED_WIDTH, WORKFLOW_TOOLBAR_CONTROL_HEIGHT)
        self.cube_stack_button = AppOrbCubeStackButton(self)
        self.override_button = AppOrbOverrideButton(self)
        self._separator = QWidget(self)
        self._separator.setObjectName(APP_ORB_ACTION_SEPARATOR_OBJECT_NAME)
        self._separator.setFixedSize(_SEPARATOR_WIDTH, _SEPARATOR_HEIGHT)
        self._sync_child_geometry()
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    def resizeEvent(self, _event: object) -> None:
        """Keep action children aligned inside the fixed cluster."""

        self._sync_child_geometry()

    def _sync_child_geometry(self) -> None:
        """Position actions around the orb-center separator."""

        self.cube_stack_button.setGeometry(0, 0, _BUTTON_WIDTH, _BUTTON_HEIGHT)
        self._separator.setGeometry(
            _BUTTON_WIDTH,
            _SEPARATOR_Y,
            _SEPARATOR_WIDTH,
            _SEPARATOR_HEIGHT,
        )
        self.override_button.setGeometry(
            _BUTTON_WIDTH + _SEPARATOR_WIDTH,
            0,
            _BUTTON_WIDTH,
            _BUTTON_HEIGHT,
        )

    def _apply_theme_styles(self) -> None:
        """Refresh the separator color after theme changes."""

        self._separator.setStyleSheet(
            f"""
            QWidget#{APP_ORB_ACTION_SEPARATOR_OBJECT_NAME} {{
                background: {toolbar_separator_rgba()};
                border: none;
                min-width: 1px;
                max-width: 1px;
                border-radius: 0.5px;
            }}
            """
        )


class AppOrbActionButton(QAbstractButton):
    """Paint one punched under-orb toolbar action."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        cluster_x: float,
    ) -> None:
        """Create one shaped action button with a cluster-relative cutout."""

        super().__init__(parent)
        self._cluster_x = cluster_x
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(_BUTTON_WIDTH, _BUTTON_HEIGHT)
        self.toggled.connect(self._refresh_visual_state)
        connect_theme_refresh(self, self.update)

    def hitButton(self, pos: QPoint) -> bool:
        """Return whether ``pos`` falls inside the punched action shape."""

        return self._button_path().contains(pos)

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Paint shaped hover, press, checked, focus, and icon states."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = self._button_path()
        background = self._background_color()
        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawPath(path)
        painter.save()
        painter.setClipPath(path)
        self._draw_icon(painter)
        painter.restore()

    def _button_path(self) -> QPainterPath:
        """Return the rounded action path with the orb punch removed."""

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 5.0, 5.0)
        cutout = QPainterPath()
        cutout.addEllipse(
            self._orb_center_x() - _BUTTON_TOP_CUTOUT_RADIUS,
            _BUTTON_TOP_CUTOUT_CENTER_Y - _BUTTON_TOP_CUTOUT_RADIUS,
            _BUTTON_TOP_CUTOUT_RADIUS * 2,
            _BUTTON_TOP_CUTOUT_RADIUS * 2,
        )
        return path.subtracted(cutout)

    def _orb_center_x(self) -> float:
        """Return the orb center in this button's local coordinates."""

        return (APP_ORB_DIAMETER / 2) - self._cluster_x

    def _background_color(self) -> QColor:
        """Return the state fill for the current button state."""

        is_dark = self._is_dark_theme()
        channel = 255 if is_dark else 0
        if not self.isEnabled():
            return QColor(channel, channel, channel, 0)
        if self.isDown():
            return QColor(channel, channel, channel, 30 if is_dark else 20)
        if self._clicked_visual_active():
            return QColor(channel, channel, channel, 24 if is_dark else 18)
        if self.underMouse():
            return QColor(channel, channel, channel, 22 if is_dark else 14)
        return QColor(channel, channel, channel, 0)

    def _clicked_visual_active(self) -> bool:
        """Return whether the button should paint its persistent clicked state."""

        return False

    def _icon_color(self) -> QColor:
        """Return a theme-aware icon foreground."""

        color = QColor("#ffffff") if self._is_dark_theme() else QColor("#000000")
        color.setAlpha(215 if self.isEnabled() else 92)
        return color

    def _icon_theme(self) -> Theme:
        """Return the icon theme matching the active shell theme."""

        return Theme.DARK if self._is_dark_theme() else Theme.LIGHT

    def _is_dark_theme(self) -> bool:
        """Return whether the active QFluent theme is dark."""

        try:
            from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover - lightweight test stubs
            return True
        return bool(isDarkTheme())

    def _draw_icon(self, painter: QPainter) -> None:
        """Draw the action glyph."""

        raise NotImplementedError

    def enterEvent(self, event: QEnterEvent) -> None:
        """Refresh hover painting when the pointer enters the shaped button."""

        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        """Refresh hover painting when the pointer leaves the shaped button."""

        super().leaveEvent(event)
        self.update()

    def _refresh_visual_state(self, _checked: bool = False) -> None:
        """Repaint the shaped button when its checked state changes."""

        self.update()


class AppOrbCubeStackButton(AppOrbActionButton):
    """Toggle cube-stack collapsed state below the app orb."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the cube-stack mode action."""

        super().__init__(parent, cluster_x=0.0)
        self.setObjectName(APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME)
        self.setCheckable(True)
        self._icon: object = AppIcon.PANEL_LEFT_20_FILLED
        self.setToolTip("Collapse cube stack")
        self.setAccessibleName("Collapse cube stack")

    def setIcon(self, icon: object) -> None:
        """Store the current cube-stack icon descriptor."""

        self._icon = icon
        self.update()

    def setIconSize(self, _size: QSize) -> None:
        """Accept toolbar-compatible icon size updates without resizing glyphs."""

    def _draw_icon(self, painter: QPainter) -> None:
        """Draw the cube-stack state icon."""

        _render_fluent_icon(
            self._icon,
            painter,
            self._icon_rect(),
            color=self._icon_color(),
            theme=self._icon_theme(),
        )

    def _icon_rect(self) -> QRectF:
        """Return the lowered cube-stack glyph bounds."""

        icon_rect = QRectF(
            (self.width() - _CUBE_ICON_SIZE) / 2,
            (self.height() - _CUBE_ICON_SIZE) / 2 + _CUBE_ICON_Y_OFFSET,
            _CUBE_ICON_SIZE,
            _CUBE_ICON_SIZE,
        )
        return icon_rect


class AppOrbOverrideButton(AppOrbActionButton):
    """Open the global overrides menu below the app orb."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the override-menu action."""

        super().__init__(parent, cluster_x=float(_BUTTON_WIDTH + _SEPARATOR_WIDTH))
        self.setObjectName(APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME)
        self.setToolTip("Select Global Field Overrides")
        self.setAccessibleName("Select Global Field Overrides")
        self._menu_controller = ShellMenuButtonController(
            self,
            menu_position=lambda: self.mapToGlobal(QPoint(0, self.height() - 2)),
        )
        self.clicked.connect(self._show_menu)

    def setMenu(self, menu: object) -> None:
        """Attach the global override menu to this shaped button."""

        self._menu_controller.set_menu(menu)

    def menu(self) -> object | None:
        """Return the attached menu."""

        return self._menu_controller.menu()

    def _show_menu(self, _checked: bool = False) -> None:
        """Open the attached override menu below the button."""

        self._menu_controller.handle_button_clicked(_checked)

    def _clicked_visual_active(self) -> bool:
        """Return whether the attached menu is visibly open."""

        return self._menu_controller.is_menu_open()

    def _draw_icon(self, painter: QPainter) -> None:
        """Draw a vertically stacked pin and chevron glyph."""

        icon_color = self._icon_color()
        _render_fluent_icon(
            FIF.PIN,
            painter,
            self._pin_icon_rect(),
            color=icon_color,
            theme=self._icon_theme(),
        )
        painter.setPen(
            QPen(
                icon_color,
                _CHEVRON_STROKE,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._chevron_path())

    def _pin_icon_rect(self) -> QRectF:
        """Return the lowered override pin glyph bounds."""

        return QRectF(
            (self.width() - _PIN_ICON_SIZE) / 2,
            _PIN_ICON_Y,
            _PIN_ICON_SIZE,
            _PIN_ICON_SIZE,
        )

    def _chevron_path(self) -> QPainterPath:
        """Return the lowered override menu chevron path."""

        center_x = self.width() / 2
        chevron = QPainterPath()
        chevron.moveTo(center_x - (_CHEVRON_WIDTH / 2), _CHEVRON_Y)
        chevron.lineTo(center_x, _CHEVRON_Y + _CHEVRON_HEIGHT)
        chevron.lineTo(center_x + (_CHEVRON_WIDTH / 2), _CHEVRON_Y)
        return chevron


def _render_fluent_icon(
    icon: object,
    painter: QPainter,
    rect: QRectF,
    *,
    color: QColor,
    theme: Theme,
) -> None:
    """Render either an app-owned or QFluent icon into ``rect``."""

    render = getattr(icon, "render", None)
    if callable(render):
        painter.save()
        painter.setOpacity(color.alphaF())
        render(painter, rect, theme=theme, fill=color.name(QColor.NameFormat.HexRgb))
        painter.restore()
        return
    qicon = icon if isinstance(icon, QIcon) else QIcon()
    qicon.paint(painter, rect.toRect(), Qt.AlignmentFlag.AlignCenter)


__all__ = [
    "APP_ORB_ACTION_CLUSTER_OBJECT_NAME",
    "APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME",
    "APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH",
    "APP_ORB_ACTION_SEPARATOR_OBJECT_NAME",
    "APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME",
    "APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME",
    "AppOrbActionCluster",
    "AppOrbCubeStackButton",
    "AppOrbOverrideButton",
]
