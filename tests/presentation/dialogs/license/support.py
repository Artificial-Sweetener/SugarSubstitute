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

"""Own license dialog fixtures with exact native lifetimes."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from substitute.presentation.dialogs.license_dialog import LicenseDialog
from tests.support.qt.lifecycle import destroy_qt_object


class LicenseDialogOwner:
    """Own license dialogs and their modal parent surfaces per test."""

    def __init__(self) -> None:
        """Initialize empty dialog and parent ownership."""

        self._dialogs: list[LicenseDialog] = []
        self._parents: list[QWidget] = []

    def build(self, *, parent_size: QSize, license_html: str) -> LicenseDialog:
        """Build and retain one dialog with an independently owned parent."""

        parent = QWidget()
        parent.resize(parent_size)
        dialog = LicenseDialog(license_html=license_html, parent=parent)
        self._parents.append(parent)
        self._dialogs.append(dialog)
        return dialog

    def destroy_all(self) -> None:
        """Destroy modal surfaces before their parent windows."""

        for dialog in reversed(self._dialogs):
            destroy_qt_object(dialog)
        self._dialogs.clear()
        for parent in reversed(self._parents):
            destroy_qt_object(parent)
        self._parents.clear()


__all__ = ["LicenseDialogOwner"]
