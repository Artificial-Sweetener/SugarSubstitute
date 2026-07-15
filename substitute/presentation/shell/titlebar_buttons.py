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

"""Provide shell-specific titlebar buttons that match native frameless chrome."""

from __future__ import annotations

from typing import Literal, cast

from PySide6.QtCore import (
    Property,
    QAbstractAnimation,
    QEvent,
    QEasingCurve,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIntValidator,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QSizePolicy, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        FluentStyleSheet,
        isDarkTheme,
        themeColor,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return False

    def themeColor() -> QColor:
        """Return a stable accent color for lightweight test stubs."""

        return QColor("#009faa")

    class _FallbackFluentWindowStyle:
        """Provide a no-op Fluent window stylesheet for lightweight stubs."""

        def apply(self, _widget: object) -> None:
            """Ignore stylesheet application when qfluentwidgets is stubbed."""

    class _FallbackFluentStyleSheet:
        """Provide the qfluent stylesheet enum shape used at runtime."""

        FLUENT_WINDOW = _FallbackFluentWindowStyle()

    FluentStyleSheet = _FallbackFluentStyleSheet()


from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButton,
    TitleBarButtonState,
)

from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.semantic_colors import (
    legible_text_color_for_background,
    semantic_error_color,
    semantic_warning_color,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationPlayPresentationMode,
    GenerationSelectedMode,
)
from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    connect_theme_refresh,
    resolved_backdrop_mode,
    winui_accent_button_disabled_fill_color,
    winui_accent_button_disabled_foreground_color,
    workflow_chrome_wash_color,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
    is_reduced_motion_enabled,
    restart_property_animation,
)
from substitute.presentation.widgets.cursor_tooltip_filter import (
    CursorToolTipFilter,
    install_cursor_tooltip_filter,
)

GenerationSegmentRole = Literal["play", "skip", "queue", "stop"]
GenerationSegmentEdge = Literal["first", "middle", "last"]
GenerationBatchChevronRole = Literal["up", "down"]
_SEGMENT_WIDTH = 40
_CLUSTER_HEIGHT = 32
_SEGMENT_ICON_SIZE = 16.0
_CONTINUOUS_SEGMENT_ICON_SIZE = 24.0
_SKIP_SEGMENT_ICON_SIZE = 20.0
_BATCH_ACCESSORY_WIDTH = 72
_BATCH_CHEVRON_WIDTH = 14
_BATCH_CHEVRON_TRAILING_GAP = 14
_BATCH_CLUSTER_OVERLAP = 6
_BATCH_MAX_COUNT = 999
_BATCH_CHEVRON_STROKE = 1.15
_BATCH_CHEVRON_HALF_WIDTH = 3.0
_BATCH_CHEVRON_HALF_HEIGHT = 2.0
_STARTUP_DIAGNOSTICS_WIDTH = 46
_TITLEBAR_BUTTON_HEIGHT = 32
_BOTTOM_CORNER_RADIUS = 6.0
_TOP_BLEED = 2.0
_BOTTOM_INSET = 2.0
_DIVIDER_COLOR = QColor(0, 0, 0, 82)
_QUEUE_BADGE_LIGHT_FILL = QColor("#ffffff")
_QUEUE_BADGE_DARK_FILL = QColor("#000000")
_ALERT_ICON_RADIUS = 7.0
_QUEUE_BADGE_HEIGHT = 12.0
_COLLAPSE_DURATION_MS = 160
_CONTINUOUS_GENERATION_ICON = AppIcon.INFINITY_HIGH_CONTRAST
_GENERATION_REVEAL_BUTTON_WIDTH = 46
_GENERATION_REVEAL_CHEVRON_HALF_WIDTH = 2.75
_GENERATION_REVEAL_CHEVRON_HALF_HEIGHT = 4.25
_GENERATION_REVEAL_CHEVRON_STROKE = 1.15


