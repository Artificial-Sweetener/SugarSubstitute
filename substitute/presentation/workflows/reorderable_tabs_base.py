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

"""Shared workflow/cube tab primitives used by presentation tab views."""
# mypy: disable-error-code=attr-defined

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from copy import deepcopy
from enum import Enum
from typing import Callable, TypeVar, cast

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QLineEdit,
)
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets import MenuAnimationType
from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIcon,
    FluentIconBase,
    drawIcon,
)

try:
    from qfluentwidgets.common.color import themeColor  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        themeColor,
    )
from qfluentwidgets.common.style_sheet import isDarkTheme
from qfluentwidgets.components.widgets.button import (  # type: ignore[import-untyped]
    PushButton,
    TransparentToolButton,
)
from qfluentwidgets.components.widgets.scroll_area import (  # type: ignore[import-untyped]
    SingleDirectionScrollArea,
)

from substitute.presentation.shell.chrome_style import (
    WORKFLOW_TAB_TOP_ACCENT_HEIGHT,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ensure_fluent_tooltip_filter,
    set_fluent_tooltip_text,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

ItemT = TypeVar("ItemT", bound="ReorderableTabItemBase")


class ReorderableCloseButtonDisplayMode(Enum):
    """Declare close-button visibility behavior for reorderable tab items."""

    ALWAYS = 0
    ON_HOVER = 1
    NEVER = 2


def checkIndex(
    *default: object,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Return a decorator that short-circuits index-overflow access."""

    def outer(func: Callable[..., object]) -> Callable[..., object]:
        def inner(
            tabBar: object, index: int, *args: object, **kwargs: object
        ) -> object:
            items = getattr(tabBar, "items", [])
            if 0 <= index < len(items):
                return func(tabBar, index, *args, **kwargs)

            value = deepcopy(default)
            if len(value) == 0:
                return None
            if len(value) == 1:
                return value[0]
            return value

        return inner

    return outer


class ReorderableTabToolButton(TransparentToolButton):  # type: ignore[misc]
    """Draw a small icon-only button used by tab items and add buttons."""

    def _postInit(self) -> None:
        """Initialize control dimensions and icon size."""
        self.setFixedSize(32, 24)
        self.setIconSize(QSize(12, 12))

    @staticmethod
    def _normalize_icon_state(state: object) -> QIcon.State:
        """Return a valid Qt icon-state enum for paint delegation."""
        if isinstance(state, QIcon.State):
            return state

        if isinstance(state, int):
            try:
                return QIcon.State(state)
            except ValueError:
                return QIcon.State.Off

        return QIcon.State.Off

    @staticmethod
    def _resolve_themed_icon(icon: QIcon | str | FluentIconBase) -> QIcon | str:
        """Return theme-aware icon while preserving non-Fluent icon payloads."""
        if isinstance(icon, FluentIconBase):
            color = "#eaeaea" if isDarkTheme() else "#484848"
            return cast(QIcon, icon.icon(color=color))
        return icon

    def _drawIcon(
        self,
        icon: QIcon | str | FluentIconBase,
        painter: QPainter,
        rect: QRectF,
        state: object = QIcon.State.Off,
    ) -> None:
        """Draw icon with normalized state and themed Fluent icon colors."""
        themed_icon = self._resolve_themed_icon(icon)
        icon_state = self._normalize_icon_state(state)
        super()._drawIcon(themed_icon, painter, rect, icon_state)


class ReorderableTabItemBase(PushButton):  # type: ignore[misc]
    """Provide shared drawing and interaction behavior for tab-like items."""

    closed = Signal()
    renamed = Signal(object, str)

    tab_font_size: int = 12
    fixed_width: int | None = None
    fixed_height: int = 36
    default_maximum_width: int = 240
    default_minimum_width: int = 64
    size_hint_width: int | None = None
    selected_fill_radius: float | None = None
    selected_fill_color: tuple[int, int, int, int] | None = None
    selected_accent_position: str = "bottom"
    selected_accent_visible: bool = True
    selected_bottom_corner_radius: float = 0.0
    selected_bottom_corner_width: float = 0.0
    selected_connects_to_bottom_surface: bool = False
    selected_border_reacts_to_hover: bool = True
    selected_bottom_border_mode: str = "top"
    unselected_top_rounded_only: bool = False
    unselected_inset: float = 1.0
    unselected_radius: float | None = None
    unselected_separator_color: tuple[int, int, int, int] | None = None
    inactive_text_alpha: int | None = None
    selected_font_weight: int | None = None
    icon_paint_size: int = 16
    icon_left_padding: int = 10
    text_left_padding: int = 10
    text_left_padding_with_icon: int = 33

    def _postInit(self) -> None:
        """Create rendering state, child controls, and in-place rename editor."""
        super()._postInit()
        self.borderRadius = 5
        self.isSelected = False
        self.isShadowEnabled = True
        self.closeButtonDisplayMode = ReorderableCloseButtonDisplayMode.ALWAYS
        self._forward_parent_mouse_events = True
        self._routeKey: str | None = None
        self.textColor: QColor | None = None
        self._tooltip_filter: FluentToolTipFilter | None = None
        self.lightSelectedBackgroundColor = QColor(249, 249, 249)
        self.darkSelectedBackgroundColor = QColor(40, 40, 40)

        self.closeButton = ReorderableTabToolButton(FluentIcon.CLOSE, self)
        self.shadowEffect = QGraphicsDropShadowEffect(self)
        self.slideAni = QPropertyAnimation(self, b"pos", self)

        self._initWidget()
        self._initRenameEditor()

    def _initWidget(self) -> None:
        """Set dimensions, tooltip behavior, and close-button visuals."""
        setFont(self, self.tab_font_size)
        if self.fixed_width is not None:
            self.setFixedWidth(self.fixed_width)
        self.setFixedHeight(self.fixed_height)
        self.setMaximumWidth(self.default_maximum_width)
        self.setMinimumWidth(self.default_minimum_width)
        self._tooltip_filter = ensure_fluent_tooltip_filter(
            self,
            self,
            show_delay_ms=1000,
            cursor_anchor=True,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

        self.closeButton.setIconSize(QSize(10, 10))
        self.shadowEffect.setBlurRadius(5)
        self.shadowEffect.setOffset(0, 1)
        self.setGraphicsEffect(self.shadowEffect)
        self.setSelected(False)
        self.closeButton.clicked.connect(self._request_removal)

    def _initRenameEditor(self) -> None:
        """Create inline rename editor that overlays the tab text region."""
        self.rename_editor = QLineEdit(self)
        self.rename_editor.setVisible(False)
        self.rename_editor.setFrame(False)
        self.rename_editor.setContentsMargins(0, 0, 0, 0)
        self.rename_editor.setTextMargins(0, 0, 0, 0)
        self.rename_editor.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        setFont(self.rename_editor, self.tab_font_size)
        self._syncRenameEditorTextColor()
        self.rename_editor.returnPressed.connect(self._commitRename)
        self.rename_editor.editingFinished.connect(self._commitRename)

    def _startRename(self) -> None:
        """Enter inline rename mode."""
        self._originalText = self.text()
        self.setText("")
        self.rename_editor.setText(self._originalText)
        self._syncRenameEditorTextColor()
        self._syncRenameEditorGeometry()
        self.rename_editor.setVisible(True)
        self.rename_editor.setFocus()
        self.rename_editor.selectAll()

    def _commitRename(self) -> None:
        """Commit inline rename and emit request when value changed."""
        new_name = self.rename_editor.text().strip()
        self.rename_editor.setVisible(False)
        self.setText(new_name or self._originalText)
        if new_name and new_name != self._originalText:
            self.renamed.emit(self, new_name)

    def _request_removal(self) -> None:
        """Emit the shared removal request for all tab removal entry points."""

        self.closed.emit()

    def setParentMouseEventForwarding(self, enabled: bool) -> None:
        """Set whether this item synthesizes mouse events for its parent."""

        self._forward_parent_mouse_events = enabled

    def _showContextMenu(self, global_pos: QPoint) -> None:
        """Show right-click rename menu."""
        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "workflow_tab.rename",
                        app_text("Rename"),
                        callback=self._startRename,
                        icon=FIF.EDIT,
                    ),
                )
            )
        )
        menu.exec(global_pos, aniType=MenuAnimationType.DROP_DOWN)

    def _slideTo(self, target_pos: QPoint, duration: int = 250) -> None:
        """Animate tab item movement to target position."""
        self.slideAni.setStartValue(self.pos())
        self.slideAni.setEndValue(target_pos)
        self.slideAni.setDuration(duration)
        self.slideAni.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.slideAni.start()

    def slideTo(self, x: int, duration: int = 250) -> None:
        """Animate horizontal movement while keeping current Y."""
        self._slideTo(QPoint(x, self.y()), duration)

    def slideToY(self, y: int, duration: int = 250) -> None:
        """Animate vertical movement while keeping current X."""
        self._slideTo(QPoint(self.x(), y), duration)

    def setShadowEnabled(self, isEnabled: bool) -> None:
        """Enable or disable selection shadow effect."""
        if isEnabled == self.isShadowEnabled:
            return
        self.isShadowEnabled = isEnabled
        self.shadowEffect.setColor(QColor(0, 0, 0, 50 * self._canShowShadow()))

    def _canShowShadow(self) -> bool:
        """Return True when shadow should be visible."""
        return self.isSelected and self.isShadowEnabled

    def setRouteKey(self, key: str) -> None:
        """Store route key used by owning tab container."""
        self._routeKey = key

    def routeKey(self) -> str | None:
        """Return route key used by owning tab container."""
        return self._routeKey

    def setBorderRadius(self, radius: int) -> None:
        """Update paint radius and refresh."""
        self.borderRadius = radius
        self.update()

    def setSelected(self, isSelected: bool) -> None:
        """Set selected state and synchronize visual affordances."""
        self.isSelected = isSelected
        self.shadowEffect.setColor(QColor(0, 0, 0, 50 * self._canShowShadow()))
        self.update()

        if isSelected:
            self.raise_()

        if self.closeButtonDisplayMode == ReorderableCloseButtonDisplayMode.ON_HOVER:
            self.closeButton.setVisible(isSelected)
            self._syncRenameEditorGeometry()

    def setCloseButtonDisplayMode(
        self, mode: ReorderableCloseButtonDisplayMode
    ) -> None:
        """Apply close button visibility mode."""
        if mode == self.closeButtonDisplayMode:
            return

        self.closeButtonDisplayMode = mode
        if mode == ReorderableCloseButtonDisplayMode.NEVER:
            self.closeButton.hide()
        elif mode == ReorderableCloseButtonDisplayMode.ALWAYS:
            self.closeButton.show()
        else:
            self.closeButton.setVisible(self.isHover or self.isSelected)
        self._syncRenameEditorGeometry()

    def setTextColor(self, color: QColor) -> None:
        """Override tab text color."""
        self.textColor = QColor(color)
        self._syncRenameEditorTextColor()
        self.update()

    def setSelectedBackgroundColor(self, light: QColor, dark: QColor) -> None:
        """Configure selected-state background colors."""
        self.lightSelectedBackgroundColor = QColor(light)
        self.darkSelectedBackgroundColor = QColor(dark)
        self.update()

    def _textRect(self) -> QRectF:
        """Return drawing region for text and rename editor."""
        if self.icon().isNull():
            dw = 47 if self.closeButton.isVisible() else 20
            return QRectF(
                self.text_left_padding,
                0,
                self.width() - dw - (self.text_left_padding - 10),
                self.height(),
            )

        dw = 70 if self.closeButton.isVisible() else 45
        return QRectF(
            self.text_left_padding_with_icon,
            0,
            self.width() - dw - (self.text_left_padding_with_icon - 33),
            self.height(),
        )

    def resizeEvent(self, event: object) -> None:
        """Position close button and inline rename editor."""
        self.closeButton.move(
            self.width() - 6 - self.closeButton.width(),
            int(self.height() / 2 - self.closeButton.height() / 2),
        )
        self._syncRenameEditorGeometry()
        super().resizeEvent(event)

    def _syncRenameEditorGeometry(self) -> None:
        """Align inline rename editing with the painted tab text bounds."""

        self.rename_editor.setGeometry(self._textRect().toRect())

    def enterEvent(self, event: object) -> None:
        """Show close button on hover when configured."""
        super().enterEvent(event)
        if self.closeButtonDisplayMode == ReorderableCloseButtonDisplayMode.ON_HOVER:
            self.closeButton.show()
            self._syncRenameEditorGeometry()

    def leaveEvent(self, event: object) -> None:
        """Hide close button after hover when item is not selected."""
        super().leaveEvent(event)
        if (
            self.closeButtonDisplayMode == ReorderableCloseButtonDisplayMode.ON_HOVER
            and not self.isSelected
        ):
            self.closeButton.hide()
            self._syncRenameEditorGeometry()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle context menu and forward mouse events to parent container."""
        if event.button() == Qt.MouseButton.RightButton:
            if self.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
                super().mousePressEvent(event)
                return
            self._showContextMenu(event.globalPos())
            return
        super().mousePressEvent(event)
        if self._forward_parent_mouse_events:
            self._forwardMouseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Start inline rename on left-button double click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._startRename()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Forward move events for parent drag handling."""
        super().mouseMoveEvent(event)
        if self._forward_parent_mouse_events:
            self._forwardMouseEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Forward release events for parent drag handling."""
        super().mouseReleaseEvent(event)
        if self._forward_parent_mouse_events:
            self._forwardMouseEvent(event)

    def _forwardMouseEvent(self, event: QMouseEvent) -> None:
        """Forward mapped child mouse event to parent tab container."""
        pos = self.mapToParent(event.pos())
        parent_event = QMouseEvent(
            event.type(),
            pos,
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QApplication.sendEvent(self.parent(), parent_event)

    def sizeHint(self) -> QSize:
        """Return preferred item dimensions."""
        hint_width = self.size_hint_width or self.maximumWidth()
        return QSize(hint_width, self.fixed_height)

    def paintEvent(self, event: object) -> None:
        """Paint selected/hovered state, icon, and text label."""
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        if self.isSelected:
            self._drawSelectedBackground(painter)
        else:
            self._drawNotSelectedBackground(painter)

        icon_size = self.icon_paint_size
        icon_x = self.icon_left_padding
        icon_y = int((self.height() - icon_size) / 2)
        if not self.isSelected:
            painter.setOpacity(0.79 if isDarkTheme() else 0.61)
        drawIcon(self._icon, painter, QRectF(icon_x, icon_y, icon_size, icon_size))
        painter.setOpacity(1.0)
        self._drawText(painter)

    def _drawSelectedBackground(self, painter: QPainter) -> None:
        """Draw selected frame and highlighted background."""
        width, height = self.width(), self.height()
        radius = self.borderRadius
        diameter = 2 * radius
        is_dark = isDarkTheme()

        if self.selected_connects_to_bottom_surface:
            self._drawConnectedSelectedBackground(painter, is_dark)
            return

        top_border_path = QPainterPath()
        top_border_path.arcMoveTo(1, height - diameter - 1, diameter, diameter, 225)
        top_border_path.arcTo(1, height - diameter - 1, diameter, diameter, 225, -45)
        top_border_path.lineTo(1, radius)
        top_border_path.arcTo(1, 1, diameter, diameter, -180, -90)
        top_border_path.lineTo(width - radius, 1)
        top_border_path.arcTo(width - diameter - 1, 1, diameter, diameter, 90, -90)
        top_border_path.lineTo(width - 1, height - radius)
        top_border_path.arcTo(
            width - diameter - 1,
            height - diameter - 1,
            diameter,
            diameter,
            0,
            -45,
        )

        top_border_color = QColor(0, 0, 0, 20)
        if is_dark:
            if self.isPressed:
                top_border_color = QColor(255, 255, 255, 18)
            elif self.isHover:
                top_border_color = QColor(255, 255, 255, 13)
        else:
            top_border_color = QColor(0, 0, 0, 16)
        painter.strokePath(top_border_path, top_border_color)

        bottom_border_path = QPainterPath()
        bottom_border_path.arcMoveTo(1, height - diameter - 1, diameter, diameter, 225)
        bottom_border_path.arcTo(1, height - diameter - 1, diameter, diameter, 225, 45)
        bottom_border_path.lineTo(width - radius - 1, height - 1)
        bottom_border_path.arcTo(
            width - diameter - 1,
            height - diameter - 1,
            diameter,
            diameter,
            270,
            45,
        )
        painter.strokePath(
            bottom_border_path,
            self._resolveBottomBorderColor(top_border_color, is_dark),
        )

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(self._resolveSelectedFillColor())
        painter.setPen(QColor(255, 255, 255, 25))
        selected_radius = (
            self.selected_fill_radius
            if self.selected_fill_radius is not None
            else float(self.borderRadius)
        )
        painter.drawRoundedRect(rect, selected_radius, selected_radius)

        self._drawSelectedAccent(painter)

    def _drawConnectedSelectedBackground(
        self,
        painter: QPainter,
        is_dark: bool,
    ) -> None:
        """Draw a selected tab that visually joins the surface below it."""
        rect = QRectF(self.rect().adjusted(1, 1, -1, 0))
        rect.setBottom(rect.bottom() + 1.0)
        radius = (
            self.selected_fill_radius
            if self.selected_fill_radius is not None
            else float(self.borderRadius)
        )
        fill_path = self._topRoundedPath(rect, radius)
        border_path = self._topRoundedBorderPath(rect, radius)
        border_color = self._resolveSelectedBorderColor(is_dark)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._resolveSelectedFillColor())
        painter.drawPath(fill_path)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(border_color)
        painter.drawPath(border_path)

        self._drawSelectedAccent(painter, fill_path, rect)

    @staticmethod
    def _topRoundedPath(rect: QRectF, radius: float) -> QPainterPath:
        """Return a path with rounded top corners and a square bottom edge."""
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        return path

    @staticmethod
    def _topRoundedBorderPath(rect: QRectF, radius: float) -> QPainterPath:
        """Return the top and side outline for a square-bottom connected tab."""
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom())
        return path

    def _resolveSelectedBorderColor(self, is_dark: bool) -> QColor:
        """Resolve the subtle selected-tab outline color."""
        if is_dark and self.selected_border_reacts_to_hover:
            if self.isPressed:
                return QColor(255, 255, 255, 18)
            if self.isHover:
                return QColor(255, 255, 255, 13)
        return QColor(0, 0, 0, 20)

    def _resolveSelectedFillColor(self) -> QColor:
        """Resolve the selected-tab fill color."""
        if self.selected_fill_color is not None:
            return QColor(*self.selected_fill_color)
        return QColor(255, 255, 255, 20)

    def _drawSelectedAccent(
        self,
        painter: QPainter,
        clip_path: QPainterPath | None = None,
        body_rect: QRectF | None = None,
    ) -> None:
        """Draw the configured accent decoration for a selected tab."""
        if not self.selected_accent_visible or self.selected_accent_position != "top":
            return

        rect = body_rect if body_rect is not None else QRectF(self.rect())
        if rect.width() <= 0:
            return

        accent_rect = QRectF(
            rect.left(),
            rect.top(),
            rect.width(),
            WORKFLOW_TAB_TOP_ACCENT_HEIGHT,
        )
        if clip_path is not None:
            painter.save()
            painter.setClipPath(clip_path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(themeColor()))
        painter.drawRect(accent_rect)
        if clip_path is not None:
            painter.restore()

    def _resolveBottomBorderColor(
        self, top_border_color: QColor, is_dark: bool
    ) -> QColor:
        """Resolve bottom-border color strategy for selected tabs."""
        if (
            self.selected_bottom_border_mode == "theme"
            and self.selected_accent_position == "bottom"
        ):
            return QColor(themeColor())
        if self.selected_bottom_border_mode == "cube" and not is_dark:
            return QColor(0, 0, 0, 63)
        return QColor(top_border_color)

    def _drawNotSelectedBackground(self, painter: QPainter) -> None:
        """Draw hover/pressed affordance for non-selected tabs."""
        if not (self.isPressed or self.isHover):
            self._drawUnselectedSeparator(painter)
            return

        is_dark = isDarkTheme()
        if self.isPressed:
            color = QColor(255, 255, 255, 12) if is_dark else QColor(0, 0, 0, 7)
        else:
            color = QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 10)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.unselected_top_rounded_only:
            inset = self.unselected_inset
            radius = (
                self.unselected_radius
                if self.unselected_radius is not None
                else float(self.borderRadius)
            )
            rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
            painter.drawPath(self._topRoundedPath(rect, radius))
            return

        painter.drawRoundedRect(
            self.rect().adjusted(1, 1, -1, -1),
            self.borderRadius,
            self.borderRadius,
        )

    def _drawUnselectedSeparator(self, painter: QPainter) -> None:
        """Draw a Firefox-style separator for quiet inactive tabs."""
        if self.unselected_separator_color is None:
            return

        color = QColor(*self.unselected_separator_color)
        if not color.isValid() or color.alpha() <= 0:
            return

        center_y = self.height() / 2
        half_height = min(10.0, max(0.0, (self.height() - 8) / 2))
        separator_x = self.width() - 1
        painter.setPen(color)
        painter.drawLine(
            int(separator_x),
            int(center_y - half_height),
            int(separator_x),
            int(center_y + half_height),
        )

    def _drawText(self, painter: QPainter) -> None:
        """Draw tab text with right-edge gradient clipping when needed."""
        if not self.text():
            return
        text_width = self.fontMetrics().boundingRect(self.text()).width()
        if text_width <= 0:
            return
        rect = self._textRect()
        pen = QPen()
        color = self._resolvedTextColor()
        if not self.isSelected and self.inactive_text_alpha is not None:
            color = QColor(color)
            color.setAlpha(self.inactive_text_alpha)
        rect_width = rect.width()

        if text_width > rect_width:
            gradient = QLinearGradient(rect.x(), 0, text_width + rect.x(), 0)
            gradient.setColorAt(0, color)
            gradient.setColorAt(max(0, (rect_width - 10) / text_width), color)
            gradient.setColorAt(
                max(0, rect_width / text_width), Qt.GlobalColor.transparent
            )
            gradient.setColorAt(1, Qt.GlobalColor.transparent)
            pen.setBrush(QBrush(gradient))
        else:
            pen.setColor(color)

        painter.setPen(pen)
        font = self.font()
        if self.isSelected and self.selected_font_weight is not None:
            font.setWeight(QFont.Weight(self.selected_font_weight))
        painter.setFont(font)
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )

    def _resolvedTextColor(self) -> QColor:
        """Return the primary tab text color for the current theme."""

        if self.textColor is not None:
            return QColor(self.textColor)
        return QColor(Qt.GlobalColor.white if isDarkTheme() else Qt.GlobalColor.black)

    def _syncRenameEditorTextColor(self) -> None:
        """Apply the painted tab text color to the inline rename editor."""

        color = self._resolvedTextColor()
        palette = self.rename_editor.palette()
        palette.setColor(QPalette.ColorRole.Text, color)
        self.rename_editor.setPalette(palette)
        self.rename_editor.setStyleSheet(
            "QLineEdit { "
            "background: transparent; "
            "border: none; "
            "margin: 0px; "
            "padding: 0px; "
            f"color: {self._css_color(color)}; "
            "}"
        )

    @staticmethod
    def _css_color(color: QColor) -> str:
        """Return a Qt stylesheet color literal preserving alpha."""

        return (
            f"rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{color.alpha() / 255:.3f})"
        )


