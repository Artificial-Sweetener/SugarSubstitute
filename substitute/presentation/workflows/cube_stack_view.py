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

"""Cube-stack presentation view built on shared reorderable-tab primitives."""
# mypy: disable-error-code=attr-defined

from __future__ import annotations

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Property, QEvent, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QWheelEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIconBase,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    FluentStyleSheet,
    isDarkTheme,
    setCustomStyleSheet,
)
from shiboken6 import isValid

from substitute.presentation.motion import (
    CUBE_STACK_INDICATOR_DURATION_MS,
    TRANSFORM_EASING_CURVE,
)
from substitute.presentation.cubes.cube_card_visual import (
    CubeCardIssueSeverity,
)
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_BUTTON_SIZE,
    CUBE_ITEM_CLOSE_TEXT_RESERVE,
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
    CUBE_ITEM_ICON_INSET_EXPANDED,
    CUBE_ITEM_ICON_SIZE_COMPACT,
    CUBE_ITEM_ICON_SIZE_EXPANDED,
    CUBE_ITEM_ICON_X,
    CUBE_ITEM_TEXT_BLOCK_HEIGHT,
    CUBE_ITEM_TEXT_GAP_EXPANDED,
    CUBE_ITEM_TEXT_PRIMARY_HEIGHT,
    CUBE_ITEM_TEXT_ROW_OVERLAP,
    CUBE_ITEM_TEXT_SECONDARY_HEIGHT,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EDGE_INSET,
    CUBE_STACK_EXPANDED_WIDTH,
    CUBE_STACK_ITEM_SPACING,
)
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableCloseButtonDisplayMode,
    ReorderableTabBarBase,
    ReorderableTabItemBase,
)
from substitute.presentation.workflows.cube_item import CubeItem
from substitute.presentation.workflows.cube_stack_indicator_overlay import (
    CubeStackIndicatorOverlay,
)
from substitute.presentation.workflows.cube_stack_presentation_geometry import (
    CubeStackPresentationGeometry,
)

CubeCloseButtonDisplayMode = ReorderableCloseButtonDisplayMode

_STACK_TRANSPARENCY_QSS = "CubeStack { background-color: transparent; border: none; }"
_STACK_VIEW_TRANSPARENCY_QSS = (
    "QWidget#view { background-color: transparent; border: none; }"
)


