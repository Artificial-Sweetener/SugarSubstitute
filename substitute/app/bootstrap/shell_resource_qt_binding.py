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

"""Bind shell resources to the safe portion of the Qt application lifetime."""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)


class ShellResourceQtBinding(QObject):
    """Release one shell before application-global Qt objects are destroyed."""

    def __init__(
        self,
        *,
        application: QApplication,
        shell: QWidget,
        lifecycle: ShellResourceLifecycle,
    ) -> None:
        """Connect application exit and shell replacement to one idempotent owner."""

        super().__init__(shell)
        self._lifecycle = lifecycle
        application.aboutToQuit.connect(self._handle_application_quit)
        shell.destroyed.connect(self._handle_shell_destroyed)

    @Slot()
    def _handle_application_quit(self) -> None:
        """Release resources while application-global Qt services remain alive."""

        self._lifecycle.shutdown()

    @Slot(QObject)
    def _handle_shell_destroyed(self, _shell: QObject | None = None) -> None:
        """Release resources when a shell is replaced without application exit."""

        self._lifecycle.shutdown()


def bind_shell_resource_lifecycle(
    *,
    application: QApplication,
    shell: QWidget,
    lifecycle: ShellResourceLifecycle,
) -> ShellResourceQtBinding:
    """Bind shell cleanup to application exit and shell replacement."""

    return ShellResourceQtBinding(
        application=application,
        shell=shell,
        lifecycle=lifecycle,
    )


__all__ = ["ShellResourceQtBinding", "bind_shell_resource_lifecycle"]