class ComfyOutputToggleButton(TitleBarButton):  # type: ignore[misc]
    """Render a checkable titlebar button for the shell Comfy output panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the checkable titlebar button and tooltip state."""

        super().__init__(parent)
        self._icon = AppIcon.WINDOW_CONSOLE_20_FILLED
        self.setCheckable(True)
        self._apply_theme_palette()
        connect_theme_refresh(self, self._apply_theme_palette)
        self.toggled.connect(self._update_tooltip)
        self._update_tooltip(False)

    def paintEvent(self, _event: object) -> None:
        """Paint the chrome-like background and centered qfluent icon."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color())
        painter.drawRect(self.rect())

        icon_rect = QRectF(
            (self.width() - 16) / 2,
            (self.height() - 16) / 2,
            16,
            16,
        )
        self._icon.render(
            painter,
            icon_rect,
            fill=self._icon_color().name(),
        )

    def _background_color(self) -> QColor:
        """Return the correct background color for state and checked value."""

        state = self._effective_state()
        if state in (TitleBarButtonState.HOVER, TitleBarButtonState.PRESSED):
            return QColor(self._background_color_for_state(state))
        if self.isChecked():
            return self._checked_background

        return QColor(self._background_color_for_state(state))

    def _icon_color(self) -> QColor:
        """Return the correct icon color for the current button state."""

        return QColor(self._icon_color_for_state(self._effective_state()))

    def _effective_state(self) -> TitleBarButtonState:
        """Return the qframeless state, including live hover fallback."""

        if self._state == TitleBarButtonState.NORMAL and self.underMouse():
            return TitleBarButtonState.HOVER
        return self._state

    def _background_color_for_state(self, state: TitleBarButtonState) -> QColor:
        """Return the qframeless background color for one titlebar state."""

        if state == TitleBarButtonState.HOVER:
            return QColor(self.getHoverBackgroundColor())
        if state == TitleBarButtonState.PRESSED:
            return QColor(self.getPressedBackgroundColor())
        return QColor(self.getNormalBackgroundColor())

    def _icon_color_for_state(self, state: TitleBarButtonState) -> QColor:
        """Return the qframeless icon color for one titlebar state."""

        if state == TitleBarButtonState.HOVER:
            return QColor(self.getHoverColor())
        if state == TitleBarButtonState.PRESSED:
            return QColor(self.getPressedColor())
        return QColor(self.getNormalColor())

    def _update_tooltip(self, checked: bool) -> None:
        """Set tooltip text that matches the current toggle state."""

        self.setToolTip("Hide Comfy output" if checked else "Show Comfy output")

    def _apply_theme_palette(self) -> None:
        """Reapply icon and checked-background colors after theme changes."""

        FluentStyleSheet.FLUENT_WINDOW.apply(self)
        icon_color = QColor("#ffffff") if isDarkTheme() else QColor("#000000")
        self._checked_background = (
            QColor(255, 255, 255, 28) if isDarkTheme() else QColor(0, 0, 0, 18)
        )
        self.setNormalColor(icon_color)
        self.setHoverColor(icon_color)
        self.setPressedColor(icon_color)


class StartupDiagnosticsTitleBarButton(TitleBarButton):  # type: ignore[misc]
    """Render a startup diagnostics indicator in the shell titlebar."""

    activated = Signal()
    expanded = Signal()

    visible_width = _STARTUP_DIAGNOSTICS_WIDTH

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the diagnostics indicator with hidden empty state."""

        super().__init__(parent)
        self._count = 0
        self._has_errors = True
        self._collapsed = False
        self._collapse_animation = QPropertyAnimation(self, b"maximumWidth", self)
        self._collapse_animation.setDuration(_COLLAPSE_DURATION_MS)
        self._collapse_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._collapse_animation.finished.connect(self._finish_collapse_animation)
        self.setFixedHeight(_TITLEBAR_BUTTON_HEIGHT)
        self.setToolTip("View ComfyUI startup diagnostics")
        self.setAccessibleName("ComfyUI startup diagnostics")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tooltip_filter: CursorToolTipFilter = install_cursor_tooltip_filter(
            self,
            self,
            show_delay_ms=600,
            show_when_disabled=True,
        )
        self.clicked.connect(self.activated.emit)
        self._apply_theme_palette()
        connect_theme_refresh(self, self._apply_theme_palette)
        self.set_collapsed(True, animated=False)

    def set_count(self, count: int, *, has_errors: bool) -> None:
        """Update badge count and severity treatment."""

        self._count = max(0, count)
        self._has_errors = has_errors
        self.update()

    def set_collapsed(self, collapsed: bool, *, animated: bool = True) -> None:
        """Animate the titlebar button between visible and collapsed widths."""

        if self._collapsed == collapsed and self.isHidden() == collapsed:
            return
        self._collapsed = collapsed
        self.setEnabled(not collapsed)
        if not animated:
            self._collapse_animation.stop()
            self.setMinimumWidth(0 if collapsed else self.visible_width)
            self.setMaximumWidth(0 if collapsed else self.visible_width)
            self.setVisible(not collapsed)
            self._settle_parent_layout()
            if not collapsed:
                self.expanded.emit()
            return

        self._collapse_animation.stop()
        if collapsed:
            self.setMinimumWidth(0)
            self._collapse_animation.setStartValue(max(0, self.width()))
            self._collapse_animation.setEndValue(0)
        else:
            self.setVisible(True)
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
            self._collapse_animation.setStartValue(0)
            self._collapse_animation.setEndValue(self.visible_width)
        self._collapse_animation.start()

    def is_collapsed(self) -> bool:
        """Return whether the indicator is in the collapsed titlebar state."""

        return self._collapsed

    def count(self) -> int:
        """Return the current diagnostics count."""

        return self._count

    def has_errors(self) -> bool:
        """Return whether the current diagnostics use error treatment."""

        return self._has_errors

    def badge_color(self) -> QColor:
        """Return the current count badge fill color."""

        if self._has_errors:
            return semantic_error_color()
        return semantic_warning_color()

    def paintEvent(self, _event: object) -> None:
        """Paint the titlebar diagnostics icon, hover background, and count badge."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        icon_color, background_color = self._getColors()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_color)
        painter.drawRect(self.rect())
        self._paint_alert_icon(painter, icon_color)
        self._paint_count_badge(painter)

    def _finish_collapse_animation(self) -> None:
        """Settle width and visibility after a collapse or expand animation."""

        if self._collapsed:
            self.hide()
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
            return
        self.setMinimumWidth(self.visible_width)
        self.setMaximumWidth(self.visible_width)
        self._settle_parent_layout()
        self.expanded.emit()

    def _settle_parent_layout(self) -> None:
        """Force the titlebar layout to consume current width constraints."""

        parent = self.parentWidget()
        if parent is None or parent.layout() is None:
            return
        layout = parent.layout()
        layout.invalidate()
        layout.activate()

    def _paint_alert_icon(self, painter: QPainter, icon_color: QColor) -> None:
        """Paint a circled exclamation mark."""

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        radius = _ALERT_ICON_RADIUS
        pen = QPen(icon_color, 1.6)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        )
        painter.setPen(icon_color)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(
            QRectF(center_x - radius, center_y - radius - 1, radius * 2, radius * 2),
            Qt.AlignmentFlag.AlignCenter,
            "!",
        )

    def _paint_count_badge(self, painter: QPainter) -> None:
        """Paint the severity-colored diagnostics count badge over the icon."""

        text = str(min(self._count, 99))
        badge_width = 12.0 if self._count < 10 else 16.0
        badge_height = 12.0
        icon_center_x = self.width() / 2.0
        icon_center_y = self.height() / 2.0
        badge_rect = QRectF(
            icon_center_x + _ALERT_ICON_RADIUS - (badge_width / 2.0),
            icon_center_y + _ALERT_ICON_RADIUS - (badge_height / 2.0),
            badge_width,
            badge_height,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        badge_color = self.badge_color()
        painter.setBrush(badge_color)
        painter.drawRoundedRect(badge_rect, badge_height / 2.0, badge_height / 2.0)
        painter.setPen(legible_text_color_for_background(badge_color))
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _apply_theme_palette(self) -> None:
        """Reapply titlebar icon and background colors after theme changes."""

        icon_color = QColor("#ffffff") if isDarkTheme() else QColor("#000000")
        hover_bg = QColor(255, 255, 255, 28) if isDarkTheme() else QColor(0, 0, 0, 18)
        pressed_bg = QColor(255, 255, 255, 42) if isDarkTheme() else QColor(0, 0, 0, 30)
        self.setNormalColor(icon_color)
        self.setHoverColor(icon_color)
        self.setPressedColor(icon_color)
        self.setNormalBackgroundColor(QColor(0, 0, 0, 0))
        self.setHoverBackgroundColor(hover_bg)
        self.setPressedBackgroundColor(pressed_bg)


class GenerationTitleBarSegmentButton(TitleBarButton):  # type: ignore[misc]
    """Render one hit-tested segment inside the generation titlebar cluster."""

    rightClicked = Signal()

    def __init__(
        self,
        role: GenerationSegmentRole,
        icon: object,
        tooltip: str,
        parent: QWidget | None = None,
    ) -> None:
        """Create one icon-only segment with titlebar button state handling."""

        super().__init__(parent)
        self.role = role
        self._icon = icon
        self._edge: GenerationSegmentEdge = "middle"
        self._primary_action_enabled = True
        self._badge_count = 0
        self.setFixedSize(_SEGMENT_WIDTH, _CLUSTER_HEIGHT)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self._tooltip_filter: CursorToolTipFilter = install_cursor_tooltip_filter(
            self,
            self,
            show_delay_ms=600,
            show_when_disabled=True,
        )
        self._apply_theme_palette()
        connect_theme_refresh(self, self._apply_theme_palette)

    def set_segment_edge(self, edge: GenerationSegmentEdge) -> None:
        """Set the segment edge position used for rounded overlay painting."""

        self._edge = edge
        self.update()

    def set_segment_icon(self, icon: object) -> None:
        """Update the centered segment icon."""

        self._icon = icon
        self.update()

    def set_primary_action_enabled(self, enabled: bool) -> None:
        """Set whether left-click activation is available for this segment."""

        if self._primary_action_enabled == enabled:
            return
        self._primary_action_enabled = enabled
        self.update()

    def primary_action_enabled(self) -> bool:
        """Return whether left-click activation is available for this segment."""

        return self._primary_action_enabled

    def set_badge_count(self, count: int) -> None:
        """Set the queue count badge value for this segment."""

        normalized_count = max(0, count)
        if self._badge_count == normalized_count:
            return
        self._badge_count = normalized_count
        self.update()

    def badge_count(self) -> int:
        """Return the current queue count badge value."""

        return self._badge_count

    def badge_fill_color(self) -> QColor:
        """Return queue badge fill color for the current theme."""

        return QColor(
            _QUEUE_BADGE_DARK_FILL if isDarkTheme() else _QUEUE_BADGE_LIGHT_FILL
        )

    def badge_text_color(self) -> QColor:
        """Return queue badge count text color from the active accent."""

        return QColor(themeColor())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit a separate right-click intent without triggering the segment."""

        if event.button() == Qt.MouseButton.RightButton:
            self.setState(TitleBarButtonState.HOVER)
            self.rightClicked.emit()
            event.accept()
            return
        if not self._primary_action_enabled:
            self.setState(TitleBarButtonState.HOVER)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event: object) -> None:
        """Paint per-segment feedback and a centered icon."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._segment_fill_color())
        painter.drawPath(self._segment_overlay_path())

        icon_rect = self._icon_rect()
        self._render_icon(painter, icon_rect, self._icon_color())
        self._paint_queue_badge(painter, icon_rect)

    def _icon_rect(self) -> QRectF:
        """Return an icon rect centered in the visible accent surface."""

        visual_height = self.height() - _BOTTOM_INSET
        icon_size = self._icon_size()
        return QRectF(
            (self.width() - icon_size) / 2,
            (visual_height - icon_size) / 2,
            icon_size,
            icon_size,
        )

    def _icon_size(self) -> float:
        """Return the visual icon rect size for the current segment glyph."""

        if self._icon is _CONTINUOUS_GENERATION_ICON:
            return _CONTINUOUS_SEGMENT_ICON_SIZE
        if self.role == "skip":
            return _SKIP_SEGMENT_ICON_SIZE
        return _SEGMENT_ICON_SIZE

    def _paint_queue_badge(self, painter: QPainter, icon_rect: QRectF) -> None:
        """Paint the queue job-count badge over the queue segment icon."""

        if self.role != "queue" or self._badge_count <= 0 or self.isHidden():
            return
        text = str(self._badge_count)
        badge_width = max(_QUEUE_BADGE_HEIGHT, 8.0 + (len(text) * 5.0))
        badge_rect = QRectF(
            min(
                self.width() - badge_width - 3.0,
                icon_rect.right() - (badge_width / 2.0) + 3.0,
            ),
            icon_rect.bottom() - (_QUEUE_BADGE_HEIGHT / 2.0) - 1.0,
            badge_width,
            _QUEUE_BADGE_HEIGHT,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.badge_fill_color())
        painter.drawRoundedRect(
            badge_rect,
            _QUEUE_BADGE_HEIGHT / 2.0,
            _QUEUE_BADGE_HEIGHT / 2.0,
        )
        painter.setPen(self.badge_text_color())
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _segment_fill_color(self) -> QColor:
        """Return the per-segment fill for disabled and enabled feedback states."""

        if not self.isEnabled() or not self._primary_action_enabled:
            return winui_accent_button_disabled_fill_color()
        return QColor(self._getColors()[1])

    def _segment_overlay_path(self) -> QPainterPath:
        """Return an overlay path matching the cluster's outer rounded corners."""

        width = float(self.width())
        height = float(self.height()) - _BOTTOM_INSET
        radius = _BOTTOM_CORNER_RADIUS
        path = QPainterPath()
        path.moveTo(0.0, 0.0)
        path.lineTo(width, 0.0)
        if self._edge == "last":
            path.lineTo(width, height - radius)
            path.quadTo(width, height, width - radius, height)
        else:
            path.lineTo(width, height)
        if self._edge == "first":
            path.lineTo(radius, height)
            path.quadTo(0.0, height, 0.0, height - radius)
        else:
            path.lineTo(0.0, height)
        path.lineTo(0.0, 0.0)
        path.closeSubpath()
        return path

    def _icon_color(self) -> QColor:
        """Return icon color that contrasts with the accent surface."""

        if not self.isEnabled() or not self._primary_action_enabled:
            return winui_accent_button_disabled_foreground_color()
        if self._is_acrylic_cluster():
            accent_fill = self._cluster_accent_color()
            return accent_fill
        return QColor("#ffffff") if not isDarkTheme() else QColor("#000000")

    def _is_acrylic_cluster(self) -> bool:
        """Return whether the parent cluster is using acrylic-specific styling."""

        parent = self.parent()
        return bool(getattr(parent, "uses_acrylic_style", lambda: False)())

    def _cluster_accent_color(self) -> QColor:
        """Return the accent fill color supplied by the parent acrylic cluster."""

        parent = self.parent()
        color = getattr(parent, "accent_color", lambda: QColor(themeColor()))()
        return QColor(color)

    def _apply_theme_palette(self) -> None:
        """Apply background and icon colors for the active material."""

        if self._is_acrylic_cluster():
            self.setNormalBackgroundColor(QColor(0, 0, 0, 0))
            self.setHoverBackgroundColor(
                QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 12)
            )
            self.setPressedBackgroundColor(
                QColor(255, 255, 255, 28) if isDarkTheme() else QColor(0, 0, 0, 20)
            )
            icon_color = self._icon_color()
            self.setNormalColor(icon_color)
            self.setHoverColor(icon_color)
            self.setPressedColor(icon_color)
            return

        white = QColor("#ffffff")
        self.setNormalColor(white)
        self.setHoverColor(white)
        self.setPressedColor(white)
        self.setNormalBackgroundColor(QColor(0, 0, 0, 0))
        self.setHoverBackgroundColor(QColor(255, 255, 255, 30))
        self.setPressedBackgroundColor(QColor(0, 0, 0, 32))

    def _render_icon(
        self,
        painter: QPainter,
        icon_rect: QRectF,
        icon_color: QColor,
    ) -> None:
        """Render a qfluent-style icon when the icon object supports it."""

        render = getattr(self._icon, "render", None)
        if callable(render):
            painter.save()
            painter.setOpacity(icon_color.alphaF())
            render(painter, icon_rect, fill=icon_color.name(QColor.NameFormat.HexRgb))
            painter.restore()


