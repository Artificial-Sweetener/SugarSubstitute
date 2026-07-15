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

"""Render the Comfy environment package inventory browser."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
    QTableWidgetItem,
    QWidget,
)
from qfluentwidgets import TableWidget  # type: ignore[import-untyped]

from substitute.application.comfy_environment import ComfyEnvironmentPackage

_PACKAGE_ITEM_ID_ROLE = Qt.ItemDataRole.UserRole
_PACKAGE_NAME_COLUMN = 0
_VERSION_COLUMN = 1
_CLAIMANT_COUNT_COLUMN = 2


class PackageInventoryList(TableWidget):  # type: ignore[misc]
    """Display selectable packages in a dense, zebra-striped table."""

    package_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty package inventory table."""

        super().__init__(parent)
        self.setObjectName("comfyEnvironmentPackageList")
        self.setColumnCount(3)
        self.setMinimumHeight(120)
        self.setMinimumWidth(380)
        self.setMaximumWidth(440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(54)
        header.setSectionResizeMode(
            _PACKAGE_NAME_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(_VERSION_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(
            _CLAIMANT_COUNT_COLUMN, QHeaderView.ResizeMode.Fixed
        )
        header.setSectionsClickable(False)
        header.setSortIndicatorShown(False)
        self.setColumnWidth(_VERSION_COLUMN, 74)
        self.setColumnWidth(_CLAIMANT_COUNT_COLUMN, 88)
        self.setHorizontalHeaderLabels(("Package", "Version", "Required by"))
        self._render_signature: tuple[tuple[str, str, str, str], ...] = ()
        self._render_generation = 0
        self.itemSelectionChanged.connect(self._emit_selected_package)

    def render_packages(self, packages: tuple[ComfyEnvironmentPackage, ...]) -> None:
        """Render packages in their already-filtered display order."""

        signature = _package_render_signature(packages)
        if signature == self._render_signature:
            return
        self._render_signature = signature
        self._render_generation += 1
        self.blockSignals(True)
        self.setRowCount(0)
        for package in packages:
            row = self.rowCount()
            self.insertRow(row)
            item_id = package_item_id(package)
            self._set_item(row, _PACKAGE_NAME_COLUMN, package.name, item_id)
            self._set_item(row, _VERSION_COLUMN, package.version, item_id)
            self._set_item(
                row,
                _CLAIMANT_COUNT_COLUMN,
                str(claimant_count(package)),
                item_id,
            )
        self.blockSignals(False)

    def render_generation(self) -> int:
        """Return the number of table row rebuilds performed by this widget."""

        return self._render_generation

    def select_item(self, item_id: str) -> bool:
        """Select one package item by stable inventory item id."""

        for row in range(self.rowCount()):
            item = self.item(row, _PACKAGE_NAME_COLUMN)
            if item is not None and item.data(_PACKAGE_ITEM_ID_ROLE) == item_id:
                self.selectRow(row)
                return True
        return False

    def selected_item_id(self) -> str | None:
        """Return the currently selected package item id."""

        selected_items = self.selectedItems()
        if not selected_items:
            return None
        item_id = selected_items[0].data(_PACKAGE_ITEM_ID_ROLE)
        return item_id if isinstance(item_id, str) else None

    def _set_item(self, row: int, column: int, text: str, item_id: str) -> None:
        """Set one non-editable package table item."""

        item = QTableWidgetItem(text)
        item.setData(_PACKAGE_ITEM_ID_ROLE, item_id)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if column in {_VERSION_COLUMN, _CLAIMANT_COUNT_COLUMN}:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        self.setItem(row, column, item)

    def _emit_selected_package(self) -> None:
        """Emit the selected package id after table selection changes."""

        item_id = self.selected_item_id()
        if item_id is not None:
            self.package_selected.emit(item_id)


def package_item_id(package: ComfyEnvironmentPackage) -> str:
    """Return the stable rendered id for one package row."""

    return f"package:{package.normalized_name}"


def _package_render_signature(
    packages: tuple[ComfyEnvironmentPackage, ...],
) -> tuple[tuple[str, str, str, str], ...]:
    """Return the table-visible row data signature for packages."""

    return tuple(
        (
            package_item_id(package),
            package.name,
            package.version,
            str(claimant_count(package)),
        )
        for package in packages
    )


def sorted_packages(
    *,
    packages: tuple[ComfyEnvironmentPackage, ...],
    filter_text: str,
    sort_column: int,
    ascending: bool,
) -> tuple[ComfyEnvironmentPackage, ...]:
    """Return packages ordered for the package selector."""

    normalized_filter = filter_text.strip().lower()
    return tuple(
        sorted(
            matching_packages(packages, filter_text=filter_text),
            key=lambda package: _package_sort_key(
                package,
                filter_text=normalized_filter,
                sort_column=sort_column,
                ascending=ascending,
            ),
        )
    )


def matching_packages(
    packages: tuple[ComfyEnvironmentPackage, ...],
    *,
    filter_text: str,
) -> tuple[ComfyEnvironmentPackage, ...]:
    """Return packages matching one search string."""

    normalized_filter = filter_text.strip().lower()
    if not normalized_filter:
        return packages
    return tuple(
        package
        for package in packages
        if normalized_filter in package_search_text(package)
    )


def claimant_count(package: ComfyEnvironmentPackage) -> int:
    """Return the number of unique dependency claimants for one package."""

    return len(
        {
            (claimant.kind, claimant.claimant_id)
            for claimant in package.claimants
            if claimant.claimant_id
        }
    )


def package_search_text(package: ComfyEnvironmentPackage) -> str:
    """Return searchable package text."""

    claimant_text = " ".join(
        f"{claimant.display_name} {claimant.required_via or ''}"
        for claimant in package.claimants
    )
    tag_text = " ".join(
        f"{tag.display_name} {' '.join(tag.supported_actions)}"
        for tag in package.management_tags
    )
    return (
        f"{package.name} {package.version} {package.attribution} "
        f"{package.summary or ''} {package.summary_source} "
        f"{claimant_text} {tag_text}"
    ).lower()


def _package_sort_key(
    package: ComfyEnvironmentPackage,
    *,
    filter_text: str,
    sort_column: int,
    ascending: bool,
) -> tuple[int, str | int, str]:
    """Return the package selector sort key."""

    name = package.name.casefold()
    name_rank = 0 if filter_text and filter_text in name else 1
    if sort_column == _PACKAGE_NAME_COLUMN:
        sort_value: str | int = name if ascending else _reverse_sort_text(name)
    else:
        count = claimant_count(package)
        sort_value = count if ascending else -count
    return (name_rank, sort_value, name)


def _reverse_sort_text(text: str) -> str:
    """Return a string key that reverses lexicographic ordering."""

    return "".join(chr(0x10FFFF - ord(character)) for character in text)
