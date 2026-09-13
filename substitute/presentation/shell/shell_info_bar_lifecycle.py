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

"""Release Fluent notification bars before application-owned Qt services."""

from __future__ import annotations

from weakref import ReferenceType, ref

from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]
from shiboken6 import isValid


class ShellInfoBarLifecycle:
    """Close every Fluent notification owned by one shell while Qt is intact."""

    def __init__(self, shell: QWidget) -> None:
        """Observe the shell weakly so cleanup cannot retain a replaced window."""

        self._shell_ref: ReferenceType[QWidget] = ref(shell)

    def shutdown(self) -> None:
        """Synchronously detach all live bars from QFluent's global manager."""

        shell = self._shell_ref()
        if shell is None or not isValid(shell):
            return
        for bar in tuple(shell.findChildren(InfoBar)):
            if isValid(bar):
                bar.close()


__all__ = ["ShellInfoBarLifecycle"]