class GenerationBatchCountAccessory(QWidget):
    """Render a custom titlebar batch-count accessory for generation actions."""

    valueChanged = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        acrylic_style_enabled: bool = False,
    ) -> None:
        """Create the compact value and chevron accessory."""

        super().__init__(parent)
        self._batch_count = 1
        self._acrylic_style_enabled = acrylic_style_enabled
        self._hover_role: GenerationBatchChevronRole | None = None
        self._pressed_role: GenerationBatchChevronRole | None = None
        self._application_filter_installed = False
        self._committing_editor = False
        self._editor = QLineEdit(self)
        self._editor.setValidator(QIntValidator(1, _BATCH_MAX_COUNT, self._editor))
        self._editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._editor.setFrame(False)
        self._editor.hide()
        self._editor.returnPressed.connect(self._commit_editor_value)
        self._editor.editingFinished.connect(self._commit_editor_value)
        self._editor.installEventFilter(self)
        self.setFixedSize(_BATCH_ACCESSORY_WIDTH, _CLUSTER_HEIGHT)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Batch count")
        self.setAccessibleDescription("Number of queued generations to create")
        connect_theme_refresh(self, self._refresh_palette)
        self._refresh_editor_palette()

    def batch_count(self) -> int:
        """Return the current positive batch count."""

        return self._batch_count

    def set_batch_count(self, value: int) -> None:
        """Set the batch count after clamping it to the supported range."""

        normalized_value = min(_BATCH_MAX_COUNT, max(1, int(value)))
        if self._batch_count == normalized_value:
            return
        self._batch_count = normalized_value
        self._editor.setText(str(self._batch_count))
        self.valueChanged.emit(self._batch_count)
        self.update()

    def set_acrylic_style_enabled(self, enabled: bool) -> None:
        """Switch acrylic-specific styling on or off."""

        if self._acrylic_style_enabled == enabled:
            return
        self._acrylic_style_enabled = enabled
        self.update()

    def set_accessory_enabled(self, enabled: bool) -> None:
        """Set whether the accessory accepts input and paints as enabled."""

        if self.isEnabled() == enabled:
            return
        self.setEnabled(enabled)
        self._hover_role = None
        self._pressed_role = None
        if not enabled:
            self._cancel_editor_value()
        self.update()

    def increment(self) -> None:
        """Increase the batch count by one within the supported range."""

        self.set_batch_count(self._batch_count + 1)

    def decrement(self) -> None:
        """Decrease the batch count by one when above the minimum."""

        self.set_batch_count(self._batch_count - 1)

    def down_chevron_enabled(self) -> bool:
        """Return whether the decrement affordance is currently active."""

        return self.isEnabled() and self._batch_count > 1

    def paintEvent(self, _event: object) -> None:
        """Paint the tray, current value, and chevron controls."""

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._surface_color())
        painter.drawPath(self._surface_path())
        self._paint_chevron_overlay(painter, "up")
        self._paint_chevron_overlay(painter, "down")
        if self._editor.isHidden():
            self._paint_value(painter)
        self._paint_chevron(painter, "up")
        self._paint_chevron(painter, "down")

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the transparent editor aligned with the painted value region."""

        self._editor.setGeometry(self._editor_rect().toRect())
        super().resizeEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Refresh hover state as the pointer crosses chevron hit zones."""

        self._set_hover_role(self._chevron_hit_role(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear transient pointer state when the pointer exits the accessory."""

        self._set_hover_role(None)
        self._pressed_role = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track pressed chevron state for left-button pointer input."""

        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            super().mousePressEvent(event)
            return
        role = self._chevron_hit_role(event.position().toPoint())
        if role is None and self._value_rect().contains(event.position()):
            self._begin_manual_edit()
            event.accept()
            return
        if role is None or not self._role_enabled(role):
            super().mousePressEvent(event)
            return
        self._pressed_role = role
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Apply the chevron command when release matches the pressed role."""

        if event.button() != Qt.MouseButton.LeftButton or self._pressed_role is None:
            super().mouseReleaseEvent(event)
            return
        pressed_role = self._pressed_role
        self._pressed_role = None
        release_role = self._chevron_hit_role(event.position().toPoint())
        if release_role == pressed_role and self._role_enabled(pressed_role):
            self._activate_role(pressed_role)
        self.update()
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Adjust the batch count with mouse-wheel steps over the accessory."""

        if not self.isEnabled():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.increment()
            event.accept()
            return
        if delta < 0 and self.down_chevron_enabled():
            self.decrement()
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Support keyboard increment and decrement while focused."""

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._begin_manual_edit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.increment()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down and self.down_chevron_enabled():
            self.decrement()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Commit or cancel manual editing from the embedded numeric editor."""

        if watched is self._editor and event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit_editor_value()
                return True
            if key_event.key() == Qt.Key.Key_Escape:
                self._cancel_editor_value()
                return True
        if watched is self._editor and event.type() == QEvent.Type.FocusOut:
            self._commit_editor_value()
            return False
        if (
            self._editor.isVisible()
            and event.type() == QEvent.Type.MouseButtonPress
            and not self._is_watched_inside_accessory(watched)
        ):
            self._commit_editor_value()
            return False
        return super().eventFilter(watched, event)

    def _refresh_palette(self) -> None:
        """Refresh the accessory after theme or accent changes."""

        self._refresh_editor_palette()
        self.update()

    def _surface_path(self) -> QPainterPath:
        """Return the tray path with only the lower-left corner rounded."""

        width = float(self.width())
        height = float(self.height()) - _BOTTOM_INSET
        radius = _BOTTOM_CORNER_RADIUS
        top = -_TOP_BLEED
        path = QPainterPath()
        path.moveTo(0.0, top)
        path.lineTo(width, top)
        path.lineTo(width, height)
        path.lineTo(radius, height)
        path.quadTo(0.0, height, 0.0, height - radius)
        path.lineTo(0.0, top)
        path.closeSubpath()
        return path

    def _surface_color(self) -> QColor:
        """Return the accessory tray fill for the current material state."""

        backdrop_mode = (
            "acrylic" if self._acrylic_style_enabled else resolved_backdrop_mode(self)
        )
        color = QColor(*body_material_wash_color(backdrop_mode))
        if not self.isEnabled():
            color.setAlpha(max(30, int(color.alpha() * 0.55)))
        return color

    def _foreground_color(
        self, role: GenerationBatchChevronRole | None = None
    ) -> QColor:
        """Return value or chevron foreground color for the current state."""

        if role == "down" and not self.down_chevron_enabled():
            color = self._enabled_foreground_color()
            color.setAlphaF(0.36)
            return color
        if not self.isEnabled():
            color = self._enabled_foreground_color()
            color.setAlphaF(0.42)
            return color
        return self._enabled_foreground_color()

    def _enabled_foreground_color(self) -> QColor:
        """Return enabled foreground color aligned with titlebar segment policy."""

        return QColor("#ffffff") if isDarkTheme() else QColor("#000000")

    def _paint_value(self, painter: QPainter) -> None:
        """Paint the centered numeric batch count."""

        value_rect = self._value_rect()
        painter.setPen(self._foreground_color())
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(
            value_rect,
            Qt.AlignmentFlag.AlignCenter,
            str(self._batch_count),
        )

    def _paint_chevron_overlay(
        self,
        painter: QPainter,
        role: GenerationBatchChevronRole,
    ) -> None:
        """Paint hover or pressed feedback behind one chevron."""

        if not self.isEnabled() or not self._role_enabled(role):
            return
        if self._pressed_role == role:
            overlay = self._pressed_overlay_color()
        elif self._hover_role == role:
            overlay = self._hover_overlay_color()
        else:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(overlay)
        painter.drawRect(self._role_rect(role))

    def _paint_chevron(
        self,
        painter: QPainter,
        role: GenerationBatchChevronRole,
    ) -> None:
        """Paint one compact chevron glyph into its hit zone."""

        rect = self._role_rect(role)
        center_x = rect.center().x()
        center_y = rect.center().y()
        half_width = _BATCH_CHEVRON_HALF_WIDTH
        half_height = _BATCH_CHEVRON_HALF_HEIGHT
        pen = QPen(self._foreground_color(role), _BATCH_CHEVRON_STROKE)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if role == "up":
            painter.drawLine(
                QPointF(center_x - half_width, center_y + half_height),
                QPointF(center_x, center_y - half_height),
            )
            painter.drawLine(
                QPointF(center_x, center_y - half_height),
                QPointF(center_x + half_width, center_y + half_height),
            )
            return
        painter.drawLine(
            QPointF(center_x - half_width, center_y - half_height),
            QPointF(center_x, center_y + half_height),
        )
        painter.drawLine(
            QPointF(center_x, center_y + half_height),
            QPointF(center_x + half_width, center_y - half_height),
        )

    def _hover_overlay_color(self) -> QColor:
        """Return the Fluent-style chevron hover overlay."""

        if self._acrylic_style_enabled:
            return QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 12)
        return QColor(255, 255, 255, 22) if isDarkTheme() else QColor(0, 0, 0, 14)

    def _pressed_overlay_color(self) -> QColor:
        """Return the Fluent-style chevron pressed overlay."""

        if self._acrylic_style_enabled:
            return QColor(255, 255, 255, 28) if isDarkTheme() else QColor(0, 0, 0, 20)
        return QColor(255, 255, 255, 34) if isDarkTheme() else QColor(0, 0, 0, 24)

    def _set_hover_role(self, role: GenerationBatchChevronRole | None) -> None:
        """Store hover role changes and repaint only when needed."""

        if self._hover_role == role:
            return
        self._hover_role = role
        self.update()

    def _chevron_hit_role(
        self,
        point: QPoint,
    ) -> GenerationBatchChevronRole | None:
        """Return the chevron role at a local point, if any."""

        if self._role_rect("up").contains(point):
            return "up"
        if self._role_rect("down").contains(point):
            return "down"
        return None

    def _activate_role(self, role: GenerationBatchChevronRole) -> None:
        """Run the increment or decrement action for one chevron role."""

        if role == "up":
            self.increment()
            return
        self.decrement()

    def _role_enabled(self, role: GenerationBatchChevronRole) -> bool:
        """Return whether one chevron role can currently activate."""

        if role == "up":
            return self.isEnabled() and self._batch_count < _BATCH_MAX_COUNT
        return self.down_chevron_enabled()

    def _role_rect(self, role: GenerationBatchChevronRole) -> QRectF:
        """Return the local hit and paint rect for one chevron role."""

        chevron_x = float(self._chevron_x())
        chevron_height = self._visual_height() / 2.0
        y = 0.0 if role == "up" else chevron_height
        return QRectF(
            chevron_x,
            y,
            float(_BATCH_CHEVRON_WIDTH),
            chevron_height,
        )

    def _value_width(self) -> int:
        """Return the horizontal value region width."""

        return self.width() - _BATCH_CHEVRON_WIDTH - _BATCH_CHEVRON_TRAILING_GAP

    def _chevron_x(self) -> int:
        """Return the left edge of the chevron rail."""

        return self._value_width()

    def _value_rect(self) -> QRectF:
        """Return the local paint and hit rect for manual value entry."""

        return QRectF(0.0, 0.0, float(self._value_width()), self._visual_height())

    def _editor_rect(self) -> QRectF:
        """Return the transparent editor geometry within the value region."""

        return self._value_rect().adjusted(4.0, 2.0, -2.0, -2.0)

    def _visual_height(self) -> float:
        """Return the visible accent height excluding the bottom inset."""

        return float(self.height() - _BOTTOM_INSET)

    def _begin_manual_edit(self) -> None:
        """Show the embedded editor for direct numeric batch entry."""

        if not self.isEnabled():
            return
        self._editor.setText(str(self._batch_count))
        self._editor.setGeometry(self._editor_rect().toRect())
        self._install_application_edit_filter()
        self._editor.show()
        self._editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self._editor.selectAll()
        self.update()

    def _commit_editor_value(self) -> None:
        """Validate and commit the embedded editor text."""

        if self._committing_editor or self._editor.isHidden():
            return
        self._committing_editor = True
        text = self._editor.text().strip()
        value = int(text) if text else self._batch_count
        self._editor.hide()
        self._editor.clearFocus()
        self.clearFocus()
        self._remove_application_edit_filter()
        self._committing_editor = False
        self.set_batch_count(value)
        self.update()

    def _cancel_editor_value(self) -> None:
        """Close manual editing without changing the current batch count."""

        if self._editor.isHidden():
            return
        self._editor.hide()
        self._editor.clearFocus()
        self.clearFocus()
        self._remove_application_edit_filter()
        self.update()

    def _install_application_edit_filter(self) -> None:
        """Watch application mouse presses while manual editing is active."""

        if self._application_filter_installed:
            return
        app = QApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._application_filter_installed = True

    def _remove_application_edit_filter(self) -> None:
        """Stop watching application mouse presses after manual editing closes."""

        if not self._application_filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._application_filter_installed = False

    def _is_watched_inside_accessory(self, watched: QObject) -> bool:
        """Return whether an event target belongs to the accessory editor."""

        if watched is self or watched is self._editor:
            return True
        if not isinstance(watched, QWidget):
            return False
        widget: QWidget | None = watched
        while widget is not None:
            if widget is self:
                return True
            widget = widget.parentWidget()
        return False

    def _refresh_editor_palette(self) -> None:
        """Apply transparent editor styling that matches the painted accessory."""

        color = self._enabled_foreground_color()
        self._editor.setStyleSheet(
            "QLineEdit {"
            "background: transparent;"
            "border: none;"
            f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            "font-weight: 600;"
            "selection-background-color: rgba(96, 96, 96, 90);"
            "}"
        )


class GenerationTitleBarActionCluster(QWidget):
    """Expose titlebar generation actions as one accent segmented surface."""

    playClicked = Signal()
    skipClicked = Signal()
    queueClicked = Signal()
    queueContextMenuRequested = Signal()
    stopClicked = Signal()
    generateModeSelected = Signal(str)

    segment_roles: tuple[GenerationSegmentRole, ...] = (
        "stop",
        "play",
        "skip",
        "queue",
    )
    bottom_corner_radius = _BOTTOM_CORNER_RADIUS
    top_bleed = _TOP_BLEED
    bottom_inset = _BOTTOM_INSET
    divider_color = _DIVIDER_COLOR

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        acrylic_style_enabled: bool = False,
    ) -> None:
        """Create the stop, play, skip, and queue titlebar segments."""

        super().__init__(parent)
        self._acrylic_style_enabled = acrylic_style_enabled
        self._queue_segment_visible = True
        self._mode_menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "generation_mode.generate",
                        "Generate",
                        callback=lambda: self.generateModeSelected.emit("generate"),
                        icon=FIF.PLAY_SOLID,
                    ),
                    MenuItem(
                        "generation_mode.continuous",
                        "Continuous",
                        callback=lambda: self.generateModeSelected.emit("continuous"),
                        icon=_CONTINUOUS_GENERATION_ICON,
                    ),
                )
            )
        )
        self._action_generate = self._rendered_mode_action("generation_mode.generate")
        self._action_continuous = self._rendered_mode_action(
            "generation_mode.continuous"
        )

        self.playButton = GenerationTitleBarSegmentButton(
            "play",
            FIF.PLAY_SOLID,
            "Generate",
            self,
        )
        self.skipButton = GenerationTitleBarSegmentButton(
            "skip",
            AppIcon.NEXT_24_FILLED,
            "Skip generation",
            self,
        )
        self.queueButton = GenerationTitleBarSegmentButton(
            "queue",
            FIF.HISTORY,
            "Generation queue",
            self,
        )
        self.stopButton = GenerationTitleBarSegmentButton(
            "stop",
            AppIcon.STOP_SOLID,
            "Stop generation",
            self,
        )
        self._segments = (
            self.stopButton,
            self.playButton,
            self.skipButton,
            self.queueButton,
        )
        self._apply_segment_edges()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for segment in self._segments:
            layout.addWidget(segment)

        self.setFixedSize(_SEGMENT_WIDTH * len(self._segments), _CLUSTER_HEIGHT)
        self.playButton.clicked.connect(self.playClicked)
        self.playButton.rightClicked.connect(self._show_mode_menu)
        self.skipButton.clicked.connect(self.skipClicked)
        self.queueButton.clicked.connect(self.queueClicked)
        self.queueButton.rightClicked.connect(self.queueContextMenuRequested)
        self.stopButton.clicked.connect(self.stopClicked)
        connect_theme_refresh(self, self._refresh_palette)

    def _rendered_mode_action(self, action_id: str) -> QAction:
        """Return one renderer-created generation mode action by stable id."""

        for action in self._mode_menu.menuActions():
            if (
                isinstance(action, QAction)
                and action.property("menuActionId") == action_id
            ):
                return action
        raise RuntimeError(f"Generation mode action was not rendered: {action_id}")

    def queue_button_target(self) -> QWidget:
        """Return the widget that should anchor the generation queue flyout."""

        return self.queueButton

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Apply a complete generation action presentation snapshot."""

        self._apply_play_presentation(
            presentation.play_mode,
            presentation.play_tooltip,
        )
        self.playButton.setEnabled(presentation.play_enabled)
        self.stopButton.setEnabled(presentation.stop_enabled)
        self.skipButton.setEnabled(presentation.skip_enabled)
        self._action_generate.setEnabled(presentation.mode_menu_enabled)
        self._action_continuous.setEnabled(presentation.mode_menu_enabled)
        self.queueButton.set_primary_action_enabled(presentation.queue_primary_enabled)
        self._set_queue_badge_count(presentation.queue_badge_count)
        self._set_queue_segment_visible(presentation.queue_segment_visible)

    def _apply_play_presentation(
        self,
        play_mode: GenerationPlayPresentationMode,
        tooltip: str,
    ) -> None:
        """Apply the play segment icon, tooltip, and accessible name."""

        if play_mode == "generate":
            icon: object = FIF.PLAY_SOLID
        elif play_mode == "continuous":
            icon = _CONTINUOUS_GENERATION_ICON
        else:
            icon = FIF.PAUSE_BOLD
        self.playButton.set_segment_icon(icon)
        self.playButton.setToolTip(tooltip)
        self.playButton.setAccessibleName(tooltip)

    def _set_queue_badge_count(self, count: int) -> None:
        """Apply the visible generation queue count badge."""

        self.queueButton.set_badge_count(count)

    def _set_queue_segment_visible(self, visible: bool) -> None:
        """Show or hide the queue segment inside the generation action cluster."""

        if self._queue_segment_visible == visible:
            return
        self._queue_segment_visible = visible
        self.queueButton.setVisible(visible)
        self._apply_segment_edges()
        self._sync_cluster_width()
        self.update()

    def paintEvent(self, _event: object) -> None:
        """Paint the single accent surface shared by all segments."""

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._cluster_surface_color())
        painter.drawPath(self._accent_surface_path())
        self._paint_segment_dividers(painter)

    def set_acrylic_style_enabled(self, enabled: bool) -> None:
        """Switch acrylic-specific styling on or off for this cluster."""

        if self._acrylic_style_enabled == enabled:
            return
        self._acrylic_style_enabled = enabled
        self._refresh_palette()

    def uses_acrylic_style(self) -> bool:
        """Return whether this cluster is using acrylic-only styling."""

        return self._acrylic_style_enabled

    def accent_color(self) -> QColor:
        """Return the accent fill color used by acrylic segment backgrounds."""

        return QColor(themeColor())

    def _refresh_palette(self) -> None:
        """Refresh segment palettes and repaint after theme or accent changes."""

        for segment in self._segments:
            segment._apply_theme_palette()
        self.update()

    def _apply_segment_edges(self) -> None:
        """Assign first/middle/last edge positions from the current segment order."""

        visible_segments = self._visible_segments()
        for index, segment in enumerate(visible_segments):
            if index == 0:
                segment.set_segment_edge("first")
            elif index == len(visible_segments) - 1:
                segment.set_segment_edge("last")
            else:
                segment.set_segment_edge("middle")

    def _visible_segments(self) -> tuple[GenerationTitleBarSegmentButton, ...]:
        """Return segments currently participating in cluster geometry."""

        if self._queue_segment_visible:
            return self._segments
        return tuple(
            segment for segment in self._segments if segment is not self.queueButton
        )

    def _sync_cluster_width(self) -> None:
        """Resize the segmented surface to the number of visible segments."""

        visible_count = len(self._visible_segments())
        self.setFixedSize(_SEGMENT_WIDTH * visible_count, _CLUSTER_HEIGHT)

    def _cluster_surface_color(self) -> QColor:
        """Return the base cluster surface color for the active material."""

        if self._acrylic_style_enabled:
            return QColor(*workflow_chrome_wash_color("acrylic"))
        return QColor(themeColor())

    def _accent_surface_path(self) -> QPainterPath:
        """Return a top-bleeding path with only bottom corners rounded."""

        width = float(self.width())
        height = float(self.height()) - self.bottom_inset
        radius = self.bottom_corner_radius
        top = -self.top_bleed
        path = QPainterPath()
        path.moveTo(0.0, top)
        path.lineTo(width, top)
        path.lineTo(width, height - radius)
        path.quadTo(width, height, width - radius, height)
        path.lineTo(radius, height)
        path.quadTo(0.0, height, 0.0, height - radius)
        path.lineTo(0.0, top)
        path.closeSubpath()
        return path

    def _paint_segment_dividers(self, painter: QPainter) -> None:
        """Draw subtle straight dividers between segments."""

        painter.setPen(
            QColor(255, 255, 255, 16)
            if self._acrylic_style_enabled
            else self.divider_color
        )
        divider_bottom = int(self.height() - self.bottom_inset - 5)
        for index in range(1, len(self._visible_segments())):
            x = _SEGMENT_WIDTH * index
            painter.drawLine(x, 5, x, divider_bottom)

    def _show_mode_menu(self) -> None:
        """Open the generate-mode menu below the play segment."""

        self._mode_menu.exec(
            self.playButton.mapToGlobal(QPoint(0, self.playButton.height()))
        )


class GenerationTitleBarRunControl(QWidget):
    """Compose batch count and segmented generation actions into one control."""

    playClicked = Signal()
    skipClicked = Signal()
    queueClicked = Signal()
    queueContextMenuRequested = Signal()
    stopClicked = Signal()
    generateModeSelected = Signal(str)
    batchCountChanged = Signal(int)
    segment_roles = GenerationTitleBarActionCluster.segment_roles
    bottom_corner_radius = GenerationTitleBarActionCluster.bottom_corner_radius
    top_bleed = GenerationTitleBarActionCluster.top_bleed
    bottom_inset = GenerationTitleBarActionCluster.bottom_inset
    divider_color = GenerationTitleBarActionCluster.divider_color

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        acrylic_style_enabled: bool = False,
    ) -> None:
        """Create the batch accessory and the generation action cluster."""

        super().__init__(parent)
        self._current_mode: GenerationSelectedMode = "generate"
        self._accessory_visible = True
        self._batch_accessory = GenerationBatchCountAccessory(
            self,
            acrylic_style_enabled=acrylic_style_enabled,
        )
        self._action_cluster = GenerationTitleBarActionCluster(
            self,
            acrylic_style_enabled=acrylic_style_enabled,
        )
        self.playButton = self._action_cluster.playButton
        self.skipButton = self._action_cluster.skipButton
        self.queueButton = self._action_cluster.queueButton
        self.stopButton = self._action_cluster.stopButton
        self._segments = self._action_cluster._segments

        self._action_cluster.playClicked.connect(self.playClicked)
        self._action_cluster.skipClicked.connect(self.skipClicked)
        self._action_cluster.queueClicked.connect(self.queueClicked)
        self._action_cluster.queueContextMenuRequested.connect(
            self.queueContextMenuRequested
        )
        self._action_cluster.stopClicked.connect(self.stopClicked)
        self._action_cluster.generateModeSelected.connect(self.generateModeSelected)
        self._batch_accessory.valueChanged.connect(self.batchCountChanged)
        self._sync_geometry()

    def batch_count(self) -> int:
        """Return the stored batch count from the accessory."""

        return self._batch_accessory.batch_count()

    def effective_batch_count(self) -> int:
        """Return the active batch count for generate mode, otherwise one."""

        if self._current_mode != "generate":
            return 1
        return self._batch_accessory.batch_count()

    def set_batch_count(self, value: int) -> None:
        """Set the accessory batch count."""

        self._batch_accessory.set_batch_count(value)

    def queue_button_target(self) -> QWidget:
        """Return the queue segment used as flyout anchor."""

        return self._action_cluster.queue_button_target()

    def progress_strip_stop_target(self) -> QWidget:
        """Return the leftmost control the floating progress strip must avoid."""

        if self._accessory_visible:
            return self._batch_accessory
        return self._action_cluster

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Apply a complete generation action presentation snapshot."""

        self._current_mode = (
            "generate" if presentation.batch_accessory_visible else "continuous"
        )
        self._action_cluster.apply_generation_presentation(presentation)
        self._set_accessory_visible(presentation.batch_accessory_visible)
        self._batch_accessory.set_accessory_enabled(
            presentation.batch_accessory_enabled
        )
        self._sync_geometry()

    def set_acrylic_style_enabled(self, enabled: bool) -> None:
        """Switch acrylic styling for the accessory and action cluster."""

        self._batch_accessory.set_acrylic_style_enabled(enabled)
        self._action_cluster.set_acrylic_style_enabled(enabled)

    def uses_acrylic_style(self) -> bool:
        """Return whether the wrapped action cluster uses acrylic styling."""

        return self._action_cluster.uses_acrylic_style()

    def accent_color(self) -> QColor:
        """Return the accent color used by the wrapped action cluster."""

        return self._action_cluster.accent_color()

    def _set_accessory_visible(self, visible: bool) -> None:
        """Show or hide the batch accessory and update wrapper geometry."""

        if self._accessory_visible == visible:
            return
        self._accessory_visible = visible
        self._batch_accessory.setVisible(visible)
        self._sync_geometry()

    def _sync_geometry(self) -> None:
        """Position children with the accessory tray overlapped under stop."""

        cluster_width = self._action_cluster.width()
        if self._accessory_visible:
            cluster_x = _BATCH_ACCESSORY_WIDTH - _BATCH_CLUSTER_OVERLAP
            total_width = cluster_x + cluster_width
            self._batch_accessory.setGeometry(
                0,
                0,
                _BATCH_ACCESSORY_WIDTH,
                _CLUSTER_HEIGHT,
            )
        else:
            cluster_x = 0
            total_width = cluster_width
        self._action_cluster.setGeometry(
            cluster_x,
            0,
            cluster_width,
            _CLUSTER_HEIGHT,
        )
        self.setFixedSize(total_width, _CLUSTER_HEIGHT)
        self._action_cluster.raise_()


