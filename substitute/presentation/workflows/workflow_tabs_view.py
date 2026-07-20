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

"""Workflow-tab presentation view built on shared reorderable-tab primitives."""
# mypy: disable-error-code=attr-defined

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    app_text,
)

from typing import Callable, cast

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIcon,
    FluentIconBase,
)
from qfluentwidgets.common.router import qrouter  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    FluentStyleSheet,
    isDarkTheme,
    themeColor,
)

from substitute.presentation.shell.chrome_style import (
    APP_ORB_TAB_CUTOUT_ANIMATION_MS,
    APP_ORB_TAB_CUTOUT_CENTER_X,
    APP_ORB_TAB_CUTOUT_CENTER_Y,
    APP_ORB_TAB_CUTOUT_RADIUS,
    WORKFLOW_TAB_BODY_TOP_RADIUS,
    WORKFLOW_TAB_BOTTOM_CORNER_RADIUS,
    WORKFLOW_TAB_BOTTOM_CORNER_WIDTH,
    WORKFLOW_TAB_CORNER_OVERLAY_WIDTH,
    WORKFLOW_TAB_HEIGHT,
    WORKFLOW_TAB_ICON_LEFT_PADDING,
    WORKFLOW_TAB_INACTIVE_INSET,
    WORKFLOW_TAB_INACTIVE_RADIUS,
    WORKFLOW_TAB_INACTIVE_TEXT_ALPHA,
    WORKFLOW_TAB_SELECTED_FONT_WEIGHT,
    WORKFLOW_TAB_TEXT_LEFT_PADDING,
    WORKFLOW_TAB_TEXT_LEFT_PADDING_WITH_ICON,
    connect_theme_refresh,
    workflow_chrome_wash_color,
)
from substitute.application.workflows import workflow_tab_display_text
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.shell.window_frame import ShellBackdropMode
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableCloseButtonDisplayMode,
    ReorderableTabBarBase,
    ReorderableTabItemBase,
    ReorderableTabToolButton,
)
from substitute.presentation.workflows.workflow_tab_drag_preview_presenter import (
    WorkflowTabDragPreviewPresenter,
)
from substitute.presentation.workflows.workflow_tab_gesture_controller import (
    WorkflowTabGestureController,
    WorkflowTabGestureResult,
    WorkflowTabGestureResultKind,
)
from substitute.presentation.workflows.workflow_tab_orb_adjacency_controller import (
    WorkflowTabOrbAdjacencyController,
)
from substitute.presentation.workflows.workflow_tab_reorder_controller import (
    WorkflowTabReorderController,
    WorkflowTabReorderPreview,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.workflows.workflow_tabs_view")

TabCloseButtonDisplayMode = ReorderableCloseButtonDisplayMode
SETTINGS_WORKSPACE_ROUTE = "settings"
_UNREAD_RESULT_HIGHLIGHT_ALPHA_DARK = 44
_UNREAD_RESULT_HIGHLIGHT_ALPHA_LIGHT = 28
_UNREAD_SHIMMER_DURATION_MS = 800
_UNREAD_SHIMMER_MIN_BAND_WIDTH = 24.0
_UNREAD_SHIMMER_MAX_BAND_WIDTH = 36.0
_UNREAD_SHIMMER_WIDTH_RATIO = 0.32
_UNREAD_SHIMMER_EDGE_ALPHA_DARK = 16
_UNREAD_SHIMMER_EDGE_ALPHA_LIGHT = 22
_UNREAD_SHIMMER_CENTER_ALPHA_DARK = 45
_UNREAD_SHIMMER_CENTER_ALPHA_LIGHT = 55
REOPEN_CLOSED_WORKFLOW_MENU_TEXT: ApplicationMessage = app_text(
    "Reopen Closed Workflow"
)


class TabItem(ReorderableTabItemBase):
    """Render workflow tabs with connected Firefox-like chrome styling."""

    fixed_height = WORKFLOW_TAB_HEIGHT
    selected_accent_position = "top"
    selected_border_reacts_to_hover = False
    selected_bottom_corner_radius = WORKFLOW_TAB_BOTTOM_CORNER_RADIUS
    selected_bottom_corner_width = WORKFLOW_TAB_BOTTOM_CORNER_WIDTH
    selected_bottom_border_mode = "none"
    selected_connects_to_bottom_surface = True
    selected_fill_color = workflow_chrome_wash_color()
    selected_fill_radius = WORKFLOW_TAB_BODY_TOP_RADIUS
    selected_font_weight = WORKFLOW_TAB_SELECTED_FONT_WEIGHT
    icon_left_padding = WORKFLOW_TAB_ICON_LEFT_PADDING
    text_left_padding = WORKFLOW_TAB_TEXT_LEFT_PADDING
    text_left_padding_with_icon = WORKFLOW_TAB_TEXT_LEFT_PADDING_WITH_ICON
    unselected_inset = WORKFLOW_TAB_INACTIVE_INSET
    unselected_radius = WORKFLOW_TAB_INACTIVE_RADIUS
    unselected_top_rounded_only = True
    inactive_text_alpha = WORKFLOW_TAB_INACTIVE_TEXT_ALPHA

    def _postInit(self) -> None:
        """Disable selected-tab shadow so workflow tabs stay flat."""
        super()._postInit()
        self.setParentMouseEventForwarding(False)
        self._source_text = str(self.text())
        self._backdrop_mode: ShellBackdropMode | None = None
        self._owning_tab_bar: TabBar | None = None
        self._orb_cutout_progress = 0.0
        self._orb_cutout_animation = QPropertyAnimation(
            self,
            b"orbCutoutProgress",
            self,
        )
        self._orb_cutout_animation.setDuration(APP_ORB_TAB_CUTOUT_ANIMATION_MS)
        self._orb_cutout_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._unread_result_visible = False
        self._unread_shimmer_progress = 1.0
        self._unread_shimmer_animation = QPropertyAnimation(
            self,
            b"unreadShimmerProgress",
            self,
        )
        self._unread_shimmer_animation.setDuration(_UNREAD_SHIMMER_DURATION_MS)
        self._unread_shimmer_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setShadowEnabled(False)
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    def set_source_text(self, text: str) -> None:
        """Store invariant workflow text and project its localized display label."""

        self._source_text = text
        apply_application_text(self, workflow_tab_display_text(text))

    def source_text(self) -> str:
        """Return the invariant authored or generated workflow label."""

        return self._source_text

    def set_owning_tab_bar(self, tab_bar: "TabBar") -> None:
        """Set the tab bar that owns orb-cutout role and overlay invalidation."""

        self._owning_tab_bar = tab_bar

    def orb_cutout_progress(self) -> float:
        """Return the current normalized orb-cutout tween progress."""

        return self._orb_cutout_progress

    def _get_orb_cutout_progress(self) -> float:
        """Return the current Qt property value for cutout animation."""

        return self._orb_cutout_progress

    def _set_orb_cutout_progress(self, progress: float) -> None:
        """Set cutout animation progress and repaint dependent chrome."""

        clamped_progress = max(0.0, min(1.0, progress))
        if self._orb_cutout_progress == clamped_progress:
            return

        self._orb_cutout_progress = clamped_progress
        self.update()
        if (
            self._owning_tab_bar is not None
            and self._owning_tab_bar.currentTab() is self
        ):
            self._owning_tab_bar.invalidate_orb_cutout_overlay()

    orbCutoutProgress = Property(
        float,
        _get_orb_cutout_progress,
        _set_orb_cutout_progress,
    )

    def set_orb_cutout_active(
        self,
        active: bool,
        *,
        animated: bool = True,
    ) -> None:
        """Animate this tab between normal and orb-adjacent cutout states."""

        target_progress = 1.0 if active else 0.0
        self._orb_cutout_animation.stop()
        if not animated:
            self._set_orb_cutout_progress(target_progress)
            return

        if self._orb_cutout_progress == target_progress:
            return

        self._orb_cutout_animation.setStartValue(self._orb_cutout_progress)
        self._orb_cutout_animation.setEndValue(target_progress)
        self._orb_cutout_animation.start()

    def set_orb_cutout_preview_progress(self, progress: float) -> None:
        """Set cutout progress directly for pointer-driven drag preview."""

        self._orb_cutout_animation.stop()
        self._set_orb_cutout_progress(progress)

    def _get_unread_shimmer_progress(self) -> float:
        """Return the current normalized unread shimmer progress."""

        return self._unread_shimmer_progress

    def _set_unread_shimmer_progress(self, progress: float) -> None:
        """Update unread shimmer progress and repaint only this tab."""

        clamped_progress = max(0.0, min(1.0, progress))
        if self._unread_shimmer_progress == clamped_progress:
            return

        self._unread_shimmer_progress = clamped_progress
        self.update()

    unreadShimmerProgress = Property(
        float,
        _get_unread_shimmer_progress,
        _set_unread_shimmer_progress,
    )

    def setShadowEnabled(self, isEnabled: bool) -> None:
        """Keep workflow selected tabs free of shadow/glow effects."""
        super().setShadowEnabled(False)
        self.shadowEffect.setEnabled(False)

    def setSelected(self, isSelected: bool) -> None:
        """Set selected state and stop hidden unread shimmer work when active."""

        super().setSelected(isSelected)
        if isSelected:
            self._stop_unread_shimmer()

    def _apply_theme_styles(self) -> None:
        """Refresh selected tab fill color after theme changes."""

        self.selected_fill_color = workflow_chrome_wash_color(self._backdrop_mode)
        self._syncRenameEditorTextColor()
        self.update()

    def set_backdrop_mode(self, backdrop_mode: ShellBackdropMode | None) -> None:
        """Update the backdrop mode used by the selected tab fill."""

        self._backdrop_mode = backdrop_mode
        self._apply_theme_styles()

    def _drawConnectedSelectedBackground(
        self,
        painter: QPainter,
        is_dark: bool,
    ) -> None:
        """Draw the selected workflow tab with optional orb-adjacent cutout."""

        if self._orb_cutout_progress <= 0.0:
            super()._drawConnectedSelectedBackground(painter, is_dark)
            return

        rect = QRectF(self.rect().adjusted(1, 1, -1, 0))
        rect.setBottom(rect.bottom() + 1.0)
        radius = (
            self.selected_fill_radius
            if self.selected_fill_radius is not None
            else float(self.borderRadius)
        )
        fill_path = self._top_rounded_orb_cutout_path(rect, radius)
        border_path = self._top_rounded_orb_cutout_border_path(rect, radius)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._resolveSelectedFillColor())
        painter.drawPath(fill_path)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._resolveSelectedBorderColor(is_dark))
        painter.drawPath(border_path)

        self._drawSelectedAccent(painter, fill_path, rect)

    def _drawNotSelectedBackground(self, painter: QPainter) -> None:
        """Draw unread accent, hover wash, and pressed wash for inactive tabs."""

        if self._unread_result_visible:
            self._draw_unread_result_background(painter)

        if not (self.isPressed or self.isHover):
            super()._drawNotSelectedBackground(painter)
        else:
            self._draw_inactive_interaction_wash(painter)

        if self._unread_result_visible:
            self._draw_unread_result_shimmer(painter)

    def _inactive_tab_body_path(self) -> QPainterPath:
        """Return the inactive workflow tab body path used by all state fills."""

        inset = self.unselected_inset
        radius = (
            self.unselected_radius
            if self.unselected_radius is not None
            else float(self.borderRadius)
        )
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        if self._orb_cutout_progress > 0.0:
            return self._top_rounded_orb_cutout_path(rect, radius)
        return self._topRoundedPath(rect, radius)

    def _draw_unread_result_background(self, painter: QPainter) -> None:
        """Draw the persistent unread-result accent fill for inactive tabs."""

        if not self._unread_result_visible or self.isSelected:
            return

        painter.setBrush(self._unread_result_background_color())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(self._inactive_tab_body_path())

    def _unread_result_background_color(self) -> QColor:
        """Return the current accent color adjusted for unread-tab fill."""

        color = QColor(themeColor())
        color.setAlpha(
            _UNREAD_RESULT_HIGHLIGHT_ALPHA_DARK
            if isDarkTheme()
            else _UNREAD_RESULT_HIGHLIGHT_ALPHA_LIGHT
        )
        return color

    def _draw_inactive_interaction_wash(self, painter: QPainter) -> None:
        """Draw hover or pressed wash over the inactive tab body."""

        color = self._inactive_interaction_wash_color()
        if color is None:
            return

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(self._inactive_tab_body_path())

    def _inactive_interaction_wash_color(self) -> QColor | None:
        """Return the current inactive hover/pressed wash color when active."""

        if not (self.isPressed or self.isHover):
            return None

        is_dark = isDarkTheme()
        if self.isPressed:
            return QColor(255, 255, 255, 12) if is_dark else QColor(0, 0, 0, 7)
        return QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 10)

    def _top_rounded_orb_cutout_path(
        self,
        rect: QRectF,
        radius: float,
    ) -> QPainterPath:
        """Return the normal top-rounded tab path minus the animated orb bite."""

        normal_path = self._topRoundedPath(rect, radius)
        if self._orb_cutout_progress <= 0.0:
            return normal_path

        return normal_path.subtracted(self._orb_cutout_ellipse_path(rect))

    def _top_rounded_orb_cutout_border_path(
        self,
        rect: QRectF,
        radius: float,
    ) -> QPainterPath:
        """Return the selected tab border path with the same orb cutout."""

        return self._top_rounded_orb_cutout_path(rect, radius)

    def _orb_cutout_ellipse_path(self, rect: QRectF) -> QPainterPath:
        """Return the local ellipse path that subtracts the orb-adjacent bite."""

        ellipse_path = QPainterPath()
        progress = self._orb_cutout_progress
        if progress <= 0.0:
            return ellipse_path

        full_radius = APP_ORB_TAB_CUTOUT_RADIUS
        radius = full_radius * progress
        full_center = self._orb_cutout_center()
        full_right_edge = full_center.x() + full_radius
        target_right_edge = (
            rect.left() + max(0.0, full_right_edge - rect.left()) * progress
        )
        center = QPointF(target_right_edge - radius, full_center.y())
        ellipse_path.addEllipse(center, radius, radius)
        return ellipse_path

    def _orb_cutout_center(self) -> QPointF:
        """Return the full-progress orb center in this tab's local coordinates."""

        return QPointF(APP_ORB_TAB_CUTOUT_CENTER_X, APP_ORB_TAB_CUTOUT_CENTER_Y)

    def set_unread_result_visible(self, visible: bool) -> None:
        """Set whether the tab should draw an unread-result marker."""

        if self._unread_result_visible == visible:
            return
        self._unread_result_visible = visible
        if visible:
            self._start_unread_shimmer()
        else:
            self._stop_unread_shimmer()
        self.update()

    def _start_unread_shimmer(self) -> None:
        """Play the one-shot unread shimmer from the beginning."""

        self._unread_shimmer_animation.stop()
        if self.isSelected:
            self._set_unread_shimmer_progress(1.0)
            return

        self._set_unread_shimmer_progress(0.0)
        self._unread_shimmer_animation.setStartValue(0.0)
        self._unread_shimmer_animation.setEndValue(1.0)
        self._unread_shimmer_animation.start()

    def _stop_unread_shimmer(self) -> None:
        """Stop unread shimmer and reset progress to the inactive value."""

        self._unread_shimmer_animation.stop()
        self._set_unread_shimmer_progress(1.0)

    def _draw_unread_result_shimmer(self, painter: QPainter) -> None:
        """Draw the transient unread-result shimmer clipped to the tab body."""

        if (
            not self._unread_result_visible
            or self.isSelected
            or self._unread_shimmer_animation.state()
            != QPropertyAnimation.State.Running
            or self.width() <= 0
            or self.height() <= 0
        ):
            return

        path = self._inactive_tab_body_path()
        progress = self._unread_shimmer_progress
        band_width = min(
            _UNREAD_SHIMMER_MAX_BAND_WIDTH,
            max(
                _UNREAD_SHIMMER_MIN_BAND_WIDTH,
                self.width() * _UNREAD_SHIMMER_WIDTH_RATIO,
            ),
        )
        start_x = -band_width + (self.width() + band_width * 2.0) * progress
        gradient = QLinearGradient(
            QPointF(start_x - band_width, float(self.height())),
            QPointF(start_x + band_width, 0.0),
        )
        edge_alpha = (
            _UNREAD_SHIMMER_EDGE_ALPHA_DARK
            if isDarkTheme()
            else _UNREAD_SHIMMER_EDGE_ALPHA_LIGHT
        )
        center_alpha = (
            _UNREAD_SHIMMER_CENTER_ALPHA_DARK
            if isDarkTheme()
            else _UNREAD_SHIMMER_CENTER_ALPHA_LIGHT
        )
        transparent = QColor(255, 255, 255, 0)
        edge = QColor(255, 255, 255, edge_alpha)
        center = QColor(255, 255, 255, center_alpha)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(0.45, edge)
        gradient.setColorAt(0.5, center)
        gradient.setColorAt(0.55, edge)
        gradient.setColorAt(1.0, transparent)

        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(path)
        painter.restore()


