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

"""Render one interactive cube card within a cube stack."""
# mypy: disable-error-code=attr-defined

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text


from PySide6.QtCore import Property, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
)
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIcon,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
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
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_BUTTON_SIZE,
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableCloseButtonDisplayMode,
    ReorderableTabItemBase,
)
from substitute.presentation.workflows.cube_stack_geometry_trace import (
    log_cube_item_icon_paint,
)

CubeCloseButtonDisplayMode = ReorderableCloseButtonDisplayMode


class CubeItem(ReorderableTabItemBase):
    """Render cube-stack items with stack-specific dimensions and borders."""

    aliasEditRequested = Signal(object)
    aliasEditingFinished = Signal(str)
    duplicateRequested = Signal(object)
    bypassToggleRequested = Signal(object)
    outputPersistenceToggleRequested = Signal(object)

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
        self._output_persistence_enabled = True
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

    def setOutputPersistenceEnabled(self, enabled: bool) -> None:
        """Set whether the workflow cube instance saves generated outputs."""

        self._output_persistence_enabled = enabled

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
                        "cube_stack.output_persistence",
                        (
                            app_text("Don't save outputs")
                            if self._output_persistence_enabled
                            else app_text("Save outputs")
                        ),
                        callback=self._request_output_persistence_toggle,
                        icon=FluentIcon.SAVE,
                    ),
                    MenuItem(
                        "cube_stack.rename",
                        app_text("Rename"),
                        callback=self._request_alias_editing,
                        icon=FluentIcon.EDIT,
                    ),
                    MenuItem(
                        "cube_stack.duplicate",
                        app_text("Duplicate"),
                        callback=self._request_duplication,
                        icon=FluentIcon.COPY,
                    ),
                    MenuItem(
                        "cube_stack.bypass",
                        (
                            app_text("Remove bypass")
                            if self._bypassed
                            else app_text("Bypass")
                        ),
                        callback=self._request_bypass_toggle,
                        icon=FluentIcon.PAUSE,
                    ),
                    MenuItem(
                        "cube_stack.remove",
                        app_text("Remove"),
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

    def _request_output_persistence_toggle(self) -> None:
        """Request workflow-local output persistence toggling."""

        self.outputPersistenceToggleRequested.emit(self)

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


def _normalize_cube_card_issue_severity(
    severity: CubeCardIssueSeverity | str | None,
) -> CubeCardIssueSeverity | None:
    """Return a cube-card issue severity from supported caller values."""

    if isinstance(severity, CubeCardIssueSeverity):
        return severity
    if severity == CubeCardIssueSeverity.ERROR.value:
        return CubeCardIssueSeverity.ERROR
    return None


__all__ = ["CubeItem"]