class GenerationClusterRevealButton(TitleBarButton):  # type: ignore[misc]
    """Render the output-canvas titlebar chevron reveal button."""

    toggleRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a chevron titlebar button using default titlebar chrome."""

        super().__init__(parent)
        self._expanded = False
        self.setFixedSize(_GENERATION_REVEAL_BUTTON_WIDTH, _TITLEBAR_BUTTON_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        FluentStyleSheet.FLUENT_WINDOW.apply(self)
        self.clicked.connect(self.toggleRequested.emit)
        self._update_accessible_text()

    def set_expanded(self, expanded: bool) -> None:
        """Update chevron direction and accessible text."""

        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._update_accessible_text()
        self.update()

    def is_expanded(self) -> bool:
        """Return whether the button currently represents an expanded host."""

        return self._expanded

    def paintEvent(self, _event: object) -> None:
        """Paint the state background and horizontal reveal chevron."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color())
        painter.drawRect(self.rect())

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        half_width = _GENERATION_REVEAL_CHEVRON_HALF_WIDTH
        half_height = _GENERATION_REVEAL_CHEVRON_HALF_HEIGHT
        direction = -1.0 if self._expanded else 1.0
        pen = QPen(self._icon_color(), _GENERATION_REVEAL_CHEVRON_STROKE)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(
            QPointF(center_x - (direction * half_width), center_y - half_height),
            QPointF(center_x + (direction * half_width), center_y),
        )
        painter.drawLine(
            QPointF(center_x + (direction * half_width), center_y),
            QPointF(center_x - (direction * half_width), center_y + half_height),
        )

    def _background_color(self) -> QColor:
        """Return the titlebar background color for the current button state."""

        return QColor(self._getColors()[1])

    def _icon_color(self) -> QColor:
        """Return the chevron color for the current button state."""

        return QColor(self._getColors()[0])

    def _update_accessible_text(self) -> None:
        """Match tooltip and accessible text to the reveal state."""

        text = (
            "Hide generation controls" if self._expanded else "Show generation controls"
        )
        self.setToolTip(text)
        self.setAccessibleName(text)