def workflow_tab_source_text(item: object) -> str:
    """Return invariant workflow text from a production tab or compatible stub."""

    source_text = getattr(item, "source_text", None)
    if callable(source_text):
        return str(source_text())
    text = getattr(item, "text", None)
    return str(text()) if callable(text) else ""


def set_workflow_tab_source_text(item: object, text: str) -> None:
    """Set invariant workflow text on a production tab or compatible stub."""

    set_source_text = getattr(item, "set_source_text", None)
    if callable(set_source_text):
        set_source_text(text)
        return
    set_text = getattr(item, "setText", None)
    if not callable(set_text):
        raise TypeError("Workflow tab items must expose a text setter.")
    set_text(text)


class WorkflowTabCornerOverlay(QWidget):
    """Paint selected workflow tab bottom corners above neighboring tabs."""

    _join_overlap = 1.0
    _bottom_join_extension = 1.0

    def __init__(self, tab_bar: "TabBar") -> None:
        """Create a mouse-transparent overlay in workflow tab coordinates."""
        super().__init__(tab_bar.view)
        self._tab_bar = tab_bar
        self._corner_path_cache_signature: tuple[object, ...] | None = None
        self._corner_path_cache: (
            tuple[
                QPainterPath,
                QPainterPath,
                QPainterPath,
                QPainterPath,
            ]
            | None
        ) = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    def sync(self) -> None:
        """Keep overlay geometry and stacking aligned with the tab view."""
        selected_item = self._selectedItem()
        self.setGeometry(self._tab_bar.view.rect())
        self.raise_()
        self.setVisible(selected_item is not None and selected_item.isVisible())
        self.update()

    def paintEvent(self, event: object) -> None:
        """Draw the selected tab's CSS-style bottom corner pseudo-elements."""
        selected_item = self._selectedItem()
        if selected_item is None or not selected_item.isVisible():
            return

        (
            left_corner_path,
            right_corner_path,
            left_border_path,
            right_border_path,
        ) = self._selectedCornerPaths(selected_item)
        if left_corner_path.isEmpty() and right_corner_path.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QColor(*workflow_chrome_wash_color(self._tab_bar.backdrop_mode))
        )
        painter.drawPath(left_corner_path)
        painter.drawPath(right_corner_path)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._selectedBorderColor())
        painter.drawPath(left_border_path)
        painter.drawPath(right_border_path)

    def _selectedCornerPaths(
        self,
        selected_item: ReorderableTabItemBase,
    ) -> tuple[QPainterPath, QPainterPath, QPainterPath, QPainterPath]:
        """Return cached selected-corner fill and border paths."""

        selected_rect = self._selectedBodyRect(selected_item)
        cutout_progress = (
            selected_item.orb_cutout_progress()
            if isinstance(selected_item, TabItem)
            else 0.0
        )
        signature = (
            self._tab_bar.selected_route_key(),
            selected_rect.getRect(),
            self.rect().getRect(),
            self._tab_bar.backdrop_mode,
            cutout_progress,
            isDarkTheme(),
        )
        if (
            self._corner_path_cache_signature == signature
            and self._corner_path_cache is not None
        ):
            return self._corner_path_cache

        corner_width = WORKFLOW_TAB_CORNER_OVERLAY_WIDTH
        corner_radius = WORKFLOW_TAB_BOTTOM_CORNER_RADIUS
        corner_paths = (
            self._leftBottomPseudoCornerPath(
                selected_rect,
                corner_width,
                corner_radius,
            ),
            self._rightBottomPseudoCornerPath(
                selected_rect,
                corner_width,
                corner_radius,
            ),
            self._leftBottomPseudoCornerBorderPath(
                selected_rect,
                corner_width,
                corner_radius,
            ),
            self._rightBottomPseudoCornerBorderPath(
                selected_rect,
                corner_width,
                corner_radius,
            ),
        )
        self._corner_path_cache_signature = signature
        self._corner_path_cache = corner_paths
        return corner_paths

    def _selectedItem(self) -> ReorderableTabItemBase | None:
        """Return the current tab item if the tab bar has a valid selection."""
        return cast(
            ReorderableTabItemBase | None,
            self._tab_bar.tabItem(self._tab_bar.currentIndex()),
        )

    def _selectedBodyRect(self, selected_item: ReorderableTabItemBase) -> QRectF:
        """Map the selected tab's painted body rect into overlay coordinates."""
        selected_top_left = self.mapFromGlobal(selected_item.mapToGlobal(QPoint(0, 0)))
        body_rect = QRectF(selected_item.rect().adjusted(1, 1, -1, 0))
        body_rect.translate(selected_top_left)
        body_rect.setBottom(body_rect.bottom() + self._bottom_join_extension)
        return body_rect

    @staticmethod
    def _selectedBorderColor() -> QColor:
        """Return the same subtle outline family as selected workflow tabs."""
        return QColor(0, 0, 0, 20 if not isDarkTheme() else 24)

    @staticmethod
    def _leftBottomPseudoCornerPath(
        selected_rect: QRectF,
        corner_width: float,
        corner_radius: float,
    ) -> QPainterPath:
        """Return the left bottom corner fill in overlay coordinates."""
        path = QPainterPath()
        if corner_radius <= 0 or corner_width <= 0:
            return path

        left = selected_rect.left() - corner_width
        right = selected_rect.left() + WorkflowTabCornerOverlay._join_overlap
        bottom = selected_rect.bottom()
        top = bottom - corner_radius
        path.moveTo(left, bottom)
        path.lineTo(right, bottom)
        path.lineTo(right, top)
        path.cubicTo(
            right,
            top + (corner_radius * 0.55),
            left + (corner_width * 0.55),
            bottom,
            left,
            bottom,
        )
        path.closeSubpath()
        return path

    @staticmethod
    def _leftBottomPseudoCornerBorderPath(
        selected_rect: QRectF,
        corner_width: float,
        corner_radius: float,
    ) -> QPainterPath:
        """Return the left bottom corner outline without a bottom seam."""
        path = QPainterPath()
        if corner_radius <= 0 or corner_width <= 0:
            return path

        left = selected_rect.left() - corner_width
        right = selected_rect.left() + WorkflowTabCornerOverlay._join_overlap
        bottom = selected_rect.bottom()
        top = bottom - corner_radius
        path.moveTo(left, bottom)
        path.cubicTo(
            left + (corner_width * 0.55),
            bottom,
            right,
            top + (corner_radius * 0.55),
            right,
            top,
        )
        return path

    @staticmethod
    def _rightBottomPseudoCornerPath(
        selected_rect: QRectF,
        corner_width: float,
        corner_radius: float,
    ) -> QPainterPath:
        """Return the right bottom corner fill in overlay coordinates."""
        path = QPainterPath()
        if corner_radius <= 0 or corner_width <= 0:
            return path

        left = selected_rect.right() - WorkflowTabCornerOverlay._join_overlap
        right = selected_rect.right() + corner_width
        bottom = selected_rect.bottom()
        top = bottom - corner_radius
        path.moveTo(left, bottom)
        path.lineTo(right, bottom)
        path.cubicTo(
            right - (corner_width * 0.55),
            bottom,
            left,
            top + (corner_radius * 0.55),
            left,
            top,
        )
        path.lineTo(left, bottom)
        path.closeSubpath()
        return path

    @staticmethod
    def _rightBottomPseudoCornerBorderPath(
        selected_rect: QRectF,
        corner_width: float,
        corner_radius: float,
    ) -> QPainterPath:
        """Return the right bottom corner outline without a bottom seam."""
        path = QPainterPath()
        if corner_radius <= 0 or corner_width <= 0:
            return path

        left = selected_rect.right() - WorkflowTabCornerOverlay._join_overlap
        right = selected_rect.right() + corner_width
        bottom = selected_rect.bottom()
        top = bottom - corner_radius
        path.moveTo(left, top)
        path.cubicTo(
            left,
            top + (corner_radius * 0.55),
            right - (corner_width * 0.55),
            bottom,
            right,
            bottom,
        )
        return path


