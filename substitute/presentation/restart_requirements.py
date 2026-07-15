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

"""Bridge process-local restart requirements into shell widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtWidgets import QDialog, QWidget

from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.presentation.dialogs.restart_required_dialog import (
    RestartRequiredDialog,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.restart_requirements")


class RestartDialogProtocol(Protocol):
    """Describe the dialog behavior consumed by the restart UI controller."""

    def exec(self) -> int:
        """Execute the modal dialog and return a Qt dialog code."""


class PendingRestartButtonProtocol(Protocol):
    """Describe the button behavior needed by restart requirement UI."""

    activated: Any

    def set_count(self, count: int) -> None:
        """Set the pending restart badge count."""

    def set_collapsed(self, collapsed: bool, *, animated: bool = True) -> None:
        """Show or hide the pending restart indicator."""


RestartDialogFactory = Callable[
    [RestartRequirementSnapshot, QWidget | None],
    RestartDialogProtocol,
]


class RestartRequirementUiController:
    """Synchronize restart requirement snapshots with shell UI and restart actions."""

    def __init__(
        self,
        *,
        service: RestartRequirementService,
        button: PendingRestartButtonProtocol,
        restart_full_app: Callable[[], None],
        restart_window: Callable[[], None],
        parent: QWidget | None,
        dialog_factory: RestartDialogFactory | None = None,
    ) -> None:
        """Create the controller and bind initial snapshot state."""

        self._service = service
        self._button = button
        self._restart_full_app = restart_full_app
        self._restart_window = restart_window
        self._parent = parent
        self._dialog_factory = dialog_factory or _create_restart_dialog
        self._latest_snapshot = service.snapshot()
        self._button.activated.connect(self.show_restart_required_dialog)
        self._service.add_observer(self.set_snapshot)
        self.set_snapshot(self._latest_snapshot)

    def dispose(self) -> None:
        """Disconnect this controller from the shared restart service."""

        self._service.remove_observer(self.set_snapshot)
        try:
            self._button.activated.disconnect(self.show_restart_required_dialog)
        except (RuntimeError, TypeError):
            return

    def set_snapshot(self, snapshot: RestartRequirementSnapshot) -> None:
        """Apply one restart requirement snapshot to the titlebar button."""

        self._latest_snapshot = snapshot
        self._button.set_count(snapshot.count)
        self._button.set_collapsed(snapshot.count == 0)

    def show_restart_required_dialog(self) -> None:
        """Open the shared restart dialog when pending items exist."""

        snapshot = self._latest_snapshot
        if snapshot.count == 0:
            return
        dialog = self._dialog_factory(snapshot, self._parent)
        if dialog.exec() == int(QDialog.DialogCode.Accepted):
            self._handle_restart_now(snapshot.required_scope)

    def show_if_pending(self) -> None:
        """Open the dialog only when at least one pending restart item exists."""

        if self._latest_snapshot.count > 0:
            self.show_restart_required_dialog()

    def _handle_restart_now(self, scope: RestartScope) -> None:
        """Dispatch the most expensive required restart through existing callbacks."""

        if scope is RestartScope.FULL_APP:
            log_info(_LOGGER, "Full app restart requested from restart cart")
            self._restart_full_app()
            return
        if scope is RestartScope.WINDOW:
            log_info(_LOGGER, "GUI restart requested from restart cart")
            self._restart_window()


def _create_restart_dialog(
    snapshot: RestartRequirementSnapshot,
    parent: QWidget | None,
) -> RestartDialogProtocol:
    """Create the default restart-required dialog."""

    return RestartRequiredDialog(snapshot=snapshot, parent=parent)


__all__ = [
    "RestartDialogFactory",
    "RestartDialogProtocol",
    "RestartRequirementUiController",
]