class GenerationClusterRevealHost(QWidget):
    """Host an output-canvas-only horizontal generation control reveal."""

    expandedChanged = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        acrylic_style_enabled: bool = False,
    ) -> None:
        """Create the chevron and contained generation run control."""

        super().__init__(parent)
        self._expanded = False
        self._reveal_width = _GENERATION_REVEAL_BUTTON_WIDTH
        self._setting_reveal_state = False
        self._reveal_animation = QPropertyAnimation(self, b"revealWidth", self)
        self._reveal_animation.finished.connect(self._finish_reveal_animation)

        self.revealButton = GenerationClusterRevealButton(self)
        self.control = GenerationTitleBarRunControl(
            self,
            acrylic_style_enabled=acrylic_style_enabled,
        )
        self.control.installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.revealButton)
        layout.addWidget(self.control)
        self.setFixedHeight(_CLUSTER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.revealButton.toggleRequested.connect(self._toggle_expanded)
        self.set_expanded(False, animated=False)

    def is_expanded(self) -> bool:
        """Return whether the output generation controls are revealed."""

        return self._expanded

    def set_expanded(self, expanded: bool, animated: bool = True) -> None:
        """Reveal or hide the contained generation controls horizontally."""

        if (
            self._expanded == expanded
            and self._reveal_width == self._target_width()
            and self.control.isHidden() == (not expanded)
        ):
            return
        self._expanded = expanded
        self.expandedChanged.emit(expanded)
        self.revealButton.set_expanded(expanded)
        self._setting_reveal_state = True
        try:
            if expanded:
                self.control.show()

            end_width = self._target_width()
            if not animated or is_reduced_motion_enabled():
                self._reveal_animation.stop()
                self._set_reveal_width(end_width)
                self._finish_reveal_animation()
                return

            restart_property_animation(
                self._reveal_animation,
                start_value=self._reveal_width,
                end_value=end_width,
                duration_ms=(
                    ACCORDION_EXPAND_DURATION_MS
                    if expanded
                    else ACCORDION_COLLAPSE_DURATION_MS
                ),
                easing_curve=(
                    ACCORDION_EXPAND_EASING_CURVE
                    if expanded
                    else ACCORDION_COLLAPSE_EASING_CURVE
                ),
            )
        finally:
            self._setting_reveal_state = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Keep host width synchronized when the contained control changes size."""

        if (
            not self._setting_reveal_state
            and watched is self.control
            and event.type()
            in {
                QEvent.Type.Resize,
                QEvent.Type.LayoutRequest,
                QEvent.Type.Show,
                QEvent.Type.Hide,
            }
        ):
            self._sync_reveal_width_to_state()
        return super().eventFilter(watched, event)

    def _toggle_expanded(self) -> None:
        """Toggle the output generation control reveal state."""

        self.set_expanded(not self._expanded)

    def _target_width(self) -> int:
        """Return the current width for the selected reveal state."""

        return self._expanded_width() if self._expanded else self._collapsed_width()

    def _collapsed_width(self) -> int:
        """Return the chevron-only width."""

        return _GENERATION_REVEAL_BUTTON_WIDTH

    def _expanded_width(self) -> int:
        """Return the chevron plus generation control width."""

        control_width = max(self.control.width(), self.control.sizeHint().width())
        return self._collapsed_width() + control_width

    def _set_reveal_width(self, width: int) -> None:
        """Apply the animated host width to layout constraints."""

        self._reveal_width = max(self._collapsed_width(), int(width))
        self.setMinimumWidth(self._reveal_width)
        self.setMaximumWidth(self._reveal_width)
        self.resize(self._reveal_width, _CLUSTER_HEIGHT)
        self.updateGeometry()

    def _get_reveal_width(self) -> int:
        """Return the current animated host width."""

        return self._reveal_width

    revealWidth = Property(int, _get_reveal_width, _set_reveal_width)

    def _sync_reveal_width_to_state(self) -> None:
        """Settle width after generation presentation changes resize the control."""

        if self._reveal_animation.state() == QAbstractAnimation.State.Running:
            return
        self._set_reveal_width(self._target_width())
        self._finish_reveal_animation()

    def _finish_reveal_animation(self) -> None:
        """Settle child visibility after a reveal animation completes."""

        self._set_reveal_width(self._target_width())
        self.control.setVisible(self._expanded)


__all__ = [
    "ComfyOutputToggleButton",
    "GenerationClusterRevealButton",
    "GenerationClusterRevealHost",
    "GenerationBatchCountAccessory",
    "GenerationTitleBarActionCluster",
    "GenerationTitleBarRunControl",
    "GenerationTitleBarSegmentButton",
    "StartupDiagnosticsTitleBarButton",
]