class TabBar(ReorderableTabBarBase):
    """Display and reorder workflow tabs in the title-bar row."""

    currentChanged = Signal(int)
    tabBarClicked = Signal(int)
    tabCloseRequested = Signal(int)
    tabAddRequested = Signal()
    tabRenamed = Signal(str, str)
    workflowSelected = Signal(str)
    workflowCloseRequested = Signal(str)
    workflowAddRequested = Signal()
    workflowRenameRequested = Signal(str, str)
    workflowDuplicateRequested = Signal(str)
    workflowReopenClosedRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create horizontal workflow tab bar."""
        super().__init__(parent=parent, orient=Qt.Orientation.Horizontal)
        self.backdrop_mode: ShellBackdropMode | None = None
        self._initCommonState()
        self._suppress_workflow_intent = False
        self._corner_overlay_sync_signature: tuple[object, ...] | None = None
        self._orb_adjacent_tab_route_key: str | None = None
        self._orb_cutout_sync_initialized = False
        self._gesture_controller = WorkflowTabGestureController(self)
        self._reorder_controller = WorkflowTabReorderController(self)
        self._drag_preview_presenter = WorkflowTabDragPreviewPresenter()
        self._orb_adjacency_controller = WorkflowTabOrbAdjacencyController(
            settings_route_key=SETTINGS_WORKSPACE_ROUTE,
        )
        self._drag_preview_workflow_id: str | None = None
        self._drag_settle_animation: QPropertyAnimation | None = None
        self._reopen_closed_workflow_enabled = False

        self.view = QWidget(self)
        self.hBoxLayout = QHBoxLayout(self.view)
        self.itemLayout = QHBoxLayout()
        self.widgetLayout = QHBoxLayout()
        self.addButton = ReorderableTabToolButton(FluentIcon.ADD, self)
        self.cornerOverlay = WorkflowTabCornerOverlay(self)

        self._initWidget()
        connect_theme_refresh(self, self._apply_theme_styles)

    def _initWidget(self) -> None:
        """Configure scroll area, styles, and add-button wiring."""
        self.setFixedHeight(WORKFLOW_TAB_HEIGHT)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hBoxLayout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        self.addButton.clicked.connect(self._emit_add_requested)
        self.view.setObjectName("view")
        FluentStyleSheet.TAB_VIEW.apply(self)
        FluentStyleSheet.TAB_VIEW.apply(self.view)
        self._initLayout()
        self._syncOrbAdjacentTab(animated=False)
        self._syncCornerOverlay()

    def _initLayout(self) -> None:
        """Apply horizontal layout geometry and spacing."""
        self.hBoxLayout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.itemLayout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.widgetLayout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.itemLayout.setContentsMargins(5, 0, 5, 0)
        self.widgetLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.itemLayout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMinAndMaxSize)
        self.hBoxLayout.setSpacing(0)
        self.itemLayout.setSpacing(0)

        self.hBoxLayout.addLayout(self.itemLayout)
        self.hBoxLayout.addSpacing(3)
        self.widgetLayout.addWidget(self.addButton, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.addLayout(self.widgetLayout)
        self.hBoxLayout.addStretch(1)

    def _createTabItem(
        self,
        text: str,
        icon: QIcon | FluentIconBase | str | None = None,
    ) -> ReorderableTabItemBase:
        """Create workflow tab item."""
        item = TabItem(text, self.view, icon)
        item.set_owning_tab_bar(self)
        item.set_backdrop_mode(self.backdrop_mode)
        return item

    def set_backdrop_mode(self, backdrop_mode: ShellBackdropMode | None) -> None:
        """Apply one backdrop mode across current and future workflow tabs."""

        self.backdrop_mode = backdrop_mode
        for item in self.items:
            if isinstance(item, TabItem):
                item.set_backdrop_mode(backdrop_mode)
        self.cornerOverlay.update()

    def insertTab(
        self,
        index: int,
        routeKey: str,
        text: str,
        icon: QIcon | FluentIconBase | str | None = None,
        onClick: Callable[..., object] | None = None,
    ) -> ReorderableTabItemBase:
        """Insert workflow tab and wire native context-menu behavior."""

        if self.is_settings_route(routeKey):
            raise ValueError("Settings is a shell-owned route, not a workflow tab.")
        item = super().insertTab(index, routeKey, text, icon, onClick)
        if isinstance(item, TabItem):
            item.set_source_text(text)
        item.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        item.installEventFilter(self)
        item.customContextMenuRequested.connect(
            lambda _pos, tab_item=item: self._show_tab_context_menu(tab_item)
        )
        self._syncOrbAdjacentTab(animated=False)
        self._syncCornerOverlay()
        QTimer.singleShot(0, self._sync_tab_visibility_chrome)
        return item

    def is_settings_route(self, route_key: str | None) -> bool:
        """Return whether a route key is the shell-owned Settings route."""

        return route_key == SETTINGS_WORKSPACE_ROUTE

    def selected_route_key(self) -> str | None:
        """Return the route key for the current tab."""

        current = self.currentTab()
        return current.routeKey() if current is not None else None

    def setCurrentIndex(self, index: int) -> None:
        """Select the current workflow tab and refresh overlay geometry."""
        super().setCurrentIndex(index)
        self._syncCornerOverlay()
        self.tabItem(index) if 0 <= index < self.count() else None

    def clear_selection(self) -> None:
        """Clear workflow selection while a non-tab shell route is active."""

        super().clear_selection()
        self._syncCornerOverlay()

    def workflow_ids_in_order(self) -> list[str]:
        """Return current workflow route keys in rendered tab order."""

        return [
            item.routeKey() or ""
            for item in self.items
            if not self.is_settings_route(item.routeKey())
        ]

    def workflow_tab_id_at(self, pos: QPoint) -> str | None:
        """Return the workflow id for the tab at the tab-row position."""

        if not self.itemLayout.geometry().contains(pos):
            return None
        for item in self.items:
            route_key = item.routeKey()
            if route_key is None or self.is_settings_route(route_key):
                continue
            if item.geometry().contains(pos):
                return route_key
        return None

    def workflow_tab_index(self, workflow_id: str) -> int:
        """Return the current rendered index for workflow_id."""

        item = self.itemMap.get(workflow_id)
        if item is None:
            return -1
        return self.items.index(item)

    def is_draggable_workflow_tab(self, workflow_id: str) -> bool:
        """Return whether workflow_id can participate in drag reorder."""

        return (
            self.isMovable()
            and self.count() > 1
            and workflow_id in self.itemMap
            and not self.is_settings_route(workflow_id)
        )

    def workflow_tab_rect_by_id(self, workflow_id: str) -> QRect | None:
        """Return the layout slot rectangle for workflow_id."""

        index = self.workflow_tab_index(workflow_id)
        return self.tabRect(index) if index >= 0 else None

    def workflow_tab_gesture_is_idle(self) -> bool:
        """Return whether workflow tab gesture state is idle."""

        return self._gesture_controller.is_idle()

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select workflow tab by id with optional workflow-intent emission."""

        if self.is_settings_route(workflow_id):
            return
        tab_item = self.itemMap.get(workflow_id)
        if tab_item is None:
            return
        previous = self._suppress_workflow_intent
        self._suppress_workflow_intent = not emit
        try:
            self.setCurrentIndex(self.items.index(tab_item))
        finally:
            self._suppress_workflow_intent = previous
        if emit:
            self.workflowSelected.emit(workflow_id)

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Remove workflow tab by id with optional workflow-intent emission."""

        if self.is_settings_route(workflow_id):
            return
        tab_item = self.itemMap.get(workflow_id)
        if tab_item is None:
            return
        previous = self._suppress_workflow_intent
        self._suppress_workflow_intent = not emit
        try:
            self.removeTab(self.items.index(tab_item))
        finally:
            self._suppress_workflow_intent = previous
        self._syncOrbAdjacentTab(animated=False)

    def setCloseButtonDisplayMode(
        self,
        mode: ReorderableCloseButtonDisplayMode,
    ) -> None:
        """Set workflow close-button mode for all workflow tabs."""

        super().setCloseButtonDisplayMode(mode)

    def setTabVisible(self, index: int, isVisible: bool) -> None:
        """Set workflow tab visibility and enforce orb-adjacent ownership."""

        super().setTabVisible(index, isVisible)
        self._syncOrbAdjacentTab(animated=False)

    def set_workflow_unread_result(self, workflow_id: str, unread: bool) -> None:
        """Update unread-result marker state for one workflow tab."""

        if self.is_settings_route(workflow_id):
            return
        tab_item = self.itemMap.get(workflow_id)
        if isinstance(tab_item, TabItem):
            tab_item.set_unread_result_visible(unread)

    def set_reopen_closed_workflow_enabled(self, enabled: bool) -> None:
        """Set whether the tab-bar context menu can reopen a closed workflow."""

        self._reopen_closed_workflow_enabled = enabled

    def _onTabRenamed(self, tab_item: ReorderableTabItemBase, new_name: str) -> None:
        """Forward inline rename request to workflow manager."""
        old_key = tab_item.routeKey() or ""
        if self.is_settings_route(old_key):
            return
        if isinstance(tab_item, TabItem):
            tab_item.set_source_text(new_name)
        self.tabRenamed.emit(old_key, new_name)
        self.workflowRenameRequested.emit(old_key, new_name)

    def tabText(self, index: int) -> str:
        """Return invariant workflow text rather than its localized projection."""

        item = self.tabItem(index)
        if isinstance(item, TabItem):
            return item.source_text()
        return workflow_tab_source_text(item) if item is not None else ""

    def setTabText(self, index: int, text: str) -> None:
        """Set invariant workflow text and refresh its localized projection."""

        item = self.tabItem(index)
        if isinstance(item, TabItem):
            item.set_source_text(text)
            return
        if item is not None:
            set_workflow_tab_source_text(item, text)

    def _emitBarClicked(self, index: int) -> None:
        """Emit workflow tab clicked signal."""
        self.tabBarClicked.emit(index)

    def _emitCloseRequested(self, index: int) -> None:
        """Emit workflow tab close requested signal."""
        tab_item = self.tabItem(index)
        workflow_id = tab_item.routeKey() if tab_item is not None else None
        if self.is_settings_route(workflow_id):
            return
        self.tabCloseRequested.emit(index)
        if workflow_id:
            self.workflowCloseRequested.emit(workflow_id)

    def _emitCurrentChanged(self, index: int) -> None:
        """Emit workflow current-tab changed signal."""
        self.currentChanged.emit(index)
        if not self._suppress_workflow_intent:
            tab_item = self.tabItem(index)
            workflow_id = tab_item.routeKey() if tab_item is not None else None
            if workflow_id and not self.is_settings_route(workflow_id):
                self.workflowSelected.emit(workflow_id)
        self._syncCornerOverlay()
        self.tabItem(index) if 0 <= index < self.count() else None

    def _emit_add_requested(self) -> None:
        """Emit legacy and workflow-id add intent signals."""

        self.tabAddRequested.emit()
        self.workflowAddRequested.emit()

    def _enforce_orb_adjacent_tab_shape(
        self,
        *,
        animated: bool = False,
        reason: str,
    ) -> None:
        """Synchronize the first visible workflow tab with the orb cutout."""

        del reason
        result = self._orb_adjacency_controller.sync_committed(
            items=tuple(item for item in self.items if isinstance(item, TabItem)),
            previous_route_key=self._orb_adjacent_tab_route_key,
            initialized=self._orb_cutout_sync_initialized,
            animated=animated,
        )
        self._orb_adjacent_tab_route_key = result.route_key
        if result.route_key is not None:
            self._orb_cutout_sync_initialized = True
        else:
            self._orb_cutout_sync_initialized = False
        if result.owner_changed or result.progress_changed:
            self.invalidate_orb_cutout_overlay()

    def _syncOrbAdjacentTab(self, *, animated: bool = False) -> None:
        """Synchronize the first visible workflow tab with the orb cutout."""

        self._enforce_orb_adjacent_tab_shape(
            animated=animated,
            reason="legacy_sync",
        )

    def invalidate_orb_cutout_overlay(self) -> None:
        """Repaint selected-tab corner overlay after an orb cutout tween step."""

        self._corner_overlay_sync_signature = None
        self.cornerOverlay._corner_path_cache_signature = None
        self._syncCornerOverlay()

    def _syncCornerOverlay(self) -> None:
        """Keep selected-corner overlay sized, raised, and repainted."""

        current_index = self.currentIndex()
        current_item = self.tabItem(current_index)
        current_rect = self.tabRect(current_index) if current_item is not None else None
        cutout_progress = (
            current_item.orb_cutout_progress()
            if isinstance(current_item, TabItem)
            else 0.0
        )
        signature = (
            self.selected_route_key(),
            current_index,
            len(self.items),
            self.view.rect().getRect(),
            current_rect.getRect() if current_rect is not None else (),
            current_item.isVisible() if current_item is not None else False,
            cutout_progress,
        )
        if self._corner_overlay_sync_signature == signature:
            return
        self._corner_overlay_sync_signature = signature
        self.cornerOverlay.sync()

    def _apply_theme_styles(self) -> None:
        """Refresh theme-owned overlay surfaces for the workflow tab bar."""

        self.cornerOverlay.update()
        for item in self.items:
            apply_theme_styles = getattr(item, "_apply_theme_styles", None)
            if callable(apply_theme_styles):
                apply_theme_styles()

    def _show_tab_context_menu(self, tab_item: ReorderableTabItemBase) -> None:
        """Show workflow-tab context menu for one concrete tab."""

        self._show_workflow_tab_context_menu(
            tab_item=tab_item,
            global_pos=QCursor.pos(),
        )

    def _show_workflow_tab_context_menu(
        self,
        *,
        tab_item: ReorderableTabItemBase | None,
        global_pos: QPoint,
    ) -> None:
        """Show workflow tab-bar context commands for tab or empty-row space."""

        self.cancel_tab_drag()
        if tab_item is not None:
            if tab_item not in self.items:
                return
            if self.is_settings_route(tab_item.routeKey()):
                return

        entries: list[MenuEntry] = []
        if tab_item is not None:
            entries.extend(
                (
                    MenuItem(
                        "workflow_tab.rename",
                        app_text("Rename"),
                        callback=tab_item._startRename,
                        icon=FIF.EDIT,
                    ),
                    MenuItem(
                        "workflow_tab.duplicate",
                        app_text("Duplicate"),
                        callback=lambda item=tab_item: self._emit_duplicate_requested(
                            item
                        ),
                        icon=FIF.COPY,
                    ),
                    MenuSeparator(),
                )
            )
        entries.append(
            MenuItem(
                "workflow_tab.reopen_closed",
                REOPEN_CLOSED_WORKFLOW_MENU_TEXT,
                callback=self._emit_reopen_closed_workflow_requested,
                enabled=self._reopen_closed_workflow_enabled,
                icon=FIF.HISTORY,
            )
        )
        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(entries=tuple(entries))
        )
        menu.exec(global_pos)

    def _emit_duplicate_requested(self, tab_item: ReorderableTabItemBase) -> None:
        """Emit duplicate intent for one workflow tab item."""

        workflow_id = tab_item.routeKey()
        if workflow_id and not self.is_settings_route(workflow_id):
            self.workflowDuplicateRequested.emit(workflow_id)

    def _emit_reopen_closed_workflow_requested(self, *_args: object) -> None:
        """Emit reopen intent only while a closed workflow is available."""

        if self._reopen_closed_workflow_enabled:
            self.workflowReopenClosedRequested.emit()

    def _onTabRemoved(self, route_key: str) -> None:
        """Clean up qrouter registration for removed route key."""
        qrouter.remove(route_key)
        self._syncCornerOverlay()

    def paintEvent(self, event: QMouseEvent) -> None:
        """Draw tab separators between non-hovered neighboring items."""
        painter = QPainter(self.viewport())
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        color = QColor(255, 255, 255, 21) if isDarkTheme() else QColor(0, 0, 0, 15)
        painter.setPen(color)

        for i, item in enumerate(self.items[:-1]):
            nextItem = self.items[i + 1]
            canDraw = not (
                item.isHover
                or item.isSelected
                or nextItem.isHover
                or nextItem.isSelected
            )

            if canDraw:
                x = item.geometry().right()
                y = self.height() // 2 - 8
                painter.drawLine(x, y, x, y + 16)

        super().paintEvent(event)

    def resizeEvent(self, event: object) -> None:
        """Resize the overlay with the tab bar/view geometry."""
        super().resizeEvent(event)
        self._syncCornerOverlay()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route workflow tab item mouse events through the tab gesture owner."""

        if isinstance(watched, TabItem) and watched in self.items:
            if event.type() in {
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.ShowToParent,
                QEvent.Type.HideToParent,
            }:
                QTimer.singleShot(0, self._sync_tab_visibility_chrome)
            if isinstance(event, QMouseEvent):
                self._handle_tab_mouse_event(
                    self._tab_item_mouse_event(watched, event),
                    select_on_press=False,
                )
        return super().eventFilter(watched, event)

    def _sync_tab_visibility_chrome(self) -> None:
        """Repair first-tab orb ownership after Qt commits tab visibility changes."""

        self._syncOrbAdjacentTab(animated=False)
        self._syncCornerOverlay()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Delegate tab-row press handling to the workflow gesture controller."""
        if event.button() == Qt.MouseButton.RightButton:
            pos = event.position().toPoint()
            if self.workflow_tab_id_at(pos) is None:
                self._show_workflow_tab_context_menu(
                    tab_item=None,
                    global_pos=self.mapToGlobal(pos),
                )
                event.accept()
                return
        super().mousePressEvent(event)
        self._handle_tab_mouse_event(event, select_on_press=True)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Delegate tab-row movement to the workflow gesture controller."""
        super().mouseMoveEvent(event)
        self._handle_tab_mouse_event(event, select_on_press=False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Delegate tab-row release handling to the workflow gesture controller."""
        super().mouseReleaseEvent(event)
        self._handle_tab_mouse_event(event, select_on_press=False)

    def cancel_tab_drag(self) -> None:
        """Cancel any active workflow-tab drag preview and return to idle."""

        self._gesture_controller.cancel()
        self._reorder_controller.clear_preview()
        if self._drag_preview_workflow_id is not None:
            self._drag_preview_presenter.cancel(
                items_by_workflow_id=self._workflow_tab_items_by_id(),
                committed_order=tuple(self.workflow_ids_in_order()),
                slot_rects=self._workflow_tab_slot_rects(),
            )
            self._syncOrbAdjacentTab(animated=True)
        self._drag_preview_workflow_id = None

    def move_workflow_tab(
        self,
        workflow_id: str,
        target_index: int,
        *,
        animated: bool = False,
    ) -> None:
        """Move one workflow tab to target_index after a validated drag gesture."""

        item = self.itemMap.get(workflow_id)
        if item is None or self.is_settings_route(workflow_id):
            return
        old_index = self.items.index(item)
        clamped_target = max(0, min(target_index, len(self.items) - 1))
        if old_index == clamped_target:
            self._settle_workflow_tab(workflow_id)
            return

        current_tab = self.currentTab()
        self.items.pop(old_index)
        self.items.insert(clamped_target, item)
        if current_tab in self.items:
            self._currentIndex = self.items.index(current_tab)
        else:
            self._currentIndex = min(clamped_target, len(self.items) - 1)
        if animated:
            self._syncOrbAdjacentTab(animated=True)
            self._drag_preview_presenter.settle_to_committed_order(
                items_by_workflow_id=self._workflow_tab_items_by_id(),
                committed_order=tuple(self.workflow_ids_in_order()),
                slot_rects=self._workflow_tab_slot_rects(),
            )
            self._connect_drag_settle_cleanup(workflow_id)
        else:
            self._adjustLayout()
        self._syncCornerOverlay()

    def _handle_tab_mouse_event(
        self,
        event: QMouseEvent,
        *,
        select_on_press: bool,
    ) -> None:
        """Apply one tab-row mouse event through explicit gesture results."""

        if event.type() == QEvent.Type.MouseButtonPress:
            if select_on_press and event.button() == Qt.MouseButton.LeftButton:
                workflow_id = self.workflow_tab_id_at(event.position().toPoint())
                if workflow_id is not None:
                    self._select_workflow_tab_from_press(workflow_id)
            result = self._gesture_controller.handle_mouse_press(event)
        elif event.type() == QEvent.Type.MouseMove:
            result = self._gesture_controller.handle_mouse_move(event)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            result = self._gesture_controller.handle_mouse_release(event)
        else:
            return

        self._apply_gesture_result(result)

    def _apply_gesture_result(self, result: WorkflowTabGestureResult) -> None:
        """Apply semantic gesture output to preview or commit tab reorder."""

        if result.kind == WorkflowTabGestureResultKind.NONE:
            return
        if result.kind == WorkflowTabGestureResultKind.DRAG_CANCELLED:
            self.cancel_tab_drag()
            return
        if (
            result.workflow_id is None
            or result.origin_index is None
            or result.current_pos is None
        ):
            return

        if result.kind in {
            WorkflowTabGestureResultKind.DRAG_STARTED,
            WorkflowTabGestureResultKind.DRAG_UPDATED,
        }:
            preview = self._reorder_controller.preview(
                workflow_id=result.workflow_id,
                origin_index=result.origin_index,
                pointer_pos=result.current_pos,
            )
            self._preview_workflow_tab_drag(preview, result.press_pos)
            return

        if result.kind == WorkflowTabGestureResultKind.DRAG_FINISHED:
            command = self._reorder_controller.finish(
                workflow_id=result.workflow_id,
                origin_index=result.origin_index,
                pointer_pos=result.current_pos,
            )
            self._drag_preview_workflow_id = None
            if command is None:
                self._settle_workflow_tab(result.workflow_id)
            else:
                self.move_workflow_tab(
                    command.workflow_id,
                    command.target_index,
                    animated=True,
                )

    def _preview_workflow_tab_drag(
        self,
        preview: WorkflowTabReorderPreview,
        press_pos: QPoint | None,
    ) -> None:
        """Move the dragged tab as a visual preview without mutating order."""

        item = self.itemMap.get(preview.workflow_id)
        if item is None or press_pos is None:
            return

        preview_state = self._drag_preview_presenter.preview(
            items_by_workflow_id=self._workflow_tab_items_by_id(),
            committed_order=tuple(self.workflow_ids_in_order()),
            preview_order=preview.preview_order,
            dragged_workflow_id=preview.workflow_id,
            pointer_pos=preview.pointer_pos,
            press_pos=press_pos,
            slot_rects=self._workflow_tab_slot_rects(),
        )
        self._orb_adjacent_tab_route_key = preview_state.orb_adjacent_route_key
        self._orb_cutout_sync_initialized = (
            preview_state.orb_adjacent_route_key is not None
        )
        self.invalidate_orb_cutout_overlay()
        self._drag_preview_workflow_id = preview.workflow_id
        self._syncCornerOverlay()

    def _workflow_tab_items_by_id(self) -> dict[str, TabItem]:
        """Return visible workflow tab items keyed by route id."""

        result: dict[str, TabItem] = {}
        for item in self.items:
            if not isinstance(item, TabItem):
                continue
            route_key = item.routeKey()
            if route_key and not self.is_settings_route(route_key):
                result[route_key] = item
        return result

    def _workflow_tab_slot_rects(self) -> tuple[QRect, ...]:
        """Return committed workflow tab slots in workflow order."""

        return tuple(
            rect
            for index in range(self.count())
            if (rect := self.tabRect(index)) is not None
        )

    def _settle_workflow_tab(self, workflow_id: str) -> None:
        """Return one workflow tab to its current layout slot."""

        item = self.itemMap.get(workflow_id)
        rect = self.workflow_tab_rect_by_id(workflow_id)
        if item is None or rect is None:
            return
        item.move(rect.x(), item.y())
        self._adjustLayout()
        self._syncCornerOverlay()

    def _connect_drag_settle_cleanup(self, workflow_id: str) -> None:
        """Normalize layout after the animated drag-release settle completes."""

        item = self.itemMap.get(workflow_id)
        if not isinstance(item, TabItem):
            self._adjustLayout()
            return

        if self._drag_settle_animation is not None:
            try:
                self._drag_settle_animation.finished.disconnect(
                    self._finish_drag_settle_cleanup
                )
            except RuntimeError:
                pass
        self._drag_settle_animation = item.slideAni
        item.slideAni.finished.connect(self._finish_drag_settle_cleanup)

    def _finish_drag_settle_cleanup(self) -> None:
        """Clean up layout after an animated workflow-tab move settles."""

        if self._drag_settle_animation is not None:
            try:
                self._drag_settle_animation.finished.disconnect(
                    self._finish_drag_settle_cleanup
                )
            except RuntimeError:
                pass
            self._drag_settle_animation = None
        self._adjustLayout()

    def _select_workflow_tab_from_press(self, workflow_id: str) -> None:
        """Apply normal tab selection semantics for direct tab-bar presses."""

        item = self.itemMap.get(workflow_id)
        if item is None:
            return
        for tab_item in self.items:
            tab_item.setSelected(tab_item is item)

        index = self.items.index(item)
        self._emitBarClicked(index)
        if index != self.currentIndex():
            self.setCurrentIndex(index)
            self._emitCurrentChanged(index)

    def _tab_item_mouse_event(
        self,
        tab_item: TabItem,
        event: QMouseEvent,
    ) -> QMouseEvent:
        """Return a tab-row-local mouse event for a child tab item event."""

        pos = tab_item.mapTo(self.view, event.position().toPoint())
        return QMouseEvent(
            event.type(),
            QPointF(pos),
            event.button(),
            event.buttons(),
            event.modifiers(),
        )

    def _adjustLayout(self) -> None:
        """Rebuild item layout order and enforce committed orb ownership."""

        for item in self.items:
            self.itemLayout.removeWidget(item)
        for item in self.items:
            self.itemLayout.addWidget(item)
        self._syncOrbAdjacentTab(animated=False)
        self._syncCornerOverlay()

    def _swapItem(self, index: int) -> None:
        """Legacy helper for direct swap tests; drag preview uses the presenter."""
        swappedItem = self.tabItem(index)
        current_item = self.tabItem(self.currentIndex())
        if self.is_settings_route(swappedItem.routeKey() if swappedItem else None):
            return
        if self.is_settings_route(current_item.routeKey() if current_item else None):
            return
        rect = self.tabRect(self.currentIndex())
        if swappedItem is None or rect is None:
            return

        self.items[self.currentIndex()], self.items[index] = (
            self.items[index],
            self.items[self.currentIndex()],
        )
        self._currentIndex = index
        swappedItem.slideTo(rect.x())
        # Drag-preview swaps are the one intentionally animated ownership transition.
        self._syncOrbAdjacentTab(animated=True)
        self._syncCornerOverlay()


__all__ = [
    "REOPEN_CLOSED_WORKFLOW_MENU_TEXT",
    "SETTINGS_WORKSPACE_ROUTE",
    "TabBar",
    "TabCloseButtonDisplayMode",
    "TabItem",
    "WorkflowTabCornerOverlay",
    "set_workflow_tab_source_text",
    "workflow_tab_source_text",
]
