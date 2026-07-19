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

"""Render grouped managed-text asset list rows independently from modal flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QSizePolicy,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    ListItemDelegate,
    isDarkTheme,
)

from substitute.application.managed_text_assets import ManagedTextAsset

HEADER_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
ASSET_ID_ROLE = Qt.ItemDataRole.UserRole + 2
STRIPE_ROLE = Qt.ItemDataRole.UserRole + 3


@dataclass(frozen=True, slots=True)
class AssetEntry:
    """Track the list item and rendered row for one asset."""

    asset: ManagedTextAsset
    item: QListWidgetItem
    row: "AssetRow"


class AssetRow(QWidget):
    """Render one selectable managed-text asset row."""

    selected = Signal(str)

    def __init__(
        self,
        asset: ManagedTextAsset,
        *,
        parent: QWidget | None = None,
    ) -> None:
        """Create a dense label and subtitle row."""

        super().__init__(parent)
        self._asset = asset
        self._full_label = asset.label
        self._full_subtitle = asset.subtitle
        self.setMinimumHeight(56)
        self.setToolTip(asset.subtitle)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        text_container = QWidget(self)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        self._label = QLabel(asset.label, text_container)
        self._label.setMinimumWidth(0)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._label.setStyleSheet("font-weight: 600; margin: 0; padding: 0;")
        text_layout.addWidget(self._label)
        self._subtitle = CaptionLabel(asset.subtitle, text_container)
        self._subtitle.setMinimumWidth(0)
        self._subtitle.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._subtitle.setStyleSheet(
            f"QLabel{{color:{muted_text_color().name()}; margin: -2px 0 0 0;}}"
        )
        text_layout.addWidget(self._subtitle)
        layout.addWidget(text_container, 1)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        """Refresh elided text after row width changes."""

        super().resizeEvent(event)  # type: ignore[arg-type]
        self._apply_elision()

    def showEvent(self, event: object) -> None:  # noqa: N802
        """Refresh elided text when Qt has real row geometry."""

        super().showEvent(event)  # type: ignore[arg-type]
        self._apply_elision()

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        """Select this asset when the row body is clicked."""

        button = getattr(event, "button", None)
        if callable(button) and button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._asset.id)
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def _apply_elision(self) -> None:
        """Elide long labels and subtitles to keep rows stable."""

        width = max(0, self.width() - 20)
        self._label.setText(
            QFontMetrics(self._label.font()).elidedText(
                self._full_label, Qt.TextElideMode.ElideRight, width
            )
        )
        self._subtitle.setText(
            QFontMetrics(self._subtitle.font()).elidedText(
                self._full_subtitle, Qt.TextElideMode.ElideRight, width
            )
        )


class AssetListItemDelegate(ListItemDelegate):  # type: ignore[misc]
    """Paint list section headers and selectable asset rows."""

    def paint(self, painter: Any, option: Any, index: Any) -> None:
        """Paint grouped headers and subtle row interaction state."""

        if index.data(HEADER_KIND_ROLE) == "header":
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(option.palette.brush(QPalette.ColorRole.Base))
            painter.drawRect(option.rect)
            painter.restore()
            return
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        patched_option = cast(Any, QStyleOptionViewItem(option))
        patched_option.rect.adjust(0, self.margin, 0, -self.margin)
        stripe_index = index.data(STRIPE_ROLE)
        is_hover = self.hoverRow == index.row()
        is_pressed = self.pressedRow == index.row()
        is_selected = index.row() in self.selectedRows
        is_alternate = isinstance(stripe_index, int) and stripe_index % 2 == 0
        grayscale = 255 if isDarkTheme() else 0
        alpha = 0
        if is_selected:
            alpha = 25 if is_hover else 17
            if is_pressed:
                alpha = 15 if isDarkTheme() else 9
        elif is_pressed:
            alpha = 9 if isDarkTheme() else 6
        elif is_hover:
            alpha = 12
        elif is_alternate:
            alpha = 5
        painter.setBrush(QColor(grayscale, grayscale, grayscale, alpha))
        self._drawBackground(painter, patched_option, index)
        if (
            is_selected
            and index.column() == 0
            and self.parent().horizontalScrollBar().value() == 0
        ):
            self._drawIndicator(painter, patched_option, index)
        painter.restore()
        QStyledItemDelegate.paint(self, painter, patched_option, index)


def group_assets(
    assets: tuple[ManagedTextAsset, ...],
) -> tuple[tuple[str, tuple[ManagedTextAsset, ...]], ...]:
    """Group assets in first-seen group order."""

    groups: dict[str, list[ManagedTextAsset]] = {}
    for asset in assets:
        groups.setdefault(asset.group, []).append(asset)
    return tuple((group, tuple(items)) for group, items in groups.items())


def muted_text_color() -> QColor:
    """Return theme-aware secondary text color."""

    return QColor(180, 180, 180) if isDarkTheme() else QColor(96, 96, 96)


__all__ = [
    "ASSET_ID_ROLE",
    "AssetEntry",
    "AssetListItemDelegate",
    "AssetRow",
    "group_assets",
    "HEADER_KIND_ROLE",
    "muted_text_color",
    "STRIPE_ROLE",
]