class ReorderableTabBarBase(SingleDirectionScrollArea):  # type: ignore[misc]
    """Provide shared tab-container state management for workflow/cube views."""

    def _initCommonState(self) -> None:
        """Initialize common tab-container state fields."""
        configure_qfluent_scroll_surface(self)
        self.items: list[ReorderableTabItemBase] = []
        self.itemMap: dict[str, ReorderableTabItemBase] = {}
        self._currentIndex = -1
        self._isMovable = False
        self._isScrollable = False
        self._isTabShadowEnabled = True
        self._tabMaxWidth = 240
        self._tabMinWidth = 64
        self.dragPos = QPoint()
        self.isDraging = False
        self.lightSelectedBackgroundColor = QColor(249, 249, 249)
        self.darkSelectedBackgroundColor = QColor(40, 40, 40)
        self.closeButtonDisplayMode = ReorderableCloseButtonDisplayMode.ALWAYS

    def setAddButtonVisible(self, isVisible: bool) -> None:
        """Set add-button visibility."""
        self.addButton.setVisible(isVisible)

    def _createTabItem(
        self,
        text: str,
        icon: QIcon | str | FluentIconBase | None,
    ) -> ReorderableTabItemBase:
        """Create tab item instance for specialized wrappers."""
        raise NotImplementedError

    def _onTabRenamed(
        self,
        tab_item: ReorderableTabItemBase,
        new_name: str,
    ) -> None:
        """Handle inline rename request from tab item."""
        raise NotImplementedError

    def _emitBarClicked(self, index: int) -> None:
        """Emit wrapper-specific clicked signal."""
        raise NotImplementedError

    def _emitCloseRequested(self, index: int) -> None:
        """Emit wrapper-specific close-request signal."""
        raise NotImplementedError

    def _emitCurrentChanged(self, index: int) -> None:
        """Emit wrapper-specific current-changed signal."""
        raise NotImplementedError

    def _onTabRemoved(self, route_key: str) -> None:
        """Run specialization-specific tab-removal side effects."""

    def addTab(
        self,
        routeKey: str,
        text: str,
        icon: QIcon | str | FluentIconBase | None = None,
        onClick: Callable[..., object] | None = None,
    ) -> ReorderableTabItemBase:
        """Add a new tab at the end of the item sequence."""
        return self.insertTab(-1, routeKey, text, icon, onClick)

    def insertTab(
        self,
        index: int,
        routeKey: str,
        text: str,
        icon: QIcon | str | FluentIconBase | None = None,
        onClick: Callable[..., object] | None = None,
    ) -> ReorderableTabItemBase:
        """Insert tab item at index and keep current-index bookkeeping stable."""
        if routeKey in self.itemMap:
            raise ValueError(f"The route key `{routeKey}` is duplicated.")

        if index == -1:
            index = len(self.items)

        if index <= self.currentIndex() and self.currentIndex() >= 0:
            self._currentIndex += 1

        item = self._createTabItem(text, icon)
        item.setRouteKey(routeKey)

        width = (
            self.tabMaximumWidth() if self.isScrollable() else self.tabMinimumWidth()
        )
        item.setMinimumWidth(width)
        item.setMaximumWidth(self.tabMaximumWidth())
        item.setShadowEnabled(self.isTabShadowEnabled())
        item.setCloseButtonDisplayMode(self.closeButtonDisplayMode)
        item.setSelectedBackgroundColor(
            self.lightSelectedBackgroundColor,
            self.darkSelectedBackgroundColor,
        )

        item.pressed.connect(self._onItemPressed)
        item.renamed.connect(self._onTabRenamed)
        if onClick:
            item.pressed.connect(onClick)
        item.closed.connect(lambda: self._emitCloseRequested(self.items.index(item)))

        self.itemLayout.insertWidget(index, item, 1)
        self.items.insert(index, item)
        self.itemMap[routeKey] = item

        if len(self.items) == 1:
            self.setCurrentIndex(0)

        return item

    def removeTab(self, index: int) -> None:
        """Remove tab by index and preserve legacy current-index transitions."""
        if not 0 <= index < len(self.items):
            return

        if index < self.currentIndex():
            self._currentIndex -= 1
        elif index == self.currentIndex():
            if self.currentIndex() > 0:
                self.setCurrentIndex(self.currentIndex() - 1)
                self._emitCurrentChanged(self.currentIndex())
            elif len(self.items) == 1:
                self._currentIndex = -1
            else:
                self.setCurrentIndex(1)
                self._currentIndex = 0
                self._emitCurrentChanged(0)

        item = self.items.pop(index)
        route_key = item.routeKey()
        if route_key is not None:
            self.itemMap.pop(route_key, None)
            self._onTabRemoved(route_key)
        self.hBoxLayout.removeWidget(item)
        item.deleteLater()
        self.update()

    def removeTabByKey(self, routeKey: str) -> None:
        """Remove tab by route key."""
        if routeKey not in self.itemMap:
            return
        tab_item = self.tab(routeKey)
        if tab_item is None:
            return
        self.removeTab(self.items.index(tab_item))

    def setCurrentIndex(self, index: int) -> None:
        """Set currently selected index for horizontal tab wrappers."""
        if index == self._currentIndex:
            return

        if self.currentIndex() >= 0:
            self.items[self.currentIndex()].setSelected(False)

        self._currentIndex = index
        self.items[index].setSelected(True)

    def clear_selection(self) -> None:
        """Clear the current selection without emitting tab activation intent."""

        if self.currentIndex() >= 0:
            self.items[self.currentIndex()].setSelected(False)
        self._currentIndex = -1
        self.update()

    def setCurrentTab(self, routeKey: str) -> None:
        """Select tab matching route key."""
        if routeKey not in self.itemMap:
            return
        tab_item = self.tab(routeKey)
        if tab_item is None:
            return
        self.setCurrentIndex(self.items.index(tab_item))

    def currentIndex(self) -> int:
        """Return current tab index."""
        return self._currentIndex

    def currentTab(self) -> ReorderableTabItemBase | None:
        """Return currently selected tab item."""
        return cast(ReorderableTabItemBase | None, self.tabItem(self.currentIndex()))

    def _onItemPressed(self) -> None:
        """Handle item pressed state transition and change notifications."""
        sender = self.sender()
        for item in self.items:
            item.setSelected(item is sender)

        index = self.items.index(sender)
        self._emitBarClicked(index)
        if index != self.currentIndex():
            self.setCurrentIndex(index)
            self._emitCurrentChanged(index)

    def setCloseButtonDisplayMode(
        self, mode: ReorderableCloseButtonDisplayMode
    ) -> None:
        """Set close-button display mode for all items."""
        if mode == self.closeButtonDisplayMode:
            return

        self.closeButtonDisplayMode = mode
        for item in self.items:
            item.setCloseButtonDisplayMode(mode)

    @checkIndex()
    def tabItem(self, index: int) -> ReorderableTabItemBase | None:
        """Return tab item by index."""
        return self.items[index]

    def tab(self, routeKey: str) -> ReorderableTabItemBase | None:
        """Return tab item by route key."""
        return self.itemMap.get(routeKey, None)

    def tabRegion(self) -> QRect:
        """Return bounding rectangle of all tabs."""
        return cast(QRect, self.itemLayout.geometry())

    @checkIndex()
    def tabRect(self, index: int) -> QRect | None:
        """Return visual rectangle for tab at index."""
        item = self.tabItem(index)
        if item is None:
            return None

        margins = self.itemLayout.contentsMargins()
        spacing = max(0, self.itemLayout.spacing())
        rect = item.geometry()
        if self.orient == Qt.Orientation.Vertical:
            y = margins.top()
            for i in range(index):
                current = self.tabItem(i)
                if current is not None:
                    y += current.height() + spacing
            rect.moveTop(y)
        else:
            x = margins.left()
            for i in range(index):
                current = self.tabItem(i)
                if current is not None:
                    x += current.width() + spacing
            rect.moveLeft(x)
        return cast(QRect, rect)

    @checkIndex("")
    def tabText(self, index: int) -> str:
        """Return tab text at index."""
        item = self.tabItem(index)
        return item.text() if item is not None else ""

    @checkIndex()
    def tabIcon(self, index: int) -> QIcon | None:
        """Return tab icon at index."""
        item = self.tabItem(index)
        return item.icon() if item is not None else None

    @checkIndex("")
    def tabToolTip(self, index: int) -> str:
        """Return tab tooltip text at index."""
        item = self.tabItem(index)
        return item.toolTip() if item is not None else ""

    def setTabsClosable(self, isClosable: bool) -> None:
        """Toggle close buttons for all tabs."""
        if isClosable:
            self.setCloseButtonDisplayMode(ReorderableCloseButtonDisplayMode.ALWAYS)
            return
        self.setCloseButtonDisplayMode(ReorderableCloseButtonDisplayMode.NEVER)

    def tabsClosable(self) -> bool:
        """Return True when tab close buttons are enabled."""
        return self.closeButtonDisplayMode != ReorderableCloseButtonDisplayMode.NEVER

    @checkIndex()
    def setTabIcon(self, index: int, icon: QIcon | FluentIconBase | str) -> None:
        """Set tab icon by index."""
        item = self.tabItem(index)
        if item is not None:
            item.setIcon(icon)

    @checkIndex()
    def setTabText(self, index: int, text: str) -> None:
        """Set tab text by index."""
        item = self.tabItem(index)
        if item is not None:
            item.setText(text)

    @checkIndex()
    def setTabVisible(self, index: int, isVisible: bool) -> None:
        """Set tab visibility while preserving legacy current-index transitions."""
        item = self.tabItem(index)
        if item is None:
            return
        item.setVisible(isVisible)

        if isVisible and self.currentIndex() < 0:
            self.setCurrentIndex(0)
        elif not isVisible:
            if self.currentIndex() > 0:
                self.setCurrentIndex(self.currentIndex() - 1)
                self._emitCurrentChanged(self.currentIndex())
            elif len(self.items) == 1:
                self._currentIndex = -1
            else:
                self.setCurrentIndex(1)
                self._currentIndex = 0
                self._emitCurrentChanged(0)

    @checkIndex()
    def setTabTextColor(self, index: int, color: QColor) -> None:
        """Set tab text color."""
        item = self.tabItem(index)
        if item is not None:
            item.setTextColor(color)

    @checkIndex()
    def setTabToolTip(self, index: int, toolTip: str) -> None:
        """Set tab tooltip text."""
        item = self.tabItem(index)
        if item is not None:
            set_fluent_tooltip_text(item, toolTip)

    def setTabSelectedBackgroundColor(self, light: QColor, dark: QColor) -> None:
        """Set selected background colors for all tabs."""
        self.lightSelectedBackgroundColor = QColor(light)
        self.darkSelectedBackgroundColor = QColor(dark)
        for item in self.items:
            item.setSelectedBackgroundColor(light, dark)

    def setTabShadowEnabled(self, isEnabled: bool) -> None:
        """Enable or disable tab shadow for all items."""
        if isEnabled == self.isTabShadowEnabled():
            return
        self._isTabShadowEnabled = isEnabled
        for item in self.items:
            item.setShadowEnabled(isEnabled)

    def isTabShadowEnabled(self) -> bool:
        """Return tab-shadow enabled state."""
        return self._isTabShadowEnabled

    def setMovable(self, movable: bool) -> None:
        """Enable or disable tab drag-reorder behavior."""
        self._isMovable = movable

    def isMovable(self) -> bool:
        """Return True when drag-reorder is enabled."""
        return self._isMovable

    def setScrollable(self, scrollable: bool) -> None:
        """Set scrollable sizing mode."""
        self._isScrollable = scrollable
        width = self._tabMaxWidth if scrollable else self._tabMinWidth
        for item in self.items:
            item.setMinimumWidth(width)

    def setTabMaximumWidth(self, width: int) -> None:
        """Set maximum tab width."""
        if width == self._tabMaxWidth:
            return
        self._tabMaxWidth = width
        for item in self.items:
            item.setMaximumWidth(width)

    def setTabMinimumWidth(self, width: int) -> None:
        """Set minimum tab width for non-scrollable mode."""
        if width == self._tabMinWidth:
            return
        self._tabMinWidth = width
        if not self.isScrollable():
            for item in self.items:
                item.setMinimumWidth(width)

    def tabMaximumWidth(self) -> int:
        """Return configured maximum tab width."""
        return self._tabMaxWidth

    def tabMinimumWidth(self) -> int:
        """Return configured minimum tab width."""
        return self._tabMinWidth

    def isScrollable(self) -> bool:
        """Return True when scrollable mode is active."""
        return self._isScrollable

    def count(self) -> int:
        """Return number of tabs."""
        return len(self.items)

    movable = Property(bool, isMovable, setMovable)
    scrollable = Property(bool, isScrollable, setScrollable)
    tabMaxWidth = Property(int, tabMaximumWidth, setTabMaximumWidth)
    tabMinWidth = Property(int, tabMinimumWidth, setTabMinimumWidth)
    tabShadowEnabled = Property(bool, isTabShadowEnabled, setTabShadowEnabled)


__all__ = [
    "ReorderableCloseButtonDisplayMode",
    "ReorderableTabBarBase",
    "ReorderableTabItemBase",
    "ReorderableTabToolButton",
    "checkIndex",
]
