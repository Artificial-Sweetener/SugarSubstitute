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

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Property, QEvent, QPoint, QRectF, QSize, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QWheelEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIcon,
    FluentIconBase,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    FluentStyleSheet,
    isDarkTheme,
)
from qfluentwidgets.common.color import themeColor  # type: ignore[import-untyped]

from substitute.presentation.motion import (
    CUBE_STACK_INDICATOR_DURATION_MS,
    TRANSFORM_EASING_CURVE,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
)
from substitute.presentation.cubes.cube_card_visual import (
    CubeCardIssueSeverity,
    CubeCardVisual,
    CubeCardVisualState,
)
from substitute.presentation.cubes.cube_alias_editor import CubeAliasEditor
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
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableCloseButtonDisplayMode,
    ReorderableTabBarBase,
    ReorderableTabItemBase,
)
from substitute.presentation.workflows.cube_stack_geometry_trace import (
    log_cube_item_icon_paint,
    log_cube_stack_transition_frame,
)

CubeCloseButtonDisplayMode = ReorderableCloseButtonDisplayMode


class CubeItem(ReorderableTabItemBase):
    """Render cube-stack items with stack-specific dimensions and borders."""

    aliasEditRequested = Signal(object)
    aliasEditingFinished = Signal(str)
    duplicateRequested = Signal(object)
    bypassToggleRequested = Signal(object)

    tab_font_size = 14
    fixed_width = CUBE_ITEM_EXPANDED_WIDTH
    fixed_height = CUBE_ITEM_HEIGHT
    selected_fill_radius = 4.0
    selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(None)
    size_hint_width = 180
    selected_bottom_border_mode = "cube"

    def _postInit(self) -> None:
        """Refresh selected fill so cube cards stay aligned with workspace chrome."""

        super()._postInit()
        self._secondary_text = ""
        self._compact = False
        self._compact_progress = 0.0
        self._compact_transition_active = False
        self._issue_severity: CubeCardIssueSeverity | None = None
        self._bypassed = False
        self._alias_editing_route_key: str | None = None
        self.alias_editor = CubeAliasEditor(self)
        self.alias_editor.accepted.connect(self._commitAliasRename)
        self.alias_editor.cancelled.connect(self._cancelAliasRename)
        self.alias_editor.editingFinished.connect(self._finishAliasEditing)
        self.rename_editor.hide()
        self.rename_editor.setEnabled(False)
        self.closeButton.setFixedSize(
            CUBE_ITEM_CLOSE_BUTTON_SIZE,
            CUBE_ITEM_CLOSE_BUTTON_SIZE,
        )
        self.closeButton.setIconSize(QSize(10, 10))
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    def setSecondaryText(self, text: str) -> None:
        """Set the cube metadata row and refresh the item."""

        if text == self._secondary_text:
            return
        self._secondary_text = text
        self.update()

    def secondaryText(self) -> str:
        """Return the cube metadata row."""

        return self._secondary_text

    def setIssueSeverity(self, severity: CubeCardIssueSeverity | str | None) -> None:
        """Set presentation-local issue severity for this cube item."""

        normalized = _normalize_cube_card_issue_severity(severity)
        if normalized is self._issue_severity:
            return
        self._issue_severity = normalized
        self.update()

    def issueSeverity(self) -> CubeCardIssueSeverity | None:
        """Return the current issue severity for this cube item."""

        return self._issue_severity

    def setBypassed(self, bypassed: bool) -> None:
        """Set cube-level bypass presentation state."""

        if bypassed == self._bypassed:
            return
        self._bypassed = bypassed
        self.update()

    def isBypassed(self) -> bool:
        """Return whether this cube item is visually bypassed."""

        return self._bypassed

    def setCompact(self, compact: bool) -> None:
        """Toggle icon-only cube item presentation."""

        target_progress = 1.0 if compact else 0.0
        if compact == self._compact and self._compact_progress == target_progress:
            return
        self._compact = compact
        self._compact_transition_active = False
        self.setFixedWidth(
            CUBE_ITEM_COMPACT_WIDTH if compact else CUBE_ITEM_EXPANDED_WIDTH
        )
        self.setCompactProgress(target_progress)
        self._cancelAliasEditing()
        self._sync_close_button_visibility()
        self.update()

    def isCompact(self) -> bool:
        """Return whether this cube item is in icon-only mode."""

        return self._compact

    def beginCompactTransition(self, target_compact: bool) -> None:
        """Prepare the cube item for animated compact-state rendering."""

        _ = target_compact
        self._compact_transition_active = True
        self._cancelAliasEditing()
        self._sync_close_button_visibility()

    def finishCompactTransition(self, compact: bool) -> None:
        """Commit the cube item to one final compact-state presentation."""

        self._compact_transition_active = False
        self.setCompact(compact)

    def compact_progress(self) -> float:
        """Return the current rendered compactness, where 1 is icon-only."""

        return self._compact_progress

    def setCompactProgress(self, progress: float) -> None:
        """Set rendered compactness for width-sensitive text opacity."""

        clamped = max(0.0, min(1.0, float(progress)))
        if clamped == self._compact_progress:
            return
        if 0.0 < clamped < 1.0 and abs(clamped - self._compact_progress) < 0.0001:
            return
        self._compact_progress = clamped
        self._cancelAliasEditing()
        self._sync_close_button_visibility()
        self._sync_alias_editor_geometry()
        self.update()

    @staticmethod
    def _text_opacity(compact_progress: float) -> float:
        """Return text opacity for one compactness progress value."""

        return CubeCardVisual.text_opacity(compact_progress)

    @staticmethod
    def _icon_x() -> int:
        """Return the stable cube icon X used by every compactness state."""

        return CubeCardVisual.icon_x()

    def setSelected(self, isSelected: bool) -> None:
        """Set selected state while keeping compact mode icon-only."""

        super().setSelected(isSelected)
        self._sync_close_button_visibility()

    def setCloseButtonDisplayMode(
        self, mode: ReorderableCloseButtonDisplayMode
    ) -> None:
        """Apply close-button mode without showing it in compact mode."""

        super().setCloseButtonDisplayMode(mode)
        self._sync_close_button_visibility()

    def enterEvent(self, event: object) -> None:
        """Keep compact cube items icon-only on hover."""

        super().enterEvent(event)
        self._sync_close_button_visibility()

    def leaveEvent(self, event: object) -> None:
        """Keep compact cube items icon-only after hover state changes."""

        super().leaveEvent(event)
        self._sync_close_button_visibility()

    def _sync_close_button_visibility(self) -> None:
        """Derive remove-button availability from rendered compactness."""

        if self._isAliasEditing() or getattr(self, "_compact_progress", 0.0) > 0.0:
            self.closeButton.hide()
            self.closeButton.setEnabled(False)
            return

        self.closeButton.setEnabled(True)
        if self.closeButtonDisplayMode == ReorderableCloseButtonDisplayMode.NEVER:
            self.closeButton.hide()
        elif self.closeButtonDisplayMode == ReorderableCloseButtonDisplayMode.ALWAYS:
            self.closeButton.show()
        else:
            self.closeButton.setVisible(self.isHover or self.isSelected)

    def _showContextMenu(self, global_pos: QPoint) -> None:
        """Show cube actions, including removal when the X is hidden."""

        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "cube_stack.rename",
                        "Rename",
                        callback=self._request_alias_editing,
                        icon=FluentIcon.EDIT,
                    ),
                    MenuItem(
                        "cube_stack.duplicate",
                        "Duplicate",
                        callback=self._request_duplication,
                        icon=FluentIcon.COPY,
                    ),
                    MenuItem(
                        "cube_stack.bypass",
                        "Remove bypass" if self._bypassed else "Bypass",
                        callback=self._request_bypass_toggle,
                        icon=FluentIcon.PAUSE,
                    ),
                    MenuItem(
                        "cube_stack.remove",
                        "Remove",
                        callback=self._request_removal,
                        icon=FluentIcon.DELETE,
                    ),
                )
            )
        )
        menu.exec(global_pos, aniType=MenuAnimationType.DROP_DOWN)

    def _request_alias_editing(self) -> None:
        """Request coordinated alias editing for this cube item."""

        self.aliasEditRequested.emit(self)

    def _request_bypass_toggle(self) -> None:
        """Request cube-level bypass toggling for this cube item."""

        self.bypassToggleRequested.emit(self)

    def _request_duplication(self) -> None:
        """Request duplication for this cube item."""

        self.duplicateRequested.emit(self)

    def _startRename(self) -> None:
        """Enter inline rename or request coordinated editing when compact."""

        if self.begin_alias_editing():
            return
        self._request_alias_editing()

    def begin_alias_editing(self) -> bool:
        """Begin inline rename only while the cube item has expanded text space."""

        if (
            self._compact
            or self._compact_transition_active
            or self._compact_progress > 0.0
        ):
            return False
        self.alias_editor.setPrimaryFont(self.font())
        color = (
            self.textColor
            if self.textColor is not None
            else (
                QColor(Qt.GlobalColor.white)
                if isDarkTheme()
                else QColor(Qt.GlobalColor.black)
            )
        )
        self.alias_editor.setTextColor(color)
        self._alias_editing_route_key = self.routeKey() or ""
        self.alias_editor.begin(self.text())
        self._sync_close_button_visibility()
        self._sync_alias_editor_geometry()
        self.update()
        return True

    def _commitAliasRename(self, new_name: str) -> None:
        """Forward committed cube alias text through the existing rename signal."""

        if new_name and new_name != self.text():
            self.renamed.emit(self, new_name)

    def _cancelAliasRename(self) -> None:
        """Refresh cube item state after alias editing is cancelled."""

        self._finishAliasEditing()

    def _finishAliasEditing(self) -> None:
        """Restore cube controls after alias editing finishes."""

        route_key = self._alias_editing_route_key
        self._alias_editing_route_key = None
        self._sync_close_button_visibility()
        self.update()
        if route_key is not None:
            self.aliasEditingFinished.emit(route_key)

    def _cancelAliasEditing(self) -> None:
        """Cancel active cube alias editing when layout mode changes."""

        alias_editor = getattr(self, "alias_editor", None)
        self.rename_editor.setVisible(False)
        if alias_editor is not None and alias_editor.isEditing():
            alias_editor.cancel()

    def _isAliasEditing(self) -> bool:
        """Return whether the cube alias editor is currently visible."""

        alias_editor = getattr(self, "alias_editor", None)
        return bool(alias_editor is not None and alias_editor.isEditing())

    def _sync_alias_editor_geometry(self) -> None:
        """Place the alias editor over the primary cube text row."""

        alias_editor = getattr(self, "alias_editor", None)
        if alias_editor is None:
            return
        primary_rect, _secondary_rect = CubeCardVisual.text_row_rects(self._textRect())
        alias_editor.setGeometry(primary_rect.toAlignedRect())

    def resizeEvent(self, event: object) -> None:
        """Keep the close button centered in the cube text reserve."""

        super().resizeEvent(event)
        self._position_close_button()
        self._sync_alias_editor_geometry()

    def _position_close_button(self) -> None:
        """Position the close button in the expanded card action reserve."""

        self.closeButton.move(
            self._close_button_x(self.width(), self.closeButton.width()),
            int(self.height() / 2 - self.closeButton.height() / 2),
        )

    @staticmethod
    def _close_button_x(item_width: int, button_width: int) -> int:
        """Return close-button X centered between text cutoff and card edge."""

        return CubeCardVisual.close_button_x(item_width, button_width)

    def _apply_theme_styles(self) -> None:
        """Reapply selected fill after theme changes."""

        self.selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.update()

    def _textRect(self) -> QRectF:
        """Return drawing region for expanded cube text and rename editor."""

        return self._textRectForWidth(self.width(), self._compact_progress)

    def _textRectForWidth(self, item_width: int, compact_progress: float) -> QRectF:
        """Return text bounds for a rendered width and compactness progress."""

        return CubeCardVisual.text_rect_for_width(
            item_width,
            self.height(),
            has_icon=CubeCardVisual.has_icon(self.icon()),
            close_visible=self.closeButton.isVisible(),
            compact_progress=compact_progress,
        )

    def paintEvent(self, event: object) -> None:
        """Paint cube item with the shared cube-card visual."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        CubeCardVisual.draw(
            painter,
            rect=self.rect(),
            font=self.font(),
            state=self._visual_state(),
            icon_paint_callback=lambda icon_x, icon_y, icon_size: (
                log_cube_item_icon_paint(
                    item=self,
                    icon_x=icon_x,
                    icon_y=icon_y,
                    icon_size=icon_size,
                )
            ),
        )

    def _visual_state(self) -> CubeCardVisualState:
        """Return the shared visual state for this live stack item."""

        return CubeCardVisualState(
            primary_text=self.text(),
            secondary_text=self._secondary_text,
            icon=self._icon,
            selected=self.isSelected,
            hovered=self.isHover,
            pressed=self.isPressed,
            enabled=self.isEnabled(),
            close_visible=self.closeButton.isVisible(),
            compact_progress=self._compact_progress,
            text_color=self.textColor,
            selected_fill_color=self.selected_fill_color,
            inactive_text_alpha=self.inactive_text_alpha,
            selected_font_weight=self.selected_font_weight,
            editing_primary_text=self._isAliasEditing(),
            issue_severity=self._issue_severity,
            bypassed=self._bypassed,
        )

    @staticmethod
    def _text_row_rects(rect: QRectF) -> tuple[QRectF, QRectF]:
        """Return text rows centered vertically within the cube tab."""

        return CubeCardVisual.text_row_rects(rect)

    compactProgress = Property(float, compact_progress, setCompactProgress)


class CubeStackIndicatorOverlay(QWidget):
    """Paint the selected-cube indicator above cube item widgets."""

    def __init__(self, stack: CubeStack) -> None:
        """Create a transparent overlay tied to one cube stack viewport."""

        super().__init__(stack.view)
        self._stack = stack
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    def sync(self) -> None:
        """Match viewport geometry and z-order before repainting."""

        current_item = self._stack.currentTab()
        self.setGeometry(self._stack.view.rect())
        self.raise_()
        self.setVisible(current_item is not None and current_item.isVisible())
        self.update()

    def paintEvent(self, event: object) -> None:
        """Draw the active selection indicator in viewport coordinates."""

        _ = event
        item = self._stack.currentTab()
        if item is None or not item.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        indicator_x = item.x() + 1
        painter.drawRoundedRect(
            indicator_x,
            self._stack._getIndicatorY(),
            3,
            16,
            1.5,
            1.5,
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
    aliasEditingFinished = Signal(str)
    cubeMoved = Signal(int, int)
    cubeMoveFinished = Signal()
    tabMouseReleased = Signal(int)
    cubeStackWheelRerouteRequested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create vertical cube stack view."""
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self._initCommonState()
        self._compact = False
        self._compact_transition_active = False
        self._indicatorY = 0
        self._indicator_realign_pending = False

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
        self.setStyleSheet("background-color: transparent; border: none;")
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setStyleSheet("background-color: transparent; border: none;")
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.setStyleSheet("background-color: transparent; border: none;")
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
        self._set_add_placeholder_compact(False)
        self._sync_indicator_overlay()

    def _createTabItem(
        self,
        text: str,
        icon: FluentIconBase | str | None = None,
    ) -> ReorderableTabItemBase:
        """Create cube-stack item."""
        item = CubeItem(text, self.view, icon)
        item.setCompact(self._compact)
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
        self._apply_item_compact_state(item)
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
        item.setToolTip(tooltip_text)
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

    def setCompact(self, compact: bool) -> None:
        """Toggle icons-only stack presentation."""

        if compact == self._compact and not self._compact_transition_active:
            return
        self.finishCompactTransition(compact)

    def isCompact(self) -> bool:
        """Return whether the stack is in icons-only mode."""

        return self._compact

    def beginCompactTransition(self, target_compact: bool) -> None:
        """Prepare stack items for an animated compact-mode transition."""

        self._compact_transition_active = True
        for item in self.items:
            if isinstance(item, CubeItem):
                item.beginCompactTransition(target_compact)

    def applyCompactTransition(
        self,
        *,
        stack_width: int,
        item_width: int,
        compact_progress: float,
    ) -> None:
        """Apply one frame of compact-mode transition geometry."""

        log_cube_stack_transition_frame(
            stack=self,
            stack_width=stack_width,
            item_width=item_width,
            compact_progress=compact_progress,
        )
        self.setFixedWidth(stack_width)
        for item in self.items:
            item.setFixedWidth(item_width)
            if isinstance(item, CubeItem):
                item.setCompactProgress(compact_progress)
        self.addPlaceholder.setCompactProgress(compact_progress)
        self._sync_indicator_overlay()

    def finishCompactTransition(self, target_compact: bool) -> None:
        """Commit final compact-mode state after immediate or animated changes."""

        self._compact_transition_active = False
        self._compact = target_compact
        self.setFixedWidth(
            CUBE_STACK_COMPACT_WIDTH if target_compact else CUBE_STACK_EXPANDED_WIDTH
        )
        self._set_add_placeholder_compact(target_compact)
        for item in self.items:
            self._apply_item_compact_state(item)
        self._schedule_indicator_realign()

    def _set_add_placeholder_compact(self, compact: bool) -> None:
        """Apply current stack compact mode to the add placeholder card."""

        self.addPlaceholder.setCompact(compact)

    def _apply_item_compact_state(self, item: ReorderableTabItemBase) -> None:
        """Apply current stack presentation mode to one tab item."""

        width = CUBE_ITEM_COMPACT_WIDTH if self._compact else CUBE_ITEM_EXPANDED_WIDTH
        if isinstance(item, CubeItem):
            item.finishCompactTransition(self._compact)
            item.setFixedWidth(width)
            return
        item.setFixedWidth(width)

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
        QTimer.singleShot(0, self._complete_indicator_realign)

    def _complete_indicator_realign(self) -> None:
        """Complete a pending indicator realignment after layout activation."""

        self._indicator_realign_pending = False
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
    "CubeStackIndicatorOverlay",
    "CubeItem",
    "CubeStack",
]


def _normalize_cube_card_issue_severity(
    severity: CubeCardIssueSeverity | str | None,
) -> CubeCardIssueSeverity | None:
    """Return a cube-card issue severity from supported caller values."""

    if isinstance(severity, CubeCardIssueSeverity):
        return severity
    if severity == CubeCardIssueSeverity.ERROR.value:
        return CubeCardIssueSeverity.ERROR
    return None