class CubeStack(ReorderableTabBarBase):
    """Display and reorder cube aliases in a vertical stack."""

    currentCubeChanged = Signal(int)
    dragStarted = Signal()
    cubeBarClicked = Signal(int)
    cubeCloseRequested = Signal(int)
    cubeAddRequested = Signal()
    cubeRenameEditRequested = Signal(str)
    cubeRenameRequested = Signal(str, str)
    cubeDuplicateRequested = Signal(str)
    cubeBypassToggleRequested = Signal(str)
    cubeOutputPersistenceToggleRequested = Signal(str)
    aliasEditingFinished = Signal(str)
    cubeMoved = Signal(int, int)
    cubeMoveFinished = Signal()
    tabMouseReleased = Signal(int)
    cubeStackWheelRerouteRequested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create vertical cube stack view."""
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self._initCommonState()
        self._indicatorY = 0
        self._indicator_realign_pending = False
        self._indicator_realign_timer = QTimer(self)
        self._indicator_realign_timer.setSingleShot(True)
        self._indicator_realign_timer.timeout.connect(self._complete_indicator_realign)

        from PySide6.QtCore import QPropertyAnimation

        self.slideAni = QPropertyAnimation(self, b"indicatorY", self)

        self.view = QWidget(self)
        self.hBoxLayout = QVBoxLayout(self.view)
        self.itemLayout = QVBoxLayout()
        self.widgetLayout = QVBoxLayout()
        self.addPlaceholder = CubePlaceholderCard(
            self.view,
            plus_visible=True,
            interactive=True,
        )
        self.addPlaceholder.setObjectName("cubeStackAddPlaceholder")
        self.indicatorOverlay = CubeStackIndicatorOverlay(self)
        self._presentation_geometry = CubeStackPresentationGeometry(
            stack=self,
            items=lambda: tuple(self.items),
            set_stack_width=self.setFixedWidth,
            set_placeholder_compact=self.addPlaceholder.setCompact,
            set_placeholder_progress=self.addPlaceholder.setCompactProgress,
            sync_indicator=self._sync_indicator_overlay,
            schedule_indicator_realign=self._schedule_indicator_realign,
        )

        self._initWidget()

    def _initWidget(self) -> None:
        """Configure scroll area, styles, and add-button wiring."""
        self.setFixedWidth(CUBE_STACK_EXPANDED_WIDTH)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hBoxLayout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        self.addPlaceholder.activated.connect(self.cubeAddRequested)
        self.view.setObjectName("view")
        FluentStyleSheet.TAB_VIEW.apply(self)
        FluentStyleSheet.TAB_VIEW.apply(self.view)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        setCustomStyleSheet(
            self,
            _STACK_TRANSPARENCY_QSS,
            _STACK_TRANSPARENCY_QSS,
        )
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setStyleSheet("background-color: transparent; border: none;")
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        setCustomStyleSheet(
            self.view,
            _STACK_VIEW_TRANSPARENCY_QSS,
            _STACK_VIEW_TRANSPARENCY_QSS,
        )
        self.addPlaceholder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._initLayout()

    def _initLayout(self) -> None:
        """Apply vertical layout geometry and spacing."""
        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.itemLayout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.widgetLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.itemLayout.setContentsMargins(
            CUBE_STACK_EDGE_INSET,
            0,
            CUBE_STACK_EDGE_INSET,
            0,
        )
        self.widgetLayout.setContentsMargins(
            CUBE_STACK_EDGE_INSET,
            0,
            CUBE_STACK_EDGE_INSET,
            0,
        )
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.itemLayout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMinAndMaxSize)
        self.hBoxLayout.setSpacing(0)
        self.itemLayout.setSpacing(CUBE_STACK_ITEM_SPACING)
        self.widgetLayout.setSpacing(0)

        self.hBoxLayout.addLayout(self.itemLayout)
        self.hBoxLayout.addSpacing(3)
        self.widgetLayout.addWidget(
            self.addPlaceholder,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        self.hBoxLayout.addLayout(self.widgetLayout)
        self.hBoxLayout.addStretch(1)
        self.addPlaceholder.setCompact(False)
        self._sync_indicator_overlay()

    def _createTabItem(
        self,
        text: str,
        icon: FluentIconBase | str | None = None,
    ) -> ReorderableTabItemBase:
        """Create cube-stack item."""
        item = CubeItem(text, self.view, icon)
        item.setCompact(self._presentation_geometry.compact)
        return item

    def _onAliasEditRequested(self, tab_item: CubeItem) -> None:
        """Forward an alias-edit request with the current route key."""

        route_key = tab_item.routeKey() or ""
        if route_key:
            self.cubeRenameEditRequested.emit(route_key)

    def _onAliasEditingFinished(self, route_key: str) -> None:
        """Forward alias-edit completion for shell-level compact restoration."""

        if route_key:
            self.aliasEditingFinished.emit(route_key)

    def _onBypassToggleRequested(self, tab_item: CubeItem) -> None:
        """Forward a bypass-toggle request with the current route key."""

        route_key = tab_item.routeKey() or ""
        if route_key:
            self.cubeBypassToggleRequested.emit(route_key)

    def _onOutputPersistenceToggleRequested(self, tab_item: CubeItem) -> None:
        """Forward an output-persistence request with the cube route key."""

        route_key = tab_item.routeKey() or ""
        if route_key:
            self.cubeOutputPersistenceToggleRequested.emit(route_key)

    def _onDuplicateRequested(self, tab_item: CubeItem) -> None:
        """Forward a duplicate request with the current route key."""

        route_key = tab_item.routeKey() or ""
        if route_key:
            self.cubeDuplicateRequested.emit(route_key)

    def _onTabRenamed(self, tab_item: ReorderableTabItemBase, new_name: str) -> None:
        """Forward one inline rename request without resolving alias policy locally."""
        old_key = tab_item.routeKey() or ""
        self.cubeRenameRequested.emit(old_key, new_name)

    def _emitBarClicked(self, index: int) -> None:
        """Emit cube bar clicked signal."""
        self.cubeBarClicked.emit(index)

    def _emitCloseRequested(self, index: int) -> None:
        """Emit cube close requested signal."""
        self.cubeCloseRequested.emit(index)

    def _emitCurrentChanged(self, index: int) -> None:
        """Emit cube current-changed signal."""
        self.currentCubeChanged.emit(index)

    def insertTab(
        self,
        index: int,
        routeKey: str,
        text: str,
        icon: QIcon | FluentIconBase | str | None = None,
        onClick: Callable[..., object] | None = None,
    ) -> ReorderableTabItemBase:
        """Insert one cube tab and schedule post-layout indicator alignment."""

        item = super().insertTab(index, routeKey, text, icon, onClick)
        if isinstance(item, CubeItem):
            item.aliasEditRequested.connect(self._onAliasEditRequested)
            item.aliasEditingFinished.connect(self._onAliasEditingFinished)
            item.duplicateRequested.connect(self._onDuplicateRequested)
            item.bypassToggleRequested.connect(self._onBypassToggleRequested)
            item.outputPersistenceToggleRequested.connect(
                self._onOutputPersistenceToggleRequested
            )
        self._presentation_geometry.apply_item(item)
        self._schedule_indicator_realign()
        return item

    def begin_alias_editing(self, route_key: str) -> bool:
        """Begin inline alias editing for one expanded cube tab."""

        tab_item = self.itemMap.get(route_key)
        if not isinstance(tab_item, CubeItem):
            return False
        return tab_item.begin_alias_editing()

    def removeTab(self, index: int) -> None:
        """Remove one cube tab and schedule post-layout indicator alignment."""

        super().removeTab(index)
        self._schedule_indicator_realign()

    def setTabText(self, index: int, text: str) -> None:
        """Set tab text and schedule post-layout indicator alignment."""

        super().setTabText(index, text)
        self._schedule_indicator_realign()

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Set all display text for one cube tab."""

        if not 0 <= index < len(self.items):
            return
        item = self.items[index]
        item.setText(primary_text)
        set_fluent_tooltip_text(item, tooltip_text)
        if isinstance(item, CubeItem):
            item.setSecondaryText(secondary_text)
        self._schedule_indicator_realign()

    def setTabIssueSeverity(
        self,
        route_key: str,
        severity: CubeCardIssueSeverity | str | None,
    ) -> None:
        """Apply issue severity to one tab by route key."""

        item = self.itemMap.get(route_key)
        if isinstance(item, CubeItem):
            item.setIssueSeverity(severity)

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Apply cube-level bypass presentation state to one tab."""

        if not 0 <= index < len(self.items):
            return
        item = self.items[index]
        if isinstance(item, CubeItem):
            item.setBypassed(bypassed)

    def setTabOutputPersistenceEnabled(self, index: int, enabled: bool) -> None:
        """Apply workflow-local output persistence state to one cube tab."""

        if not 0 <= index < len(self.items):
            return
        item = self.items[index]
        if isinstance(item, CubeItem):
            item.setOutputPersistenceEnabled(enabled)

    def setCompact(self, compact: bool) -> None:
        """Toggle icons-only stack presentation."""

        self._presentation_geometry.set_compact(compact)

    def isCompact(self) -> bool:
        """Return whether the stack is in icons-only mode."""

        return self._presentation_geometry.compact

    def beginCompactTransition(self, target_compact: bool) -> None:
        """Prepare stack items for an animated compact-mode transition."""

        self._presentation_geometry.begin_transition(target_compact)

    def applyCompactTransition(
        self,
        *,
        stack_width: int,
        item_width: int,
        compact_progress: float,
    ) -> None:
        """Apply one frame of compact-mode transition geometry."""

        self._presentation_geometry.apply_frame(
            stack_width=stack_width,
            item_width=item_width,
            compact_progress=compact_progress,
        )

    def finishCompactTransition(self, target_compact: bool) -> None:
        """Commit final compact-mode state after immediate or animated changes."""

        self._presentation_geometry.finish_transition(target_compact)

    def setTabIcon(self, index: int, icon: QIcon | FluentIconBase | str) -> None:
        """Set tab icon and schedule post-layout indicator alignment."""

        super().setTabIcon(index, icon)
        self._schedule_indicator_realign()

    def clear(self) -> None:
        """Remove all cube tabs from the stack."""
        while self.count() > 0:
            self.removeTab(0)

    def select_cube(self, route_key: str, *, animated: bool = True) -> None:
        """Select one cube tab by route key and synchronize selection visuals."""

        tab_item = self.itemMap.get(route_key)
        if tab_item is None:
            return
        try:
            index = self.items.index(tab_item)
        except ValueError:
            return
        self._select_index(index, animate_indicator=animated)

    def reorder_by_route_keys(self, route_keys: list[str]) -> None:
        """Project tab order from validated route keys while preserving widgets."""

        if len(route_keys) != len(self.items):
            return
        ordered_items = [self.itemMap.get(route_key) for route_key in route_keys]
        if any(item is None for item in ordered_items):
            return
        current_route_key = None
        current_tab = self.currentTab()
        if current_tab is not None:
            current_route_key = current_tab.routeKey()

        self.items = cast(list[ReorderableTabItemBase], ordered_items)
        for item in self.items:
            self.itemLayout.removeWidget(item)
        for item in self.items:
            self.itemLayout.addWidget(item)

        if current_route_key in route_keys:
            self._currentIndex = route_keys.index(cast(str, current_route_key))
        elif self.items:
            self._currentIndex = min(self._currentIndex, len(self.items) - 1)
        else:
            self._currentIndex = -1

        for index, item in enumerate(self.items):
            item.setSelected(index == self._currentIndex)
        self._schedule_indicator_realign()

    def setCurrentIndex(self, index: int) -> None:
        """Set current index and animate indicator to selected cube tab."""
        self._select_index(index, animate_indicator=True)

    def _select_index(self, index: int, *, animate_indicator: bool) -> None:
        """Select one index and align the indicator from current geometry."""

        if not 0 <= index < len(self.items):
            return

        current_index = self.currentIndex()
        if index != self._currentIndex and 0 <= current_index < len(self.items):
            self.items[current_index].setSelected(False)

        self._currentIndex = index
        self.items[index].setSelected(True)
        self._sync_indicator_to_current(animated=animate_indicator)
        self._sync_indicator_overlay()

    def realign_indicator(self, *, animated: bool = False) -> None:
        """Align the indicator to the current tab using current widget geometry."""

        self._sync_indicator_to_current(animated=animated)

    def _sync_indicator_to_current(self, *, animated: bool) -> None:
        """Move the indicator to the current tab's current layout position."""

        item = self.currentTab()
        if item is None:
            return
        target_y = item.y() + item.height() // 2 - 8
        self.slideAni.stop()
        if animated:
            self.slideAni.setEndValue(target_y)
            self.slideAni.setDuration(CUBE_STACK_INDICATOR_DURATION_MS)
            self.slideAni.setEasingCurve(TRANSFORM_EASING_CURVE)
            self.slideAni.start()
            return
        self.setIndicatorY(target_y)

    def _schedule_indicator_realign(self) -> None:
        """Realign the selected indicator after pending Qt layout work completes."""

        if self._indicator_realign_pending:
            return
        self._indicator_realign_pending = True
        self._indicator_realign_timer.start(0)

    def _complete_indicator_realign(self) -> None:
        """Complete a pending indicator realignment after layout activation."""

        self._indicator_realign_pending = False
        if not isValid(self.view):
            return
        layout = self.view.layout()
        if layout is not None:
            layout.activate()
        item_layout_activate = getattr(self.itemLayout, "activate", None)
        if callable(item_layout_activate):
            item_layout_activate()
        self.realign_indicator(animated=False)
        self._sync_indicator_overlay()

    def _onItemPressed(self) -> None:
        """Handle cube item click while guarding against stale senders."""
        sender = self.sender()
        if sender not in self.items:
            return

        for item in self.items:
            item.setSelected(item is sender)

        index = self.items.index(sender)
        self.cubeBarClicked.emit(index)

        if index != self.currentIndex():
            self.setCurrentIndex(index)
            self.currentCubeChanged.emit(index)

    def paintEvent(self, event: QMouseEvent) -> None:
        """Draw horizontal separators for stack items."""
        painter = QPainter(self.viewport())
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        color = QColor(255, 255, 255, 21) if isDarkTheme() else QColor(0, 0, 0, 15)
        painter.setPen(color)

        for i, item in enumerate(self.items):
            canDraw = not (item.isHover or item.isSelected)
            if i < len(self.items) - 1:
                nextItem = self.items[i + 1]
                if nextItem.isHover or nextItem.isSelected:
                    canDraw = False

            if canDraw:
                x = self.width() // 2 - 8
                y = item.geometry().bottom()
                painter.drawLine(x, y, x + 16, y)

        super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Capture drag start position when vertical reorder is allowed."""
        super().mousePressEvent(event)
        if (
            not self.isMovable()
            or event.button() != Qt.MouseButton.LeftButton
            or not self.itemLayout.geometry().contains(event.pos())
        ):
            return

        self.dragPos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle live vertical drag/reorder and indicator tracking."""
        super().mouseMoveEvent(event)

        if (
            not self.isMovable()
            or self.count() <= 1
            or not self.itemLayout.geometry().contains(event.pos())
        ):
            return

        if not self.isDraging:
            self.dragStarted.emit()

        index = self.currentIndex()
        item = self.tabItem(index)
        if item is None:
            return

        new_y = item.y() + (event.pos().y() - self.dragPos.y())
        self.dragPos = event.pos()

        slot_centers = [w.y() + w.height() // 2 for w in self.items]
        dragged_center = new_y + item.height() // 2
        target_index = min(
            range(len(slot_centers)),
            key=lambda i: abs(slot_centers[i] - dragged_center),
        )

        if target_index != index:
            item_widget = cast(QWidget, item)
            self.items.insert(target_index, self.items.pop(index))
            self._currentIndex = target_index
            self.itemLayout.removeWidget(item_widget)
            self.itemLayout.insertWidget(target_index, item_widget)
            layout = self.view.layout()
            if layout is not None:
                layout.activate()

        y = 0
        for stack_item in self.items:
            if stack_item is item:
                stack_item.move(stack_item.x(), new_y)
                self.setIndicatorY(new_y + stack_item.height() // 2 - 8)
            else:
                stack_item.move(stack_item.x(), y)
            y += stack_item.height()

        self.isDraging = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finalize drag order and emit post-drag synchronization signals."""
        super().mouseReleaseEvent(event)
        current_index = self.currentIndex()

        if not self.isMovable() or not self.isDraging:
            self.tabMouseReleased.emit(current_index)
            return

        self.isDraging = False

        item = self.tabItem(current_index)
        rect = self.tabRect(current_index)
        if item is None or rect is None:
            self.tabMouseReleased.emit(current_index)
            return

        y = rect.y()
        duration = int(abs(item.y() - y) * 250 / max(1, item.height()))
        item.slideToY(y, duration)

        self.slideAni.stop()
        self.slideAni.setEndValue(y + item.height() // 2 - 8)
        self.slideAni.setDuration(duration)
        self.slideAni.setEasingCurve(TRANSFORM_EASING_CURVE)
        self.slideAni.start()

        self._adjustLayout()
        self.viewport().update()

        self.cubeMoveFinished.emit()
        self.tabMouseReleased.emit(current_index)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Own wheel input only when cube-stack content can scroll."""

        scroll_bar = self.verticalScrollBar()
        if scroll_bar.maximum() > scroll_bar.minimum():
            super().wheelEvent(event)
            event.accept()
            return
        self.cubeStackWheelRerouteRequested.emit(event)
        event.accept()

    def _adjustLayout(self) -> None:
        """Normalize layout order and animate moved tabs into slot positions."""
        sender = self.sender()
        try:
            if sender is not None:
                sender.finished.disconnect()
        except Exception:
            pass

        for item in self.items:
            self.itemLayout.removeWidget(item)
        for item in self.items:
            self.itemLayout.addWidget(item)

        layout = self.view.layout()
        if layout is not None:
            layout.activate()
        for item in self.items:
            target_y = item.pos().y()
            if item.y() != target_y:
                duration = int(abs(item.y() - target_y) * 250 / max(1, item.height()))
                item.slideToY(target_y, duration)
        self._schedule_indicator_realign()

    def _swapItem(self, index: int) -> None:
        """Swap selected tab with sibling and emit current cube-moved signal payload."""
        swappedItem = self.tabItem(index)
        rect = self.tabRect(self.currentIndex())
        if swappedItem is None or rect is None:
            return

        self.items[self.currentIndex()], self.items[index] = (
            self.items[index],
            self.items[self.currentIndex()],
        )
        self._currentIndex = index
        swappedItem.slideToY(rect.y())
        self.cubeMoved.emit(self.currentIndex(), index)

    def _getIndicatorY(self) -> int:
        """Return active indicator Y coordinate."""
        return self._indicatorY

    def setIndicatorY(self, y: int) -> None:
        """Set active indicator Y coordinate and refresh the overlay."""
        self._indicatorY = y
        self.indicatorOverlay.update()

    def _sync_indicator_overlay(self) -> None:
        """Keep the indicator overlay aligned with the viewport layer."""

        self.indicatorOverlay.sync()

    def showEvent(self, event: object) -> None:
        """Initialize indicator position once layout is finalized."""
        super().showEvent(event)
        self._sync_indicator_overlay()
        self._schedule_indicator_realign()

    def resizeEvent(self, event: object) -> None:
        """Realign presentation geometry after stack viewport changes."""

        super().resizeEvent(event)
        self._sync_indicator_overlay()
        self._schedule_indicator_realign()

    def event(self, event: object) -> bool:
        """Schedule geometry realignment for relevant layout changes."""

        if event.type() in {QEvent.Type.LayoutRequest, QEvent.Type.Show}:
            self._schedule_indicator_realign()
        return super().event(event)

    def _adjustIndicatorPos(self) -> None:
        """Align indicator to current tab without animation."""
        self.realign_indicator(animated=False)

    indicatorY = Property(int, _getIndicatorY, setIndicatorY)


__all__ = [
    "CUBE_ITEM_COMPACT_WIDTH",
    "CUBE_ITEM_CLOSE_BUTTON_SIZE",
    "CUBE_ITEM_CLOSE_TEXT_RESERVE",
    "CUBE_ITEM_EXPANDED_WIDTH",
    "CUBE_ITEM_HEIGHT",
    "CUBE_ITEM_ICON_INSET_EXPANDED",
    "CUBE_ITEM_ICON_SIZE_COMPACT",
    "CUBE_ITEM_ICON_SIZE_EXPANDED",
    "CUBE_ITEM_ICON_X",
    "CUBE_ITEM_TEXT_BLOCK_HEIGHT",
    "CUBE_ITEM_TEXT_GAP_EXPANDED",
    "CUBE_ITEM_TEXT_PRIMARY_HEIGHT",
    "CUBE_ITEM_TEXT_ROW_OVERLAP",
    "CUBE_ITEM_TEXT_SECONDARY_HEIGHT",
    "CUBE_STACK_COMPACT_WIDTH",
    "CUBE_STACK_EDGE_INSET",
    "CUBE_STACK_EXPANDED_WIDTH",
    "CubeCloseButtonDisplayMode",
    "CubeCardIssueSeverity",
    "CubeStack",
]
