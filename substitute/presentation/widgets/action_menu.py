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

"""Render action-local check indicators within QFluent menu chrome."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QIcon, QPainter
from PySide6.QtWidgets import (
    QListWidgetItem,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOption,
    QStyleOptionViewItem,
    QWidget,
)
from qfluentwidgets import FluentIcon  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    MenuAnimationType,
    RoundMenu,
    ShortcutMenuItemDelegate,
)


class ActionMenu(RoundMenu):  # type: ignore[misc]
    """Keep indicator layout local to checkable actions, including mixed menus."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        """Use Qt row layout with Fluent checkmarks and normal menu padding."""

        super().__init__(title, parent)
        indicator_style = _MenuIndicatorStyle(QStyleFactory.create("fusion"))
        indicator_style.setParent(self.view)
        self.view.setStyle(indicator_style)
        self.view.setItemDelegate(ActionMenuItemDelegate(self.view))
        self.view.ensurePolished()

    def exec(
        self,
        pos: object,
        ani: bool = True,
        aniType: MenuAnimationType = MenuAnimationType.DROP_DOWN,
    ) -> object:
        """Keep QFluent's popup API visible across PySide's native QMenu binding."""

        return super().exec(pos, ani, aniType)

    def _adjustItemText(self, item: QListWidgetItem, action: QAction) -> int:  # noqa: N802
        """Include the row's check slot when QFluent calculates its width."""

        width = int(super()._adjustItemText(item, action))
        if action.isCheckable():
            style = self.view.style()
            width += style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
            width += style.pixelMetric(QStyle.PixelMetric.PM_CheckBoxLabelSpacing)
            item.setSizeHint(QSize(width, self.itemHeight))
        return width


class ActionMenuItemDelegate(ShortcutMenuItemDelegate):  # type: ignore[misc]
    """Derive row check geometry from QAction rather than list-wide styling."""

    def initStyleOption(  # noqa: N802
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Reserve a native check slot only when this action is checkable."""

        super().initStyleOption(option, index)
        action = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(action, QAction) or not action.isCheckable():
            return
        option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        option.checkState = (
            Qt.CheckState.Checked if action.isChecked() else Qt.CheckState.Unchecked
        )
        if action.icon().isNull():
            # QFluent supplies blank peer-icon slots; the check is this row's icon.
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
            option.icon = QIcon()
            option.text = action.text()


class _MenuIndicatorStyle(QProxyStyle):
    """Paint Fluent ticks in Qt's per-row check-indicator rectangle."""

    def drawPrimitive(  # noqa: N802
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        """Preserve normal item painting and replace only the check glyph."""

        if element != QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck:
            super().drawPrimitive(element, option, painter, widget)
            return
        if not option.state & QStyle.StateFlag.State_On:
            return
        painter.save()
        if not option.state & QStyle.StateFlag.State_Enabled:
            painter.setOpacity(0.4)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        FluentIcon.ACCEPT.render(painter, QRectF(option.rect))
        painter.restore()


__all__ = ["ActionMenu", "ActionMenuItemDelegate"]
